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

def _load_or_create_secret() -> bytes:
    """
    Return the persisted shared secret, creating it if necessary.
    File permissions are set to 0o600 (owner read/write only).
    Falls back to an ephemeral secret on I/O failure so the server still
    starts, but logs a warning.
    """
    dir_path = Path.home() / ".khazna"
    dir_path.mkdir(parents=True, exist_ok=True)
    path = dir_path / _SECRET_FILENAME
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
        self._secret = _load_or_create_secret()

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

    def __init_buffers(self) -> None:
        """Lazily initialised per-connection receive buffers."""
        if not hasattr(self, "_buffers"):
            self._buffers: dict[int, bytearray] = {}

    @Slot()
    def _handle_new_connection(self) -> None:
        self.__init_buffers()
        client = self._server.nextPendingConnection()
        fd = client.socketDescriptor()
        self._buffers[fd] = bytearray()

        client.readyRead.connect(lambda: self._on_data(client, fd))
        client.disconnected.connect(lambda: self._on_disconnect(client, fd))

    def _on_data(self, client, fd: int) -> None:
        """Accumulate data; attempt to process as soon as a full JSON object arrives."""
        chunk = client.readAll().data()
        if not chunk:
            return
        self._buffers.setdefault(fd, bytearray()).extend(chunk)
        buf = self._buffers[fd]

        # ── HTTP detection (for browser fetch() fallback) ─────
        if buf[:4] in (b"POST", b"OPTI", b"GET "):
            if b"\r\n\r\n" not in buf:
                return  # headers incomplete — wait for more
            
            header_end = buf.index(b"\r\n\r\n")
            header_section = buf[:header_end].decode("utf-8", errors="replace")
            content_length = 0
            for line in header_section.split("\r\n"):
                if line.lower().startswith("content-length:"):
                    try:
                        content_length = int(line.split(":")[1].strip())
                    except ValueError:
                        pass
                    break
            
            if len(buf) < header_end + 4 + content_length:
                return  # body incomplete — wait for more

            self._buffers.pop(fd, None)
            self._handle_http(client, buf)
            return

        # ── Raw JSON path (native messaging / direct TCP) ─────
        try:
            raw = buf.decode("utf-8")
            request = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Incomplete data — wait for more or for disconnect
            return

        # Full request received — process it
        self._buffers.pop(fd, None)
        self._respond(client, request)

    def _on_disconnect(self, client, fd: int) -> None:
        """If the client disconnects before we parsed, try to process whatever we got."""
        buf = self._buffers.pop(fd, None)
        if buf:
            try:
                request = json.loads(buf.decode("utf-8"))
                self._respond(client, request)
            except (json.JSONDecodeError, UnicodeDecodeError):
                _log.warning("Extension server: invalid JSON received")
                try:
                    client.write(json.dumps({"error": "invalid_json"}).encode("utf-8"))
                    client.flush()
                except Exception:
                    pass
            except Exception:
                _log.exception("Extension server: unexpected error on disconnect")
        client.deleteLater()

    def _respond(self, client, request: dict) -> None:
        """Process a complete request and write the JSON response."""
        try:
            response = self._process_request(request)
            client.write(json.dumps(response).encode("utf-8"))
            client.flush()
            client.disconnectFromHost()
        except Exception:
            _log.exception("Extension server: unexpected error")
            try:
                client.write(json.dumps({"error": "server_error"}).encode("utf-8"))
                client.flush()
                client.disconnectFromHost()
            except Exception:
                pass

    # ── HTTP handler (browser fetch fallback) ─────

    _CORS_HEADERS = (
        "Access-Control-Allow-Origin: *\r\n"
        "Access-Control-Allow-Methods: POST, OPTIONS\r\n"
        "Access-Control-Allow-Headers: Content-Type\r\n"
    )

    def _handle_http(self, client, buf: bytes) -> None:
        """Handle an HTTP request on the same TCP port (for browser fetch fallback)."""
        try:
            header_end = buf.index(b"\r\n\r\n")
            header_section = buf[:header_end].decode("utf-8", errors="replace")
            body = buf[header_end + 4:]
            first_line = header_section.split("\r\n")[0]

            # CORS preflight
            if first_line.startswith("OPTIONS"):
                resp = (
                    "HTTP/1.1 204 No Content\r\n"
                    + self._CORS_HEADERS
                    + "Content-Length: 0\r\n\r\n"
                )
                client.write(resp.encode("utf-8"))
                client.flush()
                client.disconnectFromHost()
                return

            # POST — extract JSON body and process
            if first_line.startswith("POST"):
                try:
                    request = json.loads(body.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    self._http_respond(client, 400, {"error": "invalid_json"})
                    return
                result = self._process_request(request)
                self._http_respond(client, 200, result)
                return

            # Anything else
            self._http_respond(client, 405, {"error": "method_not_allowed"})

        except Exception:
            _log.exception("Extension server: HTTP handler error")
            self._http_respond(client, 500, {"error": "server_error"})

    def _http_respond(self, client, status: int, body: dict) -> None:
        """Write an HTTP response with JSON body and CORS headers."""
        phrases = {200: "OK", 204: "No Content", 400: "Bad Request",
                   405: "Method Not Allowed", 500: "Internal Server Error"}
        body_bytes = json.dumps(body).encode("utf-8")
        resp = (
            f"HTTP/1.1 {status} {phrases.get(status, 'Error')}\r\n"
            f"Content-Type: application/json\r\n"
            f"{self._CORS_HEADERS}"
            f"Content-Length: {len(body_bytes)}\r\n"
            f"\r\n"
        ).encode("utf-8") + body_bytes
        try:
            client.write(resp)
            client.flush()
            client.disconnectFromHost()
        except Exception:
            pass

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
            
            from urllib.parse import urlparse
            try:
                parsed = urlparse(url)
                domain = parsed.netloc.lower()
                if domain.startswith("www."):
                    domain = domain[4:]
            except Exception:
                domain = url.lower()
            
            all_entries = self._vault.get_all_entries()
            matched = []
            
            for e in all_entries:
                if not e.url:
                    continue
                e_url = e.url.lower()
                try:
                    e_parsed = urlparse(e_url)
                    e_domain = e_parsed.netloc.lower() or e_url
                    if e_domain.startswith("www."):
                        e_domain = e_domain[4:]
                except Exception:
                    e_domain = e_url

                score = 0
                if domain == e_domain and domain:
                    score = 100
                elif domain.endswith("." + e_domain) or e_domain.endswith("." + domain):
                    score = 50
                elif e_domain in url.lower() or domain in e_url:
                    score = 10
                    
                if score > 0:
                    matched.append((score, e))
            
            matched.sort(key=lambda x: (-x[0], x[1].site_name.lower()))
            
            logins  = [
                {
                    "id":        e.id,
                    "username":  e.username,
                    "password":  e.password,
                    "site_name": e.site_name,
                }
                for score, e in matched
            ]
            return {"status": "ok", "logins": logins}

        if command == "search":
            if self._vault.is_locked:
                return {"error": "locked"}
            query = req.get("query", "")
            entries = self._vault.search_entries(query)
            logins = [
                {
                    "id":        e.id,
                    "username":  e.username,
                    "password":  e.password,
                    "site_name": e.site_name,
                }
                for e in entries
            ]
            return {"status": "ok", "logins": logins}

        return {"error": "unknown_command"}
