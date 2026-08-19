from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .. import __version__
from ..services.credential_vault import vault

MAGIC = b"PLAIBAK1"


def _key(passphrase: str, salt: bytes) -> bytes:
    if len(passphrase) < 10:
        raise ValueError("Backup passphrase must contain at least 10 characters")
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=600_000).derive(passphrase.encode())


def collect() -> dict[str, Any]:
    from ..database import connection, conversation_messages, list_conversations, list_mcp_servers, list_resources, list_workspaces
    with connection() as database:
        settings = {row["key"]: json.loads(row["value"]) for row in database.execute("SELECT key, value FROM settings")}
    resources = []
    for item in list_resources():
        resources.append({**item, "password": vault.get_json(f"resource:{item['id']}").get("password", "")})
    servers = []
    for item in list_mcp_servers():
        servers.append({**item, "secrets": vault.get_json(f"mcp:{item['id']}")})
    conversations = list_conversations(archived=False) + list_conversations(archived=True)
    return {
        "format": 1, "app_version": __version__,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "settings": settings, "resources": resources, "mcp_servers": servers,
        "workspaces": list_workspaces(),
        "conversations": [{**item, "messages": conversation_messages(item["id"])} for item in conversations],
    }


def encrypt(passphrase: str) -> bytes:
    salt, nonce = os.urandom(16), os.urandom(12)
    plaintext = json.dumps(collect(), ensure_ascii=False, separators=(",", ":")).encode()
    ciphertext = AESGCM(_key(passphrase, salt)).encrypt(nonce, plaintext, MAGIC)
    return MAGIC + salt + nonce + ciphertext


def decrypt(payload: bytes, passphrase: str) -> dict[str, Any]:
    if not payload.startswith(MAGIC) or len(payload) < 52:
        raise ValueError("This is not a Local AI backup")
    salt, nonce, ciphertext = payload[8:24], payload[24:36], payload[36:]
    try:
        plaintext = AESGCM(_key(passphrase, salt)).decrypt(nonce, ciphertext, MAGIC)
        data = json.loads(plaintext)
    except Exception as exc:
        raise ValueError("Backup passphrase is incorrect or the file is damaged") from exc
    if data.get("format") != 1:
        raise ValueError("Unsupported backup format")
    return data


def restore(payload: bytes, passphrase: str) -> dict[str, int]:
    from ..database import connection, initialize_database
    from ..config import CONTEXT_DIR
    data = decrypt(payload, passphrase)
    initialize_database()
    with connection() as database:
        old_resources = [row["id"] for row in database.execute("SELECT id FROM resources")]
        old_servers = [row["id"] for row in database.execute("SELECT id FROM mcp_servers")]
        if database.execute("SELECT 1 FROM sqlite_master WHERE name = 'context_chunks_fts'").fetchone():
            database.execute("DELETE FROM context_chunks_fts")
        database.executescript("DELETE FROM context_chunks; DELETE FROM context_sources; DELETE FROM messages; DELETE FROM conversations; DELETE FROM tool_audit; DELETE FROM resources; DELETE FROM mcp_servers; DELETE FROM workspaces; DELETE FROM settings;")
        for key, value in data.get("settings", {}).items():
            database.execute("INSERT INTO settings(key, value) VALUES(?, ?)", (key, json.dumps(value)))
        for item in data.get("resources", []):
            database.execute(
                "INSERT INTO resources(id,name,resource_type,url,username,password,notes) VALUES(?,?,?,?,?,'',?)",
                (item["id"], item["name"], item["resource_type"], item.get("url", ""), item.get("username", ""), item.get("notes", "")),
            )
        for item in data.get("mcp_servers", []):
            database.execute(
                """INSERT INTO mcp_servers(id,name,category,description,enabled,transport,endpoint,command,arguments,working_directory,auth_type,public_config,secret_config,permissions,connection_status,last_error,capabilities,last_connected)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (item["id"], item["name"], item.get("category", "custom"), item.get("description", ""), int(item.get("enabled", False)), item["transport"], item.get("endpoint", ""), item.get("command", ""), item.get("arguments", ""), item.get("working_directory", ""), item.get("auth_type", "none"), json.dumps(item.get("public_config", {})), "{}", json.dumps(item.get("permissions", {})), "not-tested", "", "{}", None),
            )
        for item in data.get("workspaces", []):
            database.execute("INSERT INTO workspaces(id,name,path,approved,selected) VALUES(?,?,?,?,?)", (item["id"], item["name"], item["path"], int(item.get("approved", True)), int(item.get("selected", False))))
        for item in data.get("conversations", []):
            database.execute("INSERT INTO conversations(id,title,archived) VALUES(?,?,?)", (item["id"], item["title"], int(item.get("archived", False))))
            for message in item.get("messages", []):
                database.execute("INSERT INTO messages(conversation_id,role,content,metadata,created_at) VALUES(?,?,?,?,?)", (item["id"], message["role"], message["content"], json.dumps(message.get("metadata", {})), message.get("created_at") or datetime.now(timezone.utc).isoformat()))
    for resource_id in old_resources:
        vault.delete(f"resource:{resource_id}")
    for server_id in old_servers:
        vault.delete(f"mcp:{server_id}")
    if CONTEXT_DIR.is_dir():
        shutil.rmtree(CONTEXT_DIR)
        CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
        try:
            CONTEXT_DIR.chmod(0o700)
        except OSError:
            pass
    for item in data.get("resources", []):
        if item.get("password"):
            vault.set_json(f"resource:{item['id']}", {"password": item["password"]})
    for item in data.get("mcp_servers", []):
        if item.get("secrets"):
            vault.set_json(f"mcp:{item['id']}", item["secrets"])
    return {key: len(data.get(key, [])) for key in ("resources", "mcp_servers", "workspaces", "conversations")}
