"""Strict discovery stays atomic across active skill policy and graph state."""

import asyncio
import json
from types import SimpleNamespace

import pytest
from langchain.agents import create_agent
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.types import Command
from pydantic import Field

from omniharness.agents.middlewares.deferred_tool_filter_middleware import DeferredToolFilterMiddleware
from omniharness.agents.middlewares.skill_tool_policy_middleware import SkillToolPolicyMiddleware
from omniharness.agents.middlewares.tool_promotion_audit_middleware import DeferredToolPromotionAuditMiddleware
from omniharness.agents.thread_state import ThreadState, merge_promoted
from omniharness.skills.tool_policy import ALWAYS_AVAILABLE_BUILTIN_TOOL_NAMES
from omniharness.tools.builtins.tool_search import DeferredToolCatalog, build_tool_search_tool


def _policy():
    return SkillToolPolicyMiddleware(slash_source_owner_token="strict-search-policy-test")


def _request(args):
    return SimpleNamespace(tool_call={"name": "tool_search", "id": "search-1", "args": args})


def _result(names, *, nested=False):
    schemas = [{"name": name, "description": f"private schema for {name}"} for name in names]
    if nested:
        schemas = [{"type": "function", "function": schema} for schema in schemas]
    return Command(
        update={
            "promoted": {"catalog_hash": "catalog-1", "names": names},
            "messages": [ToolMessage(content=json.dumps(schemas), tool_call_id="search-1", name="tool_search")],
        }
    )


@pytest.mark.parametrize(
    ("requested", "returned", "allowed"),
    [
        (["mcp_allowed", "mcp_denied"], ["mcp_allowed", "mcp_denied"], {"mcp_allowed"}),
        (["mcp_allowed", "mcp_missing"], ["mcp_allowed"], {"mcp_allowed", "mcp_missing"}),
        (["mcp_allowed", "mcp_missing"], [], {"mcp_allowed", "mcp_missing"}),
        (["MCP_allowed"], ["mcp_allowed"], {"mcp_allowed"}),
    ],
)
def test_strict_policy_rejects_entire_batch_without_schema(requested, returned, allowed):
    original = _result(returned)

    filtered = _policy()._filter_tool_search_result(_request({"names": requested}), original, allowed=allowed)

    assert isinstance(filtered, Command)
    assert filtered.update["promoted"] == {"catalog_hash": "catalog-1", "names": []}
    message = filtered.update["messages"][0]
    assert message.status == "error"
    assert message.name == "tool_search"
    assert message.tool_call_id == "search-1"
    assert "entire batch was not loaded" in message.content
    assert "Every requested name must be available and allowed by the active skill policy" in message.content
    assert "Correct the complete names list" in message.content
    assert "use query to discover exact tool names" in message.content
    assert "private schema" not in message.content
    assert "mcp_allowed" not in message.content
    assert original.update["promoted"]["names"] == returned


@pytest.mark.parametrize("args", [None, [], "names", 7])
def test_malformed_search_arguments_fail_closed_without_promotion(args):
    filtered = _policy()._filter_tool_search_result(_request(args), _result(["mcp_allowed"]), allowed={"mcp_allowed"})

    assert isinstance(filtered, ToolMessage)
    assert filtered.status == "error"
    assert filtered.content == "Error: tool_search returned a result that could not be validated against the active skill policy."


@pytest.mark.parametrize("nested", [False, True])
def test_strict_policy_normalizes_names_without_inventing_aliases(nested):
    filtered = _policy()._filter_tool_search_result(
        _request({"names": [" mcp_allowed ", "mcp_allowed", "mcp_second"]}),
        _result(["mcp_allowed", "mcp_second"], nested=nested),
        allowed={"mcp_allowed", "mcp_second"},
    )

    assert filtered.update["promoted"]["names"] == ["mcp_allowed", "mcp_second"]
    assert len(json.loads(filtered.update["messages"][0].content)) == 2


@pytest.mark.parametrize("args", [{"query": "mcp"}, {"query": "select:mcp_allowed,mcp_denied"}, {"query": "mcp", "names": None}])
def test_legacy_query_keeps_partial_policy_filtering(args):
    filtered = _policy()._filter_tool_search_result(
        _request(args),
        _result(["mcp_allowed", "mcp_denied"]),
        allowed={"mcp_allowed"},
    )

    assert filtered.update["promoted"]["names"] == ["mcp_allowed"]
    assert [schema["name"] for schema in json.loads(filtered.update["messages"][0].content)] == ["mcp_allowed"]
    assert filtered.update["messages"][0].status == "success"


def test_unrestricted_policy_leaves_strict_results_untouched():
    original = _result(["mcp_allowed", "mcp_denied"])

    assert _policy()._filter_tool_search_result(_request({"names": ["mcp_allowed", "mcp_denied"]}), original, allowed=None) is original


def test_rejected_batch_preserves_preexisting_promotion_in_reducer():
    filtered = _policy()._filter_tool_search_result(
        _request({"names": ["mcp_allowed", "mcp_denied"]}),
        _result(["mcp_allowed", "mcp_denied"]),
        allowed={"mcp_allowed"},
    )
    existing = {"catalog_hash": "catalog-1", "names": ["mcp_existing"]}

    assert merge_promoted(existing, filtered.update["promoted"]) == existing


@pytest.mark.parametrize("async_mode", [False, True], ids=["sync", "async"])
@pytest.mark.parametrize("names", [["mcp_allowed", "mcp_denied"], ["MCP_allowed"], ["mcp_allowed", "   "], ["mcp_allowed", 7], [], "mcp_allowed"])
def test_strict_policy_rejects_before_calling_tool_handler(async_mode, names):
    policy = _policy()
    policy._allowed_names_for_paths = lambda paths: {"tool_search", "mcp_allowed"}
    request = _request({"names": names})
    request.state = {"skill_context": [{"path": "/mnt/skills/public/restricted/SKILL.md"}]}
    request.runtime = SimpleNamespace(context={})
    calls = []

    def handler(_):
        calls.append("executed")
        return _result(["mcp_allowed", "mcp_denied"])

    async def async_handler(request):
        return handler(request)

    result = asyncio.run(policy.awrap_tool_call(request, async_handler)) if async_mode else policy.wrap_tool_call(request, handler)

    assert isinstance(result, ToolMessage)
    assert result.status == "error"
    assert "entire batch was not loaded" in result.content
    assert calls == []


class _ToolCallbacks(BaseCallbackHandler):
    def __init__(self):
        self.starts = []
        self.outputs = []

    def on_tool_start(self, serialized, input_str, **kwargs):
        self.starts.append(serialized["name"])

    def on_tool_end(self, output, **kwargs):
        self.outputs.append(output)


class _RecordingModel(GenericFakeChatModel):
    bound_tools: list[list[str]] = Field(default_factory=list)

    def bind_tools(self, tools, **kwargs):
        self.bound_tools.append([tool.name for tool in tools])
        return self


class _Recorder:
    def __init__(self):
        self.events = []
        self.claimed = set()

    def claim_tool_promotions(self, tool_names):
        names = sorted(set(tool_names) - self.claimed)
        self.claimed.update(names)
        return names

    def record_middleware(self, **kwargs):
        self.events.append(kwargs)


def _echo(value: str) -> str:
    """Return a test value without calling an external service."""
    return value


def _graph(args):
    tools = [StructuredTool.from_function(_echo, name=name) for name in ("mcp_allowed", "mcp_second", "mcp_denied", "mcp_existing")]
    catalog = DeferredToolCatalog(tuple(tools))
    model = _RecordingModel(
        messages=iter(
            [
                AIMessage(content="", tool_calls=[{"name": "tool_search", "args": args, "id": "search-1", "type": "tool_call"}]),
                AIMessage(content="done"),
            ]
        )
    )
    policy = _policy()
    policy._deferred_catalog = catalog
    policy._allowed_names_for_paths = lambda paths: set(ALWAYS_AVAILABLE_BUILTIN_TOOL_NAMES) | {"mcp_allowed", "mcp_second", "mcp_existing", "mcp_missing"}
    graph = create_agent(
        model=model,
        tools=[*tools, build_tool_search_tool(catalog)],
        middleware=[
            DeferredToolPromotionAuditMiddleware(catalog.names, catalog.hash),
            policy,
            DeferredToolFilterMiddleware(catalog.names, catalog.hash),
        ],
        state_schema=ThreadState,
        context_schema=dict,
    )
    recorder = _Recorder()
    initial = {
        "messages": [HumanMessage(content="Discover the requested capabilities.")],
        "skill_context": [{"name": "restricted", "path": "/mnt/skills/public/restricted/SKILL.md", "description": "", "loaded_at": 0}],
        "promoted": {"catalog_hash": catalog.hash, "names": ["mcp_existing"]},
    }
    return graph, model, recorder, initial


@pytest.mark.parametrize("async_mode", [False, True], ids=["sync", "async"])
@pytest.mark.parametrize("reason", ["denied", "missing"])
def test_graph_rejected_strict_batch_preserves_bindings_and_does_not_audit_promotions(async_mode, reason):
    args = {"names": ["mcp_allowed", "mcp_denied" if reason == "denied" else "mcp_missing"]}
    graph, model, recorder, initial = _graph(args)
    context = {"__run_journal": recorder}
    callbacks = _ToolCallbacks()
    config = {"callbacks": [callbacks]}

    result = asyncio.run(graph.ainvoke(initial, config=config, context=context)) if async_mode else graph.invoke(initial, config=config, context=context)

    assert result["promoted"] == initial["promoted"]
    messages = [message for message in result["messages"] if isinstance(message, ToolMessage)]
    assert len(messages) == 1
    assert messages[0].status == "error"
    assert "description" not in messages[0].content
    assert model.bound_tools == [["mcp_existing", "tool_search"], ["mcp_existing", "tool_search"]]
    assert recorder.events == []
    if reason == "denied":
        assert callbacks.starts == []
        assert callbacks.outputs == []
    else:
        assert callbacks.starts == ["tool_search"]
        assert len(callbacks.outputs) == 1
        assert callbacks.outputs[0].update["promoted"]["names"] == []
    assert "description" not in repr(callbacks.outputs)


@pytest.mark.parametrize("async_mode", [False, True], ids=["sync", "async"])
def test_graph_successful_strict_batch_promotes_all_and_binds_next_model_call(async_mode):
    graph, model, recorder, initial = _graph({"names": [" mcp_allowed ", "mcp_second", "mcp_allowed"]})
    context = {"__run_journal": recorder}
    callbacks = _ToolCallbacks()
    config = {"callbacks": [callbacks]}

    result = asyncio.run(graph.ainvoke(initial, config=config, context=context)) if async_mode else graph.invoke(initial, config=config, context=context)

    assert result["promoted"]["names"] == ["mcp_existing", "mcp_allowed", "mcp_second"]
    assert model.bound_tools == [["mcp_existing", "tool_search"], ["mcp_allowed", "mcp_second", "mcp_existing", "tool_search"]]
    messages = [message for message in result["messages"] if isinstance(message, ToolMessage)]
    assert messages[0].status == "success"
    assert [schema["name"] for schema in json.loads(messages[0].content)] == ["mcp_allowed", "mcp_second"]
    assert len(recorder.events) == 1
    assert recorder.events[0]["changes"]["tool_names"] == ["mcp_allowed", "mcp_second"]
    assert callbacks.starts == ["tool_search"]
    assert len(callbacks.outputs) == 1
    assert callbacks.outputs[0].update["promoted"]["names"] == ["mcp_allowed", "mcp_second"]


@pytest.mark.parametrize("async_mode", [False, True], ids=["sync", "async"])
def test_graph_legacy_select_still_promotes_allowed_subset(async_mode):
    graph, model, recorder, initial = _graph({"query": "select:mcp_allowed,mcp_denied"})
    context = {"__run_journal": recorder}

    result = asyncio.run(graph.ainvoke(initial, context=context)) if async_mode else graph.invoke(initial, context=context)

    assert result["promoted"]["names"] == ["mcp_existing", "mcp_allowed"]
    assert model.bound_tools[-1] == ["mcp_allowed", "mcp_existing", "tool_search"]
    messages = [message for message in result["messages"] if isinstance(message, ToolMessage)]
    assert messages[0].status == "success"
    assert [schema["name"] for schema in json.loads(messages[0].content)] == ["mcp_allowed"]
    assert len(recorder.events) == 1
    assert recorder.events[0]["changes"]["tool_names"] == ["mcp_allowed"]


@pytest.mark.parametrize("async_mode", [False, True], ids=["sync", "async"])
@pytest.mark.parametrize("mode", ["services", "tools"])
def test_graph_readonly_discovery_filters_before_paging_and_callbacks(async_mode, mode):
    graph, model, recorder, initial = _graph({"mode": mode, "page_size": 2})
    callbacks = _ToolCallbacks()
    config = {"callbacks": [callbacks]}
    context = {"__run_journal": recorder}
    result = asyncio.run(graph.ainvoke(initial, config=config, context=context)) if async_mode else graph.invoke(initial, config=config, context=context)
    message = next(message for message in result["messages"] if isinstance(message, ToolMessage))
    data = json.loads(message.content)
    assert "mcp_denied" not in message.content and "parameters" not in message.content
    assert data["total"] == (1 if mode == "services" else 3)
    assert result["promoted"] == initial["promoted"]
    assert recorder.events == []
    assert callbacks.outputs == []  # The active policy builds safe pages before the inner callable boundary.
    assert model.bound_tools[-1] == ["mcp_existing", "tool_search"]
