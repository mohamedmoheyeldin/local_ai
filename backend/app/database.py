from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .config import DATABASE_PATH, ensure_directories, environment_setting_overrides, load_defaults
from .services.credential_vault import vault


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    ensure_directories()
    database = sqlite3.connect(DATABASE_PATH, timeout=10)
    try:
        DATABASE_PATH.chmod(0o600)
    except OSError:
        pass
    database.row_factory = sqlite3.Row
    database.execute("PRAGMA journal_mode=WAL")
    database.execute("PRAGMA foreign_keys=ON")
    try:
        yield database
        database.commit()
    finally:
        database.close()
        for path in (DATABASE_PATH, Path(f"{DATABASE_PATH}-wal"), Path(f"{DATABASE_PATH}-shm")):
            try:
                if path.exists():
                    path.chmod(0o600)
            except OSError:
                pass


def initialize_database() -> None:
    with connection() as database:
        database.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS models (
                id TEXT PRIMARY KEY,
                relative_path TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                modified_at REAL NOT NULL,
                discovered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS resources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                resource_type TEXT NOT NULL DEFAULT 'website',
                url TEXT NOT NULL DEFAULT '',
                username TEXT NOT NULL DEFAULT '',
                password TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS mcp_servers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'custom',
                description TEXT NOT NULL DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 0,
                transport TEXT NOT NULL,
                endpoint TEXT NOT NULL DEFAULT '',
                command TEXT NOT NULL DEFAULT '',
                arguments TEXT NOT NULL DEFAULT '',
                working_directory TEXT NOT NULL DEFAULT '',
                auth_type TEXT NOT NULL DEFAULT 'none',
                public_config TEXT NOT NULL DEFAULT '{}',
                secret_config TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT 'New conversation',
                archived INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_messages_conversation
                ON messages(conversation_id, id);
            CREATE TABLE IF NOT EXISTS context_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                media_type TEXT NOT NULL DEFAULT 'application/octet-stream',
                size_bytes INTEGER NOT NULL,
                sha256 TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'ready',
                chunk_count INTEGER NOT NULL DEFAULT 0,
                error TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(conversation_id, relative_path)
            );
            CREATE INDEX IF NOT EXISTS idx_context_sources_conversation
                ON context_sources(conversation_id, id);
            CREATE TABLE IF NOT EXISTS context_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL REFERENCES context_sources(id) ON DELETE CASCADE,
                conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_context_chunks_conversation
                ON context_chunks(conversation_id, source_id, chunk_index);
            CREATE TABLE IF NOT EXISTS workspaces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                path TEXT NOT NULL UNIQUE,
                approved INTEGER NOT NULL DEFAULT 1,
                selected INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        try:
            database.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS context_chunks_fts USING fts5(content, source_id UNINDEXED, conversation_id UNINDEXED, tokenize='unicode61')"
            )
        except sqlite3.OperationalError:
            # Minimal SQLite builds may omit FTS5; context search falls back to LIKE.
            pass
        columns = {row["name"] for row in database.execute("PRAGMA table_info(mcp_servers)").fetchall()}
        migrations = {
            "permissions": "TEXT NOT NULL DEFAULT '{\"read\":true,\"write\":false,\"execute\":false,\"network\":false,\"always_confirm\":true}'",
            "connection_status": "TEXT NOT NULL DEFAULT 'not-tested'",
            "last_error": "TEXT NOT NULL DEFAULT ''",
            "capabilities": "TEXT NOT NULL DEFAULT '{}'",
            "last_connected": "TEXT",
        }
        for name, definition in migrations.items():
            if name not in columns:
                database.execute(f"ALTER TABLE mcp_servers ADD COLUMN {name} {definition}")
        database.executescript(
            """
            CREATE TABLE IF NOT EXISTS tool_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id INTEGER REFERENCES mcp_servers(id) ON DELETE SET NULL,
                tool_name TEXT NOT NULL,
                arguments TEXT NOT NULL DEFAULT '{}',
                outcome TEXT NOT NULL,
                detail TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        for key, value in load_defaults().items():
            database.execute(
                "INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)",
                (key, json.dumps(value)),
            )
        for row in database.execute("SELECT id, password FROM resources WHERE password != ''").fetchall():
            vault.set_json(f"resource:{row['id']}", {"password": row["password"]})
            database.execute("UPDATE resources SET password = '' WHERE id = ?", (row["id"],))
        for row in database.execute("SELECT id, secret_config FROM mcp_servers WHERE secret_config != '{}'").fetchall():
            try:
                secrets = json.loads(row["secret_config"])
            except json.JSONDecodeError:
                secrets = {}
            if secrets:
                vault.set_json(f"mcp:{row['id']}", secrets)
            database.execute("UPDATE mcp_servers SET secret_config = '{}' WHERE id = ?", (row["id"],))


def get_settings() -> dict[str, Any]:
    initialize_database()
    with connection() as database:
        rows = database.execute("SELECT key, value FROM settings").fetchall()
    settings = {row["key"]: json.loads(row["value"]) for row in rows}
    settings.update(environment_setting_overrides())
    return settings


def update_settings(values: dict[str, Any]) -> dict[str, Any]:
    with connection() as database:
        for key, value in values.items():
            database.execute(
                """
                INSERT INTO settings(key, value, updated_at)
                VALUES(?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value=excluded.value,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (key, json.dumps(value)),
            )
    return get_settings()


def replace_models(models: list[dict[str, Any]]) -> None:
    with connection() as database:
        database.execute("DELETE FROM models")
        database.executemany(
            """
            INSERT INTO models(id, relative_path, name, size_bytes, modified_at)
            VALUES(:id, :relative_path, :name, :size_bytes, :modified_at)
            """,
            models,
        )


def list_models() -> list[dict[str, Any]]:
    initialize_database()
    with connection() as database:
        rows = database.execute(
            "SELECT id, relative_path, name, size_bytes, modified_at FROM models ORDER BY name"
        ).fetchall()
    return [dict(row) for row in rows]


def list_resources() -> list[dict[str, Any]]:
    initialize_database()
    with connection() as database:
        rows = database.execute(
            """
            SELECT id, name, resource_type, url, username, notes, created_at, updated_at
            FROM resources
            ORDER BY name COLLATE NOCASE, id
            """
        ).fetchall()
    resources = []
    for row in rows:
        item = dict(row)
        item["has_password"] = bool(vault.get_json(f"resource:{item['id']}").get("password"))
        resources.append(item)
    return resources


def create_resource(values: dict[str, Any]) -> dict[str, Any]:
    values = dict(values)
    password = values.pop("password", "")
    values["password"] = ""
    with connection() as database:
        cursor = database.execute(
            """
            INSERT INTO resources(name, resource_type, url, username, password, notes)
            VALUES(:name, :resource_type, :url, :username, :password, :notes)
            """,
            values,
        )
        resource_id = cursor.lastrowid
    if password:
        vault.set_json(f"resource:{resource_id}", {"password": password})
    return next(item for item in list_resources() if item["id"] == resource_id)


def update_resource(resource_id: int, values: dict[str, Any]) -> dict[str, Any]:
    current = next((item for item in list_resources() if item["id"] == resource_id), None)
    if not current:
        raise KeyError(resource_id)
    password = values.pop("password", None)
    allowed = ("name", "resource_type", "url", "username", "notes")
    assignments = [f"{key} = ?" for key in allowed if key in values]
    parameters = [values[key] for key in allowed if key in values]
    if assignments:
        parameters.append(resource_id)
        with connection() as database:
            database.execute(
                f"UPDATE resources SET {', '.join(assignments)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                parameters,
            )
    if password is not None:
        if password:
            vault.set_json(f"resource:{resource_id}", {"password": password})
        else:
            vault.delete(f"resource:{resource_id}")
    return next(item for item in list_resources() if item["id"] == resource_id)


def duplicate_resource(resource_id: int) -> dict[str, Any]:
    current = next((item for item in list_resources() if item["id"] == resource_id), None)
    if not current:
        raise KeyError(resource_id)
    values = {key: current[key] for key in ("name", "resource_type", "url", "username", "notes")}
    values["name"] = f"{values['name']} copy"[:120]
    values["password"] = vault.get_json(f"resource:{resource_id}").get("password", "")
    return create_resource(values)


def delete_resource(resource_id: int) -> bool:
    with connection() as database:
        cursor = database.execute("DELETE FROM resources WHERE id = ?", (resource_id,))
        deleted = cursor.rowcount > 0
    if deleted:
        vault.delete(f"resource:{resource_id}")
    return deleted


def list_mcp_servers() -> list[dict[str, Any]]:
    initialize_database()
    with connection() as database:
        rows = database.execute(
            """
            SELECT id, name, category, description, enabled, transport, endpoint,
                   command, arguments, working_directory, auth_type, public_config,
                   secret_config, permissions, connection_status, last_error,
                   capabilities, last_connected, created_at, updated_at
            FROM mcp_servers
            ORDER BY name COLLATE NOCASE, id
            """
        ).fetchall()
    servers = []
    for row in rows:
        item = dict(row)
        item.pop("secret_config")
        secrets = vault.get_json(f"mcp:{item['id']}")
        item["public_config"] = json.loads(item["public_config"])
        item["permissions"] = json.loads(item["permissions"])
        item["capabilities"] = json.loads(item["capabilities"])
        item["enabled"] = bool(item["enabled"])
        item["has_secrets"] = any(bool(value) for value in secrets.values())
        item["secret_fields"] = sorted(key for key, value in secrets.items() if value)
        servers.append(item)
    return servers


def get_mcp_server(server_id: int, include_secrets: bool = False) -> dict[str, Any]:
    initialize_database()
    with connection() as database:
        row = database.execute("SELECT * FROM mcp_servers WHERE id = ?", (server_id,)).fetchone()
    if not row:
        raise KeyError(server_id)
    item = dict(row)
    item["enabled"] = bool(item["enabled"])
    item["public_config"] = json.loads(item["public_config"])
    item["permissions"] = json.loads(item["permissions"])
    item["capabilities"] = json.loads(item["capabilities"])
    item.pop("secret_config", None)
    if include_secrets:
        item["secrets"] = vault.get_json(f"mcp:{server_id}")
    return item


def create_mcp_server(values: dict[str, Any]) -> dict[str, Any]:
    database_values = {
        **values,
        "enabled": int(bool(values.get("enabled"))),
        "public_config": json.dumps(values.get("public_config", {})),
        "secret_config": "{}",
        "permissions": json.dumps(values.get("permissions", {
            "read": True, "write": False, "execute": False,
            "network": False, "always_confirm": True,
        })),
    }
    database_values.pop("secrets", None)
    with connection() as database:
        cursor = database.execute(
            """
            INSERT INTO mcp_servers(
                name, category, description, enabled, transport, endpoint, command,
                arguments, working_directory, auth_type, public_config, secret_config, permissions
            ) VALUES(
                :name, :category, :description, :enabled, :transport, :endpoint, :command,
                :arguments, :working_directory, :auth_type, :public_config, :secret_config, :permissions
            )
            """,
            database_values,
        )
        server_id = cursor.lastrowid
    secrets = values.get("secrets", {})
    if secrets:
        vault.set_json(f"mcp:{server_id}", secrets)
    return next(item for item in list_mcp_servers() if item["id"] == server_id)


def update_mcp_server(server_id: int, values: dict[str, Any]) -> dict[str, Any]:
    get_mcp_server(server_id)
    allowed = (
        "name", "category", "description", "transport", "endpoint", "command",
        "arguments", "working_directory", "auth_type",
    )
    assignments = [f"{key} = ?" for key in allowed if key in values]
    parameters: list[Any] = [values[key] for key in allowed if key in values]
    if "enabled" in values:
        assignments.append("enabled = ?")
        parameters.append(int(bool(values["enabled"])))
    for key in ("public_config", "permissions"):
        if key in values:
            assignments.append(f"{key} = ?")
            parameters.append(json.dumps(values[key]))
    if assignments:
        assignments.extend(["connection_status = 'not-tested'", "last_error = ''"])
        parameters.append(server_id)
        with connection() as database:
            database.execute(
                f"UPDATE mcp_servers SET {', '.join(assignments)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                parameters,
            )
    if values.get("secrets"):
        saved = vault.get_json(f"mcp:{server_id}")
        saved.update({key: value for key, value in values["secrets"].items() if value})
        vault.set_json(f"mcp:{server_id}", saved)
    return get_mcp_server(server_id)


def duplicate_mcp_server(server_id: int) -> dict[str, Any]:
    current = get_mcp_server(server_id, include_secrets=True)
    values = {key: current[key] for key in (
        "name", "category", "description", "transport", "endpoint", "command",
        "arguments", "working_directory", "auth_type", "public_config", "permissions",
    )}
    values.update({"name": f"{values['name']} copy"[:120], "enabled": False, "secrets": current["secrets"]})
    return create_mcp_server(values)


def set_mcp_server_enabled(server_id: int, enabled: bool) -> bool:
    with connection() as database:
        cursor = database.execute(
            "UPDATE mcp_servers SET enabled = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (int(enabled), server_id),
        )
        return cursor.rowcount > 0


def update_mcp_connection(server_id: int, status: str, capabilities: dict[str, Any] | None = None, error: str = "") -> None:
    with connection() as database:
        database.execute(
            """UPDATE mcp_servers SET connection_status = ?, capabilities = ?, last_error = ?,
               last_connected = CASE WHEN ? = 'connected' THEN CURRENT_TIMESTAMP ELSE last_connected END,
               updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
            (status, json.dumps(capabilities or {}), error[:2000], status, server_id),
        )


def record_tool_audit(server_id: int, tool_name: str, arguments: dict[str, Any], outcome: str, detail: str = "") -> None:
    with connection() as database:
        database.execute(
            "INSERT INTO tool_audit(server_id, tool_name, arguments, outcome, detail) VALUES(?, ?, ?, ?, ?)",
            (server_id, tool_name[:300], json.dumps(arguments), outcome[:80], detail[:2000]),
        )


def list_tool_audit(limit: int = 100) -> list[dict[str, Any]]:
    with connection() as database:
        rows = database.execute(
            """SELECT a.id, a.server_id, COALESCE(s.name, 'Removed server') AS server_name,
               a.tool_name, a.arguments, a.outcome, a.detail, a.created_at
               FROM tool_audit a LEFT JOIN mcp_servers s ON s.id = a.server_id
               ORDER BY a.id DESC LIMIT ?""",
            (max(1, min(limit, 500)),),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["arguments"] = json.loads(item["arguments"])
        result.append(item)
    return result


def clear_tool_audit() -> None:
    with connection() as database:
        database.execute("DELETE FROM tool_audit")


def delete_mcp_server(server_id: int) -> bool:
    with connection() as database:
        cursor = database.execute("DELETE FROM mcp_servers WHERE id = ?", (server_id,))
        deleted = cursor.rowcount > 0
    if deleted:
        vault.delete(f"mcp:{server_id}")
    return deleted


def create_conversation(title: str = "New conversation") -> dict[str, Any]:
    conversation_id = str(uuid.uuid4())
    with connection() as database:
        database.execute(
            "INSERT INTO conversations(id, title) VALUES(?, ?)",
            (conversation_id, title.strip()[:120] or "New conversation"),
        )
    return get_conversation(conversation_id)


def get_conversation(conversation_id: str) -> dict[str, Any]:
    with connection() as database:
        row = database.execute(
            """
            SELECT c.id, c.title, c.archived, c.created_at, c.updated_at,
                   COUNT(m.id) AS message_count
            FROM conversations c LEFT JOIN messages m ON m.conversation_id = c.id
            WHERE c.id = ? GROUP BY c.id
            """,
            (conversation_id,),
        ).fetchone()
    if not row:
        raise KeyError(conversation_id)
    item = dict(row)
    item["archived"] = bool(item["archived"])
    return item


def list_conversations(query: str = "", archived: bool = False) -> list[dict[str, Any]]:
    initialize_database()
    pattern = f"%{query.strip()}%"
    with connection() as database:
        rows = database.execute(
            """
            SELECT c.id, c.title, c.archived, c.created_at, c.updated_at,
                   COUNT(DISTINCT m.id) AS message_count,
                   COALESCE(MAX(CASE WHEN m.role = 'user' THEN substr(m.content, 1, 160) END), '') AS preview
            FROM conversations c LEFT JOIN messages m ON m.conversation_id = c.id
            WHERE c.archived = ? AND (? = '%%' OR c.title LIKE ? OR m.content LIKE ?)
            GROUP BY c.id ORDER BY c.updated_at DESC
            """,
            (int(archived), pattern, pattern, pattern),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["archived"] = bool(item["archived"])
        result.append(item)
    return result


def conversation_messages(conversation_id: str) -> list[dict[str, Any]]:
    get_conversation(conversation_id)
    with connection() as database:
        rows = database.execute(
            "SELECT id, role, content, metadata, created_at FROM messages WHERE conversation_id = ? ORDER BY id",
            (conversation_id,),
        ).fetchall()
    messages = []
    for row in rows:
        item = dict(row)
        item["metadata"] = json.loads(item["metadata"])
        messages.append(item)
    return messages


def add_conversation_message(
    conversation_id: str, role: str, content: str, metadata: dict[str, Any] | None = None
) -> dict[str, Any]:
    get_conversation(conversation_id)
    with connection() as database:
        cursor = database.execute(
            "INSERT INTO messages(conversation_id, role, content, metadata) VALUES(?, ?, ?, ?)",
            (conversation_id, role, content, json.dumps(metadata or {})),
        )
        if role == "user":
            current = database.execute("SELECT title, COUNT(*) AS count FROM conversations JOIN messages ON messages.conversation_id = conversations.id WHERE conversations.id = ?", (conversation_id,)).fetchone()
            if current and current["title"] == "New conversation" and current["count"] == 1:
                title = " ".join(content.strip().split())[:72] or "New conversation"
                database.execute("UPDATE conversations SET title = ? WHERE id = ?", (title, conversation_id))
        database.execute("UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (conversation_id,))
        message_id = cursor.lastrowid
    return next(item for item in conversation_messages(conversation_id) if item["id"] == message_id)


def update_conversation(conversation_id: str, values: dict[str, Any]) -> dict[str, Any]:
    get_conversation(conversation_id)
    assignments = []
    parameters: list[Any] = []
    if "title" in values:
        assignments.append("title = ?")
        parameters.append(str(values["title"]).strip()[:120] or "New conversation")
    if "archived" in values:
        assignments.append("archived = ?")
        parameters.append(int(bool(values["archived"])))
    if assignments:
        parameters.append(conversation_id)
        with connection() as database:
            database.execute(
                f"UPDATE conversations SET {', '.join(assignments)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                parameters,
            )
    return get_conversation(conversation_id)


def delete_conversation(conversation_id: str) -> bool:
    with connection() as database:
        cursor = database.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        return cursor.rowcount > 0


def list_workspaces() -> list[dict[str, Any]]:
    initialize_database()
    with connection() as database:
        rows = database.execute("SELECT * FROM workspaces ORDER BY selected DESC, name COLLATE NOCASE").fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["approved"] = bool(item["approved"])
        item["selected"] = bool(item["selected"])
        result.append(item)
    return result


def create_workspace(name: str, path: str) -> dict[str, Any]:
    with connection() as database:
        cursor = database.execute(
            "INSERT INTO workspaces(name, path, selected) VALUES(?, ?, CASE WHEN NOT EXISTS(SELECT 1 FROM workspaces) THEN 1 ELSE 0 END)",
            (name[:120], path),
        )
        workspace_id = cursor.lastrowid
    return next(item for item in list_workspaces() if item["id"] == workspace_id)


def select_workspace(workspace_id: int) -> dict[str, Any]:
    with connection() as database:
        if not database.execute("SELECT 1 FROM workspaces WHERE id = ?", (workspace_id,)).fetchone():
            raise KeyError(workspace_id)
        database.execute("UPDATE workspaces SET selected = 0")
        database.execute("UPDATE workspaces SET selected = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (workspace_id,))
    return next(item for item in list_workspaces() if item["id"] == workspace_id)


def delete_workspace(workspace_id: int) -> bool:
    with connection() as database:
        cursor = database.execute("DELETE FROM workspaces WHERE id = ?", (workspace_id,))
        deleted = cursor.rowcount > 0
        if deleted and not database.execute("SELECT 1 FROM workspaces WHERE selected = 1").fetchone():
            first = database.execute("SELECT id FROM workspaces ORDER BY id LIMIT 1").fetchone()
            if first:
                database.execute("UPDATE workspaces SET selected = 1 WHERE id = ?", (first["id"],))
    return deleted
