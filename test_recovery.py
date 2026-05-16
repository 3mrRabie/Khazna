"""
test_recovery.py
────────────────
Comprehensive pytest test suite for the khazna recovery key system.

Covers
──────
• normalize_code  — whitespace, hyphens, case, mixed input
• generate_recovery_codes — format, uniqueness, charset
• create_recovery_data + attempt_recovery — round-trip correctness
• Wrong code rejected
• Code with varied formatting accepted (whitespace/hyphen tolerance)
• Code length validation
• Multiple records — correct record matched
• One-time-use simulation (code deleted after use)
• VaultManager.generate_recovery_keys + recover_with_code — end-to-end
• recover_with_code leaves vault locked on success
• recover_with_code leaves vault unchanged on failure
• New password too short rejected before touching the vault
• recover_with_code with no stored keys returns False
• Audit log entries written correctly

Run
───
    pytest test_recovery.py -v
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# recovery module — pure unit tests (no vault required)
# ---------------------------------------------------------------------------

from recovery import (
    normalize_code,
    generate_recovery_codes,
    create_recovery_data,
    attempt_recovery,
    _CODE_LENGTH,
    _CODE_GROUP,
    _CODE_CHARSET,
    RecoveryRecord,
)
from encryption import generate_salt, KEY_LENGTH


# ── normalize_code ──────────────────────────────────────────────────────────

class TestNormalizeCode:
    """normalize_code must produce a consistent canonical form."""

    def test_canonical_formatted_code_unchanged(self):
        code = "ABCDE-FGHIJ-KLMNO-PQRST"
        result = normalize_code(code)
        assert result == "ABCDEFGHIJKLMNOPQRST"

    def test_removes_hyphens(self):
        assert normalize_code("AB-CD-EF-GH-IJ-KL-MN-OP-QR-ST") == "ABCDEFGHIJKLMNOPQRST"

    def test_strips_leading_trailing_spaces(self):
        assert normalize_code("  ABCDEFGHIJKLMNOPQRST  ") == "ABCDEFGHIJKLMNOPQRST"

    def test_strips_internal_spaces(self):
        assert normalize_code("ABCDE FGHIJ KLMNO PQRST") == "ABCDEFGHIJKLMNOPQRST"

    def test_strips_newlines_and_tabs(self):
        assert normalize_code("ABCDE\nFGHIJ\tKLMNO\r\nPQRST") == "ABCDEFGHIJKLMNOPQRST"

    def test_uppercases_lowercase_input(self):
        assert normalize_code("abcde-fghij-klmno-pqrst") == "ABCDEFGHIJKLMNOPQRST"

    def test_mixed_case_and_separators(self):
        assert normalize_code("  abCde - fghiJ-KLMNO - pqrst  ") == "ABCDEFGHIJKLMNOPQRST"

    def test_empty_string_produces_empty(self):
        assert normalize_code("") == ""

    def test_only_hyphens_produces_empty(self):
        assert normalize_code("----") == ""

    def test_digits_preserved(self):
        result = normalize_code("12345-67890-ABCDE-FGHIJ")
        assert result == "1234567890ABCDEFGHIJ"


# ── generate_recovery_codes ─────────────────────────────────────────────────

class TestGenerateRecoveryCodes:

    def test_returns_correct_count(self):
        codes = generate_recovery_codes(count=8)
        assert len(codes) == 8

    def test_custom_count(self):
        assert len(generate_recovery_codes(count=4)) == 4

    def test_code_format(self):
        """Each code must be XXXXX-XXXXX-XXXXX-XXXXX."""
        for code in generate_recovery_codes(count=20):
            parts = code.split("-")
            assert len(parts) == _CODE_LENGTH // _CODE_GROUP, f"Wrong group count: {code!r}"
            for part in parts:
                assert len(part) == _CODE_GROUP, f"Wrong group length: {part!r}"
                assert all(c in _CODE_CHARSET for c in part), f"Illegal char in: {part!r}"

    def test_codes_are_unique(self):
        codes = generate_recovery_codes(count=100)
        assert len(set(codes)) == 100

    def test_normalised_length(self):
        for code in generate_recovery_codes(count=20):
            assert len(normalize_code(code)) == _CODE_LENGTH


# ── create_recovery_data + attempt_recovery ─────────────────────────────────

@pytest.fixture()
def master_key() -> bytes:
    """A realistic 32-byte AES key."""
    return os.urandom(KEY_LENGTH)


@pytest.fixture()
def codes_and_records(master_key):
    codes   = generate_recovery_codes(count=8)
    records = create_recovery_data(codes, master_key)
    return codes, records, master_key


class TestRoundTrip:

    def test_each_valid_code_recovers_master_key(self, codes_and_records):
        codes, records, master_key = codes_and_records
        for i, code in enumerate(codes):
            result = attempt_recovery(code, records)
            assert result == master_key, f"Code {i} failed to recover master key"

    def test_wrong_code_returns_none(self, codes_and_records):
        _, records, _ = codes_and_records
        fake_code = "AAAAA-AAAAA-AAAAA-AAAAA"
        assert attempt_recovery(fake_code, records) is None

    def test_truncated_code_returns_none(self, codes_and_records):
        codes, records, _ = codes_and_records
        assert attempt_recovery(codes[0][:10], records) is None

    def test_empty_code_returns_none(self, codes_and_records):
        _, records, _ = codes_and_records
        assert attempt_recovery("", records) is None

    def test_empty_records_returns_none(self):
        assert attempt_recovery("ABCDE-FGHIJ-KLMNO-PQRST", []) is None


class TestFormatTolerance:
    """The backend must accept any normalised variant of the same code."""

    def _round_trip(self, code_variant: str, codes: list[str],
                    records: list[RecoveryRecord], master_key: bytes) -> None:
        result = attempt_recovery(code_variant, records)
        assert result == master_key, (
            f"Code variant {code_variant!r} was rejected — normalised to "
            f"{normalize_code(code_variant)!r}"
        )

    def test_without_hyphens(self, codes_and_records):
        codes, records, master_key = codes_and_records
        for code in codes:
            self._round_trip(code.replace("-", ""), codes, records, master_key)

    def test_lowercase(self, codes_and_records):
        codes, records, master_key = codes_and_records
        for code in codes:
            self._round_trip(code.lower(), codes, records, master_key)

    def test_spaces_instead_of_hyphens(self, codes_and_records):
        codes, records, master_key = codes_and_records
        for code in codes:
            self._round_trip(code.replace("-", " "), codes, records, master_key)

    def test_leading_trailing_whitespace(self, codes_and_records):
        codes, records, master_key = codes_and_records
        for code in codes:
            self._round_trip(f"  {code}  ", codes, records, master_key)

    def test_mixed_case_and_no_hyphens(self, codes_and_records):
        codes, records, master_key = codes_and_records
        code = codes[0]
        raw  = normalize_code(code)
        mixed = raw[:10].lower() + raw[10:].upper()
        self._round_trip(mixed, codes, records, master_key)

    def test_extra_internal_newline(self, codes_and_records):
        codes, records, master_key = codes_and_records
        code = codes[0]
        # Simulate a user copying a code that got a newline inserted
        mangled = code[:11] + "\n" + code[11:]
        self._round_trip(mangled, codes, records, master_key)


class TestMultipleRecords:

    def test_correct_record_matched_among_many(self, master_key):
        codes   = generate_recovery_codes(count=8)
        records = create_recovery_data(codes, master_key)

        # Every code must resolve to the original master key
        for code in codes:
            assert attempt_recovery(code, records) == master_key

    def test_one_code_does_not_unlock_another_slot(self, master_key):
        codes   = generate_recovery_codes(count=8)
        records = create_recovery_data(codes, master_key)

        # Tamper with one record's code_hash — it must fail; others must pass
        tampered = list(records)
        original_record = tampered[3]
        tampered[3] = RecoveryRecord(
            salt          = original_record.salt,
            code_hash     = os.urandom(len(original_record.code_hash)),
            encrypted_key = original_record.encrypted_key,
            created_at    = original_record.created_at,
        )

        # Code 3 should fail; code 0 should still work
        assert attempt_recovery(codes[3], tampered) is None
        assert attempt_recovery(codes[0], tampered) == master_key


# ---------------------------------------------------------------------------
# VaultManager end-to-end tests
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_path(tmp_path):
    return str(tmp_path / "vault.db")


@pytest.fixture()
def vault(db_path):
    from app_logic import VaultManager
    v = VaultManager(db_path=db_path)
    v.setup_vault("V@ultP@ss99!")
    return v


class TestVaultManagerRecovery:

    def test_generate_recovery_keys_returns_eight_codes(self, vault):
        codes = vault.generate_recovery_keys()
        assert len(codes) == 8

    def test_has_recovery_keys_true_after_generation(self, vault):
        vault.generate_recovery_keys()
        assert vault.has_recovery_keys() is True

    def test_has_recovery_keys_false_before_generation(self, vault):
        assert vault.has_recovery_keys() is False

    def test_recover_with_valid_code_returns_true(self, vault):
        codes = vault.generate_recovery_keys()
        ok    = vault.recover_with_code(codes[0], "NewP@ss99!")
        assert ok is True

    def test_vault_is_locked_after_successful_recovery(self, vault):
        codes = vault.generate_recovery_keys()
        vault.recover_with_code(codes[0], "NewP@ss99!")
        assert vault.is_locked is True

    def test_new_password_works_after_recovery(self, vault):
        codes = vault.generate_recovery_keys()
        vault.recover_with_code(codes[0], "NewP@ss99!")
        # Must be able to unlock with the new password
        assert vault.unlock("NewP@ss99!") is True

    def test_old_password_rejected_after_recovery(self, vault):
        codes = vault.generate_recovery_keys()
        vault.recover_with_code(codes[0], "NewP@ss99!")
        assert vault.unlock("V@ultP@ss99!") is False

    def test_recovery_codes_invalidated_after_use(self, vault):
        codes = vault.generate_recovery_keys()
        code  = codes[0]
        vault.recover_with_code(code, "NewP@ss99!")
        # Unlock with new password and try to recover again — should fail
        vault.unlock("NewP@ss99!")
        ok = vault.recover_with_code(code, "AnotherP@ss!")
        assert ok is False

    def test_has_recovery_keys_false_after_successful_recovery(self, vault):
        codes = vault.generate_recovery_keys()
        vault.recover_with_code(codes[0], "NewP@ss99!")
        vault.unlock("NewP@ss99!")
        assert vault.has_recovery_keys() is False

    def test_recover_with_invalid_code_returns_false(self, vault):
        vault.generate_recovery_keys()
        ok = vault.recover_with_code("AAAAA-AAAAA-AAAAA-AAAAA", "NewP@ss99!")
        assert ok is False

    def test_vault_still_usable_after_failed_recovery(self, vault):
        """Failed recovery must leave the vault state completely unchanged."""
        vault.generate_recovery_keys()
        vault.recover_with_code("WRONG-WRONG-WRONG-WRONG", "NewP@ss99!")
        # Original password must still work
        assert vault.unlock("V@ultP@ss99!") is True

    def test_recover_with_no_keys_stored_returns_false(self, vault):
        ok = vault.recover_with_code("ABCDE-FGHIJ-KLMNO-PQRST", "NewP@ss99!")
        assert ok is False

    def test_recover_with_short_new_password_raises(self, vault):
        codes = vault.generate_recovery_keys()
        with pytest.raises(ValueError, match="8"):
            vault.recover_with_code(codes[0], "short")

    def test_recover_preserves_existing_entries(self, vault, db_path):
        """All encrypted entries must still be readable after recovery."""
        from models import PasswordEntry

        # Add a test entry before recovery
        entry = PasswordEntry(
            site_name="GitHub", url="https://github.com",
            username="alice", password="Gh1tHub$ecure!",
        )
        vault.add_entry(entry)

        codes = vault.generate_recovery_keys()
        vault.recover_with_code(codes[0], "NewP@ss99!")
        vault.unlock("NewP@ss99!")
        entries = vault.get_all_entries()
        assert any(e.site_name == "GitHub" for e in entries)
        assert any(e.password  == "Gh1tHub$ecure!" for e in entries)

    def test_recovery_code_format_tolerance(self, vault):
        """
        The same code presented without hyphens, in lowercase, or with
        surrounding whitespace must all produce a successful recovery.
        """
        codes = vault.generate_recovery_keys()
        code  = codes[0]

        # Variant: no hyphens, lowercase
        variant = normalize_code(code).lower()

        ok = vault.recover_with_code(variant, "NewP@ss99!")
        assert ok is True

    def test_audit_log_written_on_success(self, vault):
        codes = vault.generate_recovery_keys()
        vault.recover_with_code(codes[0], "NewP@ss99!")
        logs = vault.get_audit_logs(50)
        event_types = [log.event_type for log in logs]
        assert "RECOVERY_USED" in event_types
        # The successful log entry must have success=True
        used_logs = [l for l in logs if l.event_type == "RECOVERY_USED" and l.success]
        assert len(used_logs) >= 1

    def test_audit_log_written_on_failure(self, vault):
        vault.generate_recovery_keys()
        vault.recover_with_code("WRONG-WRONG-WRONG-WRONG", "NewP@ss99!")
        logs = vault.get_audit_logs(50)
        failed_logs = [l for l in logs
                       if l.event_type == "RECOVERY_USED" and not l.success]
        assert len(failed_logs) >= 1

    def test_second_set_of_codes_replaces_first(self, vault):
        """Generating codes twice must replace the first batch."""
        first_codes  = vault.generate_recovery_keys()
        second_codes = vault.generate_recovery_keys()

        # First batch must now be invalid
        ok_first  = vault.recover_with_code(first_codes[0],  "NewP@ss1!")
        assert ok_first is False

        # Second batch must still work
        ok_second = vault.recover_with_code(second_codes[0], "NewP@ss1!")
        assert ok_second is True


# ---------------------------------------------------------------------------
# Helper imported from recovery (needed for format-tolerance test above)
# ---------------------------------------------------------------------------
# (normalize_code is already imported at the top of this file)
