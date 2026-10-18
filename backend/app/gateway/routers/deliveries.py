"""Bounded owner-scoped discovery of terminal run.delivery receipts."""

import json
from contextlib import AsyncExitStack
from datetime import datetime
from pathlib import PurePosixPath
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import and_, exists, or_, select

from app.gateway.authz import require_permission
from app.gateway.deps import get_current_user, get_run_event_store, get_run_store, get_thread_store
from omniharness.persistence.engine import get_session_factory
from omniharness.persistence.models.run_event import RunEventRow
from omniharness.persistence.run.model import RunRow
from omniharness.persistence.thread_meta.model import ThreadMetaRow
from omniharness.runtime.events.store.db import DbRunEventStore
from omniharness.utils.time import coerce_iso

router = APIRouter(prefix="/api/deliveries", tags=["deliveries"])
_TERMINAL = ("success", "error", "timeout", "interrupted")
DeliveryFileType = Literal["all", "document", "spreadsheet", "presentation", "image", "code", "other"]
_FILE_EXTENSIONS = {
    "document": frozenset("pdf doc docx odt rtf md mdx txt rst tex".split()),
    "spreadsheet": frozenset("csv tsv xls xlsx ods".split()),
    "presentation": frozenset("ppt pptx odp".split()),
    "image": frozenset("png jpg jpeg gif webp svg avif bmp tif tiff ico".split()),
    "code": frozenset("html htm js jsx ts tsx json py ipynb sh bash ps1 css scss sql xml yaml yml toml ini rs go java c cpp h hpp cs rb php swift kt".split()),
}


def _file_type(path: str) -> str:
    extension = PurePosixPath(path).suffix.removeprefix(".").casefold()
    return next((name for name, extensions in _FILE_EXTENSIONS.items() if extension in extensions), "other")


def _filter_paths(paths: list[str], *, title: str, query: str, file_type: DeliveryFileType) -> list[str]:
    title_matches = query in title.casefold()
    return [path for path in paths if (file_type == "all" or _file_type(path) == file_type) and (title_matches or query in PurePosixPath(path).name.casefold())]


def _paths(content):
    if isinstance(content, str):
        if len(content) > 200000:
            return []
        try:
            content = json.loads(content)
        except ValueError:
            return []
    if not isinstance(content, dict) or not isinstance(content.get("by_tool"), dict):
        return []
    paths = content["by_tool"].get("present_files", [])
    if not isinstance(paths, list):
        return []
    result = []
    for path in paths[:200]:
        if not isinstance(path, str) or len(path) > 4096 or "\\" in path or "\x00" in path:
            continue
        parsed = PurePosixPath(path)
        if not path.startswith("/mnt/user-data/outputs/") or ".." in parsed.parts or str(parsed) != path:
            continue
        if path not in result:
            result.append(path)
    return result


@router.get("/page")
@require_permission("threads", "read")
@require_permission("runs", "read")
async def page(
    request: Request,
    limit: int = Query(20, ge=1, le=50),
    before_created_at: datetime | None = None,
    before_run_id: str | None = Query(None, min_length=1, max_length=64),
    q: str = Query("", max_length=200),
    file_type: DeliveryFileType = "all",
) -> dict:
    if (before_created_at is None) != (before_run_id is None):
        raise HTTPException(422, "Supply both cursor fields")
    user_id = await get_current_user(request)
    if user_id is None:
        raise HTTPException(401, "Identity required")
    events = get_run_event_store(request)
    sf = get_session_factory()
    candidates = []
    sql_events = isinstance(events, DbRunEventStore) and sf is not None
    query = q.strip().casefold()
    scan_limit = 50 if query or file_type != "all" or not sql_events else limit
    if sf is not None:
        statement = (
            select(RunRow, ThreadMetaRow).join(ThreadMetaRow, ThreadMetaRow.thread_id == RunRow.thread_id).where(RunRow.user_id == user_id, ThreadMetaRow.user_id == user_id, RunRow.status.in_(_TERMINAL), RunRow.operation_kind == "run")
        )
        if sql_events:
            statement = statement.where(
                exists(
                    select(RunEventRow.id).where(RunEventRow.run_id == RunRow.run_id, RunEventRow.thread_id == RunRow.thread_id, RunEventRow.event_type == "run.delivery", or_(RunEventRow.user_id == user_id, RunEventRow.user_id.is_(None)))
                )
            )
        if before_created_at is not None:
            statement = statement.where(or_(RunRow.created_at < before_created_at, and_(RunRow.created_at == before_created_at, RunRow.run_id < before_run_id)))
        async with sf() as session:
            rows = (await session.execute(statement.order_by(RunRow.created_at.desc(), RunRow.run_id.desc()).limit(scan_limit + 1))).all()
            for run, thread in rows:
                candidates.append(({"run_id": run.run_id, "thread_id": run.thread_id, "status": run.status, "created_at": coerce_iso(run.created_at)}, {"display_name": thread.display_name, "metadata": thread.metadata_json}))
    else:
        threads = await get_thread_store(request).search(user_id=user_id, limit=50)
        runs = get_run_store(request)
        for thread in threads:
            rows = await runs.list_by_thread(thread["thread_id"], user_id=user_id, limit=51, before_created_at=coerce_iso(before_created_at) if before_created_at else None, before_run_id=before_run_id)
            candidates.extend(({"run_id": run["run_id"], "thread_id": run["thread_id"], "status": run["status"], "created_at": coerce_iso(run["created_at"])}, thread) for run in rows if run.get("operation_kind", "run") == "run")
        candidates.sort(key=lambda entry: (coerce_iso(entry[0]["created_at"]), entry[0]["run_id"]), reverse=True)
        candidates = candidates[:51]
    # Filtered pages and event-store fallbacks advance across empty/invalid/unmatched receipts.
    has_more = len(candidates) > scan_limit
    scanned = candidates[:scan_limit]
    data = []
    scanned_count = 0
    async with AsyncExitStack() as stack:
        session = await stack.enter_async_context(sf()) if sql_events else None
        for run, thread in scanned:
            scanned_count += 1
            if run["status"] not in _TERMINAL:
                continue
            if session is not None:
                receipts = (
                    (
                        await session.execute(
                            select(RunEventRow.content)
                            .where(RunEventRow.run_id == run["run_id"], RunEventRow.thread_id == run["thread_id"], RunEventRow.event_type == "run.delivery", or_(RunEventRow.user_id == user_id, RunEventRow.user_id.is_(None)))
                            .limit(2)
                        )
                    )
                    .scalars()
                    .all()
                )
                content = receipts[0] if len(receipts) == 1 else None
            else:
                receipts = await events.list_events(run["thread_id"], run["run_id"], event_types=["run.delivery"], limit=2, user_id=user_id)
                content = receipts[0].get("content") if len(receipts) == 1 else None
            title = str(thread.get("display_name") or "")
            paths = _filter_paths(_paths(content), title=title, query=query, file_type=file_type)
            if paths:
                metadata = thread.get("metadata")
                agent_name = metadata.get("agent_name") if isinstance(metadata, dict) else None
                data.append({**run, "thread_title": title[:256] or None, "agent_name": agent_name[:256] if isinstance(agent_name, str) else None, "paths": paths[:50], "files_truncated": len(paths) > 50})
            if len(data) == limit:
                has_more = has_more or run is not scanned[-1][0]
                break
    last = run if scanned else None
    return {
        "data": data,
        "scope": "history" if sql_events else "recent_runs",
        "scanned_runs": scanned_count,
        "has_more": has_more,
        "next_before_created_at": last["created_at"] if has_more and last else None,
        "next_before_run_id": last["run_id"] if has_more and last else None,
    }
