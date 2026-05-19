#!/usr/bin/env python3
"""
native_host.py
──────────────
Native Messaging Host for Browser Extension integration.

This script is spawned by the browser (Chrome/Edge/Brave). It reads JSON
messages from stdin (length-prefixed) and writes JSON to stdout.
It acts as a lightweight proxy, forwarding requests via a local TCP socket
to the running khazna desktop application (extension_server.py).
"""

import sys
import struct
import json
import socket
import os
from pathlib import Path

PORT = 27584

def read_message():
    """Read a length-prefixed message from standard input."""
    raw_length = sys.stdin.buffer.read(4)
    if not raw_length or len(raw_length) < 4:
        sys.exit(0)
    message_length = struct.unpack('@I', raw_length)[0]
    
    # Read exactly message_length bytes
    buf = b""
    while len(buf) < message_length:
        chunk = sys.stdin.buffer.read(message_length - len(buf))
        if not chunk:
            sys.exit(0)
        buf += chunk
    
    message = buf.decode('utf-8')
    return json.loads(message)

def send_message(message):
    """Write a length-prefixed message to standard output."""
    encoded_message = json.dumps(message).encode('utf-8')
    sys.stdout.buffer.write(struct.pack('@I', len(encoded_message)))
    sys.stdout.buffer.write(encoded_message)
    sys.stdout.buffer.flush()

_SECRET_PATH = Path.home() / ".khazna" / "extension_secret"

def _load_token() -> str:
    """Read the shared secret and return its hex representation."""
    try:
        raw = _SECRET_PATH.read_bytes()
        if len(raw) == 32:
            return raw.hex()
    except OSError:
        pass
    return ""

def forward_to_desktop(req_dict):
    """Send the JSON request to the desktop app and return the response.
    Auto-injects the authentication token for credential commands."""
    # Auto-inject token for authenticated commands
    if "token" not in req_dict and req_dict.get("command") != "status":
        token = _load_token()
        if token:
            req_dict["token"] = token

    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=2.0) as s:
            s.sendall(json.dumps(req_dict).encode("utf-8"))
            s.shutdown(socket.SHUT_WR)  # Signal end-of-request to server
            
            # Read response
            chunks = []
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                chunks.append(chunk)
            
            resp_str = b"".join(chunks).decode("utf-8")
            return json.loads(resp_str)
            
    except (ConnectionRefusedError, TimeoutError, socket.timeout):
        return {"error": "app_not_running"}
    except Exception as e:
        return {"error": f"bridge_error: {str(e)}"}


# ──────────────────────────────────────────────
# Native Messaging Manifest Installer
# ──────────────────────────────────────────────

HOST_NAME = "com.khazna.bridge"

def generate_manifest(extension_id: str = "") -> dict:
    """
    Generate the Chrome/Edge/Brave native messaging host manifest.

    Parameters
    ----------
    extension_id : str
        The browser extension ID. Format: "chrome-extension://EXTENSION_ID/"
        If empty, a placeholder is used.
    """
    script_dir = Path(__file__).resolve().parent

    # On Windows, Chrome can't launch .py directly — use the .bat wrapper
    if sys.platform == "win32":
        host_path = str(script_dir / "native_host.bat")
    else:
        host_path = str(script_dir / "native_host.py")

    manifest = {
        "name": HOST_NAME,
        "description": "khazna Password Manager - Native Messaging Bridge",
        "path": host_path,
        "type": "stdio",
        "allowed_origins": [
            extension_id if extension_id else "chrome-extension://plcogcpoohjpoeafohfnfpmbhkmnjnmd/"
        ],
    }
    return manifest


def install_manifest(extension_id: str = "") -> None:
    """
    Write the manifest JSON and register it with the browser.

    Windows : writes to HKCU\\Software\\Google\\Chrome\\NativeMessagingHosts
    macOS   : writes to ~/Library/Application Support/Google/Chrome/NativeMessagingHosts/
    Linux   : writes to ~/.config/google-chrome/NativeMessagingHosts/
    """
    manifest = generate_manifest(extension_id)
    manifest_json = json.dumps(manifest, indent=2)

    # Determine manifest directory
    if sys.platform == "win32":
        manifest_dir = Path.home() / ".khazna"
    elif sys.platform == "darwin":
        manifest_dir = Path.home() / "Library" / "Application Support" / "Google" / "Chrome" / "NativeMessagingHosts"
    else:
        manifest_dir = Path.home() / ".config" / "google-chrome" / "NativeMessagingHosts"

    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / f"{HOST_NAME}.json"
    manifest_path.write_text(manifest_json, encoding="utf-8")
    print(f"Manifest written to: {manifest_path}")

    # Windows: register in HKCU registry for all Chromium browsers
    if sys.platform == "win32":
        try:
            import winreg
            browser_keys = [
                ("Chrome", f"Software\\Google\\Chrome\\NativeMessagingHosts\\{HOST_NAME}"),
                ("Edge",   f"Software\\Microsoft\\Edge\\NativeMessagingHosts\\{HOST_NAME}"),
                ("Brave",  f"Software\\BraveSoftware\\Brave-Browser\\NativeMessagingHosts\\{HOST_NAME}"),
            ]
            for browser_name, key_path in browser_keys:
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                    winreg.SetValueEx(key, "", 0, winreg.REG_SZ, str(manifest_path))
                print(f"Registry key set ({browser_name}): HKCU\\{key_path}")
        except Exception as e:
            print(f"Warning: Could not write registry key: {e}")
            print("You may need to register the manifest manually.")

    print("\nInstallation complete.")
    print(f"Host name: {HOST_NAME}")
    if not extension_id:
        print("\n[!] You must update 'allowed_origins' in the manifest with your")
        print("   actual extension ID before the browser will connect.")


def main():
    # Force binary mode on Windows to prevent \r\n translation issues
    if sys.platform == "win32":
        try:
            import msvcrt
            msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
            msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
        except Exception:
            pass

    if len(sys.argv) > 1 and sys.argv[1] == "--install":
        ext_id = sys.argv[2] if len(sys.argv) > 2 else ""
        install_manifest(ext_id)
        return

    # Normal native messaging host mode: read stdin, forward to desktop, write stdout
    while True:
        try:
            req = read_message()
            resp = forward_to_desktop(req)
            send_message(resp)
        except Exception:
            # Native hosts must fail silently or log to a file
            sys.exit(1)

if __name__ == '__main__':
    main()
