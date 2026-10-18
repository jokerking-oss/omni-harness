"""Read-only, permission-filtered MCP catalog pages; no schema promotion."""

import base64
import hashlib
import json
from collections import Counter
from typing import TYPE_CHECKING, Literal

from omniharness_extension_api import provenance_kwargs
from langchain_core.messages import ToolMessage
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from omniharness.tools.mcp_metadata import TOOL_NAME_COLLISION_METADATA_KEY, get_mcp_source

if TYPE_CHECKING:
    from omniharness.tools.builtins.tool_search import DeferredToolCatalog


class DiscoveryQuery(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    mode: Literal["services", "tools"]
    query: str = Field(default="", max_length=512)
    server_name: str | None = Field(default=None, max_length=256)
    page_size: int = Field(default=20, ge=1, le=20)
    cursor: str | None = Field(default=None, max_length=512)


def discovery_message(catalog: "DeferredToolCatalog", args: dict, tool_call_id: str, *, allowed_names: set[str] | None = None) -> ToolMessage:
    """Apply authority before counting, sorting and creating the bound cursor."""
    try:
        request = DiscoveryQuery.model_validate(args)
        if args.get("names") is not None:
            raise ValueError("Use names only with mode=load; discovery never loads tools.")
        visible = [candidate for candidate in catalog.tools if allowed_names is None or candidate.name in allowed_names]
        if request.server_name is not None:
            visible = [candidate for candidate in visible if (get_mcp_source(candidate) or {}).get("server_name") == request.server_name]
        terms = request.query.strip().casefold().split()
        visible = [candidate for candidate in visible if all(term in f"{candidate.name} {candidate.description or ''} {(get_mcp_source(candidate) or {}).get('server_name', '')}".casefold() for term in terms)]
        if request.mode == "services":
            counts: dict[str | None, int] = {}
            for candidate in visible:
                source = (get_mcp_source(candidate) or {}).get("server_name")
                counts[source] = counts.get(source, 0) + 1
            items = [{"server_name": source, "tool_count": counts[source]} for source in sorted(counts, key=lambda value: (value is not None, value or ""))]
        else:
            name_counts = Counter(candidate.name for candidate in catalog.tools)
            items = [
                {
                    "name": candidate.name,
                    "description": (candidate.description or "")[:320],
                    "server_name": (get_mcp_source(candidate) or {}).get("server_name"),
                    "ambiguous": (candidate.metadata or {}).get(TOOL_NAME_COLLISION_METADATA_KEY) is True or name_counts[candidate.name] > 1,
                }
                for candidate in sorted(visible, key=lambda value: (value.name, (get_mcp_source(value) or {}).get("server_name", "")))
            ]
        identity = {
            "catalog_hash": catalog.hash,
            "query": request.query,
            "mode": request.mode,
            "server_name": request.server_name,
            "page_size": request.page_size,
            "allowed_names": None if allowed_names is None else sorted(allowed_names),
        }
        binding = hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
        offset = 0
        if request.cursor:
            try:
                cursor = json.loads(base64.urlsafe_b64decode(request.cursor + "=" * (-len(request.cursor) % 4)))
                if not isinstance(cursor, dict) or cursor.get("v") != 1 or cursor.get("binding") != binding or type(cursor.get("offset")) is not int or not 0 <= cursor["offset"] <= len(items):
                    raise ValueError("invalid cursor")
                offset = cursor["offset"]
            except (ValueError, TypeError, UnicodeError) as exc:
                raise ValueError("Catalog, query, scope or permissions changed, or cursor is invalid. Restart from the first page without cursor.") from exc
        next_offset = offset + request.page_size
        next_cursor = None
        if next_offset < len(items):
            next_cursor = base64.urlsafe_b64encode(json.dumps({"v": 1, "binding": binding, "offset": next_offset}).encode("utf-8")).decode("ascii").rstrip("=")
        content = json.dumps({"kind": request.mode, "items": items[offset:next_offset], "total": len(items), "next_cursor": next_cursor}, ensure_ascii=False)
        return ToolMessage(
            content=content,
            tool_call_id=tool_call_id,
            name="tool_search",
            additional_kwargs=provenance_kwargs("tool_catalog", "tool_search_discovery", producer_entity_id=catalog.hash),
        )
    except (ValidationError, ValueError) as exc:
        return ToolMessage(content=f"Discovery rejected: {exc}", tool_call_id=tool_call_id, name="tool_search", status="error")
