"""Delivery discovery reads formal receipts, never files or model text."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from _router_auth_helpers import make_authed_test_app
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.gateway.routers import deliveries
from omniharness.persistence.base import Base
from omniharness.persistence.models.run_event import RunEventRow
from omniharness.persistence.run.model import RunRow
from omniharness.persistence.thread_meta.model import ThreadMetaRow
from omniharness.runtime.events.store.db import DbRunEventStore
from omniharness.runtime.events.store.memory import MemoryRunEventStore

NOW = datetime(2026, 10, 11, 12, tzinfo=UTC)
PATH = "/mnt/user-data/outputs/report.md"
OUTPUTS = "/mnt/user-data/outputs/"


def replace_paths(sf, paths, *, run_id="new", title=None):
    async def update():
        async with sf() as session:
            receipt = (await session.execute(select(RunEventRow).where(RunEventRow.run_id == run_id))).scalar_one()
            receipt.content = json.dumps({"by_tool": {"present_files": paths}})
            if title is not None:
                thread = await session.get(ThreadMetaRow, "mine")
                thread.display_name = title
            await session.commit()

    asyncio.run(update())


def seed_sql_window(sf, *, count, matching_indexes):
    async def seed():
        async with sf() as session:
            for index in range(count):
                run_id = f"window-{index:03d}"
                filename = "target.PDF" if index in matching_indexes else "ordinary.png"
                session.add(RunRow(run_id=run_id, thread_id="mine", user_id="user-a", status="success", operation_kind="run", created_at=NOW + timedelta(minutes=index + 1)))
                session.add(RunEventRow(thread_id="mine", run_id=run_id, user_id="user-a", event_type="run.delivery", category="outputs", seq=index + 100, content=json.dumps({"by_tool": {"present_files": [OUTPUTS + filename]}})))
            await session.commit()

    asyncio.run(seed())


@pytest.fixture()
def setup_client(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'deliveries.db'}", poolclass=NullPool)
    sf = async_sessionmaker(engine, expire_on_commit=False)

    async def seed():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with sf() as session:
            session.add_all(
                [
                    ThreadMetaRow(thread_id="mine", user_id="user-a", display_name="My research", metadata_json={"agent_name": "researcher"}),
                    ThreadMetaRow(thread_id="foreign", user_id="user-b", display_name="Private"),
                ]
            )
            for index, (run_id, thread_id, user_id, status, operation) in enumerate(
                [
                    ("old", "mine", "user-a", "success", "run"),
                    ("new", "mine", "user-a", "error", "run"),
                    ("foreign-run", "foreign", "user-b", "success", "run"),
                    ("deleted-thread", "deleted", "user-a", "success", "run"),
                    ("wrong-thread-owner", "foreign", "user-a", "success", "run"),
                    ("active", "mine", "user-a", "running", "run"),
                    ("write", "mine", "user-a", "success", "checkpoint_write"),
                    ("no-receipt", "mine", "user-a", "success", "run"),
                ]
            ):
                session.add(RunRow(run_id=run_id, thread_id=thread_id, user_id=user_id, status=status, operation_kind=operation, created_at=NOW + timedelta(seconds=index), last_ai_message=f"Download {PATH}"))
                if run_id != "no-receipt":
                    session.add(
                        RunEventRow(
                            thread_id=thread_id,
                            run_id=run_id,
                            user_id=user_id,
                            event_type="run.delivery",
                            category="outputs",
                            seq=index + 1,
                            content=json.dumps({"by_tool": {"present_files": [PATH, PATH]}}),
                            event_metadata={"content_is_json": True},
                            created_at=NOW,
                        )
                    )
            await session.commit()

    asyncio.run(seed())
    monkeypatch.setattr(deliveries, "get_session_factory", lambda: sf)
    monkeypatch.setattr(deliveries, "get_current_user", AsyncMock(return_value="user-a"))
    app = make_authed_test_app()
    app.state.run_event_store = DbRunEventStore(sf)
    app.include_router(deliveries.router)
    with TestClient(app) as client:
        yield client, sf, app
    asyncio.run(engine.dispose())


def test_sql_history_is_scoped_to_owned_existing_threads_and_formal_receipts(setup_client):
    client, _, _ = setup_client
    response = client.get("/api/deliveries/page")
    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "history"
    assert [row["run_id"] for row in body["data"]] == ["new", "old"]
    assert body["data"][0]["paths"] == [PATH]
    assert body["data"][0]["thread_title"] == "My research"
    assert body["data"][0]["agent_name"] == "researcher"
    assert body["data"][0]["status"] == "error"
    assert body["has_more"] is False


def test_keyset_pagination_has_no_duplicates(setup_client):
    client, _, _ = setup_client
    first = client.get("/api/deliveries/page?limit=1").json()
    assert [row["run_id"] for row in first["data"]] == ["new"]
    assert first["has_more"]
    second = client.get(
        "/api/deliveries/page",
        params={
            "limit": 1,
            "before_created_at": first["next_before_created_at"],
            "before_run_id": first["next_before_run_id"],
        },
    ).json()
    assert [row["run_id"] for row in second["data"]] == ["old"]
    assert not second["has_more"]


def test_memory_events_fallback_reads_bounded_runs_and_receipts(setup_client):
    client, _, app = setup_client
    events = MemoryRunEventStore()
    asyncio.run(events.put(thread_id="mine", run_id="old", event_type="run.delivery", category="outputs", content={"by_tool": {"present_files": [PATH]}}))
    app.state.run_event_store = events
    body = client.get("/api/deliveries/page").json()
    assert body["scope"] == "recent_runs"
    assert [row["run_id"] for row in body["data"]] == ["old"]
    assert body["scanned_runs"] == 3  # no-receipt + new + old; no foreign/active/internal rows


def test_duplicate_or_unsafe_receipts_do_not_become_deliveries(setup_client):
    client, sf, _ = setup_client

    async def corrupt():
        async with sf() as session:
            session.add(RunEventRow(thread_id="mine", run_id="new", user_id="user-a", event_type="run.delivery", category="outputs", seq=99, content=json.dumps({"by_tool": {"present_files": [PATH]}})))
            old = (await session.execute(__import__("sqlalchemy").select(RunEventRow).where(RunEventRow.run_id == "old"))).scalar_one()
            old.content = json.dumps({"by_tool": {"present_files": ["/mnt/user-data/uploads/secret", "/mnt/user-data/outputs/../secret"]}})
            await session.commit()

    asyncio.run(corrupt())
    body = client.get("/api/deliveries/page").json()
    assert body["data"] == []


@pytest.mark.parametrize("query", ["limit=0", "limit=51", "before_run_id=old", "before_created_at=bad&before_run_id=old"])
def test_invalid_pagination_is_rejected(setup_client, query):
    client, _, _ = setup_client
    assert client.get(f"/api/deliveries/page?{query}").status_code == 422


def test_missing_identity_fails_closed(setup_client, monkeypatch):
    client, _, _ = setup_client
    monkeypatch.setattr(deliveries, "get_current_user", AsyncMock(return_value=None))
    assert client.get("/api/deliveries/page").status_code == 401


def test_pure_memory_database_uses_owned_threads_and_advances_cursor(setup_client, monkeypatch):
    from langgraph.store.memory import InMemoryStore

    from omniharness.persistence.thread_meta.memory import MemoryThreadMetaStore
    from omniharness.runtime.runs.store.memory import MemoryRunStore

    client, _, app = setup_client
    threads, runs, events = MemoryThreadMetaStore(InMemoryStore()), MemoryRunStore(), MemoryRunEventStore()

    async def seed():
        for owner, thread in [("user-a", "mine"), ("user-b", "other")]:
            await threads.create(thread, user_id=owner, display_name=thread)
            for i in range(3):
                run_id = f"{thread}-{i}"
                await runs.put(
                    run_id,
                    thread_id=thread,
                    user_id=owner,
                    status="success",
                    created_at=(NOW + timedelta(seconds=i)).isoformat(),
                    kwargs={"input": {"messages": ["private conversation"]}, "config": {"configurable": {"private_setting": "private value"}}},
                    metadata={"private_metadata": "private value"},
                )
                await events.put(thread_id=thread, run_id=run_id, event_type="run.delivery", category="outputs", content={"by_tool": {"present_files": [PATH]}})

    asyncio.run(seed())
    monkeypatch.setattr(deliveries, "get_session_factory", lambda: None)
    app.state.thread_store, app.state.run_store, app.state.run_event_store = threads, runs, events
    first = client.get("/api/deliveries/page?limit=1").json()
    assert first["scope"] == "recent_runs" and first["data"][0]["run_id"] == "mine-2"
    assert set(first["data"][0]) == {"run_id", "thread_id", "status", "created_at", "thread_title", "agent_name", "paths", "files_truncated"}
    second = client.get("/api/deliveries/page", params={"limit": 1, "before_created_at": first["next_before_created_at"], "before_run_id": first["next_before_run_id"]}).json()
    assert second["data"][0]["run_id"] == "mine-1"


@pytest.mark.parametrize("query", [" STRASSE ", "straße", "方案"])
def test_search_trims_and_casefolds_unicode_filenames(setup_client, query):
    client, sf, _ = setup_client
    target = OUTPUTS + "Straße-方案.PDF"
    replace_paths(sf, [target, OUTPUTS + "unrelated.pdf"])
    body = client.get("/api/deliveries/page", params={"q": query}).json()
    assert [row["run_id"] for row in body["data"]] == ["new"]
    assert body["data"][0]["paths"] == [target]


def test_title_search_retains_all_files_matching_the_selected_type(setup_client):
    client, sf, _ = setup_client
    paths = [OUTPUTS + name for name in ["overview.PDF", "details.docx", "table.csv", "preview.png"]]
    replace_paths(sf, paths, title="Straße 研究方案")
    body = client.get("/api/deliveries/page", params={"q": " STRASSE 研究 ", "file_type": "document"}).json()
    assert [row["run_id"] for row in body["data"]] == ["new", "old"]
    assert body["data"][0]["paths"] == paths[:2]
    assert body["data"][1]["paths"] == [PATH]


@pytest.mark.parametrize("query", ["new", "outputs", "hidden-folder", "%", "_", ".*", "[abc]"])
def test_search_uses_literal_basename_or_title_and_never_run_id_or_directories(setup_client, query):
    client, sf, _ = setup_client
    replace_paths(sf, [OUTPUTS + "hidden-folder/ordinary.pdf"])
    body = client.get("/api/deliveries/page", params={"q": query}).json()
    assert body["data"] == []


def test_filename_search_and_type_filter_must_match_the_same_path(setup_client):
    client, sf, _ = setup_client
    paths = [OUTPUTS + name for name in ["target.csv", "other.pdf", "target.PDF", "target.pdf.exe"]]
    replace_paths(sf, paths)
    body = client.get("/api/deliveries/page", params={"q": "TARGET", "file_type": "document"}).json()
    assert [row["run_id"] for row in body["data"]] == ["new"]
    assert body["data"][0]["paths"] == [paths[2]]


@pytest.mark.parametrize(
    ("file_type", "extensions"),
    [
        ("document", "pdf doc docx odt rtf md mdx txt rst tex"),
        ("spreadsheet", "csv tsv xls xlsx ods"),
        ("presentation", "ppt pptx odp"),
        ("image", "png jpg jpeg gif webp svg avif bmp tif tiff ico"),
        ("code", "html htm js jsx ts tsx json py ipynb sh bash ps1 css scss sql xml yaml yml toml ini rs go java c cpp h hpp cs rb php swift kt"),
        ("other", "zip exe bin unknown"),
    ],
)
def test_file_type_uses_case_insensitive_final_extension(setup_client, file_type, extensions):
    client, sf, _ = setup_client
    paths = [OUTPUTS + f"target.{extension.upper()}" for extension in extensions.split()]
    if file_type == "other":
        paths += [OUTPUTS + "target", OUTPUTS + "target.pdf.zip", OUTPUTS + ".env"]
    replace_paths(sf, [*paths, OUTPUTS + "unrelated.pdf" if file_type != "document" else OUTPUTS + "unrelated.png"])
    body = client.get("/api/deliveries/page", params={"q": "target" if file_type != "other" else "", "file_type": file_type}).json()
    assert [row["run_id"] for row in body["data"]] == ["new"]
    assert body["data"][0]["paths"] == paths


@pytest.mark.parametrize("params", [{"q": "   "}, {"file_type": "all"}, {"q": "", "file_type": "all"}])
def test_empty_search_and_all_type_preserve_default_page(setup_client, params):
    client, _, _ = setup_client
    assert client.get("/api/deliveries/page", params=params).json() == client.get("/api/deliveries/page").json()


@pytest.mark.parametrize("params", [{"q": "x" * 201}, {"file_type": "pdf"}, {"file_type": "DOCUMENT"}, {"file_type": ""}])
def test_invalid_filters_are_rejected(setup_client, params):
    client, _, _ = setup_client
    assert client.get("/api/deliveries/page", params=params).status_code == 422


def test_search_accepts_the_maximum_length_as_a_literal_query(setup_client):
    client, sf, _ = setup_client
    query = "x" * 200
    replace_paths(sf, [OUTPUTS + query + ".pdf"])
    response = client.get("/api/deliveries/page", params={"q": query})
    assert response.status_code == 200
    assert [row["run_id"] for row in response.json()["data"]] == ["new"]


def test_search_does_not_expose_foreign_thread_or_receipt_owners(setup_client):
    client, sf, _ = setup_client
    replace_paths(sf, [OUTPUTS + "private.pdf"])

    async def foreign_receipt():
        async with sf() as session:
            receipt = (await session.execute(select(RunEventRow).where(RunEventRow.run_id == "new"))).scalar_one()
            receipt.user_id = "user-b"
            await session.commit()

    asyncio.run(foreign_receipt())
    body = client.get("/api/deliveries/page", params={"q": "Private", "file_type": "document"}).json()
    assert body["data"] == []


def test_search_validates_singleton_receipt_and_safe_paths_before_matching(setup_client):
    client, sf, _ = setup_client
    replace_paths(sf, [OUTPUTS + "target.pdf"])
    replace_paths(sf, [OUTPUTS + "../target.pdf", "/mnt/user-data/uploads/target.pdf"], run_id="old")

    async def duplicate():
        async with sf() as session:
            session.add(RunEventRow(thread_id="mine", run_id="new", user_id="user-a", event_type="run.delivery", category="outputs", seq=99, content=json.dumps({"by_tool": {"present_files": [OUTPUTS + "unrelated.png"]}})))
            await session.commit()

    asyncio.run(duplicate())
    assert client.get("/api/deliveries/page", params={"q": "target", "file_type": "document"}).json()["data"] == []


@pytest.mark.parametrize("params", [{"q": "target"}, {"file_type": "document"}, {"q": "target", "file_type": "document"}])
def test_filtered_sql_page_scans_past_unmatched_runs_and_keeps_keyset_order(setup_client, params):
    client, sf, _ = setup_client
    seed_sql_window(sf, count=7, matching_indexes={0, 2})
    first = client.get("/api/deliveries/page", params={"limit": 1, **params}).json()
    assert [row["run_id"] for row in first["data"]] == ["window-002"]
    assert first["scanned_runs"] == 5
    assert first["has_more"] is True
    assert first["next_before_run_id"] == "window-002"
    second = client.get(
        "/api/deliveries/page",
        params={"limit": 1, **params, "before_created_at": first["next_before_created_at"], "before_run_id": first["next_before_run_id"]},
    ).json()
    assert [row["run_id"] for row in second["data"]] == ["window-000"]
    final = client.get(
        "/api/deliveries/page",
        params={"limit": 1, "q": "target", "before_created_at": second["next_before_created_at"], "before_run_id": second["next_before_run_id"]},
    ).json()
    assert final["data"] == []
    assert final["has_more"] is False
    assert final["next_before_created_at"] is None
    assert final["next_before_run_id"] is None
    assert second["scanned_runs"] == 2


def test_filtered_sql_empty_window_advances_cursor_with_a_bounded_scan(setup_client):
    client, sf, _ = setup_client
    seed_sql_window(sf, count=54, matching_indexes={0})
    first = client.get("/api/deliveries/page", params={"limit": 1, "q": "target"}).json()
    assert first["data"] == []
    assert first["scanned_runs"] == 50
    assert first["has_more"] is True
    assert first["next_before_run_id"] == "window-004"
    second = client.get(
        "/api/deliveries/page",
        params={"limit": 1, "q": "target", "before_created_at": first["next_before_created_at"], "before_run_id": first["next_before_run_id"]},
    ).json()
    assert [row["run_id"] for row in second["data"]] == ["window-000"]


def test_filtered_paths_are_capped_and_truncation_counts_only_matching_files(setup_client):
    client, sf, _ = setup_client
    paths = [OUTPUTS + f"target-{index:02d}.pdf" for index in range(51)]
    replace_paths(sf, [OUTPUTS + "unmatched.png", *paths])
    row = client.get("/api/deliveries/page", params={"q": "target", "file_type": "document"}).json()["data"][0]
    assert row["paths"] == paths[:50]
    assert row["files_truncated"] is True
    row = client.get("/api/deliveries/page", params={"q": "target-50", "file_type": "document"}).json()["data"][0]
    assert row["paths"] == paths[50:]
    assert row["files_truncated"] is False


def test_memory_events_with_sql_runs_apply_search_and_file_type(setup_client):
    client, _, app = setup_client
    events = MemoryRunEventStore()
    paths = [OUTPUTS + "Straße.PDF", OUTPUTS + "Straße.png", OUTPUTS + "ordinary.pdf"]
    asyncio.run(events.put(thread_id="mine", run_id="old", event_type="run.delivery", category="outputs", content={"by_tool": {"present_files": paths}}))
    app.state.run_event_store = events
    body = client.get("/api/deliveries/page", params={"q": " STRASSE ", "file_type": "document"}).json()
    assert body["scope"] == "recent_runs"
    assert [row["run_id"] for row in body["data"]] == ["old"]
    assert body["data"][0]["paths"] == paths[:1]


@pytest.mark.parametrize("active_run", [False, True])
def test_pure_memory_filtered_empty_window_advances_and_preserves_owner_scope(setup_client, monkeypatch, active_run):
    from langgraph.store.memory import InMemoryStore

    from omniharness.persistence.thread_meta.memory import MemoryThreadMetaStore
    from omniharness.runtime.runs.store.memory import MemoryRunStore

    client, _, app = setup_client
    threads, runs, events = MemoryThreadMetaStore(InMemoryStore()), MemoryRunStore(), MemoryRunEventStore()

    async def seed():
        await threads.create("mine", user_id="user-a", display_name="Research")
        await threads.create("foreign", user_id="user-b", display_name="Target")
        for index in range(54):
            run_id = f"window-{index:03d}"
            paths = [OUTPUTS + "Straße.PDF", OUTPUTS + "Straße.png"] if index == 0 else [OUTPUTS + "ordinary.png"]
            await runs.put(run_id, thread_id="mine", user_id="user-a", status="success", created_at=(NOW + timedelta(minutes=index)).isoformat())
            await events.put(thread_id="mine", run_id=run_id, event_type="run.delivery", category="outputs", content={"by_tool": {"present_files": paths}})
        if active_run:
            await runs.put("active", thread_id="mine", user_id="user-a", status="running", created_at=(NOW + timedelta(days=2)).isoformat())
        await runs.put("foreign-run", thread_id="foreign", user_id="user-b", status="success", created_at=(NOW + timedelta(days=1)).isoformat())
        await events.put(thread_id="foreign", run_id="foreign-run", event_type="run.delivery", category="outputs", content={"by_tool": {"present_files": [OUTPUTS + "Straße.PDF"]}})

    asyncio.run(seed())
    monkeypatch.setattr(deliveries, "get_session_factory", lambda: None)
    app.state.thread_store, app.state.run_store, app.state.run_event_store = threads, runs, events
    first = client.get("/api/deliveries/page", params={"limit": 1, "q": "strasse", "file_type": "document"}).json()
    assert first["scope"] == "recent_runs"
    assert first["data"] == []
    assert first["scanned_runs"] == 50
    assert first["has_more"] is True
    assert first["next_before_run_id"] == ("window-005" if active_run else "window-004")
    second = client.get(
        "/api/deliveries/page",
        params={"limit": 1, "q": "strasse", "file_type": "document", "before_created_at": first["next_before_created_at"], "before_run_id": first["next_before_run_id"]},
    ).json()
    assert [row["run_id"] for row in second["data"]] == ["window-000"]
    assert second["data"][0]["paths"] == [OUTPUTS + "Straße.PDF"]
    assert second["has_more"] is False
