from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from ..config import DATA_DIR, ensure_directories

SERVICE_NAME = "local-ai"


class CredentialVault:
    """OS keyring with an encrypted, owner-only local fallback for headless WSL."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._key_path = DATA_DIR / "credential-vault.key"
        self._vault_path = DATA_DIR / "credential-vault.enc"
        self._keyring = None
        self._backend_name = "encrypted-local-vault"
        try:
            import keyring

            backend = keyring.get_keyring()
            backend_name = f"{backend.__class__.__module__}.{backend.__class__.__name__}"
            if float(getattr(backend, "priority", 0)) > 0 and not any(
                token in backend_name.casefold() for token in ("fail", "null", "plaintext")
            ):
                self._keyring = keyring
                self._backend_name = backend_name
        except Exception:
            self._keyring = None

    @property
    def backend_name(self) -> str:
        return self._backend_name

    @property
    def uses_os_keyring(self) -> bool:
        return self._keyring is not None

    def _fernet(self) -> Fernet:
        ensure_directories()
        if not self._key_path.exists():
            descriptor = os.open(self._key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(Fernet.generate_key())
        try:
            self._key_path.chmod(0o600)
        except OSError:
            pass
        return Fernet(self._key_path.read_bytes().strip())

    def _read_fallback(self) -> dict[str, str]:
        if not self._vault_path.exists():
            return {}
        try:
            decrypted = self._fernet().decrypt(self._vault_path.read_bytes())
            data = json.loads(decrypted)
            return data if isinstance(data, dict) else {}
        except (InvalidToken, OSError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("The local credential vault could not be opened") from exc

    def _write_fallback(self, values: dict[str, str]) -> None:
        ensure_directories()
        payload = self._fernet().encrypt(json.dumps(values, sort_keys=True).encode())
        temporary = self._vault_path.with_suffix(".tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(self._vault_path)
        try:
            self._vault_path.chmod(0o600)
        except OSError:
            pass

    def set(self, reference: str, value: str) -> None:
        with self._lock:
            if self._keyring:
                self._keyring.set_password(SERVICE_NAME, reference, value)
                return
            values = self._read_fallback()
            values[reference] = value
            self._write_fallback(values)

    def get(self, reference: str) -> str | None:
        with self._lock:
            if self._keyring:
                return self._keyring.get_password(SERVICE_NAME, reference)
            return self._read_fallback().get(reference)

    def delete(self, reference: str) -> None:
        with self._lock:
            if self._keyring:
                try:
                    self._keyring.delete_password(SERVICE_NAME, reference)
                except Exception:
                    pass
                return
            values = self._read_fallback()
            if reference in values:
                del values[reference]
                self._write_fallback(values)

    def set_json(self, reference: str, value: dict) -> None:
        self.set(reference, json.dumps(value, sort_keys=True))

    def get_json(self, reference: str) -> dict:
        value = self.get(reference)
        if not value:
            return {}
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}


vault = CredentialVault()
