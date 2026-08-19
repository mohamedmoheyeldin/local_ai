from __future__ import annotations

import hashlib
import io
import re
import shutil
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any
from xml.etree import ElementTree

from pypdf import PdfReader

from ..config import CONTEXT_DIR
from ..database import connection, get_conversation

MAX_FILES = 500
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_BATCH_BYTES = 250 * 1024 * 1024
MAX_CONTEXT_CHARS = 12_000
IGNORED_PARTS = {
    ".git", ".hg", ".svn", ".idea", ".vscode", ".venv", "venv", "env",
    "node_modules", "dist", "build", "coverage", ".next", ".nuxt", ".astro",
    "target", "vendor", "__pycache__", ".cache",
}
TEXT_EXTENSIONS = {
    ".txt", ".md", ".mdx", ".rst", ".log", ".csv", ".tsv", ".json", ".jsonl",
    ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".env", ".xml", ".html",
    ".htm", ".css", ".scss", ".less", ".js", ".jsx", ".ts", ".tsx", ".mjs",
    ".cjs", ".py", ".rb", ".php", ".java", ".kt", ".kts", ".go", ".rs", ".c",
    ".h", ".cpp", ".hpp", ".cs", ".swift", ".scala", ".sh", ".bash", ".zsh",
    ".fish", ".ps1", ".bat", ".cmd", ".sql", ".graphql", ".gql", ".astro",
    ".vue", ".svelte", ".dockerfile", ".gitignore", ".editorconfig",
}
OFFICE_EXTENSIONS = {".docx", ".pptx", ".xlsx"}
SUPPORTED_EXTENSIONS = TEXT_EXTENSIONS | OFFICE_EXTENSIONS | {".pdf"}


def _has_fts(database) -> bool:
    return bool(database.execute("SELECT 1 FROM sqlite_master WHERE name = 'context_chunks_fts'").fetchone())


def capabilities() -> dict[str, Any]:
    return {
        "max_files": MAX_FILES,
        "max_file_bytes": MAX_FILE_BYTES,
        "max_batch_bytes": MAX_BATCH_BYTES,
        "extensions": sorted(SUPPORTED_EXTENSIONS),
        "folder_picker": True,
    }


def _safe_relative_path(value: str, fallback: str) -> str:
    value = value.replace("\\", "/").strip().lstrip("/") or fallback
    path = PurePosixPath(value)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("Attachment path is invalid")
    if any(part.lower() in IGNORED_PARTS for part in path.parts[:-1]):
        raise LookupError("Generated or vendor folder")
    return str(path)[:2_000]


def _office_text(data: bytes, extension: str) -> str:
    patterns = {
        ".docx": ("word/document.xml",),
        ".pptx": ("ppt/slides/slide",),
        ".xlsx": ("xl/sharedStrings.xml", "xl/worksheets/sheet"),
    }[extension]
    blocks: list[str] = []
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = sorted(name for name in archive.namelist() if any(name.startswith(prefix) for prefix in patterns) and name.endswith(".xml"))
        expanded_size = sum(archive.getinfo(name).file_size for name in names)
        if expanded_size > 50 * 1024 * 1024:
            raise ValueError("Document expands beyond the 50 MB safety limit")
        for name in names:
            root = ElementTree.fromstring(archive.read(name))
            text = " ".join(node.text.strip() for node in root.iter() if node.text and node.text.strip())
            if text:
                blocks.append(text)
    return "\n\n".join(blocks)


def extract_text(data: bytes, relative_path: str) -> str:
    extension = Path(relative_path).suffix.lower()
    if extension == ".pdf":
        return "\n\n".join((page.extract_text() or "").strip() for page in PdfReader(io.BytesIO(data)).pages).strip()
    if extension in OFFICE_EXTENSIONS:
        return _office_text(data, extension)
    if extension not in TEXT_EXTENSIONS and Path(relative_path).name.lower() not in {"dockerfile", "makefile", "license"}:
        raise ValueError("Unsupported file type")
    if b"\x00" in data[:8_192]:
        raise ValueError("Binary file")
    return data.decode("utf-8", errors="replace").strip()


def chunk_text(text: str, target: int = 1_400, overlap: int = 180) -> list[str]:
    text = re.sub(r"\r\n?", "\n", text).strip()
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + target, len(text))
        if end < len(text):
            split = max(text.rfind("\n\n", start + target // 2, end), text.rfind("\n", start + target // 2, end))
            if split > start:
                end = split
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return chunks


def ingest(conversation_id: str, items: list[tuple[str, str, str, bytes]]) -> dict[str, Any]:
    get_conversation(conversation_id)
    if not items:
        raise ValueError("Choose at least one file")
    if len(items) > MAX_FILES:
        raise ValueError(f"Select no more than {MAX_FILES} files at a time")
    total = sum(len(data) for _, _, _, data in items)
    if total > MAX_BATCH_BYTES:
        raise ValueError("The selected files exceed the 250 MB batch limit")

    root = CONTEXT_DIR / conversation_id
    root.mkdir(parents=True, exist_ok=True)
    try:
        root.chmod(0o700)
    except OSError:
        pass
    indexed: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for name, raw_path, media_type, data in items:
        try:
            relative_path = _safe_relative_path(raw_path, name)
            if len(data) > MAX_FILE_BYTES:
                raise ValueError("File exceeds the 20 MB limit")
            text = extract_text(data, relative_path)
            chunks = chunk_text(text)
            if not chunks:
                raise ValueError("No searchable text found")
        except (ValueError, LookupError, OSError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
            skipped.append({"path": raw_path or name, "reason": str(exc)})
            continue

        digest = hashlib.sha256(data).hexdigest()
        stored = root / digest[:2] / f"{digest}-{Path(relative_path).name}"
        stored.parent.mkdir(parents=True, exist_ok=True)
        stored.write_bytes(data)
        try:
            stored.chmod(0o600)
        except OSError:
            pass
        with connection() as database:
            has_fts = _has_fts(database)
            old = database.execute(
                "SELECT id, stored_path FROM context_sources WHERE conversation_id = ? AND relative_path = ?",
                (conversation_id, relative_path),
            ).fetchone()
            if old:
                if has_fts:
                    database.execute("DELETE FROM context_chunks_fts WHERE source_id = ?", (old["id"],))
                database.execute("DELETE FROM context_sources WHERE id = ?", (old["id"],))
                old_path = Path(old["stored_path"])
                if old_path != stored:
                    old_path.unlink(missing_ok=True)
            cursor = database.execute(
                """INSERT INTO context_sources(conversation_id,name,relative_path,media_type,size_bytes,sha256,stored_path,chunk_count)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (conversation_id, name[:500], relative_path, media_type[:200], len(data), digest, str(stored), len(chunks)),
            )
            source_id = int(cursor.lastrowid)
            for index, content in enumerate(chunks):
                database.execute(
                    "INSERT INTO context_chunks(source_id,conversation_id,chunk_index,content) VALUES(?,?,?,?)",
                    (source_id, conversation_id, index, content),
                )
                if has_fts:
                    database.execute(
                        "INSERT INTO context_chunks_fts(content,source_id,conversation_id) VALUES(?,?,?)",
                        (content, source_id, conversation_id),
                    )
        indexed.append({"id": source_id, "name": name, "relative_path": relative_path, "size_bytes": len(data), "chunk_count": len(chunks), "status": "ready"})
    return {"indexed": indexed, "skipped": skipped, "count": len(indexed), "total_bytes": total}


def ingest_streams(conversation_id: str, items: list[tuple[str, str, str, Any, int | None]]) -> dict[str, Any]:
    """Index spooled uploads one at a time to keep folder imports memory-bounded."""
    get_conversation(conversation_id)
    if not items:
        raise ValueError("Choose at least one file")
    if len(items) > MAX_FILES:
        raise ValueError(f"Select no more than {MAX_FILES} files at a time")
    known_total = sum(int(size or 0) for *_, size in items)
    if known_total > MAX_BATCH_BYTES:
        raise ValueError("The selected files exceed the 250 MB batch limit")
    indexed: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    actual_total = 0
    for name, relative_path, media_type, stream, declared_size in items:
        if declared_size is not None and declared_size > MAX_FILE_BYTES:
            skipped.append({"path": relative_path or name, "reason": "File exceeds the 20 MB limit"})
            continue
        stream.seek(0)
        data = stream.read(MAX_FILE_BYTES + 1)
        actual_total += len(data)
        if actual_total > MAX_BATCH_BYTES:
            raise ValueError("The selected files exceed the 250 MB batch limit")
        if len(data) > MAX_FILE_BYTES:
            skipped.append({"path": relative_path or name, "reason": "File exceeds the 20 MB limit"})
            continue
        result = ingest(conversation_id, [(name, relative_path, media_type, data)])
        indexed.extend(result["indexed"])
        skipped.extend(result["skipped"])
    return {"indexed": indexed, "skipped": skipped, "count": len(indexed), "total_bytes": actual_total}


def list_sources(conversation_id: str) -> list[dict[str, Any]]:
    get_conversation(conversation_id)
    with connection() as database:
        rows = database.execute(
            "SELECT id,name,relative_path,media_type,size_bytes,sha256,status,chunk_count,error,created_at FROM context_sources WHERE conversation_id = ? ORDER BY relative_path COLLATE NOCASE",
            (conversation_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def delete_source(conversation_id: str, source_id: int) -> bool:
    with connection() as database:
        row = database.execute(
            "SELECT stored_path FROM context_sources WHERE id = ? AND conversation_id = ?",
            (source_id, conversation_id),
        ).fetchone()
        if not row:
            return False
        if _has_fts(database):
            database.execute("DELETE FROM context_chunks_fts WHERE source_id = ?", (source_id,))
        database.execute("DELETE FROM context_sources WHERE id = ?", (source_id,))
    Path(row["stored_path"]).unlink(missing_ok=True)
    return True


def delete_conversation_files(conversation_id: str) -> None:
    with connection() as database:
        if _has_fts(database):
            database.execute("DELETE FROM context_chunks_fts WHERE conversation_id = ?", (conversation_id,))
    root = CONTEXT_DIR / conversation_id
    if root.is_dir():
        shutil.rmtree(root)


def search_context(conversation_id: str, query: str, limit: int = 8) -> list[dict[str, Any]]:
    tokens = re.findall(r"[\w.-]{2,}", query.lower(), flags=re.UNICODE)[:12]
    if not tokens:
        return []
    expression = " OR ".join(f'"{token.replace(chr(34), chr(34) * 2)}"' for token in tokens)
    with connection() as database:
        bounded_limit = max(1, min(limit, 20))
        if _has_fts(database):
            rows = database.execute(
                """SELECT f.content, f.source_id, s.relative_path, bm25(context_chunks_fts) AS rank
                   FROM context_chunks_fts f JOIN context_sources s ON s.id = f.source_id
                   WHERE context_chunks_fts MATCH ? AND f.conversation_id = ?
                   ORDER BY rank LIMIT ?""",
                (expression, conversation_id, bounded_limit),
            ).fetchall()
        else:
            conditions = " OR ".join("lower(c.content) LIKE ?" for _ in tokens)
            rows = database.execute(
                f"""SELECT c.content, c.source_id, s.relative_path, 0 AS rank
                    FROM context_chunks c JOIN context_sources s ON s.id = c.source_id
                    WHERE c.conversation_id = ? AND ({conditions}) LIMIT ?""",
                (conversation_id, *(f"%{token}%" for token in tokens), bounded_limit),
            ).fetchall()
    return [dict(row) for row in rows]


def context_for_prompt(conversation_id: str, query: str) -> str:
    results = search_context(conversation_id, query)
    if not results:
        return ""
    parts: list[str] = []
    used = 0
    for item in results:
        block = f"Source: {item['relative_path']}\n{item['content']}"
        remaining = MAX_CONTEXT_CHARS - used
        if remaining <= 0:
            break
        parts.append(block[:remaining])
        used += len(parts[-1])
    return "\n\n---\n\n".join(parts)
