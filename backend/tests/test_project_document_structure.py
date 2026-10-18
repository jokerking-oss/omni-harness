"""Versioned project document structure and literal search contracts."""

from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

from omniharness.projects import document_structure as structure
from omniharness.projects import tools
from omniharness.projects.documents import add_staged_document, original_file_path, stage_document_bytes
from omniharness.runtime.context_keys import PROJECT_CONTEXT_KEY


@pytest.fixture
def document(tmp_path):
    text = (
        "# 项目\r\n\r\nFirst literal [x].\r\nSecond line.\r\n\r\n## Costs ##\r\n\r\n"
        "| Item | Cost |\r\n| --- | ---: |\r\n| A | 12 |\r\n| B | 24 |\r\n| C | 36 |\r\n\r\n"
        "```md\r\n# hidden heading\r\n| fake | table |\r\n```\r\n\r\nLast literal [x].\r\n"
    )
    path = tmp_path / "notes.md"
    path.write_bytes(text.encode("utf-8"))
    return SimpleNamespace(path=path, text=text, sha=hashlib.sha256(text.encode()).hexdigest())


def _kwargs(document):
    return {"original_path": document.path, "sha256": document.sha}


def test_structure_has_stable_versioned_blocks_and_exact_unicode_crlf_offsets(document):
    page = structure.list_document_blocks(document.path, **_kwargs(document), offset=0, limit=2)
    assert page["sha256"] == page["text_sha256"] == document.sha
    assert page["total_blocks"] == 6
    assert page["next_offset"] == 2
    blocks = structure.list_document_blocks(document.path, **_kwargs(document), offset=0, limit=50)["blocks"]
    assert [block["kind"] for block in blocks] == ["heading", "paragraph", "heading", "table", "code", "paragraph"]
    for block in blocks:
        assert block["block_id"].startswith(document.sha + ":")
        read = structure.read_document_block(document.path, **_kwargs(document), block_id=block["block_id"])
        assert read["content"] == document.text[block["start_char"] : block["end_char"]]
    assert blocks[3]["heading_path"] == ["项目", "Costs"]
    assert blocks[3]["total_rows"] == 3


def test_table_pages_keep_header_and_never_skip_rows(document):
    blocks = structure.list_document_blocks(document.path, **_kwargs(document))["blocks"]
    table = next(block for block in blocks if block["kind"] == "table")
    pages = [structure.read_document_block(document.path, **_kwargs(document), block_id=table["block_id"], row_offset=i, row_limit=1) for i in range(3)]
    assert all(page["content"].startswith("| Item | Cost |\r\n| --- | ---: |\r\n") for page in pages)
    assert [page["returned_rows"] for page in pages] == [1, 1, 1]
    assert [page["next_row_offset"] for page in pages] == [1, 2, None]
    assert [page["truncated"] for page in pages] == [True, True, False]
    assert "| A |" in pages[0]["content"] and "| B |" in pages[1]["content"] and "| C |" in pages[2]["content"]


def test_literal_search_does_not_interpret_regex_and_paginates_with_locations(document):
    first = structure.search_document_text(document.path, **_kwargs(document), query="literal [x]", limit=1)
    assert len(first["matches"]) == 1 and first["truncated"]
    hit = first["matches"][0]
    assert document.text[hit["start_char"] : hit["end_char"]] == "literal [x]"
    assert hit["start_line"] == 3 and hit["block_id"]
    second = structure.search_document_text(document.path, **_kwargs(document), query="literal [x]", offset=first["next_offset"], limit=1)
    assert len(second["matches"]) == 1 and not second["truncated"]
    assert second["matches"][0]["start_char"] > hit["start_char"]
    assert structure.search_document_text(document.path, **_kwargs(document), query="literal .x.")["matches"] == []


def test_search_handles_unicode_case_and_newlines(tmp_path):
    path = tmp_path / "text.md"
    text = "a" * 14 + "İSTANBUL\n😀needle\nnext"
    path.write_bytes(text.encode())
    kwargs = {"original_path": path, "sha256": hashlib.sha256(text.encode()).hexdigest()}
    case = structure.search_document_text(path, **kwargs, query="istanbul", case_sensitive=False)
    hit = case["matches"][0]
    assert text[hit["start_char"] : hit["end_char"]] == "İSTANBUL"
    cross = structure.search_document_text(path, **kwargs, query="needle\nnext")
    assert len(cross["matches"]) == 1
    assert cross["matches"][0]["start_line"] == 2


def test_setext_headings_and_fenced_pseudo_structure(tmp_path):
    path = tmp_path / "text.md"
    text = "Title\n=====\n\n~~~md\n# pretend\n| a |\n| --- |\n~~~\n\nparagraph\n"
    path.write_bytes(text.encode())
    kwargs = {"original_path": path, "sha256": hashlib.sha256(text.encode()).hexdigest()}
    blocks = structure.list_document_blocks(path, **kwargs)["blocks"]
    assert [block["kind"] for block in blocks] == ["heading", "code", "paragraph"]
    assert blocks[0]["heading_level"] == 1


def test_source_hash_tampering_same_size_is_rejected(document):
    document.path.write_bytes(document.path.read_bytes().replace(b"First", b"OTHER"))
    with pytest.raises(structure.DocumentStructureError, match="content_changed"):
        structure.list_document_blocks(document.path, **_kwargs(document))


def test_derived_text_version_mismatch_and_stale_block_are_rejected(document, tmp_path):
    converted = tmp_path / "converted.md"
    converted.write_bytes(b"# first\n")
    page = structure.list_document_blocks(converted, **_kwargs(document))
    converted.write_bytes(b"# other\n")
    with pytest.raises(structure.DocumentStructureError, match="version_mismatch"):
        structure.list_document_blocks(converted, **_kwargs(document), expected_text_sha256=page["text_sha256"])
    with pytest.raises(structure.DocumentStructureError, match="version_mismatch"):
        structure.read_document_block(converted, **_kwargs(document), block_id=page["blocks"][0]["block_id"])


def test_output_bounds_and_oversized_table_row_have_actionable_error(tmp_path):
    path = tmp_path / "large.md"
    text = "# title\n\n" + "match " * 6000 + "\n\n| Name |\n| --- |\n| " + "x" * 21000 + " |\n"
    path.write_bytes(text.encode())
    kwargs = {"original_path": path, "sha256": hashlib.sha256(text.encode()).hexdigest()}
    hits = structure.search_document_text(path, **kwargs, query="match", limit=9999)
    assert len(hits["matches"]) == 50
    assert all(len(hit["snippet"]) <= 384 for hit in hits["matches"])
    blocks = structure.list_document_blocks(path, **kwargs)["blocks"]
    paragraph = structure.read_document_block(path, **kwargs, block_id=blocks[1]["block_id"], limit=999999)
    assert len(paragraph["content"]) == 20000 and paragraph["next_offset"] == 20000
    with pytest.raises(structure.DocumentStructureError, match="read_project_document"):
        structure.read_document_block(path, **kwargs, block_id=blocks[2]["block_id"])


@pytest.mark.parametrize("query", ["", "   ", "x" * 257])
def test_search_rejects_empty_or_unbounded_query(document, query):
    with pytest.raises(structure.DocumentStructureError, match="query"):
        structure.search_document_text(document.path, **_kwargs(document), query=query)


@pytest.fixture
async def env(tmp_path, monkeypatch):
    import omniharness.config.paths as paths_mod
    from omniharness.persistence.engine import close_engine, get_session_factory, init_engine
    from omniharness.persistence.projects import ProjectDocumentRepository, ProjectRepository

    monkeypatch.setenv("OMNI_HARNESS_HOME", str(tmp_path))
    monkeypatch.setattr(paths_mod, "_paths", None)
    await init_engine("sqlite", url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}", sqlite_dir=str(tmp_path))
    projects = ProjectRepository(get_session_factory())
    docs = ProjectDocumentRepository(get_session_factory())
    project = await projects.create(name="P", user_id="u1")
    paths = paths_mod.get_paths()
    staged = await stage_document_bytes(paths, user_id="u1", project_id=project["id"], chunks=[b"# shelf\n\nsearch literal\n"], max_bytes=1 << 20)
    row, _ = await add_staged_document(docs, paths, user_id="u1", project_id=project["id"], name="notes.md", staged=staged)
    runtime = SimpleNamespace(context={"user_id": "u1", PROJECT_CONTEXT_KEY: {"project_id": project["id"]}})
    yield SimpleNamespace(paths=paths, docs=docs, row=row, runtime=runtime, projects=projects)
    await close_engine()


@pytest.mark.anyio
async def test_tool_wiring_reads_versions_and_reuses_existing_shelf(env):
    names = {tool.name for tool in tools.get_project_document_tools()}
    assert {"list_project_document_blocks", "read_project_document_block", "search_project_document"} <= names
    page = json.loads(await tools._list_project_document_blocks_impl(env.runtime, document_id=env.row["id"]))
    assert page["document_id"] == env.row["id"] and page["sha256"] == env.row["sha256"]
    block = json.loads(await tools._read_project_document_block_impl(env.runtime, document_id=env.row["id"], block_id=page["blocks"][1]["block_id"], expected_sha256=page["sha256"]))
    assert block["content"] == "search literal\n"
    hit = json.loads(await tools._search_project_document_impl(env.runtime, document_id=env.row["id"], query="literal", expected_sha256=page["sha256"]))
    assert hit["matches"][0]["block_id"] == page["blocks"][1]["block_id"]


@pytest.mark.anyio
@pytest.mark.parametrize("operation", ["list", "read", "search"])
async def test_tools_fail_closed_for_missing_pin_foreign_owner_project_and_trash(env, operation):
    calls = {
        "list": lambda runtime: tools._list_project_document_blocks_impl(runtime, document_id=env.row["id"]),
        "read": lambda runtime: tools._read_project_document_block_impl(runtime, document_id=env.row["id"], block_id="invalid"),
        "search": lambda runtime: tools._search_project_document_impl(runtime, document_id=env.row["id"], query="literal"),
    }
    for runtime in [
        SimpleNamespace(context={}),
        SimpleNamespace(context={"user_id": "u2", PROJECT_CONTEXT_KEY: {"project_id": env.row["project_id"]}}),
        SimpleNamespace(context={"user_id": "u1", PROJECT_CONTEXT_KEY: {"project_id": "other"}}),
    ]:
        result = json.loads(await calls[operation](runtime))
        assert "error" in result and "matches" not in result and "blocks" not in result and "content" not in result
    await env.docs.trash(env.row["id"], user_id="u1")
    assert "no longer on the shelf" in json.loads(await calls[operation](env.runtime))["error"]


@pytest.mark.anyio
async def test_tool_revision_mismatch_is_rejected_before_read_or_conversion(env, monkeypatch):
    async def forbidden(*args, **kwargs):
        pytest.fail("version mismatch must decline before content access")

    monkeypatch.setattr(tools, "read_text_serving_path", forbidden)
    result = json.loads(await tools._list_project_document_blocks_impl(env.runtime, document_id=env.row["id"], expected_sha256="0" * 64))
    assert result["code"] == "version_mismatch"


@pytest.mark.anyio
async def test_tool_conversion_disabled_binary_and_missing_content_keep_existing_errors(env, monkeypatch):
    monkeypatch.setattr(tools, "_resolve_auto_convert", lambda: False)
    for name, data, reason in [("x.pdf", b"%PDF bytes", "conversion"), ("x.bin", b"\x00binary", "binary")]:
        staged = await stage_document_bytes(env.paths, user_id="u1", project_id=env.row["project_id"], chunks=[data], max_bytes=1 << 20)
        row, _ = await add_staged_document(env.docs, env.paths, user_id="u1", project_id=env.row["project_id"], name=name, staged=staged)
        result = json.loads(await tools._search_project_document_impl(env.runtime, document_id=row["id"], query="bytes"))
        assert reason in result["error"].lower()
    original_file_path(env.paths, user_id="u1", row=env.row).unlink()
    result = json.loads(await tools._list_project_document_blocks_impl(env.runtime, document_id=env.row["id"]))
    assert "content_missing" in result["error"]
