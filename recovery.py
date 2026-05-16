"""
recovery.py
───────────
Emergency recovery key system for forgotten master passwords.

Security design
───────────────
• 8 recovery codes are generated, each 20 chars of alphanumeric (CSPRNG).
• Codes are displayed ONCE to the user and never stored in plaintext.
• Each code has its own 32-byte random salt.
• A verification hash is stored alongside an encrypted copy of the master key.
• Recovery: enter any one valid code → derive key → decrypt master key →
  re-encrypt vault under new master password → invalidate all recovery codes.

Code format
───────────
  XXXXX-XXXXX-XXXXX-XXXXX   (20 uppercase alphanumeric chars, grouped by 5)

Normalisation rules (applied before every hash / derivation)
─────────────────────────────────────────────────────────────
  1. Strip ALL whitespace (spaces, tabs, newlines).
  2. Remove ALL hyphens.
  3. Upper-case the result.

This means the following inputs are all equivalent:
  "ABCDE-FGHIJ-KLMNO-PQRST"
  "abcde fghij klmno pqrst"
  "ABCDEFGHIJKLMNOPQRST"
  "  ABCDE-FGHIJ-KLMNO-PQRST  "
"""

from __future__ import annotations

import logging
import secrets
import string
from dataclasses import dataclass
from typing import List, Optional

from encryption import (
    SCRYPT_R,
    SCRYPT_P,
    KEY_LENGTH,
    SALT_LENGTH,
    decrypt_bytes,
    encrypt_bytes,
)

from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.backends import default_backend

_log = logging.getLogger("khazna.recovery")

# ──────────────────────────────────────────────
# Code format constants  (MUST NOT CHANGE after first vault is created)
# ──────────────────────────────────────────────
_CODE_LENGTH  = 20        # total alphanumeric chars, excluding separators
_CODE_GROUP   = 5         # chars per group
_CODE_CHARSET = string.ascii_uppercase + string.digits

# Lower scrypt N for recovery codes: the codes are 20 random uppercase
# alphanumeric chars (~103 bits entropy), making offline brute-force
# infeasible even at N=2^14.  This keeps recovery fast on weak hardware
# and avoids scanning 8 × 2 records (hash + decrypt per slot) for too long.
_RECOVERY_N   = 2 ** 14

# Purpose tag appended to salt before computing the verification hash.
# This domain-separates the hash KDF from the encryption KDF even though
# they are otherwise parameterised identically.
# ⚠ DO NOT CHANGE — altering this invalidates every stored recovery key.
_VERIFY_TAG = b"_verify"


# ──────────────────────────────────────────────
# Data model
# ──────────────────────────────────────────────

@dataclass
class RecoveryRecord:
    """
    Everything stored in the DB for one recovery code.
    The code itself is NEVER stored — only its derived verification hash
    and the master key encrypted under a key derived from the code.
    """
    salt:          bytes   # 32 random bytes, unique per code
    code_hash:     bytes   # scrypt(normalised_code, salt || _VERIFY_TAG) — for verification
    encrypted_key: bytes   # AES-GCM(master_key, scrypt(normalised_code, salt))
    created_at:    str     # ISO-8601 timestamp


# ──────────────────────────────────────────────
# Code generation
# ──────────────────────────────────────────────

def generate_recovery_codes(count: int = 8) -> List[str]:
    """
    Generate ``count`` cryptographically secure recovery codes.

    Each code is ``_CODE_LENGTH`` random chars from ``_CODE_CHARSET``,
    formatted as ``XXXXX-XXXXX-XXXXX-XXXXX`` for human readability.
    """
    codes: List[str] = []
    for _ in range(count):
        raw = "".join(secrets.choice(_CODE_CHARSET) for _ in range(_CODE_LENGTH))
        formatted = "-".join(
            raw[i : i + _CODE_GROUP]
            for i in range(0, _CODE_LENGTH, _CODE_GROUP)
        )
        codes.append(formatted)
    _log.debug("Generated %d recovery codes", len(codes))
    return codes


# ──────────────────────────────────────────────
# Normalisation  (single source of truth)
# ──────────────────────────────────────────────

def normalize_code(code: str) -> str:
    """
    Canonical normalisation applied to every code before hashing or
    key-derivation.  Must be used consistently at generation AND at
    verification time.

    Rules:
      • Remove all hyphens (the formatted separator character)
      • Remove all whitespace (trim + internal spaces/tabs/newlines)
      • Upper-case the result

    Returns the raw 20-character alphanumeric string.
    """
    # Split on whitespace to remove all internal whitespace tokens, then join.
    clean = "".join(code.split())       # strips all whitespace including \n \r \t
    clean = clean.replace("-", "")      # remove dash separators
    clean = clean.upper()               # canonicalise case
    return clean


# Internal alias kept for backward compatibility within this module.
_strip_code = normalize_code


# ──────────────────────────────────────────────
# KDF helpers
# ──────────────────────────────────────────────

def _derive_key_from_code(code: str, salt: bytes) -> bytes:
    """
    Derive a 256-bit encryption key from ``code`` using scrypt(salt).
    Used to encrypt / decrypt the master key stored in each RecoveryRecord.
    """
    clean = normalize_code(code)
    kdf = Scrypt(
        salt=salt,
        length=KEY_LENGTH,
        n=_RECOVERY_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        backend=default_backend(),
    )
    return kdf.derive(clean.encode("utf-8"))


def _hash_code(code: str, salt: bytes) -> bytes:
    """
    Derive a 256-bit verification hash from ``code`` using
    scrypt(salt || _VERIFY_TAG).

    The purpose tag domain-separates this derivation from
    ``_derive_key_from_code`` so that the verification value
    cannot be repurposed as an encryption key.
    """
    verify_salt = salt + _VERIFY_TAG
    kdf = Scrypt(
        salt=verify_salt,
        length=KEY_LENGTH,
        n=_RECOVERY_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        backend=default_backend(),
    )
    return kdf.derive(normalize_code(code).encode("utf-8"))


# ──────────────────────────────────────────────
# Record creation
# ──────────────────────────────────────────────

def create_recovery_data(
    codes: List[str],
    master_key: bytes,
) -> List[RecoveryRecord]:
    """
    Produce a ``RecoveryRecord`` for each code.

    Each record is independently keyed (unique salt per code) so that
    compromise of one code's derived key does not affect the others.
    """
    from datetime import datetime

    now = datetime.now().isoformat()
    records: List[RecoveryRecord] = []

    for code in codes:
        salt = secrets.token_bytes(SALT_LENGTH)

        # Derive an encryption key from this code.
        enc_key = _derive_key_from_code(code, salt)

        # Encrypt the master key under the code-derived key.
        encrypted_master = encrypt_bytes(master_key, enc_key)

        # Derive the verification hash under the domain-separated salt.
        code_hash = _hash_code(code, salt)

        records.append(RecoveryRecord(
            salt=salt,
            code_hash=code_hash,
            encrypted_key=encrypted_master,
            created_at=now,
        ))

    _log.info("Created %d recovery records", len(records))
    return records


# ──────────────────────────────────────────────
# Recovery
# ──────────────────────────────────────────────

def attempt_recovery(
    code: str,
    records: List[RecoveryRecord],
) -> Optional[bytes]:
    """
    Try to recover the vault master key using ``code``.

    The code is normalised (whitespace stripped, hyphens removed, uppercased)
    before comparison, so the user may enter it with or without separators.

    Algorithm per record
    ─────────────────────
      1. Recompute the verification hash from (code, record.salt).
      2. Constant-time compare with the stored hash.
      3. On match: derive the encryption key and decrypt the master key.
      4. Return the plaintext master key on success.

    Returns ``None`` if no record matches or if decryption fails.
    """
    if not records:
        _log.warning("attempt_recovery called with empty record list")
        return None

    normalised = normalize_code(code)
    _log.info("Attempting recovery: normalised code length=%d, records=%d",
              len(normalised), len(records))

    if len(normalised) != _CODE_LENGTH:
        _log.warning(
            "Recovery code has wrong length after normalisation: "
            "got %d, expected %d.  Input may be truncated or garbled.",
            len(normalised), _CODE_LENGTH,
        )
        # Do not return early — let the hash comparison fail gracefully so we
        # do not leak timing information about the expected length.

    matched_record_index: Optional[int] = None

    for i, record in enumerate(records):
        try:
            expected_hash = _hash_code(code, record.salt)
            if not secrets.compare_digest(expected_hash, record.code_hash):
                _log.debug("Record %d: verification hash mismatch", i)
                continue

            _log.info("Record %d: verification hash matched — decrypting master key", i)
            matched_record_index = i

        except Exception as exc:
            # Log the real reason so it is visible in the log file.
            _log.error("Record %d: error computing verification hash: %s", i, exc)
            continue

    if matched_record_index is None:
        _log.warning("No record matched the supplied recovery code")
        return None

    # Re-use the matched record for decryption.
    record = records[matched_record_index]
    try:
        enc_key = _derive_key_from_code(code, record.salt)
        master_key = decrypt_bytes(record.encrypted_key, enc_key)
        _log.info("Recovery decryption succeeded (record %d)", matched_record_index)
        return master_key
    except Exception as exc:
        _log.error(
            "Record %d: verification hash matched but decryption failed: %s",
            matched_record_index, exc,
        )
        return None
