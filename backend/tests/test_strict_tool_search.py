"""Strict batch loading must never silently promote an incomplete tool set."""

import json

import pytest
from langchain_core.tools import tool
from pydantic import ValidationError

from omniharness.agents.thread_state import merge_promoted
from omniharness.tools.builtins.tool_search import DeferredToolCatalog, build_tool_search_tool
from omniharness.tools.mcp_metadata import tag_mcp_tool


def _tool(name: str, server: str | None = None):
    @tool(name)
    def candidate(value: str) -> str:
        "A deferred business tool."
        raise AssertionError("Discovery must never execute a business tool")

    return tag_mcp_tool(candidate, server_name=server, transport="http")


def _invoke(catalog, **args):
    return build_tool_search_tool(catalog).invoke({"type": "tool_call", "name": "tool_search", "args": args, "id": "strict-search"})


def test_strict_batch_loads_all_requested_tools_in_request_order():
    catalog = DeferredToolCatalog(tuple(_tool(f"tool_{i}", "office") for i in range(8)))
    wanted = [f"tool_{i}" for i in reversed(range(8))]
    result = _invoke(catalog, names=[" tool_7 ", *wanted, "tool_0"])

    assert result.update["promoted"] == {"catalog_hash": catalog.hash, "names": wanted}
    message = result.update["messages"][0]
    assert message.status == "success"
    assert [schema["name"] for schema in json.loads(message.content)] == wanted
    assert message.tool_call_id == "strict-search"


def test_strict_missing_name_rejects_whole_batch_and_preserves_existing_promotions():
    catalog = DeferredToolCatalog((_tool("read_records"),))
    result = _invoke(catalog, names=["read_records", "missing_submit", "missing_export"])

    assert result.update["promoted"]["names"] == []
    message = result.update["messages"][0]
    assert message.status == "error"
    assert "missing_submit" in message.content and "missing_export" in message.content
    assert '"parameters"' not in message.content
    existing = {"catalog_hash": catalog.hash, "names": ["read_records"]}
    assert merge_promoted(existing, result.update["promoted"]) == existing


@pytest.mark.parametrize("server", [None, "first", "second"])
def test_duplicate_catalog_names_cannot_be_resolved_by_scope(server):
    # Graph promotion and execution use only the name. Server scoping must not
    # claim to disambiguate two callables sharing that execution identity.
    catalog = DeferredToolCatalog((_tool("shared", "first"), _tool("shared", "second")))
    result = _invoke(catalog, names=["shared"], server_name=server)

    assert result.update["promoted"]["names"] == []
    assert result.update["messages"][0].status == "error"
    assert "ambiguous_names" in result.update["messages"][0].content


def test_strict_server_scope_uses_source_metadata_not_name_prefix():
    catalog = DeferredToolCatalog((_tool("mail_read", "docs"), _tool("docs_read", "mail"), _tool("legacy")))
    result = _invoke(catalog, names=["docs_read"], server_name="mail")
    assert result.update["promoted"]["names"] == ["docs_read"]

    for name in ["mail_read", "legacy"]:
        rejected = _invoke(catalog, names=["docs_read", name], server_name="mail")
        assert rejected.update["promoted"]["names"] == []
        assert rejected.update["messages"][0].status == "error"


@pytest.mark.parametrize("server", ["unknown", "MAIL", " "])
def test_unknown_or_mismatched_server_never_falls_back(server):
    catalog = DeferredToolCatalog((_tool("read", "mail"),))
    result = _invoke(catalog, names=["read"], server_name=server)
    assert result.update["promoted"]["names"] == []
    assert result.update["messages"][0].status == "error"


def test_legacy_queries_can_be_scoped_without_changing_unscoped_matching():
    catalog = DeferredToolCatalog((_tool("first_read", "first"), _tool("second_read", "second"), _tool("legacy_read")))
    assert [candidate.name for candidate in catalog.search("read")] == ["first_read", "second_read", "legacy_read"]
    assert [candidate.name for candidate in catalog.search("read", server_name="first")] == ["first_read"]
    assert catalog.search("read", server_name="unknown") == []
    result = _invoke(catalog, query="select:first_read,second_read", server_name="first")
    assert result.update["promoted"]["names"] == ["first_read"]
    # Keep old select:'s partial-match compatibility.
    assert _invoke(catalog, query="select:first_read,unknown").update["promoted"]["names"] == ["first_read"]


@pytest.mark.parametrize("args", [{"names": ["read"], "query": "read"}, {"names": [" "]}])
def test_invalid_strict_input_returns_actionable_error_without_schemas(args):
    catalog = DeferredToolCatalog((_tool("read"),))
    result = _invoke(catalog, **args)
    assert result.update["promoted"]["names"] == []
    assert result.update["messages"][0].status == "error"
    assert '"parameters"' not in result.update["messages"][0].content


@pytest.mark.parametrize("names", [[], ["read"] * 33, ["x" * 257]])
def test_strict_input_size_is_bounded_by_tool_schema(names):
    catalog = DeferredToolCatalog((_tool("read"),))
    with pytest.raises(ValidationError):
        _invoke(catalog, names=names)


def test_case_sensitive_names_are_not_guessed_or_corrected():
    catalog = DeferredToolCatalog((_tool("Read"),))
    result = _invoke(catalog, names=["read"])
    assert result.update["promoted"]["names"] == []
    assert "missing_names" in result.update["messages"][0].content


def test_empty_legacy_query_still_returns_no_tools():
    catalog = DeferredToolCatalog((_tool("read"),))
    assert _invoke(catalog).update["promoted"]["names"] == []


def test_server_scope_does_not_expose_source_configuration():
    candidate = _tool("read", "mail")
    candidate.metadata["omniharness_mcp_source"]["token"] = "should-never-be-returned"
    catalog = DeferredToolCatalog((candidate,))
    result = _invoke(catalog, names=["read"], server_name="mail")
    assert "should-never-be-returned" not in result.update["messages"][0].content


def test_source_identity_change_invalidates_persisted_promotions():
    original = DeferredToolCatalog((_tool("read", "first"),))
    replacement = DeferredToolCatalog((_tool("read", "second"),))
    assert original.hash != replacement.hash

    result = _invoke(replacement, names=["read"], server_name="first")
    existing = {"catalog_hash": original.hash, "names": ["read"]}
    assert merge_promoted(existing, result.update["promoted"])["names"] == []


def test_nonidentity_source_configuration_does_not_affect_catalog_hash():
    original = _tool("read", "mail")
    additional = _tool("read", "mail")
    additional.metadata["omniharness_mcp_source"]["token"] = "private-token"
    assert DeferredToolCatalog((original,)).hash == DeferredToolCatalog((additional,)).hash
