# khazna Browser Extension

> Chromium extension for the [khazna](../README.md) desktop password manager.
> Autofill, search, and manage your encrypted vault directly from the browser.

## Features

- **Auto-detect login forms** on any website
- **One-click autofill** username + password
- **Search credentials** from the popup
- **Copy** username or password to clipboard
- **Vault status** indicator (connected / locked / offline)
- **Shield badge** injected near password fields
- **SPA support** — detects dynamically loaded forms
- **Native messaging** primary transport (secure, no HTTP)
- **HTTP fallback** when native messaging isn't installed

## Installation

### 1. Load the extension in Chrome/Brave/Edge

1. Open your browser and go to `chrome://extensions/`
2. Enable **Developer mode** (toggle in top-right)
3. Click **Load unpacked**
4. Select this `extension/` directory
5. Note the **Extension ID** shown on the card (e.g. `abcdef1234567890...`)

### 2. Install the native messaging host

```bash
cd khazna/
python native_host.py --install "chrome-extension://YOUR_EXTENSION_ID/"
```

Replace `YOUR_EXTENSION_ID` with the actual ID from step 1.

This registers the native messaging manifest so Chrome can communicate with the desktop app.

### 3. Start the desktop app

```bash
python main.py
```

Unlock the vault — the extension status dot should turn green.

## How It Works

```
┌─────────────┐  sendNativeMessage  ┌───────────────┐  TCP/JSON  ┌──────────────────┐
│  Extension   │ ─────────────────► │  native_host   │ ────────► │  Extension Server │
│  (browser)   │ ◄───────────────── │  (.py stdin)   │ ◄──────── │  (desktop app)    │
└─────────────┘   JSON response    └───────────────┘           └──────────────────┘

Fallback (no native host installed):
┌─────────────┐   HTTP POST    ┌──────────────────┐
│  Extension   │ ────────────► │  Extension Server │
│  (browser)   │ ◄──────────── │  port 27584       │
└─────────────┘  JSON + CORS   └──────────────────┘
```

### Message Protocol

**Status check** (unauthenticated):
```json
→ {"command": "status"}
← {"status": "ok", "is_locked": false, "is_initialized": true}
```

**Get logins** (token auto-injected by native host):
```json
→ {"command": "get_logins", "url": "https://github.com"}
← {"status": "ok", "logins": [
     {"id": 1, "username": "user@email.com", "password": "...", "site_name": "GitHub"}
   ]}
```

**Vault locked**:
```json
→ {"command": "get_logins", "url": "..."}
← {"error": "locked"}
```

## File Structure

```
extension/
├── manifest.json    # Manifest V3 configuration
├── background.js    # Service worker — messaging transport
├── content.js       # Form detection, autofill injection
├── popup.html       # Extension popup structure
├── popup.css        # Dark cybersecurity UI
├── popup.js         # Popup logic — search, copy, autofill
├── icons/
│   ├── icon16.png
│   ├── icon32.png
│   ├── icon48.png
│   └── icon128.png
└── README.md        # This file
```

## Security

- **No passwords stored in extension** — credentials exist only in memory during autofill
- **Token never in extension** — native_host.py auto-injects the shared secret
- **Localhost only** — all communication stays on 127.0.0.1
- **Strict CSP** — no inline scripts, no eval
- **CORS restricted** — HTTP fallback only accepts requests from allowed origins

## Permissions

| Permission | Reason |
|---|---|
| `activeTab` | Read current tab URL to match credentials |
| `nativeMessaging` | Communicate with the desktop app |
| `clipboardWrite` | Copy credentials to clipboard |

## License

MIT — same as the khazna project.
