import os
import tempfile
import sqlite3
import base64
import threading
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

TEST_ROOT = Path(tempfile.mkdtemp(prefix="local-ai-tests-"))
os.environ["LOCAL_AI_DATA_DIR"] = str(TEST_ROOT / "data")
os.environ["LOCAL_AI_MODELS_DIR"] = str(TEST_ROOT / "models")
os.environ["LOCAL_AI_DATABASE"] = str(TEST_ROOT / "data" / "test.db")

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.database import get_settings


def test_health_scan_select_and_settings() -> None:
    models = TEST_ROOT / "models"
    models.mkdir(parents=True, exist_ok=True)
    (models / "tiny-test.gguf").write_bytes(b"GGUF-test")
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        scanned = client.post("/api/models/scan")
        assert scanned.status_code == 200
        assert scanned.json()["count"] == 1
        selected = client.post("/api/models/select", json={"relative_path": "tiny-test.gguf"})
        assert selected.status_code == 200
        changed = client.patch("/api/settings", json={"context_size": 4096, "parallel": 2})
        assert changed.status_code == 200
        assert changed.json()["context_size"] == 4096
        assert changed.json()["parallel"] == 2
        assert changed.json()["auto_tune"] is False

        config = client.get("/api/config")
        assert config.status_code == 200
        assert config.json()["automatic"] is False
        assert config.json()["app_url"] == "http://127.0.0.1:8181"
        assert config.json()["configured_model_url"] == "http://127.0.0.1:8180"
        assert config.json()["model_url"].startswith("http://127.0.0.1:")
        assert Path(config.json()["models_directory"]).resolve() == (TEST_ROOT / "models").resolve()
        assert Path(config.json()["workspaces_root"]).is_absolute()

        profile = client.get("/api/system/profile")
        assert profile.status_code == 200
        assert profile.json()["cpu"]["logical_cores"] >= 1
        assert profile.json()["recommended"]["parallel"] == 1


def test_invalid_model_path_is_rejected() -> None:
    with TestClient(app) as client:
        response = client.post("/api/models/select", json={"relative_path": "../secret.gguf"})
        assert response.status_code == 400


def test_environment_override_wins_after_database_initialization() -> None:
    get_settings()
    with patch.dict(os.environ, {"LOCAL_AI_MODEL_PORT": "9191"}):
        assert get_settings()["model_port"] == 9191


def test_local_resources_mask_passwords_and_can_be_removed() -> None:
    with TestClient(app) as client:
        created = client.post("/api/resources", json={
            "name": "Expedia",
            "resource_type": "website",
            "url": "https://www.expedia.com/",
            "username": "traveler@example.com",
            "password": "local-secret",
            "notes": "Travel planning account",
        })
        assert created.status_code == 201
        resource = created.json()
        assert resource["has_password"] == 1
        assert "password" not in resource

        listed = client.get("/api/resources")
        assert listed.status_code == 200
        assert all("password" not in item for item in listed.json()["resources"])

        deleted = client.delete(f"/api/resources/{resource['id']}")
        assert deleted.status_code == 200


def test_mcp_server_secrets_are_masked_and_state_can_change() -> None:
    with TestClient(app) as client:
        created = client.post("/api/mcp-servers", json={
            "name": "Private GitHub MCP",
            "category": "Developer tools",
            "transport": "streamable-http",
            "endpoint": "https://mcp.example.test/mcp",
            "auth_type": "bearer",
            "public_config": {"scope": "repo"},
            "secrets": {"access_token": "never-return-this"},
        })
        assert created.status_code == 201
        server = created.json()
        assert server["has_secrets"] is True
        assert server["secret_fields"] == ["access_token"]
        assert "never-return-this" not in created.text

        enabled = client.patch(f"/api/mcp-servers/{server['id']}", json={"enabled": True})
        assert enabled.status_code == 200
        assert enabled.json()["enabled"] is True
        assert "never-return-this" not in enabled.text

        listed = client.get("/api/mcp-servers")
        assert "never-return-this" not in listed.text
        assert client.delete(f"/api/mcp-servers/{server['id']}").status_code == 200


def test_multiple_accounts_for_the_same_mcp_provider_are_independent() -> None:
    with TestClient(app) as client:
        personal = client.post("/api/mcp-servers", json={
            "name": "Gmail", "provider_id": "gmail", "account_label": "Personal",
            "category": "Productivity", "transport": "streamable-http",
            "endpoint": "https://mcp.example.test/gmail", "auth_type": "bearer",
            "secrets": {"access_token": "personal-secret"},
        })
        work = client.post("/api/mcp-servers", json={
            "name": "Gmail", "provider_id": "gmail", "account_label": "Work",
            "category": "Productivity", "transport": "streamable-http",
            "endpoint": "https://mcp.example.test/gmail", "auth_type": "bearer",
            "secrets": {"access_token": "work-secret"},
        })
        assert personal.status_code == 201 and work.status_code == 201
        assert personal.json()["id"] != work.json()["id"]
        accounts = [item for item in client.get("/api/mcp-servers").json()["servers"] if item["provider_id"] == "gmail"]
        assert {item["account_label"] for item in accounts} >= {"Personal", "Work"}
        assert "personal-secret" not in client.get("/api/mcp-servers").text
        assert "work-secret" not in client.get("/api/mcp-servers").text

        assert client.delete(f"/api/mcp-servers/{personal.json()['id']}/credentials").status_code == 200
        remaining = next(item for item in client.get("/api/mcp-servers").json()["servers"] if item["id"] == work.json()["id"])
        assert remaining["has_secrets"] is True
        client.delete(f"/api/mcp-servers/{personal.json()['id']}")
        client.delete(f"/api/mcp-servers/{work.json()['id']}")


def test_conversations_persist_search_archive_and_export() -> None:
    with TestClient(app) as client:
        created = client.post("/api/conversations", json={"title": "Trip research"})
        assert created.status_code == 201
        conversation_id = created.json()["id"]
        from backend.app.database import add_conversation_message
        add_conversation_message(conversation_id, "user", "Find a quiet hotel")
        add_conversation_message(conversation_id, "assistant", "I can help compare options.")
        loaded = client.get(f"/api/conversations/{conversation_id}").json()
        assert [message["role"] for message in loaded["messages"]] == ["user", "assistant"]
        assert client.get("/api/conversations?query=quiet").json()["conversations"][0]["id"] == conversation_id
        assert client.patch(f"/api/conversations/{conversation_id}", json={"archived": True}).json()["archived"] is True
        exported = client.get("/api/export").json()
        assert exported["secrets_included"] is False
        assert any(item["id"] == conversation_id for item in exported["conversations"])
        assert client.delete(f"/api/conversations/{conversation_id}").status_code == 200


def test_files_and_folders_are_indexed_retrieved_and_removed() -> None:
    from backend.app.main import ChatRequest, prepare_chat
    with TestClient(app) as client:
        conversation_id = client.post("/api/conversations", json={}).json()["id"]
        response = client.post(
            f"/api/conversations/{conversation_id}/context",
            files=[
                ("files", ("architecture.md", b"The payment gateway uses a circuit breaker named CedarSwitch.", "text/markdown")),
                ("files", ("noise.js", b"generated noise", "text/javascript")),
            ],
            data={"relative_paths": '["docs/architecture.md","node_modules/noise.js"]'},
        )
        assert response.status_code == 201
        assert response.json()["count"] == 1
        assert response.json()["skipped"][0]["reason"] == "Generated or vendor folder"
        sources = client.get(f"/api/conversations/{conversation_id}/context").json()["sources"]
        assert sources[0]["relative_path"] == "docs/architecture.md"
        with patch("backend.app.main.manager.status", return_value={"healthy": True, "endpoint": "http://127.0.0.1:8080"}), \
             patch("backend.app.main.list_resources", return_value=[]), \
             patch("backend.app.main.list_mcp_servers", return_value=[]):
            _, payload = prepare_chat(ChatRequest(
                conversation_id=conversation_id,
                messages=[{"role": "user", "content": "Which circuit breaker handles payments?"}],
            ))
        assert any("CedarSwitch" in message["content"] for message in payload["messages"])
        assert client.delete(f"/api/conversations/{conversation_id}/context/{sources[0]['id']}").status_code == 200
        assert client.get(f"/api/conversations/{conversation_id}/context").json()["sources"] == []
        client.delete(f"/api/conversations/{conversation_id}")


def test_indexing_does_not_block_other_api_requests() -> None:
    entered = threading.Event()
    release = threading.Event()

    def slow_index(*_args, **_kwargs):
        entered.set()
        assert release.wait(timeout=3)
        return {"indexed": [], "skipped": [], "count": 0, "total_bytes": 4}

    with TestClient(app) as client, patch("backend.app.main.ingest_streams", side_effect=slow_index):
        conversation_id = client.post("/api/conversations", json={}).json()["id"]
        result: dict = {}

        def upload() -> None:
            result["response"] = client.post(
                f"/api/conversations/{conversation_id}/context",
                files=[("files", ("large.txt", b"work", "text/plain"))],
                data={"relative_paths": '["large.txt"]'},
            )

        worker = threading.Thread(target=upload, daemon=True)
        worker.start()
        assert entered.wait(timeout=2)
        started = time.perf_counter()
        response = client.get("/api/context/capabilities")
        elapsed = time.perf_counter() - started
        release.set()
        worker.join(timeout=3)

        assert response.status_code == 200
        assert elapsed < 0.75
        assert result["response"].status_code == 201


def test_app_health_does_not_wait_for_model_discovery() -> None:
    with TestClient(app) as client:
        with patch("backend.app.main.manager.status", side_effect=AssertionError("slow model discovery")):
            started = time.perf_counter()
            response = client.get("/api/health")
            elapsed = time.perf_counter() - started
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert elapsed < 0.25


def test_credentials_are_not_plaintext_in_sqlite_or_export() -> None:
    with TestClient(app) as client:
        secret = "plain-text-must-not-be-in-database"
        resource = client.post("/api/resources", json={
            "name": "Vault check", "resource_type": "website", "password": secret,
        }).json()
        database_bytes = (TEST_ROOT / "data" / "test.db").read_bytes()
        assert secret.encode() not in database_bytes
        assert secret not in client.get("/api/export").text
        client.delete(f"/api/resources/{resource['id']}")


def test_mcp_tool_call_requires_explicit_approval_and_execute_permission() -> None:
    with TestClient(app) as client:
        server = client.post("/api/mcp-servers", json={
            "name": "Approval check", "transport": "streamable-http",
            "endpoint": "https://mcp.example.test/mcp", "enabled": True,
            "permissions": {"read": True, "write": False, "execute": False, "network": False, "always_confirm": True},
        }).json()
        response = client.post(f"/api/mcp-servers/{server['id']}/call", json={
            "tool_name": "read_file", "arguments": {"path": "README.md"},
        })
        assert response.status_code == 409
        denied = client.post(f"/api/mcp-servers/{server['id']}/call", json={
            "tool_name": "read_file", "arguments": {}, "approved": True,
        })
        assert denied.status_code == 403
        client.delete(f"/api/mcp-servers/{server['id']}")


def test_mcp_connection_test_records_discovered_capabilities() -> None:
    with TestClient(app) as client:
        server = client.post("/api/mcp-servers", json={
            "name": "Discovery check", "transport": "streamable-http",
            "endpoint": "https://mcp.example.test/mcp",
        }).json()
        capabilities = {"tools": [{"name": "search"}], "resources": [], "prompts": []}
        with patch("backend.app.main.discover_mcp", AsyncMock(return_value=capabilities)):
            tested = client.post(f"/api/mcp-servers/{server['id']}/test")
        assert tested.status_code == 200
        refreshed = client.get("/api/mcp-servers").json()["servers"]
        current = next(item for item in refreshed if item["id"] == server["id"])
        assert current["connection_status"] == "connected"
        assert current["capabilities"]["tools"][0]["name"] == "search"
        client.delete(f"/api/mcp-servers/{server['id']}")


def test_enabled_mcp_tools_are_offered_to_local_model_with_safe_mapping() -> None:
    from backend.app.main import ChatRequest, prepare_chat
    request = ChatRequest(messages=[{"role": "user", "content": "Search my files"}])
    server = {
        "id": 7, "name": "Local files", "enabled": True,
        "permissions": {"execute": True, "always_confirm": True},
        "capabilities": {"tools": [{
            "name": "search/files", "description": "Search approved files",
            "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}},
        }]},
    }
    with patch("backend.app.main.manager.status", return_value={"healthy": True, "endpoint": "http://127.0.0.1:8080"}), \
         patch("backend.app.main.list_resources", return_value=[]), \
         patch("backend.app.main.list_mcp_servers", return_value=[server]):
        _, payload = prepare_chat(request)
    assert payload["tools"][0]["function"]["name"] == "mcp_7_search_files"
    assert payload["_mcp_tool_map"]["mcp_7_search_files"]["tool_name"] == "search/files"


def test_resources_can_be_edited_and_duplicated_without_erasing_saved_password() -> None:
    with TestClient(app) as client:
        created = client.post("/api/resources", json={"name": "Editable", "password": "kept-secret"}).json()
        updated = client.patch(f"/api/resources/{created['id']}", json={"name": "Edited", "notes": "Updated"})
        assert updated.status_code == 200
        assert updated.json()["name"] == "Edited"
        assert updated.json()["has_password"] is True
        copied = client.post(f"/api/resources/{created['id']}/duplicate")
        assert copied.status_code == 201
        assert copied.json()["has_password"] is True
        client.delete(f"/api/resources/{created['id']}")
        client.delete(f"/api/resources/{copied.json()['id']}")


def test_mcp_edit_duplicate_revoke_audit_and_native_tool_message() -> None:
    with TestClient(app) as client:
        conversation = client.post("/api/conversations", json={}).json()
        server = client.post("/api/mcp-servers", json={
            "name": "Editable MCP", "transport": "streamable-http", "endpoint": "https://mcp.example.test/mcp",
            "enabled": True, "auth_type": "bearer", "secrets": {"access_token": "secret"},
            "permissions": {"read": True, "write": False, "execute": True, "network": True, "always_confirm": True},
        }).json()
        assert client.patch(f"/api/mcp-servers/{server['id']}", json={"description": "Edited"}).json()["description"] == "Edited"
        copied = client.post(f"/api/mcp-servers/{server['id']}/duplicate").json()
        assert copied["enabled"] is False
        with patch("backend.app.main.call_mcp", AsyncMock(return_value={"content": "done"})):
            called = client.post(f"/api/mcp-servers/{server['id']}/call", json={"tool_name": "search", "arguments": {"q": "x"}, "approved": True, "conversation_id": conversation["id"]})
        assert called.status_code == 200
        assert client.get(f"/api/conversations/{conversation['id']}").json()["messages"][0]["role"] == "tool"
        assert client.get("/api/mcp-audit").json()["events"][0]["outcome"] == "completed"
        assert client.delete(f"/api/mcp-servers/{server['id']}/credentials").json()["revoked"] is True
        refreshed = next(item for item in client.get("/api/mcp-servers").json()["servers"] if item["id"] == server["id"])
        assert refreshed["has_secrets"] is False and refreshed["enabled"] is False
        client.delete(f"/api/mcp-servers/{server['id']}")
        client.delete(f"/api/mcp-servers/{copied['id']}")
        client.delete(f"/api/conversations/{conversation['id']}")


def test_workspace_provider_metrics_and_encrypted_backup() -> None:
    project_root = Path.home() / "projects"
    project_root.mkdir(exist_ok=True)
    workspace_path = Path(tempfile.mkdtemp(prefix="local-ai-workspace-", dir=project_root))
    try:
        with TestClient(app) as client:
            workspace = client.post("/api/workspaces", json={"name": "Test workspace", "path": str(workspace_path)})
            assert workspace.status_code == 201
            assert workspace.json()["approved"] is True
            assert len(client.get("/api/mcp/providers").json()["providers"]) >= 4
            metrics = client.get("/api/runtime/metrics").json()
            assert "balanced" in metrics["presets"]
            assert client.post("/api/runtime/presets/low-memory").status_code == 200

            passwordless_backup = client.post("/api/backup", json={"passphrase": ""})
            assert passwordless_backup.status_code == 200
            assert passwordless_backup.content.startswith(b"PLAIBAK1")
            backup = client.post("/api/backup", json={"passphrase": "correct horse battery staple"})
            assert backup.status_code == 200
            assert backup.content.startswith(b"PLAIBAK1")
            assert b"correct horse" not in backup.content
            from backend.app.services.backup_manager import decrypt
            decoded = decrypt(backup.content, "correct horse battery staple")
            assert decoded["format"] == 1
            assert any(item["path"] == str(workspace_path) for item in decoded["workspaces"])
            client.post("/api/resources", json={"name": "Remove during restore"})
            restored = client.post("/api/restore", json={
                "passphrase": "correct horse battery staple",
                "backup_base64": base64.b64encode(backup.content).decode(),
                "confirmation": "RESTORE",
            })
            assert restored.status_code == 200
            assert all(item["name"] != "Remove during restore" for item in client.get("/api/resources").json()["resources"])
            client.delete(f"/api/workspaces/{workspace.json()['id']}")
    finally:
        workspace_path.rmdir()
