"""
models.py
─────────
Pure data models for the vault. No encryption, no I/O – just structured
containers with (de)serialisation helpers.

These are the types that flow between every layer of the application.
All mutable default fields use `field(default_factory=…)` to avoid the
classic Python "shared mutable default" pitfall.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


# ──────────────────────────────────────────────
# Password entry
# ──────────────────────────────────────────────

@dataclass
class PasswordEntry:
    """
    Represents a single credential record.

    ``password`` is always plaintext **in memory**. It is encrypted before
    being handed to the storage layer and decrypted on read-back.  No code
    outside encryption.py / storage.py should ever write plaintext
    passwords to disk.
    """

    id:          Optional[int]  = None
    site_name:   str            = ""
    url:         str            = ""
    username:    str            = ""
    password:    str            = ""       # plaintext in RAM only
    notes:       str            = ""
    tags:        List[str]      = field(default_factory=list)
    favorite:    bool           = False
    category:    str            = "Other"  # Feature 5: entry category
    created_at:  Optional[datetime] = None
    modified_at: Optional[datetime] = None

    # ── Serialisation ─────────────────────────

    def to_dict(self) -> dict:
        return {
            "id":          self.id,
            "site_name":   self.site_name,
            "url":         self.url,
            "username":    self.username,
            "password":    self.password,
            "notes":       self.notes,
            "tags":        ",".join(self.tags),
            "favorite":    self.favorite,
            "category":    self.category,
            "created_at":  self.created_at.isoformat()  if self.created_at  else None,
            "modified_at": self.modified_at.isoformat() if self.modified_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PasswordEntry":
        raw_tags = data.get("tags", "") or ""
        tag_list = [t.strip() for t in raw_tags.split(",") if t.strip()]

        def _dt(val: Optional[str]) -> Optional[datetime]:
            if not val:
                return None
            try:
                return datetime.fromisoformat(val)
            except ValueError:
                return None

        return cls(
            id          = data.get("id"),
            site_name   = data.get("site_name",  "") or "",
            url         = data.get("url",        "") or "",
            username    = data.get("username",   "") or "",
            password    = data.get("password",   "") or "",
            notes       = data.get("notes",      "") or "",
            tags        = tag_list,
            favorite    = bool(data.get("favorite", False)),
            category    = data.get("category", "Other") or "Other",
            created_at  = _dt(data.get("created_at")),
            modified_at = _dt(data.get("modified_at")),
        )

    def display_name(self) -> str:
        """Best human-readable label for this entry."""
        return self.site_name or self.url or f"Entry #{self.id}"

    def matches_query(self, q: str) -> bool:
        """Case-insensitive search across site_name, username, url, tags, category."""
        q = q.lower()
        return (
            q in self.site_name.lower()
            or q in self.username.lower()
            or q in self.url.lower()
            or q in self.category.lower()
            or any(q in t.lower() for t in self.tags)
        )

    # ── Smart search (Feature 2) ──────────────

    # Field weights for ranked search
    _FIELD_WEIGHTS = {
        "site_name": 10,
        "username":  7,
        "url":       6,
        "category":  5,
        "tags":      4,
        "notes":     2,
    }

    def smart_search_score(self, query: str) -> float:
        """
        Multi-token ranked search.  Returns a relevance score > 0 for
        matches, 0 for non-matches.

        Tokenises the query by whitespace and scores each token against
        every searchable field.  Scoring hierarchy:
            exact field match  > starts-with > substring

        All tokens must match at least one field (AND semantics).
        """
        if not query or not query.strip():
            return 0.0

        tokens = query.lower().split()
        if not tokens:
            return 0.0

        fields = {
            "site_name": self.site_name.lower(),
            "username":  self.username.lower(),
            "url":       self.url.lower(),
            "category":  self.category.lower(),
            "tags":      " ".join(t.lower() for t in self.tags),
            "notes":     self.notes.lower(),
        }

        total_score = 0.0

        for token in tokens:
            token_score = 0.0
            matched = False

            for field_name, field_value in fields.items():
                if not field_value:
                    continue
                weight = self._FIELD_WEIGHTS.get(field_name, 1)

                if field_value == token:
                    # Exact match on entire field
                    token_score += weight * 3.0
                    matched = True
                elif field_value.startswith(token):
                    # Prefix match
                    token_score += weight * 2.0
                    matched = True
                elif token in field_value:
                    # Substring match
                    token_score += weight * 1.0
                    matched = True
                else:
                    # Check individual words in the field
                    words = field_value.split()
                    for word in words:
                        # Strip common URL chars for better matching
                        clean = word.strip("/:.-@")
                        if clean == token:
                            token_score += weight * 2.5
                            matched = True
                            break
                        elif clean.startswith(token):
                            token_score += weight * 1.5
                            matched = True
                            break

            if not matched:
                return 0.0  # AND semantics: all tokens must match

            total_score += token_score

        # Bonus for favourite entries
        if self.favorite:
            total_score *= 1.1

        return total_score


# ──────────────────────────────────────────────
# Audit log entry
# ──────────────────────────────────────────────

@dataclass
class AuditLog:
    """
    Immutable record of a security-relevant event.

    event_type examples: LOGIN_SUCCESS, LOGIN_FAILED, ENTRY_ADDED,
    ENTRY_DELETED, VAULT_LOCKED, CSV_IMPORT, BACKUP_EXPORTED …
    """

    id:          Optional[int]      = None
    timestamp:   Optional[datetime] = None
    event_type:  str                = ""
    description: str                = ""
    success:     bool               = True

    def to_dict(self) -> dict:
        return {
            "id":          self.id,
            "timestamp":   self.timestamp.isoformat() if self.timestamp else None,
            "event_type":  self.event_type,
            "description": self.description,
            "success":     self.success,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AuditLog":
        ts_raw = data.get("timestamp")
        ts = datetime.fromisoformat(ts_raw) if ts_raw else None
        return cls(
            id          = data.get("id"),
            timestamp   = ts,
            event_type  = data.get("event_type",  ""),
            description = data.get("description", ""),
            success     = bool(data.get("success", True)),
        )

    def icon(self) -> str:
        """UTF-8 icon suitable for GUI display."""
        if not self.success:
            return "✗"
        icons = {
            "LOGIN_SUCCESS":       "🔓",
            "LOGIN_FAILED":        "✗",
            "VAULT_LOCKED":        "🔒",
            "VAULT_CREATED":       "🆕",
            "ENTRY_ADDED":         "➕",
            "ENTRY_UPDATED":       "✏️",
            "ENTRY_DELETED":       "🗑",
            "CSV_IMPORT":          "📥",
            "BACKUP_EXPORTED":     "📤",
            "BACKUP_IMPORTED":     "📥",
            "PASSWORD_CHANGED":    "🔑",
            "RECOVERY_GENERATED":  "🛟",
            "RECOVERY_USED":       "🛟",
            "RECOVERY_INVALIDATED":"🛟",
            "BREACH_CHECK":        "🔍",
            "EXTENSION_CONNECTED": "🔌",
            "EXTENSION_SAVE":      "🔌",
        }
        return icons.get(self.event_type, "•")


# ──────────────────────────────────────────────
# Vault configuration / metadata
# ──────────────────────────────────────────────

@dataclass
class VaultConfig:
    """
    Per-vault security configuration stored in the vault_config table.

    ``salt`` and ``verification_token`` are raw bytes stored as
    base64 strings in SQLite.  They are never encrypted because they
    *must* be readable before the master password is known (to begin
    the key-derivation step).

    ``scrypt_n`` is stored per-vault so that:
    - Existing vaults opened with new code use the N they were created with.
    - New vaults use the current production default (2^17).
    - Upgrading N requires a password change (which re-derives with new N).
    """

    version:            str                 = "1.0"
    created_at:         Optional[datetime]  = None
    last_accessed:      Optional[datetime]  = None
    salt:               Optional[bytes]     = None
    verification_token: Optional[bytes]     = None
    failed_attempts:    int                 = 0
    lockout_until:      Optional[datetime]  = None
    # SEC-01: stored per-vault for backward compatibility
    scrypt_n:           int                 = 2 ** 17

    def is_locked_out(self) -> bool:
        if self.lockout_until is None:
            return False
        return datetime.now() < self.lockout_until

    def seconds_remaining(self) -> int:
        """Seconds left in the current lockout window (0 if not locked)."""
        if not self.is_locked_out():
            return 0
        delta = self.lockout_until - datetime.now()
        return max(0, int(delta.total_seconds()))
