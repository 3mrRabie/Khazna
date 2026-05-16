"""
breach_check.py
───────────────
Privacy-preserving password breach checking via Have I Been Pwned (HIBP).

Uses k-anonymity:
1. SHA-1 hash the password locally
2. Send only the first 5 hex characters to HIBP's range API
3. Check if the full hash appears in the returned suffix list

NEVER sends the full password or full hash over the network.
User-triggered only, never automatic.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

_log = logging.getLogger("khazna.breach")

# HIBP API
_HIBP_API  = "https://api.pwnedpasswords.com/range/"
_TIMEOUT   = 10   # seconds
_USER_AGENT = "khazna-PasswordManager"


@dataclass
class BreachResult:
    """Result of a single password breach check."""
    is_breached: bool    = False
    count:       int     = 0       # number of times seen in breaches
    error:       Optional[str] = None


def check_password_breach(password: str) -> BreachResult:
    """
    Check a password against the HIBP Pwned Passwords API using
    k-anonymity (only the first 5 chars of the SHA-1 hash are sent).

    Returns a BreachResult with breach status, count, or error info.
    """
    if not password:
        return BreachResult(error="Empty password")

    try:
        # Step 1: SHA-1 hash the password
        sha1 = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
        prefix = sha1[:5]
        suffix = sha1[5:]

        # Step 2: Query HIBP with the prefix only
        url = f"{_HIBP_API}{prefix}"
        req = Request(url, headers={"User-Agent": _USER_AGENT})

        try:
            with urlopen(req, timeout=_TIMEOUT) as resp:
                body = resp.read().decode("utf-8")
        except URLError as exc:
            _log.warning("HIBP API request failed: %s", exc)
            return BreachResult(error=f"Network error: could not reach breach database")
        except TimeoutError:
            return BreachResult(error="Request timed out — try again later")

        # Step 3: Check if our suffix appears in the response
        for line in body.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(":")
            if len(parts) != 2:
                continue
            hash_suffix, count_str = parts
            if hash_suffix.upper() == suffix:
                count = int(count_str)
                return BreachResult(is_breached=True, count=count)

        # Not found — password is clean
        return BreachResult(is_breached=False, count=0)

    except Exception as exc:
        _log.exception("Unexpected error during breach check")
        return BreachResult(error=f"Unexpected error: {exc}")
