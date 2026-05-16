"""
app_logic.py
────────────
Core application logic – authentication, CRUD, CSV import/export,
password tools, auto-lock, and clipboard management.

Security features implemented here
───────────────────────────────────
• Progressive lockout  – after MAX_FAILED_ATTEMPTS failures the vault is
  locked for an escalating duration (doubles each cycle).
• Auto-lock timer      – vault locks after a configurable idle timeout.
  The timer is reset on every user action.
• Clipboard auto-clear – passwords copied to the clipboard are cleared
  after CLIPBOARD_CLEAR_SECONDS (default 30 s).
• Key clearing         – on lock() the in-memory key is zero-filled before
  the reference is dropped.
• Atomic re-encryption – master password change is performed in a single
  SQLite transaction to prevent partial re-encryption on crash (SEC-04).
• Scrypt N stored per-vault – so existing vaults unlock correctly after a
  code upgrade increases the default N (SEC-01).
"""

from __future__ import annotations

import csv
import io
import logging
import os
import secrets
import threading
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Callable, List, Optional, Tuple
from urllib.parse import urlparse

if TYPE_CHECKING:
    from health import HealthReport

from categories import get_category_icon
from models import AuditLog, PasswordEntry
from normalizer import normalize_site_name

from encryption import (
    SCRYPT_N,
    check_password_strength,
    create_verification_token,
    derive_key,
    generate_password,
    generate_salt,
    verify_key,
    zero_bytearray,
)
from models import AuditLog, PasswordEntry, VaultConfig
from storage import StorageError, VaultStorage

_log = logging.getLogger("khazna.app_logic")


# ──────────────────────────────────────────────
# Tunable security constants
# ──────────────────────────────────────────────

MAX_FAILED_ATTEMPTS        = 5      # failures before first lockout
LOCKOUT_BASE_SECONDS       = 300    # 5-minute base lockout duration
LOCKOUT_MULTIPLIER         = 2      # each subsequent lockout doubles
AUTO_LOCK_DEFAULT_SECONDS  = 300    # 5 minutes idle → auto-lock
CLIPBOARD_CLEAR_SECONDS    = 30     # clipboard wipe delay
MAX_CSV_SIZE_BYTES         = 50 * 1024 * 1024   # SEC-06: 50 MB max CSV



# ──────────────────────────────────────────────
# Custom exceptions
# ──────────────────────────────────────────────

class AuthenticationError(Exception):
    """Wrong password or vault not initialised."""


class LockoutError(AuthenticationError):
    """Too many failed login attempts."""

    def __init__(self, message: str, lockout_until: datetime) -> None:
        super().__init__(message)
        self.lockout_until = lockout_until
        self.seconds_remaining = max(
            0, int((lockout_until - datetime.now()).total_seconds())
        )


# ──────────────────────────────────────────────
# VaultManager
# ──────────────────────────────────────────────

class VaultManager:
    """
    Façade that ties together storage, encryption, and security policy.

    Every public method that touches credential data calls _require_unlocked()
    which also resets the auto-lock timer, so timer drift is impossible.
    """

    def __init__(self, db_path: str = "vault.db") -> None:
        self._storage = VaultStorage(db_path)
        self._key: Optional[bytes] = None
        self._locked = True

        self._auto_lock_seconds = AUTO_LOCK_DEFAULT_SECONDS
        self._lock_timer:      Optional[threading.Timer] = None
        self._clipboard_timer: Optional[threading.Timer] = None
        self._lock_callback:   Optional[Callable[[], None]] = None

    # ── Properties ────────────────────────────

    @property
    def is_locked(self) -> bool:
        return self._locked

    @property
    def is_initialized(self) -> bool:
        """True if the vault has been set up with a master password."""
        return self._storage.load_vault_config() is not None

    # ── Vault initialisation ──────────────────

    def setup_vault(self, master_password: str) -> None:
        """
        First-time setup: derive key, store salt + verification token.
        Raises ValueError if the password is too weak.
        """
        if len(master_password) < 8:
            raise ValueError("Master password must be at least 8 characters.")

        salt  = generate_salt()
        key   = derive_key(master_password, salt, SCRYPT_N)
        token = create_verification_token(key)

        cfg = VaultConfig(
            version            = "1.0",
            created_at         = datetime.now(),
            salt               = salt,
            verification_token = token,
            failed_attempts    = 0,
            scrypt_n           = SCRYPT_N,   # SEC-01: persist the N used
        )
        self._storage.save_vault_config(cfg)
        self._storage.set_key(key)
        self._key    = key
        self._locked = False

        # SEC-03: audit log uses generic descriptions, not sensitive metadata
        self._storage.add_audit_log("VAULT_CREATED", "Vault initialised")
        self._start_auto_lock_timer()

    # ── Authentication ────────────────────────

    def unlock(self, master_password: str) -> bool:
        """
        Verify master_password and unlock the vault.
        """
        cfg = self._storage.load_vault_config()
        if cfg is None:
            raise AuthenticationError("Vault has not been initialised yet.")

        if cfg.is_locked_out():
            raise LockoutError(
                f"Account locked. Try again in {cfg.seconds_remaining()} seconds.",
                cfg.lockout_until,
            )
        elif cfg.lockout_until is not None:
            cfg.failed_attempts = 0
            cfg.lockout_until   = None

        # SEC-01: use the N stored with this vault (may differ from code default)
        key = derive_key(master_password, cfg.salt, cfg.scrypt_n)

        if not verify_key(key, cfg.verification_token):
            cfg.failed_attempts += 1
            lockout_until: Optional[datetime] = None

            if cfg.failed_attempts >= MAX_FAILED_ATTEMPTS:
                cycle     = cfg.failed_attempts // MAX_FAILED_ATTEMPTS
                duration  = LOCKOUT_BASE_SECONDS * (LOCKOUT_MULTIPLIER ** (cycle - 1))
                lockout_until = datetime.now() + timedelta(seconds=duration)

            self._storage.update_login_state(cfg.failed_attempts, lockout_until)
            # SEC-03: no sensitive data in the log description
            self._storage.add_audit_log(
                "LOGIN_FAILED",
                f"Failed attempt #{cfg.failed_attempts}",
                success=False,
            )

            if lockout_until:
                raise LockoutError(
                    f"Too many failed attempts. Locked for {LOCKOUT_BASE_SECONDS} seconds.",
                    lockout_until,
                )
            return False

        self._storage.update_login_state(0, None)
        self._storage.set_key(key)
        self._key    = key
        self._locked = False

        self._storage.add_audit_log("LOGIN_SUCCESS", "Vault unlocked")
        self._start_auto_lock_timer()
        return True

    def lock(self) -> None:
        """
        Lock the vault: cancel timers, zero-fill the key, discard it.
        Safe to call multiple times.
        """
        self._stop_auto_lock_timer()
        self._stop_clipboard_timer()

        if self._key is not None:
            buf = bytearray(self._key)
            zero_bytearray(buf)
            del buf
        self._key = None

        self._storage.clear_key()
        self._locked = True
        self._storage.add_audit_log("VAULT_LOCKED", "Vault locked")

    def change_master_password(
        self, old_password: str, new_password: str
    ) -> None:
        """
        SEC-04 FIX: Change master password and re-derive the key atomically.

        The entire re-encryption (all entries + vault config) is performed in
        a single SQLite transaction via storage.atomic_reencrypt().  A crash
        at any point leaves the database untouched.
        """
        self._require_unlocked()

        cfg = self._storage.load_vault_config()
        assert cfg is not None

        # Verify current password using the stored N for this vault
        old_key = derive_key(old_password, cfg.salt, cfg.scrypt_n)
        if not verify_key(old_key, cfg.verification_token):
            raise AuthenticationError("Current password is incorrect.")

        if len(new_password) < 8:
            raise ValueError("New password must be at least 8 characters.")

        # Read all entries while the old key is still active
        entries = self._storage.get_all_entries()

        # Generate new key material with a fresh salt.
        # Note: changing your password invalidates old backups — this is by
        # design.  The backup was encrypted with the old key, and restoring
        # it requires logging in with the old password.
        new_salt  = generate_salt()
        new_key   = derive_key(new_password, new_salt, SCRYPT_N)
        new_token = create_verification_token(new_key)

        # Atomically re-encrypt everything + update config in one transaction.
        # On success, storage.atomic_reencrypt() also calls set_key(new_key).
        self._storage.atomic_reencrypt(entries, new_key, new_salt, new_token, SCRYPT_N)

        # Update the in-memory key reference only after the DB commit succeeded
        if self._key is not None:
            buf = bytearray(self._key)
            zero_bytearray(buf)
            del buf
        self._key = new_key

        self._storage.add_audit_log("PASSWORD_CHANGED", "Master password changed")

    def migrate_schema(self) -> int:
        """
        Migrate plaintext site_name/tags to encrypted columns.
        Safe to call repeatedly; skips already-migrated rows.
        Call once after successful unlock.
        """
        if self._locked:
            return 0
        return self._storage.migrate_plaintext_to_encrypted()

    # ── Auto-lock ─────────────────────────────

    def set_auto_lock_timeout(self, seconds: int) -> None:
        """0 = disabled."""
        self._auto_lock_seconds = max(0, seconds)

    def set_lock_callback(self, cb: Callable[[], None]) -> None:
        """Called (from a background thread) when the vault auto-locks."""
        self._lock_callback = cb

    def reset_activity_timer(self) -> None:
        """Call on every user interaction to reset the idle countdown."""
        if not self._locked:
            self._start_auto_lock_timer()

    def _start_auto_lock_timer(self) -> None:
        self._stop_auto_lock_timer()
        if self._auto_lock_seconds > 0:
            t = threading.Timer(self._auto_lock_seconds, self._on_auto_lock)
            t.daemon = True
            t.start()
            self._lock_timer = t

    def _stop_auto_lock_timer(self) -> None:
        if self._lock_timer:
            self._lock_timer.cancel()
            self._lock_timer = None

    def _on_auto_lock(self) -> None:
        self.lock()
        if self._lock_callback:
            try:
                self._lock_callback()
            except Exception:
                pass

    # ── Guard helper ──────────────────────────

    def _require_unlocked(self) -> None:
        if self._locked:
            raise AuthenticationError("Vault is locked. Please unlock first.")
        self.reset_activity_timer()

    # ── CRUD ──────────────────────────────────

    def add_entry(self, entry: PasswordEntry) -> int:
        self._require_unlocked()
        entry.site_name = normalize_site_name(entry.site_name, entry.url)
        entry_id = self._storage.add_entry(entry)
        # SEC-03: use generic description, not the site name
        self._storage.add_audit_log("ENTRY_ADDED", "Entry created")
        return entry_id

    def update_entry(self, entry: PasswordEntry) -> None:
        self._require_unlocked()
        entry.site_name = normalize_site_name(entry.site_name, entry.url)
        self._storage.update_entry(entry)
        self._storage.add_audit_log("ENTRY_UPDATED", f"Entry #{entry.id} updated")

    def delete_entry(self, entry_id: int, site_name: str = "") -> None:
        self._require_unlocked()
        self._storage.delete_entry(entry_id)
        # SEC-03: use ID only, not the site name
        self._storage.add_audit_log("ENTRY_DELETED", f"Entry #{entry_id} deleted")

    def get_entry(self, entry_id: int) -> Optional[PasswordEntry]:
        self._require_unlocked()
        return self._storage.get_entry(entry_id)

    def get_all_entries(self) -> List[PasswordEntry]:
        self._require_unlocked()
        return self._storage.get_all_entries()

    def search_entries(self, query: str) -> List[PasswordEntry]:
        self._require_unlocked()
        if not query.strip():
            return self._storage.get_all_entries()
        return self._storage.search_entries_ranked(query.strip())

    def get_entries_by_tag(self, tag: str) -> List[PasswordEntry]:
        self._require_unlocked()
        return self._storage.get_entries_by_tag(tag)

    def get_favorite_entries(self) -> List[PasswordEntry]:
        self._require_unlocked()
        return self._storage.get_favorite_entries()

    def get_all_tags(self) -> List[str]:
        self._require_unlocked()
        return self._storage.get_all_tags()

    def get_all_categories(self) -> List[str]:
        self._require_unlocked()
        return self._storage.get_all_categories()

    def get_entry_count(self) -> int:
        # SEC-09: return 0 when locked — don't leak entry count metadata
        if self._locked:
            return 0
        return self._storage.get_entry_count()

    def toggle_favorite(self, entry: PasswordEntry) -> None:
        self._require_unlocked()
        entry.favorite = not entry.favorite
        self._storage.update_entry(entry)

    # ── CSV import ────────────────────────────

    def import_csv(
        self, csv_path: str
    ) -> Tuple[int, int, List[str]]:
        """
        Import credentials from a Chrome / Firefox CSV export.

        Returns (success_count, skipped_count, error_messages).
        """
        self._require_unlocked()

        # SEC-06 FIX: Reject oversized files before reading into memory
        try:
            csv_size = os.path.getsize(csv_path)
        except OSError as exc:
            return 0, 0, [f"Cannot access file: {exc}"]

        if csv_size > MAX_CSV_SIZE_BYTES:
            mb = csv_size // (1024 * 1024)
            return 0, 0, [
                f"CSV file too large ({mb} MB). Maximum is "
                f"{MAX_CSV_SIZE_BYTES // (1024 * 1024)} MB."
            ]

        success  = 0
        skipped  = 0
        errors: List[str] = []

        try:
            for encoding in ("utf-8-sig", "utf-8", "latin-1"):
                try:
                    with open(csv_path, "r", encoding=encoding) as fh:
                        content = fh.read()
                    break
                except UnicodeDecodeError:
                    continue
            else:
                errors.append("Could not decode the CSV file (tried utf-8 and latin-1)")
                return 0, 0, errors

            reader  = csv.DictReader(io.StringIO(content))
            headers = [h.lower().strip() for h in (reader.fieldnames or [])]
            source  = self._detect_csv_source(headers)

            existing_entries = self._storage.get_all_entries()
            seen_duplicates = set()
            for e in existing_entries:
                seen_duplicates.add(self._normalize_for_dedupe(e.url, e.username, e.password))

            for line_no, row in enumerate(reader, start=2):
                try:
                    entry = self._parse_csv_row(row, source)
                    if entry is None:
                        skipped += 1
                        continue

                    dedupe_key = self._normalize_for_dedupe(entry.url, entry.username, entry.password)
                    if dedupe_key in seen_duplicates:
                        skipped += 1
                        continue

                    seen_duplicates.add(dedupe_key)
                    self._storage.add_entry(entry)
                    success += 1

                except Exception as exc:
                    errors.append(f"Line {line_no}: {exc}")

        except FileNotFoundError:
            errors.append(f"File not found: {csv_path}")
        except Exception as exc:
            errors.append(f"Unexpected error: {exc}")

        self._storage.add_audit_log(
            "CSV_IMPORT",
            f"CSV import: {success} added, {skipped} skipped, {len(errors)} errors",
        )
        return success, skipped, errors

    def _normalize_for_dedupe(self, url: str, username: str, password: str) -> Tuple[str, str, str]:
        """Normalize fields for accurate duplicate detection during import."""
        norm_url = ""
        if url:
            url_str = url.strip()
            if "://" not in url_str:
                url_str = "http://" + url_str
            parsed = urlparse(url_str)
            host = (parsed.hostname or "").lower()
            path = parsed.path.rstrip('/')
            norm_url = f"{host}{path}"
            
        norm_user = (username or "").strip().lower()
        norm_pass = password or ""  # passwords are case sensitive
        
        return (norm_url, norm_user, norm_pass)

    def _detect_csv_source(self, headers: List[str]) -> str:
        if "httpRealm".lower() in headers or "formsubmiturl" in headers:
            return "firefox"
        if "name" in headers and "url" in headers and "password" in headers:
            return "chrome"
        return "generic"

    def _parse_csv_row(
        self, row: dict, source: str
    ) -> Optional[PasswordEntry]:
        """Normalise a CSV row into a PasswordEntry, or return None to skip."""
        norm = {k.lower().strip(): (v or "").strip() for k, v in row.items()}

        url = (
            norm.get("url")
            or norm.get("origin_url")
            or norm.get("hostname")
            or norm.get("formsubmiturl")
            or ""
        )
        username = (
            norm.get("username")
            or norm.get("login")
            or norm.get("user_name")
            or norm.get("user name")
            or norm.get("email")
            or ""
        )
        password = norm.get("password", "")
        site_name = (
            norm.get("name")
            or norm.get("title")
            or url
            or "Unknown"
        )
        site_name = normalize_site_name(site_name, url)
        notes = norm.get("note") or norm.get("notes") or norm.get("comment") or ""

        if not password or not site_name:
            return None

        return PasswordEntry(
            site_name = site_name,
            url       = url,
            username  = username,
            password  = password,
            notes     = notes,
            tags      = ["imported"],
        )

    @staticmethod
    def _domain_from_url(url: str) -> str:
        if not url:
            return ""
        try:
            netloc = urlparse(url).netloc
            if netloc.startswith("www."):
                netloc = netloc[4:]
            return netloc.split(":")[0]
        except Exception:
            return url

    # ── Password tools ────────────────────────

    def generate_password(self, **kwargs) -> str:
        return generate_password(**kwargs)

    def check_strength(self, password: str) -> dict:
        return check_password_strength(password)

    # ── Clipboard ─────────────────────────────

    def copy_password(self, password: str) -> None:
        """
        Copy password to clipboard (pyperclip fallback).
        The bridge layer prefers Qt's native clipboard; this method is kept
        for CLI / non-GUI use cases.
        """
        try:
            import pyperclip
            pyperclip.copy(password)
        except Exception:
            pass

        self._stop_clipboard_timer()
        t = threading.Timer(CLIPBOARD_CLEAR_SECONDS, self._wipe_clipboard)
        t.daemon = True
        t.start()
        self._clipboard_timer = t

    def _wipe_clipboard(self) -> None:
        try:
            import pyperclip
            pyperclip.copy("")
        except Exception:
            pass

    def _stop_clipboard_timer(self) -> None:
        if self._clipboard_timer:
            self._clipboard_timer.cancel()
            self._clipboard_timer = None

    # ── Backup / restore ──────────────────────

    def export_backup(self, path: str, password: str = "") -> None:
        self._require_unlocked()
        assert self._key is not None
        self._storage.export_encrypted_backup(path, self._key, password)
        self._storage.add_audit_log("BACKUP_EXPORTED", "Encrypted backup exported")

    def import_backup(self, path: str, password: str = "") -> int:
        self._require_unlocked()
        assert self._key is not None
        count = self._storage.import_encrypted_backup(path, self._key, password)
        self._storage.add_audit_log(
            "BACKUP_IMPORTED", f"Imported {count} entries from backup"
        )
        return count

    # ── Audit log ─────────────────────────────

    def get_audit_logs(self, limit: int = 200) -> List[AuditLog]:
        return self._storage.get_audit_logs(limit)

    # ── Categories (Feature 5) ────────────────

    def detect_category(self, url: str = "", site_name: str = "") -> str:
        """Auto-detect a category from url/site_name using the category engine."""
        from categories import detect_category as _detect
        return _detect(url=url, site_name=site_name)

    def get_all_categories(self) -> List[str]:
        """Return all categories currently in use across entries."""
        self._require_unlocked()
        return self._storage.get_all_categories()

    def get_entries_by_category(self, category: str) -> List[PasswordEntry]:
        """Return entries matching a specific category."""
        self._require_unlocked()
        return self._storage.get_entries_by_category(category)

    # ── Health analysis (Feature 4) ───────────

    def analyze_health(self) -> "HealthReport":
        """Run a full password health analysis on all entries."""
        from health import PasswordHealthAnalyzer
        self._require_unlocked()
        entries = self.get_all_entries()
        analyzer = PasswordHealthAnalyzer()
        return analyzer.analyze(entries)

    # ── Breach checking (Feature 7) ───────────

    def check_breach(self, password: str) -> dict:
        """Check a single password against HIBP (k-anonymity)."""
        from breach_check import check_password_breach
        result = check_password_breach(password)
        return {
            "is_breached": result.is_breached,
            "count": result.count,
            "error": result.error or "",
        }

    # ── Recovery keys (Feature 6) ─────────────

    def generate_recovery_keys(self) -> List[str]:
        """
        Generate recovery codes and store them.

        Returns the plaintext codes — these are shown ONCE to the user
        and cannot be recovered after this call returns.

        Calling this method again will invalidate all previously generated
        codes (they are replaced in the database).
        """
        from recovery import generate_recovery_codes, create_recovery_data
        self._require_unlocked()
        assert self._key is not None

        codes = generate_recovery_codes(count=8)
        records = create_recovery_data(codes, self._key)
        self._storage.save_recovery_keys(records)
        self._storage.add_audit_log(
            "RECOVERY_GENERATED",
            "Recovery keys generated (8 codes)",
        )
        _log.info("Recovery keys generated and stored (%d codes)", len(codes))
        return codes

    def recover_with_code(self, code: str, new_password: str) -> bool:
        """
        Attempt vault recovery using a recovery code.

        On success:
          1. Decrypts the master key stored in the recovery record.
          2. Re-encrypts the entire vault under ``new_password``.
          3. Deletes all recovery codes (they are one-batch-use).
          4. Locks the vault — caller must log in with the new password.

        Returns True on success, False if the code is wrong or not found.
        Raises ValueError if ``new_password`` is too short.
        """
        from recovery import attempt_recovery

        if len(new_password) < 8:
            raise ValueError("New master password must be at least 8 characters.")

        records = self._storage.load_recovery_keys()
        if not records:
            _log.warning("recover_with_code: no recovery keys are stored")
            self._storage.add_audit_log(
                "RECOVERY_USED",
                "Recovery attempt failed — no recovery keys exist",
                success=False,
            )
            return False

        _log.info("recover_with_code: trying code against %d stored records", len(records))
        master_key = attempt_recovery(code, records)

        if master_key is None:
            _log.warning("recover_with_code: code did not match any record")
            self._storage.add_audit_log(
                "RECOVERY_USED", "Recovery attempt failed — invalid code", success=False
            )
            return False

        # ── Code verified; re-encrypt the vault under the new password ──────
        # Set the recovered key so the storage layer can decrypt existing entries.
        self._storage.set_key(master_key)
        self._key    = master_key
        self._locked = False

        try:
            new_salt  = generate_salt()
            new_key   = derive_key(new_password, new_salt, SCRYPT_N)
            new_token = create_verification_token(new_key)
            entries   = self._storage.get_all_entries()

            # Atomically re-encrypt everything in a single SQLite transaction.
            self._storage.atomic_reencrypt(
                entries, new_key, new_salt, new_token, SCRYPT_N
            )

            # Invalidate all recovery codes after successful recovery.
            # The user must generate a new set once logged in.
            self._storage.delete_recovery_keys()
            self._storage.add_audit_log(
                "RECOVERY_USED",
                "Vault recovered successfully — recovery keys invalidated",
            )
            _log.info("recover_with_code: vault re-encrypted successfully")

        except Exception as exc:
            _log.exception("recover_with_code: re-encryption failed")
            self.lock()   # wipe all in-memory key material
            return False

        # ── Lock the vault so the user must log in with their new password ───
        # This guarantees a clean, consistent state and prevents the caller
        # from operating on a vault whose VaultManager._key is the old
        # master key while storage._key is the new one.
        self.lock()
        return True

    def invalidate_recovery_keys(self) -> None:
        """Delete all recovery keys."""
        self._storage.delete_recovery_keys()
        self._storage.add_audit_log(
            "RECOVERY_INVALIDATED", "Recovery keys invalidated"
        )

    def has_recovery_keys(self) -> bool:
        """Check if recovery keys exist (does not require unlock)."""
        return self._storage.has_recovery_keys()
