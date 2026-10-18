import asyncio
import json
from types import SimpleNamespace

import pytest
from omniharness_extension_api import provenance_kwargs
from langchain.agents.middleware.types import ModelRequest
from langchain_core.messages import AIMessage, ToolMessage

from omniharness.agents.middlewares.catalog_projection import project_catalog_messages
from omniharness.agents.middlewares.deferred_tool_filter_middleware import DeferredToolFilterMiddleware


def history(*, status="success", stamp=True):
    call = AIMessage(content="", tool_calls=[{"id": "c", "name": "tool_search", "args": {"names": ["lookup"]}}], response_metadata={"id": "resp_old"})
    result = ToolMessage(
        content=json.dumps([{"name": "lookup", "parameters": {"description": "large schema " * 100}}]),
        tool_call_id="c",
        name="tool_search",
        status=status,
        additional_kwargs=provenance_kwargs("tool_catalog", "tool_search_selection", producer_entity_id="hash") if stamp else {},
    )
    return [call, result, AIMessage(content="next", response_metadata={"id": "resp_new"})]


def test_projection_keeps_state_and_pairs_but_invalidates_provider_continuation():
    messages = history()
    projected = project_catalog_messages(messages, catalog_hash="hash", bound_names={"lookup"})
    assert len(projected) == 3
    assert projected[1].tool_call_id == "c"
    assert json.loads(projected[1].content)["loaded_names"] == ["lookup"]
    assert len(projected[1].content) < len(messages[1].content)
    assert "parameters" in messages[1].content
    assert all("id" not in m.response_metadata for m in projected if isinstance(m, AIMessage))
    assert messages[0].response_metadata["id"] == "resp_old"


def test_errors_unstamped_stale_unbound_and_unpaired_results_are_retained():
    for messages, digest, names in [(history(status="error"), "hash", {"lookup"}), (history(stamp=False), "hash", {"lookup"}), (history(), "other", {"lookup"}), (history(), "hash", set()), (history()[1:], "hash", {"lookup"})]:
        assert project_catalog_messages(messages, catalog_hash=digest, bound_names=names) is None


@pytest.mark.parametrize("async_mode", [False, True])
def test_real_model_request_projection_follows_filtered_bindings(async_mode):
    messages = history()
    state = {"promoted": {"catalog_hash": "hash", "names": ["lookup"]}}
    request = ModelRequest(model=None, tools=[SimpleNamespace(name="lookup"), SimpleNamespace(name="other")], messages=messages, state=state)
    middleware = DeferredToolFilterMiddleware(frozenset({"lookup", "other"}), "hash")

    async def async_handler(request):
        return request

    result = asyncio.run(middleware.awrap_model_call(request, async_handler)) if async_mode else middleware.wrap_model_call(request, lambda request: request)
    assert [tool.name for tool in result.tools] == ["lookup"]
    assert "tool_selection_receipt" in result.messages[1].content
    assert result.state is state and "parameters" in messages[1].content
    # Revocation removes the binding, so that historical result stays intact.
    state["promoted"]["names"] = []
    assert middleware._project_request(request).messages is messages
