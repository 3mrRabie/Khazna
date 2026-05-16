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

PORT = 27584

def read_message():
    """Read a length-prefixed message from standard input."""
    raw_length = sys.stdin.buffer.read(4)
    if len(raw_length) == 0:
        sys.exit(0)
    message_length = struct.unpack('@I', raw_length)[0]
    message = sys.stdin.buffer.read(message_length).decode('utf-8')
    return json.loads(message)

def send_message(message):
    """Write a length-prefixed message to standard output."""
    encoded_message = json.dumps(message).encode('utf-8')
    sys.stdout.buffer.write(struct.pack('@I', len(encoded_message)))
    sys.stdout.buffer.write(encoded_message)
    sys.stdout.buffer.flush()

def forward_to_desktop(req_dict):
    """Send the JSON request to the desktop app and return the response."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2.0)
            s.connect(("127.0.0.1", PORT))
            s.sendall(json.dumps(req_dict).encode("utf-8"))
            
            # Read response
            chunks = []
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                chunks.append(chunk)
            
            resp_str = b"".join(chunks).decode("utf-8")
            return json.loads(resp_str)
            
    except ConnectionRefusedError:
        return {"error": "app_not_running"}
    except Exception as e:
        return {"error": f"bridge_error: {str(e)}"}

def main():
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
