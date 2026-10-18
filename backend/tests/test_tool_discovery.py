"""Discovery paginates only visible metadata and never loads schemas."""

import json

import pytest
from langchain_core.tools import tool

from omniharness.tools.builtins.tool_search import DeferredToolCatalog, build_tool_search_tool
from omniharness.tools.mcp_metadata import tag_mcp_tool


def _candidate(name, server=None):
    @tool(name)
    def candidate(value: str) -> str:
        "Look up office records."
        raise AssertionError("Discovery must never execute business tools")

    return tag_mcp_tool(candidate, server_name=server, transport="http")


def _catalog():
    return DeferredToolCatalog(tuple(_candidate(f"tool_{i:02}", "mail" if i < 12 else "docs") for i in range(24)) + (_candidate("legacy"),))


def _invoke(catalog, **args):
    return build_tool_search_tool(catalog).invoke({"type": "tool_call", "name": "tool_search", "args": args, "id": "discover"})


def test_service_discovery_returns_only_metadata_and_no_promotion():
    result = _invoke(_catalog(), mode="services")
    assert result.name == "tool_search" and result.status == "success"
    data = json.loads(result.content)
    assert data["total"] == 3
    assert {item["server_name"]: item["tool_count"] for item in data["items"]} == {"mail": 12, "docs": 12, None: 1}
    assert "parameters" not in result.content


def test_service_scope_and_stable_cursor_page_tools_without_loading():
    catalog = _catalog()
    first = json.loads(_invoke(catalog, mode="tools", server_name="mail", page_size=5).content)
    assert first["total"] == 12
    assert [item["name"] for item in first["items"]] == [f"tool_{i:02}" for i in range(5)]
    second = json.loads(_invoke(catalog, mode="tools", server_name="mail", page_size=5, cursor=first["next_cursor"]).content)
    assert [item["name"] for item in second["items"]] == [f"tool_{i:02}" for i in range(5, 10)]
    last = json.loads(_invoke(catalog, mode="tools", server_name="mail", page_size=5, cursor=second["next_cursor"]).content)
    assert len(last["items"]) == 2 and last["next_cursor"] is None


@pytest.mark.parametrize("changes", [{"query": "records"}, {"server_name": "docs"}, {"mode": "services"}, {"page_size": 6}])
def test_cursor_is_bound_to_query_scope_and_page_size(changes):
    catalog = _catalog()
    page = json.loads(_invoke(catalog, mode="tools", server_name="mail", page_size=5).content)
    args = {"mode": "tools", "server_name": "mail", "page_size": 5, "cursor": page["next_cursor"], **changes}
    rejected = _invoke(catalog, **args)
    assert rejected.status == "error" and "first page" in rejected.content


def test_cursor_is_bound_to_catalog_revision():
    page = json.loads(_invoke(_catalog(), mode="tools", page_size=5).content)
    changed = DeferredToolCatalog((_candidate("other", "mail"),))
    assert _invoke(changed, mode="tools", page_size=5, cursor=page["next_cursor"]).status == "error"


@pytest.mark.parametrize("cursor", ["bad", "W10", "e30", "A" * 500])
def test_malformed_cursor_never_reveals_or_promotes_tools(cursor):
    result = _invoke(_catalog(), mode="tools", cursor=cursor)
    assert result.status == "error" and "parameters" not in result.content


def test_unknown_service_is_empty_without_fallback():
    result = json.loads(_invoke(_catalog(), mode="tools", server_name="unknown").content)
    assert result["total"] == 0 and result["items"] == []


def test_discovery_names_are_mutually_exclusive_with_loading():
    result = _invoke(_catalog(), mode="tools", names=["tool_00"])
    assert result.status == "error" and "parameters" not in result.content


def test_readonly_metadata_is_filtered_before_counts_and_pagination():
    from omniharness.tools.builtins.tool_discovery import discovery_message

    catalog = _catalog()
    result = discovery_message(catalog, {"mode": "services", "page_size": 1}, "d1", allowed_names={"tool_12", "tool_13"})
    data = json.loads(result.content)
    assert data["total"] == 1
    assert data["items"] == [{"server_name": "docs", "tool_count": 2}]
    result = discovery_message(catalog, {"mode": "tools", "page_size": 1}, "d2", allowed_names={"tool_12", "tool_13"})
    data = json.loads(result.content)
    assert data["total"] == 2 and data["items"][0]["name"] == "tool_12"
    old_cursor = data["next_cursor"]
    revoked = discovery_message(catalog, {"mode": "tools", "page_size": 1, "cursor": old_cursor}, "d3", allowed_names={"tool_13"})
    assert revoked.status == "error"


def test_empty_policy_and_legacy_source_are_supported():
    from omniharness.tools.builtins.tool_discovery import discovery_message

    assert json.loads(discovery_message(_catalog(), {"mode": "services"}, "d", allowed_names=set()).content)["total"] == 0
    assert json.loads(discovery_message(_catalog(), {"mode": "services"}, "d", allowed_names={"legacy"}).content)["items"] == [{"server_name": None, "tool_count": 1}]
