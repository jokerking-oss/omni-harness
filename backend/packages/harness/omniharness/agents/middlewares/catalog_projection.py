"""Replace validated historical schema results in the model request only."""

import json
from collections import Counter

from omniharness_extension_api import provenance_kwargs

from omniharness.agents.middlewares.tool_call_args import _without_response_chain_id, pair_tool_call_results


def project_catalog_messages(messages: list, *, catalog_hash: str | None, bound_names: set[str]) -> list | None:
    if not catalog_hash:
        return None
    replacements = {}
    for occurrence in pair_tool_call_results(messages):
        result = occurrence.result
        if occurrence.name != "tool_search" or result is None or result.name != "tool_search" or result.status != "success":
            continue
        if Counter(call.get("id") for call in occurrence.message.tool_calls)[occurrence.call_id] != 1:
            continue
        meta = result.additional_kwargs
        if meta.get("omniharness_producer_kind") != "tool_search_selection" or meta.get("omniharness_producer_entity_id") != catalog_hash:
            continue
        if not isinstance(result.content, str) or len(result.content) > 2_000_000:
            continue
        try:
            schemas = json.loads(result.content)
        except (ValueError, TypeError):
            continue
        if not isinstance(schemas, list) or not schemas or not all(isinstance(schema, dict) for schema in schemas):
            continue
        names = [schema.get("name") or (schema["function"].get("name") if isinstance(schema.get("function"), dict) else None) for schema in schemas]
        if not all(isinstance(name, str) and name in bound_names for name in names):
            continue
        content = json.dumps(
            {"kind": "tool_selection_receipt", "catalog_hash": catalog_hash, "loaded_names": list(dict.fromkeys(names)), "hint": "Schemas are bound to this request. Call tool_search again to reload details."}, ensure_ascii=False
        )
        if len(content) >= len(result.content):
            continue
        replacements[id(result)] = result.model_copy(update={"content": content, "additional_kwargs": {**meta, **provenance_kwargs("tool_catalog", "tool_catalog_projection", producer_entity_id=catalog_hash)}})
    if not replacements:
        return None
    return [_without_response_chain_id(replacements.get(id(message), message)) for message in messages]
