<div align="center">

# 🛡 khazna

### Encrypted Local Password Manager

**AES-256-GCM · Scrypt KDF · Offline-First · Zero Cloud**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![PySide6](https://img.shields.io/badge/PySide6-6.7%2B-41CD52?logo=qt&logoColor=white)](https://doc.qt.io/qtforpython-6/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)]()

*khazna (خزنة) — Arabic for "vault" or "safe".*

A privacy-first desktop password manager that keeps your credentials encrypted locally — never in the cloud. Built with Python and a premium QML dark interface inspired by modern cybersecurity dashboards.

---

[Features](#-features) · [Screenshots](#-screenshots) · [Installation](#-installation) · [Security](#-security-model) · [Architecture](#-architecture) · [Contributing](#-contributing)

</div>

---

##  Features

<table>
<tr>
<td width="50%">

###  Core Security
- **AES-256-GCM** authenticated encryption for all vault data
- **Scrypt KDF** (N=2¹⁷) — memory-hard key derivation
- Master password **never stored** — only a derived key
- **Auto-lock** on idle with configurable timeout
- **Clipboard auto-wipe** after 30 seconds
- Brute-force lockout with progressive delays

</td>
<td width="50%">

###  Vault Management
- Add, edit, delete, and search credentials
- **Categories** — Social, Finance, Work, Dev, and more
- **Tags** — flexible cross-category labeling
- **Favourites** — quick-access pinned entries
- **Smart search** with real-time filtering
- Keyboard shortcuts (Ctrl+N, Ctrl+F, Ctrl+L, etc.)

</td>
</tr>
<tr>
<td>

###  Password Health
- **Health Dashboard** — overall vault security score
- Detect **weak**, **reused**, and **aging** passwords
- Per-entry strength scoring with actionable tips
- Severity badges and issue-level breakdown

</td>
<td>

###  Password Generator
- Cryptographically secure (CSPRNG via `secrets`)
- Configurable length (8–64 characters)
- Toggle uppercase, lowercase, digits, symbols
- Live strength preview
- One-click copy or inject into entries

</td>
</tr>
<tr>
<td>

###  Backup & Recovery
- **Portable V4 backups** — self-contained, restorable anywhere
- Backup-specific salt — independent of vault database
- **Recovery keys** — 8 one-time codes for master password reset
- CSV import from Chrome, Firefox, Brave, Bitwarden, and more
- Full audit log of all vault operations

</td>
<td>

###  Premium Desktop UI
- **QML dark theme** — glassmorphism, micro-animations, depth layers
- Custom frameless window with drag and resize
- Sidebar navigation with category and tag filters
- Status bar, toast notifications, clipboard countdown
- Responsive layout, smooth transitions throughout

</td>
</tr>
</table>

---

##  Screenshots

> Add your own screenshots to the `screenshots/` directory and update the paths below.

<details>
<summary><strong> Login Screen</strong></summary>
<br>

<!-- ![Login Screen](screenshots/login.png) -->
*Premium login card with master password input, strength bar, and ambient glow effects.*

</details>

<details>
<summary><strong> Main Dashboard</strong></summary>
<br>

<!-- ![Dashboard](screenshots/dashboard.png) -->
*Sidebar navigation, entry table with favicons, toolbar actions, and real-time search.*

</details>

<details>
<summary><strong> Health Dashboard</strong></summary>
<br>

<!-- ![Health Dashboard](screenshots/health.png) -->
*Overall vault score ring, weak/old password badges, and scrollable issue list.*

</details>

<details>
<summary><strong> Password Generator</strong></summary>
<br>

<!-- ![Password Generator](screenshots/generator.png) -->
*Length slider, character class toggles, live preview, and one-click copy.*

</details>

<details>
<summary><strong> Backup & Restore</strong></summary>
<br>

<!-- ![Backup Dialog](screenshots/backup.png) -->
*Tabbed interface for creating and restoring self-contained encrypted backups.*

</details>

<details>
<summary><strong> Recovery Keys</strong></summary>
<br>

<!-- ![Recovery Keys](screenshots/recovery.png) -->
*Generate and manage one-time recovery codes for emergency master password reset.*

</details>

---

##  Installation

### Prerequisites

| Requirement | Version |
|---|---|
| Python | ≥ 3.10 |
| pip | Latest recommended |

### Quick Start

```bash
# Clone the repository
git clone https://github.com/3mrRabie/khazna.git
cd khazna

# Create a virtual environment (recommended)
python -m venv .venv

# Activate it
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Launch khazna
python main.py
```

### CLI Options

```
python main.py [OPTIONS]

Options:
  --db PATH          Path to vault database (default: ~/.khazna/vault.db)
  --log-level LEVEL  DEBUG | INFO | WARNING | ERROR | CRITICAL
  --version          Show version and exit
  -h, --help         Show help
```

### Environment Variables

| Variable | Purpose |
|---|---|
| `KHAZNA_HOME` | Override default vault directory (`~/.khazna`) |
| `XDG_DATA_HOME` | Respected on Linux — vault stored under `$XDG_DATA_HOME/khazna` |

---

##  Building a Standalone Executable

```bash
pip install pyinstaller
pyinstaller khazna.spec
```

The output binary will be at `dist/khazna` (or `dist/khazna.exe` on Windows). All QML files and Qt plugins are bundled automatically.

---

##  Security Model

khazna is designed so that **your data never leaves your machine** and your master password is **never stored anywhere**.

### How Encryption Works

```
Master Password ──▶ Scrypt (N=2¹⁷, r=8, p=1) ──▶ 256-bit Key
                          │
                    ┌─────┴──────┐
                    ▼            ▼
              Verification   AES-256-GCM
              Token          Encrypt/Decrypt
              (login check)  (all vault fields)
```

1. **Key Derivation** — Your master password is run through **Scrypt** with a unique random 256-bit salt, producing a 256-bit encryption key. Scrypt is memory-hard, making GPU-accelerated brute-force attacks orders of magnitude more expensive than PBKDF2 or bcrypt.

2. **Encryption** — Every field (site name, username, password, URL, notes, tags) is individually encrypted with **AES-256-GCM**. GCM provides both confidentiality and integrity — any tampering is detected and rejected.

3. **Verification** — A known plaintext token is encrypted with the derived key and stored. At login, we decrypt this token — if it matches, the password is correct. The master password itself is **never stored or hashed**.

4. **Memory Safety** — Key material is zeroed from memory as soon as it's no longer needed, using explicit `bytearray` overwrites.

### Portable Backups (V4)

Each backup generates its **own random 32-byte salt** and derives an independent encryption key from the password you provide. The backup file format:

```
[ Magic Header (22 bytes) ] + [ Salt (32 bytes) ] + [ Scrypt N (4 bytes) ] + [ AES-256-GCM Payload ]
```

This means a backup can be restored on **any machine**, into **any vault**, even if the original database was deleted — as long as you know the backup password.

### Recovery Keys

- 8 one-time recovery codes (20 uppercase alphanumeric characters each, ~103 bits of entropy)
- Each code gets its own unique salt and domain-separated KDF
- Codes are shown once and **never stored in plaintext**
- Using a recovery code invalidates all codes and triggers a full re-encryption

---

##  Architecture

### Technology Stack

| Layer | Technology |
|---|---|
| **UI** | PySide6 + QML (QtQuick Controls) |
| **Backend** | Python 3.10+ |
| **Encryption** | `cryptography` library (OpenSSL backend) |
| **Storage** | SQLite (encrypted fields, not full-disk encryption) |
| **Clipboard** | Qt native + pyperclip fallback |

### Project Structure

```
khazna/
├── qml/                        # UI layer
│   ├── components/             # Reusable components (SvField, SvButton, SvDialog)
│   ├── Main.qml                # Application shell & screen router
│   ├── Theme.qml               # Design token singleton (colors, spacing, fonts)
│   ├── LoginScreen.qml         # Unlock / first-time setup
│   ├── DashboardScreen.qml     # Main entries view with toolbar
│   ├── Sidebar.qml             # Navigation, categories, tags, utility actions
│   ├── EntryTable.qml          # Sortable credential table with favicons
│   ├── EntryDialog.qml         # Add / edit entry form
│   ├── PasswordGenDialog.qml   # Secure password generator
│   ├── HealthDashboard.qml     # Password health score & issue list
│   ├── BackupDialog.qml        # Backup export / import
│   ├── RecoveryDialog.qml      # Recovery key management
│   ├── ChangePasswordDialog.qml
│   ├── AuditLogDialog.qml      # Security event log viewer
│   └── qmldir                  # QML module registration
│
├── main.py                     # Application entry point
├── app_logic.py                # Core business logic (VaultManager)
├── bridge.py                   # Python ↔ QML bridge (signals & slots)
├── storage.py                  # SQLite persistence layer
├── encryption.py               # AES-256-GCM / Scrypt crypto primitives
├── models.py                   # Data models (PasswordEntry, VaultConfig)
├── health.py                   # Password health scoring engine
├── recovery.py                 # Recovery key generation & verification
├── breach_check.py             # HaveIBeenPwned k-anonymity API
├── categories.py               # Category definitions & icon mapping
├── favicon_provider.py         # Site favicon loader for QML
├── extension_server.py         # Browser extension native messaging
├── native_host.py              # Chrome/Firefox native host manifest
├── normalizer.py               # URL/username deduplication logic
├── requirements.txt            # Python dependencies
└── khazna.spec                 # PyInstaller build specification
```

### Data Flow

```
┌──────────────┐     Signals/Slots     ┌──────────────┐     encrypt/decrypt     ┌─────────────┐
│   QML UI     │ ◀──────────────────▶  │  VaultBridge │ ◀───────────────────▶   │   Storage   │
│  (Frontend)  │                       │  (bridge.py) │                         │ (SQLite DB) │
└──────────────┘                       └──────┬───────┘                         └─────────────┘
                                              │
                                     ┌────────┴────────┐
                                     │  VaultManager   │
                                     │ (app_logic.py)  │
                                     └────────┬────────┘
                                              │
                                     ┌────────┴────────┐
                                     │  encryption.py  │
                                     │  recovery.py    │
                                     │  health.py      │
                                     └─────────────────┘
```

---

##  Browser Extension

khazna includes a local native messaging server (`extension_server.py`) that allows a companion browser extension to:

- Query credentials by URL
- Auto-fill login forms
- Add new entries from the browser

All communication happens over **localhost only** — no data is sent to external servers. The extension authenticates using a shared secret stored at `~/.khazna/extension_secret`.

---

##  Privacy First

- **Zero cloud** — Your vault exists only on your local disk
- **No telemetry** — No analytics, no tracking, no network calls (except optional HaveIBeenPwned breach checks via k-anonymity)
- **No accounts** — No sign-up, no email, no phone number
- **Open source** — Every line of encryption code is auditable
- **Portable** — Backups are fully self-contained and restorable on any machine

---

##  Roadmap

- [ ] TOTP / 2FA token storage
- [ ] Secure file attachments
- [ ] Dark / light theme toggle
- [ ] Browser extension (Chrome & Firefox)
- [ ] Import from 1Password, LastPass, KeePass
- [ ] Cross-device sync via encrypted file (no cloud)
- [ ] Mobile companion app (Qt for Android)

---

##  Contributing

Contributions are welcome! Whether it's bug fixes, new features, or documentation improvements.

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

### Development Setup

```bash
git clone https://github.com/3mrRabie/khazna.git
cd khazna
python -m venv .venv
.venv\Scripts\activate  # or source .venv/bin/activate
pip install -r requirements.txt
python main.py --log-level DEBUG
```

### Running Tests

```bash
pip install pytest
pytest test_bridge.py test_recovery.py test_csv_dedupe.py -v
```

---

##  License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

##  Credits & Technologies

| Technology | Purpose |
|---|---|
| [Python](https://python.org) | Application backend |
| [PySide6](https://doc.qt.io/qtforpython-6/) | Qt bindings for Python |
| [QML / QtQuick](https://doc.qt.io/qt-6/qtquick-index.html) | Declarative UI framework |
| [cryptography](https://cryptography.io) | AES-GCM, Scrypt, and secure primitives |
| [pyperclip](https://github.com/asweigart/pyperclip) | Cross-platform clipboard fallback |
| [HaveIBeenPwned](https://haveibeenpwned.com) | Breach detection via k-anonymity API |

---

<div align="center">

**Built with by a privacy-first developer.**

*Your passwords. Your machine. Your rules.*

</div>
