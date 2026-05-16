"""
extension_server.py
───────────────────
Local TCP server handling requests from the browser extension via
native_host.py.  Listens on localhost only.

Security model
──────────────
A 32-byte random shared secret is generated on first launch and written to
``~/.khazna/extension_secret`` (mode 0o600).  Every request that
touches credentials must include ``{"token": "<hex_secret>"}``.  Requests
that fail authentication are rejected with ``{"error": "unauthorized"}``.

The ``status`` command is intentionally unauthenticated so the extension
can detect whether the app is running without possessing the secret.

The native host reads the same secret file so it can attach the token.
"""

from __future__ import annotations

import hmac
import json
import logging
import secrets
from pathlib import Path

from PySide6.QtCore import QObject, Slot
from PySide6.QtNetwork import QHostAddress, QTcpServer

_log = logging.getLogger("khazna.ext_server")

PORT             = 27584
_SECRET_FILENAME = "extension_secret"
_SECRET_BYTES    = 32   # 256-bit


# ──────────────────────────────────────────────
# Secret management
# ──────────────────────────────────────────────

def _load_or_create_secret(vault_dir: str) -> bytes:
    """
    Return the persisted shared secret, creating it if necessary.
    File permissions are set to 0o600 (owner read/write only).
    Falls back to an ephemeral secret on I/O failure so the server still
    starts, but logs a warning.
    """
    path = Path(vault_dir) / _SECRET_FILENAME
    try:
        if path.exists():
            raw = path.read_bytes()
            if len(raw) == _SECRET_BYTES:
                return raw
            _log.warning("extension_secret has wrong length; regenerating.")
        raw = secrets.token_bytes(_SECRET_BYTES)
        path.write_bytes(raw)
        try:
            path.chmod(0o600)
        except OSError:
            pass   # Windows – no chmod needed
        _log.info("New extension shared secret written to %s", path)
        return raw
    except OSError as exc:
        _log.error("Cannot read/write extension secret (%s); using ephemeral key.", exc)
        return secrets.token_bytes(_SECRET_BYTES)


# ──────────────────────────────────────────────
# Server
# ──────────────────────────────────────────────

class ExtensionServer(QObject):

    def __init__(self, vault_manager, parent=None) -> None:
        super().__init__(parent)
        self._vault  = vault_manager
        self._server = QTcpServer(self)
        self._server.newConnection.connect(self._handle_new_connection)

        vault_dir    = str(Path(vault_manager._storage.db_path).parent)
        self._secret = _load_or_create_secret(vault_dir)

    # ── Public helpers ────────────────────────

    def start(self) -> None:
        """Start listening on 127.0.0.1."""
        if not self._server.listen(QHostAddress.LocalHost, PORT):
            _log.error("Extension server failed to start: %s",
                       self._server.errorString())
        else:
            _log.info("Extension server listening on port %d", PORT)

    def secret_hex(self) -> str:
        """Hex representation of the secret (for native host provisioning)."""
        return self._secret.hex()

    # ── Connection handling ───────────────────

    @Slot()
    def _handle_new_connection(self) -> None:
        client = self._server.nextPendingConnection()
        client.readyRead.connect(lambda: self._handle_ready_read(client))
        client.disconnected.connect(client.deleteLater)

    def _handle_ready_read(self, client) -> None:
        try:
            raw = client.readAll().data().decode("utf-8")
            if not raw:
                return
            request  = json.loads(raw)
            response = self._process_request(request)
            client.write(json.dumps(response).encode("utf-8"))
            client.flush()
            client.disconnectFromHost()
        except json.JSONDecodeError:
            _log.warning("Extension server: invalid JSON received")
            client.write(json.dumps({"error": "invalid_json"}).encode("utf-8"))
            client.disconnectFromHost()
        except Exception:
            _log.exception("Extension server: unexpected error")
            client.write(json.dumps({"error": "server_error"}).encode("utf-8"))
            client.disconnectFromHost()

    # ── Authentication ────────────────────────

    def _authenticate(self, req: dict) -> bool:
        """
        Validate the request token using constant-time comparison.
        Returns True only when the provided hex token matches the secret.
        """
        token_hex = req.get("token", "")
        if not token_hex or not isinstance(token_hex, str):
            return False
        try:
            provided = bytes.fromhex(token_hex)
        except ValueError:
            return False
        return hmac.compare_digest(provided, self._secret)

    # ── Dispatch ─────────────────────────────

    def _process_request(self, req: dict) -> dict:
        command = req.get("command")

        # ── Unauthenticated ───────────────────
        # "status" intentionally requires no token so the extension can
        # detect the app without storing the secret.
        if command == "status":
            return {
                "status":         "ok",
                "is_locked":      self._vault.is_locked,
                "is_initialized": self._vault.is_initialized,
            }

        # ── All credential commands need a valid token ─────────────────
        if not self._authenticate(req):
            _log.warning("Extension request rejected: bad or missing token "
                         "(command=%r)", command)
            return {"error": "unauthorized"}

        if command == "get_logins":
            if self._vault.is_locked:
                return {"error": "locked"}
            url = req.get("url", "")
            if not url:
                return {"error": "missing_url"}
            entries = self._vault.search_entries(url)
            logins  = [
                {
                    "id":        e.id,
                    "username":  e.username,
                    "password":  e.password,
                    "site_name": e.site_name,
                }
                for e in entries
                if e.url and url.lower() in e.url.lower()
            ]
            return {"status": "ok", "logins": logins}

        return {"error": "unknown_command"}
