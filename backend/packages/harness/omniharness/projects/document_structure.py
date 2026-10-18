"""Versioned, bounded Markdown structure and literal search for shelf text."""

import hashlib
import re
from pathlib import Path

_MAX_BYTES = 8 * 1024 * 1024
_MAX_SOURCE_BYTES = 100 * 1024 * 1024


class DocumentStructureError(ValueError):
    pass


def _load(path: Path, *, original_path: Path, sha256: str, expected_text_sha256: str | None = None):
    digest = hashlib.sha256()
    scanned = 0
    with original_path.open("rb") as source:
        while chunk := source.read(65536):
            scanned += len(chunk)
            if scanned > _MAX_SOURCE_BYTES:
                raise DocumentStructureError("structure_size_limit: original exceeds 100 MiB; use read_project_document")
            digest.update(chunk)
    if digest.hexdigest() != sha256:
        raise DocumentStructureError("content_changed: refresh the shelf document before retrying")
    with path.open("rb") as source:
        data = source.read(_MAX_BYTES + 1)
    if len(data) > _MAX_BYTES:
        raise DocumentStructureError("structure_size_limit: use read_project_document for text over 8 MiB")
    text_sha = hashlib.sha256(data).hexdigest()
    if path == original_path and text_sha != sha256:
        raise DocumentStructureError("content_changed: original changed during read")
    if expected_text_sha256 and expected_text_sha256 != text_sha:
        raise DocumentStructureError("version_mismatch: list blocks again for the current text version")
    return data.decode("utf-8-sig"), text_sha


def _blocks(text: str, version: str) -> list[dict]:
    if text.count("\n") > 100000:
        raise DocumentStructureError("structure_size_limit: too many lines; use read_project_document")
    lines = text.splitlines(keepends=True)
    positions = [0]
    for line in lines:
        positions.append(positions[-1] + len(line))
    blocks = []
    headings: list[tuple[int, str]] = []
    i = 0
    while i < len(lines):
        if len(blocks) >= 10000:
            raise DocumentStructureError("structure_size_limit: too many blocks; use read_project_document")
        if not lines[i].strip():
            i += 1
            continue
        start = i
        kind = "paragraph"
        attrs = {}
        stripped = lines[i].strip()
        fence = re.match(r"^(`{3,}|~{3,})", stripped)
        atx = re.match(r"^(#{1,6})\s+(.+)", stripped)
        setext = i + 1 < len(lines) and re.fullmatch(r"\s*(=+|-+)\s*", lines[i + 1])
        if fence:
            kind = "code"
            marker = fence[1]
            i += 1
            while i < len(lines):
                closing = lines[i].strip()
                i += 1
                if closing and all(c == marker[0] for c in closing) and len(closing) >= len(marker):
                    break
        elif atx or setext:
            kind = "heading"
            level = len(atx[1]) if atx else (1 if lines[i + 1].strip().startswith("=") else 2)
            title = atx[2] if atx else stripped
            end = len(title.rstrip())
            suffix = end
            while suffix > 0 and title[suffix - 1] == "#":
                suffix -= 1
            if atx and 0 < suffix < end and title[suffix - 1].isspace():
                title = title[:suffix].rstrip()
            headings = [(n, value) for n, value in headings if n < level] + [(level, title[:160])]
            attrs["heading_level"] = level
            i += 1 if atx else 2
        elif i + 1 < len(lines) and "|" in lines[i] and re.fullmatch(r"[\s|:\-]+", lines[i + 1].strip()) and "---" in lines[i + 1]:
            kind = "table"
            i += 2
            while i < len(lines) and lines[i].strip() and "|" in lines[i]:
                i += 1
            attrs["total_rows"] = i - start - 2
        else:
            i += 1
            while i < len(lines) and lines[i].strip() and not re.match(r"^\s*(#{1,6}\s|`{3,}|~{3,})", lines[i]):
                if i + 1 < len(lines) and "|" in lines[i] and re.fullmatch(r"[\s|:\-]+", lines[i + 1].strip()):
                    break
                i += 1
        blocks.append(
            {
                "block_id": f"{version}:{positions[start]}:{positions[i]}",
                "kind": kind,
                "start_char": positions[start],
                "end_char": positions[i],
                "start_line": start + 1,
                "end_line": i,
                "heading_path": [value for _, value in headings],
                **attrs,
            }
        )
    return blocks


def _context(path, **kwargs):
    text, version = _load(path, **kwargs)
    return text, version, _blocks(text, version)


def list_document_blocks(path, *, original_path, sha256, expected_text_sha256=None, offset=0, limit=50):
    text, version, blocks = _context(path, original_path=original_path, sha256=sha256, expected_text_sha256=expected_text_sha256)
    offset, limit = max(0, offset), max(1, min(50, limit))
    return {"sha256": sha256, "text_sha256": version, "total_chars": len(text), "total_blocks": len(blocks), "blocks": blocks[offset : offset + limit], "next_offset": offset + limit if offset + limit < len(blocks) else None}


def read_document_block(path, *, original_path, sha256, block_id, expected_text_sha256=None, offset=0, limit=8000, row_offset=0, row_limit=50):
    text, version, blocks = _context(path, original_path=original_path, sha256=sha256, expected_text_sha256=expected_text_sha256)
    if not block_id.startswith(version + ":"):
        raise DocumentStructureError("version_mismatch: list blocks again")
    block = next((b for b in blocks if b["block_id"] == block_id), None)
    if block is None:
        raise DocumentStructureError("unknown block_id: list blocks again")
    value = text[block["start_char"] : block["end_char"]]
    result = {"sha256": sha256, "text_sha256": version, **block}
    if block["kind"] == "table":
        lines = value.splitlines(keepends=True)
        row_offset, row_limit = max(0, row_offset), max(1, min(50, row_limit))
        header = "".join(lines[:2])
        chosen = []
        size = len(header)
        for line in lines[2 + row_offset : 2 + row_offset + row_limit]:
            if size + len(line) > 20000:
                if not chosen:
                    raise DocumentStructureError("table row exceeds output bound: use read_project_document character windows")
                break
            chosen.append(line)
            size += len(line)
        if len(header) > 20000:
            raise DocumentStructureError("table header exceeds output bound: use read_project_document")
        next_row = row_offset + len(chosen)
        result.update(content=header + "".join(chosen), returned_rows=len(chosen), next_row_offset=next_row if next_row < block["total_rows"] else None, truncated=next_row < block["total_rows"])
    else:
        offset, limit = max(0, offset), max(1, min(20000, limit))
        content = value[offset : offset + limit]
        next_offset = offset + len(content)
        result.update(content=content, offset=offset, returned_chars=len(content), next_offset=next_offset if next_offset < len(value) else None, truncated=next_offset < len(value))
    return result


def search_document_text(path, *, original_path, sha256, query, expected_text_sha256=None, case_sensitive=True, offset=0, limit=20):
    if not query.strip() or len(query) > 256:
        raise DocumentStructureError("query must contain 1..256 literal characters")
    text, version, blocks = _context(path, original_path=original_path, sha256=sha256, expected_text_sha256=expected_text_sha256)
    offset, limit = max(0, offset), max(1, min(50, limit))
    matches = []
    has_more = False
    block_index = 0
    # Escaping is required: regex syntax in a user query is always literal.
    for match in re.finditer(re.escape(query), text, flags=0 if case_sensitive else re.IGNORECASE):
        if match.start() < offset:
            continue
        if len(matches) == limit:
            has_more = True
            break
        while block_index < len(blocks) and blocks[block_index]["end_char"] <= match.start():
            block_index += 1
        block = blocks[block_index] if block_index < len(blocks) else None
        matches.append(
            {
                "start_char": match.start(),
                "end_char": match.end(),
                "start_line": text.count("\n", 0, match.start()) + 1,
                "block_id": block["block_id"] if block else None,
                "snippet": text[max(0, match.start() - 64) : min(len(text), match.start() + 320)],
            }
        )
    return {"sha256": sha256, "text_sha256": version, "matches": matches, "truncated": has_more, "next_offset": matches[-1]["end_char"] if has_more else None}
