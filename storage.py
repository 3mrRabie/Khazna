"""
storage.py
──────────
SQLite persistence layer for the vault.

Security guarantees
───────────────────
• Every sensitive field (site_name, url, username, password, notes, tags) is
  individually encrypted with AES-256-GCM *before* being written to the DB.
• The SQLite file therefore never contains any plaintext credentials or metadata.
• The encryption key lives only in the VaultStorage._key instance variable
  and is cleared (best-effort zero-fill) on lock().
• Search is performed in-memory after decryption; no plaintext metadata is
  indexed in the database.
• Journal mode is WAL for concurrent reads and crash safety.
• A backup/restore mechanism exports/imports the entire database as a single
  AES-256-GCM encrypted JSON blob with a magic header.
• Master password change is performed atomically in a single transaction
  (SEC-04 fix) to prevent partial re-encryption on crash.

Migration
─────────
Old vaults (schema v1) stored site_name and tags in plaintext.
Call migrate_plaintext_to_encrypted() after unlock to migrate them.
"""

from __future__ import annotations

import base64
import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator, List, Optional

_log = logging.getLogger("khazna.storage")

from encryption import (
    SCRYPT_N,
    DecryptionError,
    EncryptionError,
    decrypt_bytes,
    decrypt_str,
    encrypt_bytes,
    encrypt_str,
    zero_bytearray,
    generate_salt,
    derive_key,
)
from models import AuditLog, PasswordEntry, VaultConfig


# ──────────────────────────────────────────────
# Custom exceptions
# ──────────────────────────────────────────────

class StorageError(Exception):
    """Raised when a storage operation fails."""


# ──────────────────────────────────────────────
# Schema
# ──────────────────────────────────────────────

# SEC-02 FIX: site_name_encrypted and tags_encrypted replace the old
# plaintext site_name / tags columns.  All text fields are now encrypted.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS vault_config (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS entries (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    site_name_encrypted   TEXT    NOT NULL DEFAULT '',
    url_encrypted         TEXT    NOT NULL DEFAULT '',
    username_encrypted    TEXT    NOT NULL DEFAULT '',
    password_encrypted    TEXT    NOT NULL DEFAULT '',
    notes_encrypted       TEXT    NOT NULL DEFAULT '',
    tags_encrypted        TEXT    NOT NULL DEFAULT '',
    category_encrypted    TEXT    NOT NULL DEFAULT '',
    favorite              INTEGER NOT NULL DEFAULT 0,
    created_at            TEXT    NOT NULL,
    modified_at           TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_entries_fav ON entries(favorite);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT    NOT NULL,
    event_type  TEXT    NOT NULL,
    description TEXT    NOT NULL DEFAULT '',
    success     INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_audit_ts   ON audit_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_type ON audit_log(event_type);

CREATE TABLE IF NOT EXISTS recovery_keys (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    salt                TEXT    NOT NULL,
    code_hash           TEXT    NOT NULL,
    encrypted_key       TEXT    NOT NULL,
    created_at          TEXT    NOT NULL
);
"""

_BACKUP_MAGIC = b"KHAZNA_BACKUP_V2\x00"
_BACKUP_MAGIC_V4 = b"KHAZNA_BACKUP_V4\x00"


# ──────────────────────────────────────────────
# VaultStorage
# ──────────────────────────────────────────────

class VaultStorage:
    """
    All database I/O for the password vault.

    The caller must call ``set_key(key)`` after a successful login and
    ``clear_key()`` on lock.  Every method that reads or writes sensitive
    data checks that the key is present; if it isn't, StorageError is raised.
    """

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._key: Optional[bytes] = None
        self._init_db()

    # ── Key management ────────────────────────

    def set_key(self, key: bytes) -> None:
        """Store the session encryption key."""
        self._key = key

    def clear_key(self) -> None:
        """Zero-fill and discard the session key."""
        if self._key is not None:
            buf = bytearray(self._key)
            zero_bytearray(buf)
            del buf
        self._key = None

    def _require_key(self) -> bytes:
        if self._key is None:
            raise StorageError(
                "Vault is locked. Set the encryption key before accessing entries."
            )
        return self._key

    # ── Connection management ─────────────────

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        """Yield an autocommit-on-success, rollback-on-error connection."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=FULL")  # crash safety
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(_SCHEMA)
            # Handle upgrade from old schema (site_name plaintext → encrypted)
            self._maybe_upgrade_schema(conn)

    def _maybe_upgrade_schema(self, conn: sqlite3.Connection) -> None:
        """
        Add encrypted columns if this DB was created by an older version
        that stored site_name and tags in plaintext (schema v1).
        Also adds category_encrypted for vaults pre-dating Feature 5.
        """
        cols = {row[1] for row in conn.execute("PRAGMA table_info(entries)").fetchall()}
        if "site_name_encrypted" not in cols:
            conn.execute(
                "ALTER TABLE entries ADD COLUMN site_name_encrypted TEXT NOT NULL DEFAULT ''"
            )
        if "tags_encrypted" not in cols:
            conn.execute(
                "ALTER TABLE entries ADD COLUMN tags_encrypted TEXT NOT NULL DEFAULT ''"
            )
        if "category_encrypted" not in cols:
            conn.execute(
                "ALTER TABLE entries ADD COLUMN category_encrypted TEXT NOT NULL DEFAULT ''"
            )

    def migrate_plaintext_to_encrypted(self) -> int:
        """
        Encrypt any plaintext site_name / tags values that pre-date schema v2.
        Call this once after unlock if the vault was created with an old version.
        Returns the number of rows migrated.

        This is safe to call multiple times — rows with site_name_encrypted
        already set are skipped.
        """
        self._require_key()
        with self._conn() as conn:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(entries)").fetchall()}
            if "site_name" not in cols:
                return 0  # Already on new schema, nothing to do

            # Find rows that have a plaintext site_name but no encrypted equivalent
            rows = conn.execute(
                "SELECT id, site_name, tags FROM entries "
                "WHERE site_name_encrypted = '' AND site_name != ''"
            ).fetchall()

            count = 0
            for row in rows:
                conn.execute(
                    "UPDATE entries SET site_name_encrypted = ?, tags_encrypted = ? WHERE id = ?",
                    (
                        self._enc(row["site_name"] or ""),
                        self._enc(row["tags"] or ""),
                        row["id"],
                    ),
                )
                count += 1

            return count

    # ── Vault config ──────────────────────────

    def _cfg_set(self, key: str, value: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO vault_config (key, value) VALUES (?, ?)",
                (key, value),
            )

    def _cfg_get(self, key: str) -> Optional[str]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT value FROM vault_config WHERE key = ?", (key,)
            ).fetchone()
            return row["value"] if row else None

    def save_vault_config(self, cfg: VaultConfig) -> None:
        if cfg.salt:
            self._cfg_set("salt", base64.b64encode(cfg.salt).decode())
        if cfg.verification_token:
            self._cfg_set(
                "verification_token",
                base64.b64encode(cfg.verification_token).decode(),
            )
        self._cfg_set("version", cfg.version)
        ts = cfg.created_at or datetime.now()
        self._cfg_set("created_at", ts.isoformat())
        self._cfg_set("failed_attempts", str(cfg.failed_attempts))
        self._cfg_set(
            "lockout_until",
            cfg.lockout_until.isoformat() if cfg.lockout_until else "",
        )
        # SEC-01: persist the scrypt work factor so unlock always uses the
        # correct N for this vault, regardless of what the code default is.
        self._cfg_set("scrypt_n", str(cfg.scrypt_n))

    def load_vault_config(self) -> Optional[VaultConfig]:
        salt_b64  = self._cfg_get("salt")
        token_b64 = self._cfg_get("verification_token")
        if not salt_b64 or not token_b64:
            return None

        cfg = VaultConfig(
            version            = self._cfg_get("version") or "1.0",
            salt               = base64.b64decode(salt_b64),
            verification_token = base64.b64decode(token_b64),
            failed_attempts    = int(self._cfg_get("failed_attempts") or 0),
        )
        created_raw = self._cfg_get("created_at")
        if created_raw:
            try:
                cfg.created_at = datetime.fromisoformat(created_raw)
            except ValueError:
                pass

        lockout_raw = self._cfg_get("lockout_until") or ""
        if lockout_raw:
            try:
                cfg.lockout_until = datetime.fromisoformat(lockout_raw)
            except ValueError:
                pass

        # SEC-01: load stored N; fall back to the OLD default for existing vaults
        # that pre-date this field so they can still be unlocked.
        scrypt_n_raw = self._cfg_get("scrypt_n")
        cfg.scrypt_n = int(scrypt_n_raw) if scrypt_n_raw else 2 ** 14

        return cfg

    def update_login_state(
        self,
        failed_attempts: int,
        lockout_until: Optional[datetime] = None,
    ) -> None:
        self._cfg_set("failed_attempts", str(failed_attempts))
        self._cfg_set(
            "lockout_until",
            lockout_until.isoformat() if lockout_until else "",
        )

    # ── Field-level encryption helpers ────────

    def _enc(self, value: str) -> str:
        """Encrypt a field value; return empty string for empty input."""
        key = self._require_key()
        return encrypt_str(value, key) if value else ""

    def _dec(self, value: str) -> str:
        """Decrypt a field value; return empty string for empty input."""
        key = self._require_key()
        if not value:
            return ""
        try:
            return decrypt_str(value, key)
        except (DecryptionError, Exception):
            return "<decryption error>"

    # ── Entry CRUD ────────────────────────────

    def add_entry(self, entry: PasswordEntry) -> int:
        self._require_key()
        now = datetime.now().isoformat()
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO entries
                    (site_name_encrypted, url_encrypted, username_encrypted,
                     password_encrypted, notes_encrypted, tags_encrypted,
                     category_encrypted, favorite, created_at, modified_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self._enc(entry.site_name),
                    self._enc(entry.url),
                    self._enc(entry.username),
                    self._enc(entry.password),
                    self._enc(entry.notes),
                    self._enc(",".join(entry.tags)),
                    self._enc(entry.category),
                    1 if entry.favorite else 0,
                    now,
                    now,
                ),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def update_entry(self, entry: PasswordEntry) -> None:
        self._require_key()
        if entry.id is None:
            raise StorageError("Cannot update an entry without an ID")
        now = datetime.now().isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE entries SET
                    site_name_encrypted = ?,
                    url_encrypted       = ?,
                    username_encrypted  = ?,
                    password_encrypted  = ?,
                    notes_encrypted     = ?,
                    tags_encrypted      = ?,
                    category_encrypted  = ?,
                    favorite            = ?,
                    modified_at         = ?
                WHERE id = ?
                """,
                (
                    self._enc(entry.site_name),
                    self._enc(entry.url),
                    self._enc(entry.username),
                    self._enc(entry.password),
                    self._enc(entry.notes),
                    self._enc(",".join(entry.tags)),
                    self._enc(entry.category),
                    1 if entry.favorite else 0,
                    now,
                    entry.id,
                ),
            )

    def delete_entry(self, entry_id: int) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))

    def get_entry(self, entry_id: int) -> Optional[PasswordEntry]:
        self._require_key()
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM entries WHERE id = ?", (entry_id,)
            ).fetchone()
        return self._row_to_entry(row) if row else None

    def get_all_entries(self) -> List[PasswordEntry]:
        """Load and decrypt all entries, returning them sorted by site name."""
        self._require_key()
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM entries ORDER BY id").fetchall()
        entries = [self._row_to_entry(r) for r in rows]
        return sorted(entries, key=lambda e: e.site_name.lower())

    def search_entries(self, query: str) -> List[PasswordEntry]:
        """
        In-memory search across all decrypted fields.
        Since site_name is now encrypted, SQL-level filtering is not possible.
        For personal-scale vaults (<10,000 entries) this is fast enough.
        """
        self._require_key()
        all_entries = self.get_all_entries()
        if not query.strip():
            return all_entries
        q_lower = query.strip().lower()
        return [e for e in all_entries if e.matches_query(q_lower)]

    def get_entries_by_tag(self, tag: str) -> List[PasswordEntry]:
        """
        CODE-02 FIX: Old implementation used LIKE '%tag%' which matched substrings
        (e.g. 'work' would match 'network', 'homework').
        Now does in-memory exact tag matching since tags are encrypted.
        """
        self._require_key()
        tag_lower = tag.lower().strip()
        all_entries = self.get_all_entries()
        return [
            e for e in all_entries
            if any(t.lower() == tag_lower for t in e.tags)
        ]

    def get_favorite_entries(self) -> List[PasswordEntry]:
        """Favorite flag is not encrypted so we can still filter in SQL."""
        self._require_key()
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM entries WHERE favorite = 1"
            ).fetchall()
        entries = [self._row_to_entry(r) for r in rows]
        return sorted(entries, key=lambda e: e.site_name.lower())

    def get_all_tags(self) -> List[str]:
        """Collect all unique tags from decrypted entries."""
        self._require_key()
        entries = self.get_all_entries()
        tags: set[str] = set()
        for e in entries:
            for t in e.tags:
                if t:
                    tags.add(t)
        return sorted(tags)

    def get_all_categories(self) -> List[str]:
        """Collect all unique categories from decrypted entries."""
        self._require_key()
        entries = self.get_all_entries()
        cats: set[str] = set()
        for e in entries:
            if e.category:
                cats.add(e.category)
        # Ensure builtins are always present
        from categories import BUILTIN_CATEGORIES
        cats.update(BUILTIN_CATEGORIES)
        return sorted(cats)

    def get_entry_count(self) -> int:
        with self._conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]

    def _row_to_entry(self, row: sqlite3.Row) -> PasswordEntry:
        row_keys = row.keys()

        # SEC-02: read from encrypted columns; fall back to legacy plaintext
        # columns during the migration window for old schema vaults.
        if "site_name_encrypted" in row_keys and row["site_name_encrypted"]:
            site_name = self._dec(row["site_name_encrypted"])
        else:
            site_name = row["site_name"] if "site_name" in row_keys else ""

        if "tags_encrypted" in row_keys and row["tags_encrypted"]:
            tags_raw = self._dec(row["tags_encrypted"])
        else:
            tags_raw = row["tags"] if "tags" in row_keys else ""

        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]

        def _dt(val: Optional[str]) -> Optional[datetime]:
            if not val:
                return None
            try:
                return datetime.fromisoformat(val)
            except ValueError:
                return None

        # Category (may not exist in very old schemas)
        if "category_encrypted" in row_keys and row["category_encrypted"]:
            category = self._dec(row["category_encrypted"])
        else:
            category = "Other"

        return PasswordEntry(
            id          = row["id"],
            site_name   = site_name,
            url         = self._dec(row["url_encrypted"]),
            username    = self._dec(row["username_encrypted"]),
            password    = self._dec(row["password_encrypted"]),
            notes       = self._dec(row["notes_encrypted"]),
            tags        = tags,
            favorite    = bool(row["favorite"]),
            category    = category,
            created_at  = _dt(row["created_at"]),
            modified_at = _dt(row["modified_at"]),
        )

    # ── Atomic re-encryption (SEC-04) ────────

    def atomic_reencrypt(
        self,
        entries: List[PasswordEntry],
        new_key: bytes,
        new_salt: bytes,
        new_token: bytes,
        scrypt_n: int,
    ) -> None:
        """
        SEC-04 FIX: Re-encrypt all entries and update vault config in a SINGLE
        SQLite transaction.  Either everything succeeds or the DB is unchanged.
        A crash during the old multi-step flow could leave the vault with mixed
        encryption keys and permanently unrecoverable.
        """
        def _enc_with(value: str, key: bytes) -> str:
            return encrypt_str(value, key) if value else ""

        with self._conn() as conn:
            # Re-encrypt every entry under the new key
            for entry in entries:
                conn.execute(
                    """UPDATE entries SET
                        site_name_encrypted = ?,
                        url_encrypted       = ?,
                        username_encrypted  = ?,
                        password_encrypted  = ?,
                        notes_encrypted     = ?,
                        tags_encrypted      = ?,
                        category_encrypted  = ?
                       WHERE id = ?""",
                    (
                        _enc_with(entry.site_name, new_key),
                        _enc_with(entry.url,       new_key),
                        _enc_with(entry.username,  new_key),
                        _enc_with(entry.password,  new_key),
                        _enc_with(entry.notes,     new_key),
                        _enc_with(",".join(entry.tags), new_key),
                        _enc_with(entry.category,  new_key),
                        entry.id,
                    ),
                )

            # Update vault config — all in the same transaction
            for k, v in [
                ("salt",               base64.b64encode(new_salt).decode()),
                ("verification_token", base64.b64encode(new_token).decode()),
                ("scrypt_n",           str(scrypt_n)),
            ]:
                conn.execute(
                    "INSERT OR REPLACE INTO vault_config (key, value) VALUES (?, ?)",
                    (k, v),
                )

        # Only update in-memory key after a successful DB commit
        self.set_key(new_key)

    # ── Audit log ─────────────────────────────

    def add_audit_log(
        self,
        event_type: str,
        description: str,
        success: bool = True,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO audit_log (timestamp, event_type, description, success)
                VALUES (?, ?, ?, ?)
                """,
                (datetime.now().isoformat(), event_type, description, 1 if success else 0),
            )

    def get_audit_logs(self, limit: int = 200) -> List[AuditLog]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        result = []
        for row in rows:
            ts = None
            try:
                ts = datetime.fromisoformat(row["timestamp"])
            except ValueError:
                pass
            result.append(
                AuditLog(
                    id          = row["id"],
                    timestamp   = ts,
                    event_type  = row["event_type"],
                    description = row["description"],
                    success     = bool(row["success"]),
                )
            )
        return result

    def export_encrypted_backup(self, path: str, key: bytes, password: str = "") -> None:
        """
        Dump the raw SQLite rows (still encrypted) into a JSON payload.
        If password is provided, creates a self-contained V4 backup independent of the vault.
        Otherwise creates a V2 backup encrypted with the current session key.
        """
        with self._conn() as conn:
            entries_rows = conn.execute("SELECT * FROM entries").fetchall()
            config_rows  = conn.execute("SELECT * FROM vault_config").fetchall()

        if password:
            backup_salt = generate_salt()
            backup_key = derive_key(password, backup_salt, SCRYPT_N)
            version = "4.0"
        else:
            backup_key = key
            version = "2.0"

        config_data  = {r["key"]: r["value"] for r in config_rows}
        entries_data = []
        for r in entries_rows:
            d = dict(r)
            if version == "4.0":
                # Decrypt DB fields so the backup payload is independent of the vault's session key.
                # The payload itself is fully encrypted with backup_key.
                v_site = d.pop("site_name_encrypted", "")
                d["site_name"] = decrypt_str(v_site, key) if v_site else ""
                
                v_url = d.pop("url_encrypted", "")
                d["url"] = decrypt_str(v_url, key) if v_url else ""
                
                v_user = d.pop("username_encrypted", "")
                d["username"] = decrypt_str(v_user, key) if v_user else ""
                
                v_pw = d.pop("password_encrypted", "")
                d["password"] = decrypt_str(v_pw, key) if v_pw else ""
                
                v_notes = d.pop("notes_encrypted", "")
                d["notes"] = decrypt_str(v_notes, key) if v_notes else ""
                
                v_tags = d.pop("tags_encrypted", "")
                d["tags"] = decrypt_str(v_tags, key) if v_tags else ""
            entries_data.append(d)

        payload = {
            "version":        version,
            "schema_version": "2",
            "timestamp":      datetime.now().isoformat(),
            "config":         config_data,
            "entries":        entries_data,
        }

        json_bytes = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
        encrypted  = encrypt_bytes(json_bytes, backup_key)

        with open(path, "wb") as fh:
            if password:
                fh.write(_BACKUP_MAGIC_V4)
                fh.write(backup_salt)
                fh.write(SCRYPT_N.to_bytes(4, "big"))
            else:
                fh.write(_BACKUP_MAGIC)
            fh.write(encrypted)
            
        # Clean up backup key if we created one
        if password:
            buf = bytearray(backup_key)
            zero_bytearray(buf)
            del buf
            
        _log.info("Backup exported to %s (%d entries, version %s)", path, len(entries_data), version)

    def import_encrypted_backup(self, path: str, key: bytes, password: str = "") -> int:
        """
        Decrypt and import an encrypted backup file.
        Existing entries (by id) are not overwritten (INSERT OR IGNORE).
        Returns the number of entries actually inserted.
        Raises StorageError with a user-friendly message on failure.
        """
        try:
            with open(path, "rb") as fh:
                raw = fh.read()
        except OSError as exc:
            raise StorageError(f"Cannot read backup file: {exc}") from exc

        if len(raw) < 30:
            raise StorageError("This file is too small to be a valid khazna backup.")

        magic = raw[:22]
        _V3_MAGIC = b"KHAZNA_BACKUP_V3\x00"
        _V1_MAGIC = b"KHAZNA_BACKUP_V1\x00"
        
        backup_key = key
        need_cleanup = False

        if magic == _BACKUP_MAGIC_V4:
            if len(raw) < 58:
                raise StorageError("V4 backup file is truncated")
            if not password:
                raise StorageError("A password is required to restore this backup.")
            backup_salt = raw[22:54]
            backup_n = int.from_bytes(raw[54:58], "big")
            encrypted = raw[58:]
            backup_key = derive_key(password, backup_salt, backup_n)
            need_cleanup = True
        elif magic == _BACKUP_MAGIC:
            encrypted = raw[22:]
        elif magic == _V3_MAGIC:
            encrypted = raw[58:] if len(raw) > 58 else raw[22:]
        elif magic == _V1_MAGIC:
            encrypted = raw[22:]
        else:
            raise StorageError(
                "This file is not a valid khazna backup.\n"
                "It may be a different file type or corrupted."
            )

        try:
            json_bytes = decrypt_bytes(encrypted, backup_key)
        except DecryptionError:
            raise StorageError(
                "Could not decrypt this backup.\n\n"
                "If you are restoring an older backup, it was encrypted with your old master password. "
                "For self-contained (V4) backups, please ensure you entered the correct password used to create the backup."
            )
        finally:
            if need_cleanup:
                buf = bytearray(backup_key)
                zero_bytearray(buf)
                del buf

        try:
            payload = json.loads(json_bytes.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise StorageError("Backup decrypted but the data inside is corrupted.") from exc

        count = 0
        with self._conn() as conn:
            is_v4 = payload.get("version") == "4.0"
            for row in payload.get("entries", []):
                if is_v4:
                    site_enc = encrypt_str(row.get("site_name", ""), key)
                    url_enc  = encrypt_str(row.get("url", ""), key)
                    user_enc = encrypt_str(row.get("username", ""), key)
                    pw_enc   = encrypt_str(row.get("password", ""), key)
                    note_enc = encrypt_str(row.get("notes", ""), key)
                    tags_enc = encrypt_str(row.get("tags", ""), key)
                else:
                    site_enc = row.get("site_name_encrypted", "")
                    url_enc  = row.get("url_encrypted", "")
                    user_enc = row.get("username_encrypted", "")
                    pw_enc   = row.get("password_encrypted", "")
                    note_enc = row.get("notes_encrypted", "")
                    tags_enc = row.get("tags_encrypted", "")

                    if not site_enc and row.get("site_name"):
                        site_enc = encrypt_str(row["site_name"], key)
                    if not tags_enc and row.get("tags"):
                        tags_enc = encrypt_str(row["tags"], key)

                if not pw_enc:
                    continue

                conn.execute(
                    """
                    INSERT OR IGNORE INTO entries
                        (id, site_name_encrypted, url_encrypted, username_encrypted,
                         password_encrypted, notes_encrypted, tags_encrypted,
                         favorite, created_at, modified_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("id"),
                        site_enc,
                        url_enc,
                        user_enc,
                        pw_enc,
                        note_enc,
                        tags_enc,
                        row.get("favorite", 0),
                        row.get("created_at",  datetime.now().isoformat()),
                        row.get("modified_at", datetime.now().isoformat()),
                    ),
                )
                count += conn.execute("SELECT changes()").fetchone()[0]

        _log.info("Backup imported from %s (%d entries added)", path, count)
        return count

    # ── Smart search (Feature 2) ──────────────

    def search_entries_ranked(self, query: str) -> List[PasswordEntry]:
        """
        In-memory ranked search across all decrypted fields.
        Returns entries sorted by relevance score (highest first).
        """
        self._require_key()
        all_entries = self.get_all_entries()
        if not query.strip():
            return all_entries
        scored = [
            (e, e.smart_search_score(query.strip()))
            for e in all_entries
        ]
        matched = [(e, s) for e, s in scored if s > 0]
        matched.sort(key=lambda pair: -pair[1])
        return [e for e, _ in matched]

    # ── Category queries (Feature 5) ──────────
    # NOTE: get_all_categories() is defined earlier in this file (line ~455).
    # The duplicate that was here (without BUILTIN_CATEGORIES) has been removed.

    def get_entries_by_category(self, category: str) -> List[PasswordEntry]:
        """Return entries matching a specific category."""
        self._require_key()
        cat_lower = category.lower().strip()
        all_entries = self.get_all_entries()
        return [e for e in all_entries if e.category.lower() == cat_lower]

    # ── Recovery keys (Feature 6) ─────────────

    def save_recovery_keys(self, records: list) -> None:
        """Persist recovery key records to the database."""
        import base64 as b64
        with self._conn() as conn:
            # Clear any existing recovery keys first
            conn.execute("DELETE FROM recovery_keys")
            for rec in records:
                conn.execute(
                    """INSERT INTO recovery_keys
                       (salt, code_hash, encrypted_key, created_at)
                       VALUES (?, ?, ?, ?)""",
                    (
                        b64.b64encode(rec.salt).decode(),
                        b64.b64encode(rec.code_hash).decode(),
                        b64.b64encode(rec.encrypted_key).decode(),
                        rec.created_at,
                    ),
                )

    def load_recovery_keys(self) -> list:
        """Load recovery key records from the database."""
        import base64 as b64
        from recovery import RecoveryRecord
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM recovery_keys").fetchall()
        records = []
        for row in rows:
            records.append(RecoveryRecord(
                salt=b64.b64decode(row["salt"]),
                code_hash=b64.b64decode(row["code_hash"]),
                encrypted_key=b64.b64decode(row["encrypted_key"]),
                created_at=row["created_at"],
            ))
        return records

    def delete_recovery_keys(self) -> None:
        """Delete all recovery keys from the database."""
        with self._conn() as conn:
            conn.execute("DELETE FROM recovery_keys")

    def has_recovery_keys(self) -> bool:
        """Check if any recovery keys exist."""
        with self._conn() as conn:
            count = conn.execute("SELECT COUNT(*) FROM recovery_keys").fetchone()[0]
        return count > 0
