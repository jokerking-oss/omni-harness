"""Real tool assembly must preserve collisions for strict deferred loading."""

from copy import deepcopy
from unittest.mock import MagicMock, patch

import pytest
from test_tool_deduplication import _make_minimal_config, _tool_alpha, _tool_alpha_dup, _tool_beta

from omniharness.tools.builtins.tool_search import build_deferred_tool_setup
from omniharness.tools.mcp_metadata import TOOL_NAME_COLLISION_METADATA_KEY, tag_mcp_tool
from omniharness.tools.tools import get_available_tools

_COLLISION_KEY = TOOL_NAME_COLLISION_METADATA_KEY


def _candidate(template, server):
    candidate = template.model_copy(update={"metadata": {"fixture": template.description}})
    return tag_mcp_tool(candidate, server_name=server, transport="http")


def _assemble(mcp_tools, *, configured=None):
    tool_configs = []
    if configured is not None:
        tool_config = MagicMock()
        tool_config.name = configured.name
        tool_config.use = "tests.fake:configured"
        tool_configs.append(tool_config)
    config = _make_minimal_config(tool_configs)
    extensions = MagicMock()
    extensions.get_enabled_mcp_servers.return_value = {"enabled": object()}
    with (
        patch("omniharness.tools.tools.is_host_bash_allowed", return_value=True),
        patch("omniharness.tools.tools.BUILTIN_TOOLS", []),
        patch("omniharness.tools.tools.is_mcp_task_runtime_available", return_value=False),
        patch("omniharness.tools.tools.resolve_variable", return_value=configured),
        patch("omniharness.config.extensions_config.ExtensionsConfig.from_file", return_value=extensions),
        patch("omniharness.mcp.cache.get_cached_mcp_tools", return_value=mcp_tools),
    ):
        tools = get_available_tools(include_upload_tool=False, app_config=config)
    return tools, build_deferred_tool_setup(tools, enabled=True)


def _search(setup, **args):
    assert setup.tool_search_tool is not None
    return setup.tool_search_tool.invoke({"type": "tool_call", "name": "tool_search", "args": args, "id": "assembly-search"})


@pytest.mark.parametrize("server", [None, "first", "second"])
def test_deduplicated_mcp_names_still_reject_the_entire_strict_batch(server):
    first = _candidate(_tool_alpha, "first")
    second = _candidate(_tool_alpha_dup, "second")
    unique = _candidate(_tool_beta, "first")
    tools, setup = _assemble([first, second, unique])

    assert [candidate.name for candidate in tools] == [first.name, unique.name]
    result = _search(setup, names=[unique.name, first.name], server_name=server)
    assert result.update["promoted"]["names"] == []
    message = result.update["messages"][0]
    assert message.status == "error"
    assert f'"ambiguous_names": ["{first.name}"]' in message.content
    assert first.name in message.content
    assert '"parameters"' not in message.content


def test_configured_tool_keeps_priority_and_collision_evidence():
    configured = _candidate(_tool_alpha, "configured")
    duplicate = _candidate(_tool_alpha_dup, "remote")
    tools, setup = _assemble([duplicate], configured=configured)

    assert len(tools) == 1
    assert tools[0].description == configured.description
    assert tools[0].metadata[_COLLISION_KEY] is True
    assert tools[0] is not configured
    result = _search(setup, names=[configured.name], server_name="configured")
    assert result.update["promoted"]["names"] == []
    assert result.update["messages"][0].status == "error"


def test_unique_assembled_tools_load_successfully():
    first = _candidate(_tool_alpha, "first")
    second = _candidate(_tool_beta, "first")
    _, setup = _assemble([first, second])

    result = _search(setup, names=[second.name, first.name], server_name="first")
    assert result.update["promoted"]["names"] == [second.name, first.name]
    assert result.update["messages"][0].status == "success"


def test_legacy_query_retains_the_first_duplicate_tool():
    first = _candidate(_tool_alpha, "first")
    second = _candidate(_tool_alpha_dup, "second")
    _, setup = _assemble([first, second])

    result = _search(setup, query=f"select:{first.name}")
    assert result.update["promoted"]["names"] == [first.name]
    assert result.update["messages"][0].status == "success"


def test_collision_metadata_is_build_local_and_disappears_when_duplicate_is_removed():
    first = _candidate(_tool_alpha, "first")
    second = _candidate(_tool_alpha_dup, "second")
    original_metadata = [deepcopy(first.metadata), deepcopy(second.metadata)]
    collided_tools, collided_setup = _assemble([first, second])

    assert first.metadata == original_metadata[0]
    assert second.metadata == original_metadata[1]
    assert collided_tools[0] is not first
    assert collided_tools[0].metadata[_COLLISION_KEY] is True
    assert _search(collided_setup, names=[first.name]).update["messages"][0].status == "error"

    clean_tools, clean_setup = _assemble([first])
    assert _COLLISION_KEY not in (clean_tools[0].metadata or {})
    assert _search(clean_setup, names=[first.name]).update["messages"][0].status == "success"
    assert collided_tools[0].metadata[_COLLISION_KEY] is True
    assert first.metadata == original_metadata[0]


def test_reassembling_a_previous_build_recomputes_collision_metadata():
    first = _candidate(_tool_alpha, "first")
    duplicate = _candidate(_tool_alpha_dup, "second")
    collided_tools, _ = _assemble([first, duplicate])

    clean_tools, setup = _assemble(collided_tools)
    assert _COLLISION_KEY not in (clean_tools[0].metadata or {})
    assert _search(setup, names=[first.name]).update["messages"][0].status == "success"
    assert collided_tools[0].metadata[_COLLISION_KEY] is True
