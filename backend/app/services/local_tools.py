from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


MAX_OUTPUT_CHARS = 40_000
MAX_READ_CHARS = 100_000


TOOL_DEFINITIONS = [
    {
        "name": "local_list_files",
        "description": "List files and folders inside the selected local workspace.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "Workspace-relative folder, default ."},
            "pattern": {"type": "string", "description": "Glob pattern, default *"},
            "recursive": {"type": "boolean", "default": False},
        }},
    },
    {
        "name": "local_read_file",
        "description": "Read a UTF-8 text file inside the selected local workspace.",
        "parameters": {"type": "object", "required": ["path"], "properties": {
            "path": {"type": "string"},
            "max_chars": {"type": "integer", "minimum": 1, "maximum": MAX_READ_CHARS},
        }},
    },
    {
        "name": "local_write_file",
        "description": "Create or replace a text file inside the selected local workspace. Creates parent folders when needed.",
        "parameters": {"type": "object", "required": ["path", "content"], "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        }},
    },
    {
        "name": "local_replace_in_file",
        "description": "Change an existing text file by replacing exact text. By default the old text must occur exactly once.",
        "parameters": {"type": "object", "required": ["path", "old_text", "new_text"], "properties": {
            "path": {"type": "string"},
            "old_text": {"type": "string"},
            "new_text": {"type": "string"},
            "replace_all": {"type": "boolean", "default": False},
        }},
    },
    {
        "name": "local_create_directory",
        "description": "Create a folder, including missing parent folders, inside the selected local workspace.",
        "parameters": {"type": "object", "required": ["path"], "properties": {"path": {"type": "string"}}},
    },
    {
        "name": "local_move_path",
        "description": "Move or rename a file or folder inside the selected local workspace.",
        "parameters": {"type": "object", "required": ["source", "destination"], "properties": {
            "source": {"type": "string"},
            "destination": {"type": "string"},
        }},
    },
    {
        "name": "local_delete_path",
        "description": "Delete a file or folder inside the selected local workspace. Non-empty folders require recursive=true.",
        "parameters": {"type": "object", "required": ["path"], "properties": {
            "path": {"type": "string"},
            "recursive": {"type": "boolean", "default": False},
        }},
    },
    {
        "name": "local_run_command",
        "description": "Run a shell command on this computer from the selected local workspace and return exit code, stdout, and stderr.",
        "parameters": {"type": "object", "required": ["command"], "properties": {
            "command": {"type": "string"},
            "cwd": {"type": "string", "description": "Workspace-relative working folder, default ."},
            "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 120},
        }},
    },
]


def _inside(root: Path, value: str, *, must_exist: bool = False) -> Path:
    root = root.expanduser().resolve()
    candidate = Path(value).expanduser()
    candidate = (candidate if candidate.is_absolute() else root / candidate).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError("Path must stay inside the selected workspace")
    if must_exist and not candidate.exists():
        raise FileNotFoundError(f"Path does not exist: {candidate.relative_to(root)}")
    return candidate


def _relative(root: Path, path: Path) -> str:
    value = path.relative_to(root).as_posix()
    return value or "."


def execute_local_tool(workspace_path: str, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    root = Path(workspace_path).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("Selected workspace is unavailable")

    if tool_name == "local_list_files":
        folder = _inside(root, str(arguments.get("path") or "."), must_exist=True)
        if not folder.is_dir():
            raise ValueError("List path must be a folder")
        pattern = str(arguments.get("pattern") or "*")[:200]
        iterator = folder.rglob(pattern) if arguments.get("recursive") else folder.glob(pattern)
        items = []
        for path in iterator:
            if ".git" in path.relative_to(root).parts:
                continue
            items.append({"path": _relative(root, path), "type": "directory" if path.is_dir() else "file"})
            if len(items) >= 500:
                break
        return {"workspace": str(root), "items": items, "truncated": len(items) >= 500}

    if tool_name == "local_read_file":
        path = _inside(root, str(arguments.get("path") or ""), must_exist=True)
        if not path.is_file():
            raise ValueError("Read path must be a file")
        limit = max(1, min(int(arguments.get("max_chars") or 40_000), MAX_READ_CHARS))
        content = path.read_text(encoding="utf-8", errors="replace")
        return {"path": _relative(root, path), "content": content[:limit], "truncated": len(content) > limit}

    if tool_name == "local_write_file":
        path = _inside(root, str(arguments.get("path") or ""))
        content = str(arguments.get("content") or "")
        path.parent.mkdir(parents=True, exist_ok=True)
        existed = path.exists()
        if existed and not path.is_file():
            raise ValueError("Write path is not a file")
        path.write_text(content, encoding="utf-8")
        return {"path": _relative(root, path), "created": not existed, "bytes": len(content.encode("utf-8"))}

    if tool_name == "local_replace_in_file":
        path = _inside(root, str(arguments.get("path") or ""), must_exist=True)
        old_text = str(arguments.get("old_text") or "")
        new_text = str(arguments.get("new_text") or "")
        if not old_text:
            raise ValueError("old_text cannot be empty")
        content = path.read_text(encoding="utf-8")
        occurrences = content.count(old_text)
        if occurrences == 0:
            raise ValueError("old_text was not found")
        replace_all = bool(arguments.get("replace_all"))
        if occurrences > 1 and not replace_all:
            raise ValueError(f"old_text occurs {occurrences} times; set replace_all=true or provide more context")
        updated = content.replace(old_text, new_text, -1 if replace_all else 1)
        path.write_text(updated, encoding="utf-8")
        return {"path": _relative(root, path), "replacements": occurrences if replace_all else 1}

    if tool_name == "local_create_directory":
        path = _inside(root, str(arguments.get("path") or ""))
        path.mkdir(parents=True, exist_ok=True)
        return {"path": _relative(root, path), "created": True}

    if tool_name == "local_move_path":
        source = _inside(root, str(arguments.get("source") or ""), must_exist=True)
        destination = _inside(root, str(arguments.get("destination") or ""))
        if destination.exists():
            raise FileExistsError(f"Destination already exists: {_relative(root, destination)}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        return {"source": _relative(root, source), "destination": _relative(root, destination)}

    if tool_name == "local_delete_path":
        path = _inside(root, str(arguments.get("path") or ""), must_exist=True)
        if path == root:
            raise ValueError("The workspace root cannot be deleted")
        if path.is_dir():
            if arguments.get("recursive"):
                shutil.rmtree(path)
            else:
                path.rmdir()
        else:
            path.unlink()
        return {"path": _relative(root, path), "deleted": True}

    if tool_name == "local_run_command":
        command = str(arguments.get("command") or "").strip()
        if not command:
            raise ValueError("command cannot be empty")
        cwd = _inside(root, str(arguments.get("cwd") or "."), must_exist=True)
        if not cwd.is_dir():
            raise ValueError("Command working directory must be a folder")
        timeout = max(1, min(int(arguments.get("timeout_seconds") or 60), 120))
        completed = subprocess.run(
            command,
            cwd=cwd,
            shell=True,
            executable=None if os.name == "nt" else "/bin/bash",
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            check=False,
        )
        return {
            "command": command,
            "cwd": _relative(root, cwd),
            "exit_code": completed.returncode,
            "stdout": completed.stdout[:MAX_OUTPUT_CHARS],
            "stderr": completed.stderr[:MAX_OUTPUT_CHARS],
            "truncated": len(completed.stdout) > MAX_OUTPUT_CHARS or len(completed.stderr) > MAX_OUTPUT_CHARS,
        }

    raise ValueError(f"Unknown local tool: {tool_name}")
