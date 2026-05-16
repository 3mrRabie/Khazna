"""
encryption.py
─────────────
All cryptographic operations for the password vault.

Key derivation : scrypt  (memory-hard, brute-force resistant)
Symmetric enc  : AES-256-GCM  (authenticated encryption, tamper-proof)
RNG            : secrets module (CSPRNG, OS-backed)

NEVER import this module and use it to store plaintext passwords.
Every value that leaves this module is either a key, a nonce+ciphertext
blob, or a base64-encoded representation of one.
"""

import os
import re
import base64
import secrets
import string
from typing import Optional

from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidTag


# ──────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────

# SEC-01 FIX: Increased from 2^14 (~100ms) to 2^17 (~400-800ms).
# At N=2^14, a GPU farm can attempt ~2000-5000 guesses/second.
# N=2^17 raises the bar to ~10-30 guesses/second — far more resistant to
# offline brute-force after a DB theft.
# The actual N used at unlock is loaded from vault_config (backward compat).
SCRYPT_N      = 2 ** 17   # Production work factor for NEW vaults
SCRYPT_R      = 8          # block size
SCRYPT_P      = 1          # parallelism factor
KEY_LENGTH    = 32         # 256-bit key for AES-256
SALT_LENGTH   = 32         # 256-bit salt
NONCE_LENGTH  = 12         # 96-bit GCM nonce (NIST recommended)

# Known plaintext used to verify the master password without storing it.
# Changing this string invalidates existing vaults – do NOT edit after release.
_VERIFICATION_PLAINTEXT = b"SECUREVAULT_KEY_VERIFICATION_TOKEN_V1_DO_NOT_MODIFY"


# ──────────────────────────────────────────────
# Custom exceptions
# ──────────────────────────────────────────────

class EncryptionError(Exception):
    """Raised when encryption fails."""


class DecryptionError(Exception):
    """Raised when decryption or authentication fails."""


# ──────────────────────────────────────────────
# Key derivation
# ──────────────────────────────────────────────

def generate_salt() -> bytes:
    """Return a cryptographically secure 256-bit random salt."""
    return secrets.token_bytes(SALT_LENGTH)


def derive_key(password: str, salt: bytes, n: int = SCRYPT_N) -> bytes:
    """
    Derive a 256-bit encryption key from a master password using scrypt.

    scrypt is intentionally slow and memory-hard, making offline brute-force
    attacks orders of magnitude more expensive than PBKDF2 or bcrypt alone.

    Parameters
    ----------
    password : str   – master password (UTF-8 encoded internally)
    salt     : bytes – per-vault random salt (from generate_salt())
    n        : int   – scrypt CPU/memory cost factor (default: SCRYPT_N).
                       Pass the value stored in vault_config for existing vaults.

    Returns
    -------
    bytes – 32-byte (256-bit) raw key, suitable for AES-256-GCM
    """
    kdf = Scrypt(
        salt=salt,
        length=KEY_LENGTH,
        n=n,
        r=SCRYPT_R,
        p=SCRYPT_P,
        backend=default_backend(),
    )
    return kdf.derive(password.encode("utf-8"))


def create_verification_token(key: bytes) -> bytes:
    """
    Encrypt a known plaintext with the derived key.
    The resulting ciphertext is stored in the vault; on login we decrypt it
    and compare to the known plaintext – if it matches, the password is correct.
    This means we NEVER store the master password or its hash directly.
    """
    return encrypt_bytes(_VERIFICATION_PLAINTEXT, key)


def verify_key(key: bytes, token: bytes) -> bool:
    """
    Return True if the key successfully decrypts the verification token.
    Any decryption or authentication failure returns False silently so as
    not to leak timing or structural information.
    """
    try:
        plaintext = decrypt_bytes(token, key)
        # Constant-time comparison to resist timing attacks
        return secrets.compare_digest(plaintext, _VERIFICATION_PLAINTEXT)
    except Exception:
        return False


# ──────────────────────────────────────────────
# AES-256-GCM primitives
# ──────────────────────────────────────────────

def encrypt_bytes(plaintext: bytes, key: bytes) -> bytes:
    """
    Encrypt *plaintext* with AES-256-GCM using a fresh random nonce.

    Wire format: nonce (12 bytes) || ciphertext+tag (variable)

    GCM provides both confidentiality and integrity; any tampering with the
    ciphertext or nonce causes decryption to raise DecryptionError.
    """
    if len(key) != KEY_LENGTH:
        raise EncryptionError(
            f"Key must be exactly {KEY_LENGTH} bytes (got {len(key)})"
        )

    nonce = secrets.token_bytes(NONCE_LENGTH)

    try:
        aesgcm = AESGCM(key)
        # encrypt() appends the 16-byte GCM authentication tag automatically
        ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data=None)
    except Exception as exc:
        raise EncryptionError(f"AES-GCM encryption failed: {exc}") from exc

    return nonce + ciphertext


def decrypt_bytes(blob: bytes, key: bytes) -> bytes:
    """
    Decrypt a blob produced by encrypt_bytes().

    Raises DecryptionError on wrong key, truncated data, or any tampering.
    """
    if len(key) != KEY_LENGTH:
        raise DecryptionError(
            f"Key must be exactly {KEY_LENGTH} bytes (got {len(key)})"
        )

    min_length = NONCE_LENGTH + 16  # nonce + GCM tag
    if len(blob) < min_length:
        raise DecryptionError("Ciphertext blob is too short to be valid")

    nonce      = blob[:NONCE_LENGTH]
    ciphertext = blob[NONCE_LENGTH:]

    try:
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ciphertext, associated_data=None)
    except InvalidTag:
        raise DecryptionError(
            "Decryption failed: wrong key or ciphertext has been tampered with"
        )
    except Exception as exc:
        raise DecryptionError(f"AES-GCM decryption error: {exc}") from exc


def encrypt_str(plaintext: str, key: bytes) -> str:
    """Encrypt a string value and return a URL-safe base64 string."""
    raw = encrypt_bytes(plaintext.encode("utf-8"), key)
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decrypt_str(encoded: str, key: bytes) -> str:
    """Decrypt a value produced by encrypt_str()."""
    raw = base64.urlsafe_b64decode(encoded.encode("ascii"))
    return decrypt_bytes(raw, key).decode("utf-8")


# ──────────────────────────────────────────────
# Secure password generation
# ──────────────────────────────────────────────

def generate_password(
    length: int = 20,
    use_upper: bool = True,
    use_lower: bool = True,
    use_digits: bool = True,
    use_symbols: bool = True,
    exclude_ambiguous: bool = False,
    custom_exclude: str = "",
) -> str:
    """
    Generate a cryptographically secure random password.

    Uses `secrets.choice` (backed by os.urandom) for each character, then
    performs a Fisher-Yates shuffle also using `secrets.randbelow`.

    The function guarantees at least one character from every enabled class
    so the password always satisfies typical complexity requirements.
    """
    if length < 8:
        raise ValueError("Password length must be at least 8 characters")

    # Build per-class char sets (used for "at least one" guarantee)
    ambiguous = set("0O1lI|`'\"")

    def filtered(chars: str) -> str:
        result = chars
        if exclude_ambiguous:
            result = "".join(c for c in result if c not in ambiguous)
        if custom_exclude:
            result = "".join(c for c in result if c not in custom_exclude)
        return result

    class_sets = []
    if use_upper:
        s = filtered(string.ascii_uppercase)
        if s:
            class_sets.append(s)
    if use_lower:
        s = filtered(string.ascii_lowercase)
        if s:
            class_sets.append(s)
    if use_digits:
        s = filtered(string.digits)
        if s:
            class_sets.append(s)
    if use_symbols:
        s = filtered("!@#$%^&*()_+-=[]{}|;:,.<>?")
        if s:
            class_sets.append(s)

    if not class_sets:
        raise ValueError("No characters available with the current filter settings")

    # Full charset for filling remaining positions
    full_charset = "".join(class_sets)

    if length < len(class_sets):
        raise ValueError(
            f"Length ({length}) is too short to include one character "
            f"from each of the {len(class_sets)} selected character classes"
        )

    # Seed the password with one mandatory character from each class
    chars: list[str] = [secrets.choice(cs) for cs in class_sets]

    # Fill remaining positions from the full charset
    while len(chars) < length:
        chars.append(secrets.choice(full_charset))

    # Cryptographically secure Fisher-Yates shuffle
    for i in range(len(chars) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        chars[i], chars[j] = chars[j], chars[i]

    return "".join(chars)


# ──────────────────────────────────────────────
# Password strength analysis
# ──────────────────────────────────────────────

_COMMON_PATTERNS = [
    "password", "qwerty", "admin", "123456", "letmein",
    "welcome", "login", "pass", "iloveyou", "monkey",
]


def check_password_strength(password: str) -> dict:
    """
    Score a password from 0-100 and return a structured result.

    Returns
    -------
    dict with keys:
        score    : int  (0-100)
        level    : str  ("Very Weak" … "Very Strong")
        color    : str  (hex colour for UI use)
        feedback : list[str]  (actionable suggestions)
        details  : dict (individual property flags)
    """
    score    = 0
    feedback = []

    length = len(password)

    # ── Length score (max 35) ──────────────────
    if length >= 24:
        score += 35
    elif length >= 20:
        score += 30
    elif length >= 16:
        score += 25
    elif length >= 12:
        score += 18
    elif length >= 8:
        score += 10
    else:
        score += 0
        feedback.append("Use at least 8 characters")

    # ── Character variety (max 40) ─────────────
    has_upper  = bool(re.search(r"[A-Z]", password))
    has_lower  = bool(re.search(r"[a-z]", password))
    has_digit  = bool(re.search(r"\d",    password))
    has_symbol = bool(re.search(r"[^A-Za-z0-9]", password))

    variety = sum([has_upper, has_lower, has_digit, has_symbol])
    score += variety * 10

    if not has_upper:  feedback.append("Add uppercase letters")
    if not has_lower:  feedback.append("Add lowercase letters")
    if not has_digit:  feedback.append("Add numbers")
    if not has_symbol: feedback.append("Add special characters (!@#…)")

    # ── Entropy bonus (max 25) ─────────────────
    charset_size = (
        (26 if has_upper  else 0) +
        (26 if has_lower  else 0) +
        (10 if has_digit  else 0) +
        (32 if has_symbol else 0)
    )
    if charset_size > 0:
        import math
        entropy = length * math.log2(charset_size)
        if entropy >= 128: score += 25
        elif entropy >= 80: score += 18
        elif entropy >= 60: score += 10
        elif entropy >= 40: score +=  5

    # ── Penalties ─────────────────────────────
    if re.search(r"(.)\1{2,}", password):
        score -= 10
        feedback.append("Avoid repeated characters (e.g. 'aaa')")

    sequences = (
        "0123456789", "abcdefghijklmnopqrstuvwxyz",
        "qwertyuiop", "asdfghjkl", "zxcvbnm"
    )
    pw_lower = password.lower()
    for seq in sequences:
        for window in range(3, min(6, len(seq) + 1)):
            for i in range(len(seq) - window + 1):
                if seq[i:i+window] in pw_lower or seq[i:i+window][::-1] in pw_lower:
                    score -= 8
                    feedback.append("Avoid keyboard or sequential patterns")
                    break

    for pattern in _COMMON_PATTERNS:
        if pattern in pw_lower:
            score -= 20
            feedback.append("Avoid common words or patterns")
            break

    score = max(0, min(100, score))

    if score >= 80:
        level, color = "Very Strong", "#00c853"
    elif score >= 65:
        level, color = "Strong",      "#64dd17"
    elif score >= 45:
        level, color = "Medium",      "#ffab00"
    elif score >= 25:
        level, color = "Weak",        "#ff6d00"
    else:
        level, color = "Very Weak",   "#dd2c00"

    return {
        "score":    score,
        "level":    level,
        "color":    color,
        "feedback": list(dict.fromkeys(feedback)),   # deduplicated, ordered
        "details": {
            "length":     length,
            "has_upper":  has_upper,
            "has_lower":  has_lower,
            "has_digit":  has_digit,
            "has_symbol": has_symbol,
            "variety":    variety,
        },
    }


# ──────────────────────────────────────────────
# Memory helpers
# ──────────────────────────────────────────────

def zero_bytearray(buf: bytearray) -> None:
    """
    Overwrite a bytearray in-place with zeros to reduce the window during
    which sensitive key material is present in process memory.

    Note: CPython does not guarantee immediate memory reclamation, but
    this is a best-effort defence-in-depth measure.
    """
    for i in range(len(buf)):
        buf[i] = 0
