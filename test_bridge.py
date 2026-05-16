"""
tests/test_bridge.py
─────────────────────
Pytest test suite for the PySide6 bridge layer.

Run headlessly:
    QT_QPA_PLATFORM=offscreen pytest tests/test_bridge.py -v

Requirements:
    pip install pytest PySide6 cryptography pyperclip
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

import pytest

# ── Headless Qt ─────────────────────────────────────────────────────
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Ensure project root is on sys.path so backend + bridge import cleanly
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtCore import QCoreApplication, QModelIndex

# One shared QCoreApplication for all tests
_app = QCoreApplication.instance() or QCoreApplication(sys.argv)


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture()
def db_path(tmp_path):
    return str(tmp_path / "test_vault.db")


@pytest.fixture()
def vault(db_path):
    """Unlocked VaultManager."""
    from app_logic import VaultManager
    v = VaultManager(db_path=db_path)
    v.setup_vault("T3stM@ster!")
    return v


@pytest.fixture()
def bridge(vault):
    """VaultBridge wrapping the unlocked vault."""
    from bridge import VaultBridge
    return VaultBridge(vault)


@pytest.fixture()
def entry_model(bridge):
    return bridge.entryModel


@pytest.fixture()
def audit_model(bridge):
    return bridge.auditModel


# ── EntryListModel ────────────────────────────────────────────────────

class TestEntryListModel:

    def test_password_always_masked(self, bridge, entry_model):
        from models import PasswordEntry
        from bridge import EntryListModel
        from datetime import datetime
        e = PasswordEntry(id=99, site_name="Test", username="u",
                          password="P@ssw0rd!", url="", notes="",
                          tags=[], favorite=False,
                          created_at=datetime.now(), modified_at=datetime.now())
        entry_model.load([e])
        idx = entry_model.index(0, 0)
        assert entry_model.data(idx, EntryListModel.PasswordRole) == "••••••••"

    def test_reveal_shows_plaintext(self, bridge, entry_model):
        from models import PasswordEntry
        from bridge import EntryListModel
        from datetime import datetime
        e = PasswordEntry(id=42, site_name="S", username="u",
                          password="SecretABC123!", url="", notes="",
                          tags=[], favorite=False,
                          created_at=datetime.now(), modified_at=datetime.now())
        entry_model.load([e])
        entry_model.set_revealed(42, True)
        idx = entry_model.index(0, 0)
        assert entry_model.data(idx, EntryListModel.PasswordRole) == "SecretABC123!"

    def test_mask_after_reveal(self, bridge, entry_model):
        from models import PasswordEntry
        from bridge import EntryListModel
        from datetime import datetime
        e = PasswordEntry(id=7, site_name="X", username="u",
                          password="Masked!99", url="", notes="",
                          tags=[], favorite=False,
                          created_at=datetime.now(), modified_at=datetime.now())
        entry_model.load([e])
        entry_model.set_revealed(7, True)
        entry_model.set_revealed(7, False)
        idx = entry_model.index(0, 0)
        assert entry_model.data(idx, EntryListModel.PasswordRole) == "••••••••"

    def test_role_names_present(self, entry_model):
        roles = entry_model.roleNames().values()
        for name in [b"siteName", b"username", b"password",
                     b"url", b"tags", b"favorite", b"revealed"]:
            assert name in roles, f"{name} role missing"

    def test_load_clears_revealed_set(self, entry_model):
        from models import PasswordEntry
        from bridge import EntryListModel
        from datetime import datetime
        e = PasswordEntry(id=1, site_name="A", username="u", password="pw",
                          url="", notes="", tags=[], favorite=False,
                          created_at=datetime.now(), modified_at=datetime.now())
        entry_model.load([e])
        entry_model.set_revealed(1, True)
        # Reload — revealed set should be cleared
        entry_model.load([e])
        idx = entry_model.index(0, 0)
        assert entry_model.data(idx, EntryListModel.PasswordRole) == "••••••••"

    def test_invalid_index_returns_none(self, entry_model):
        entry_model.load([])
        idx = entry_model.index(0, 0)
        assert entry_model.data(idx) is None


# ── VaultBridge – auth ────────────────────────────────────────────────

class TestVaultBridgeAuth:

    def test_is_initialized(self, bridge):
        assert bridge.isInitialized is True

    def test_is_not_locked_after_setup(self, bridge):
        assert bridge.isLocked is False

    def test_lock_clears_model(self, bridge, entry_model):
        bridge.addEntry("Site", "", "u", "P@ss1!", "", "", False)
        assert entry_model.rowCount() == 1
        bridge.lock()
        assert entry_model.rowCount() == 0
        assert bridge.isLocked is True

    def test_db_path_not_empty(self, bridge):
        assert len(bridge.dbPath) > 0


# ── VaultBridge – CRUD ────────────────────────────────────────────────

class TestVaultBridgeCrud:

    def test_add_entry_increments_count(self, bridge):
        before = bridge.entryCount
        bridge.addEntry("GitHub", "https://github.com", "user@x.com",
                        "G1tHub$ecure!", "notes", "work, dev", True)
        assert bridge.entryCount == before + 1

    def test_add_entry_appears_in_model(self, bridge, entry_model):
        from bridge import EntryListModel
        bridge.addEntry("Stripe", "https://stripe.com", "pay@x.com",
                        "Stripe$99!", "", "finance", False)
        assert entry_model.rowCount() >= 1
        found = False
        for r in range(entry_model.rowCount()):
            idx = entry_model.index(r, 0)
            if entry_model.data(idx, EntryListModel.SiteNameRole) == "Stripe":
                found = True
        assert found

    def test_get_entry_returns_plaintext_password(self, bridge, vault):
        bridge.addEntry("Shopify", "", "s@x.com", "Shop1fy$ecure!", "", "", False)
        eid = vault.get_all_entries()[-1].id
        data = bridge.getEntry(eid)
        assert data["password"] == "Shop1fy$ecure!"
        assert data["siteName"] == "Shopify"

    def test_update_entry(self, bridge, vault):
        bridge.addEntry("Old Name", "", "u", "OldP@ss1!", "", "", False)
        eid = vault.get_all_entries()[-1].id
        ok = bridge.updateEntry(eid, "New Name", "", "u2", "NewP@ss2!",
                                "", "updated", True)
        assert ok is True
        updated = vault.get_entry(eid)
        assert updated.site_name == "New Name"
        assert updated.favorite is True

    def test_delete_entry(self, bridge, vault):
        bridge.addEntry("ToDelete", "", "u", "D3l3te$!", "", "", False)
        before = bridge.entryCount
        eid = vault.get_all_entries()[-1].id
        ok = bridge.deleteEntry(eid)
        assert ok is True
        assert bridge.entryCount == before - 1

    def test_toggle_favorite(self, bridge, vault):
        bridge.addEntry("FavTest", "", "u", "F@v0rite!", "", "", False)
        eid = vault.get_all_entries()[-1].id
        e = vault.get_entry(eid)
        original = e.favorite
        bridge.toggleFavorite(eid)
        assert vault.get_entry(eid).favorite != original

    def test_add_entry_returns_false_on_locked_vault(self, bridge):
        bridge.lock()
        ok = bridge.addEntry("X", "", "u", "P@ss1!", "", "", False)
        assert ok is False


# ── VaultBridge – search / filter ────────────────────────────────────

class TestVaultBridgeFilter:

    def test_search_returns_matching_entries(self, bridge, entry_model):
        bridge.addEntry("Notion", "https://notion.so", "u@n.com",
                        "N0ti0n$!", "", "work", False)
        bridge.addEntry("Figma", "https://figma.com", "u@f.com",
                        "F1gm@!", "", "design", False)
        bridge.setSearchQuery("Notion")
        assert entry_model.rowCount() == 1

    def test_search_cleared_shows_all(self, bridge, entry_model):
        bridge.addEntry("A", "", "u", "P@ss1!", "", "", False)
        bridge.addEntry("B", "", "u", "P@ss2!", "", "", False)
        bridge.setSearchQuery("A")
        bridge.setSearchQuery("")
        assert entry_model.rowCount() == 2

    def test_filter_favorites(self, bridge, entry_model, vault):
        bridge.addEntry("Fav1", "", "u", "F@v1!", "", "", True)
        bridge.addEntry("NotFav", "", "u", "N0tF@v!", "", "", False)
        bridge.setFilter("favorites")
        assert entry_model.rowCount() == 1

    def test_filter_all(self, bridge, entry_model):
        bridge.addEntry("X", "", "u", "P@ss1!", "", "", False)
        bridge.addEntry("Y", "", "u", "P@ss2!", "", "", True)
        bridge.setFilter("all")
        assert entry_model.rowCount() == 2

    def test_tag_filter(self, bridge, entry_model):
        bridge.addEntry("Site1", "", "u", "P@ss1!", "", "banking", False)
        bridge.addEntry("Site2", "", "u", "P@ss2!", "", "social", False)
        bridge.setTagFilter("banking")
        assert entry_model.rowCount() == 1

    def test_get_all_tags(self, bridge):
        bridge.addEntry("S1", "", "u", "P@ss1!", "", "tagA, tagB", False)
        tags = bridge.getAllTags()
        assert "tagA" in tags
        assert "tagB" in tags


# ── VaultBridge – password tools ─────────────────────────────────────

class TestPasswordTools:

    def test_generate_password_correct_length(self, bridge):
        pw = bridge.generatePassword(24, True, True, True, True, False, "")
        assert len(pw) == 24

    def test_generate_password_emits_signal(self, bridge):
        received = []
        bridge.passwordGenerated.connect(lambda pw: received.append(pw))
        bridge.generatePassword(16, True, True, True, False, False, "")
        assert len(received) == 1
        assert len(received[0]) == 16

    def test_check_strength_emits_signal(self, bridge):
        received = []
        bridge.strengthResult.connect(
            lambda s, l, c, t: received.append((s, l, c, t))
        )
        bridge.checkStrength("weak")
        assert received[0][0] < 40   # low score

    def test_check_strength_strong_password(self, bridge):
        received = []
        bridge.strengthResult.connect(
            lambda s, l, c, t: received.append((s, l, c, t))
        )
        bridge.checkStrength("C0rrect-H0rse-Batt3ry-Staple!!!")
        assert received[0][0] > 60

    def test_check_strength_empty_emits_zero(self, bridge):
        received = []
        bridge.strengthResult.connect(
            lambda s, l, c, t: received.append((s, l, c, t))
        )
        bridge.checkStrength("")
        assert received[0][0] == 0


# ── VaultBridge – master password change ─────────────────────────────

class TestMasterPassword:

    def test_change_master_password_success(self, bridge, vault):
        ok = bridge.changeMasterPassword("T3stM@ster!", "N3wM@ster99!")
        assert ok is True
        vault.lock()
        assert vault.unlock("N3wM@ster99!") is True

    def test_change_master_password_wrong_old(self, bridge):
        errors = []
        bridge.errorOccurred.connect(lambda m: errors.append(m))
        ok = bridge.changeMasterPassword("wr0ng!", "N3wP@ss!")
        assert ok is False
        assert len(errors) > 0


# ── VaultBridge – audit log ───────────────────────────────────────────

class TestAuditLog:

    def test_refresh_populates_model(self, bridge, audit_model):
        bridge.addEntry("AuditTest", "", "u", "P@ss1!", "", "", False)
        bridge.refreshAuditLogs()
        assert audit_model.rowCount() > 0

    def test_audit_model_role_names(self, audit_model):
        from bridge import AuditLogModel
        roles = audit_model.roleNames().values()
        for name in [b"timestamp", b"eventType", b"description",
                     b"success", b"icon"]:
            assert name in roles


# ── AuditLogModel ─────────────────────────────────────────────────────

class TestAuditLogModel:

    def test_load_and_row_count(self, audit_model):
        from models import AuditLog
        from datetime import datetime
        logs = [
            AuditLog(id=1, timestamp=datetime.now(),
                     event_type="LOGIN_SUCCESS", description="ok", success=True),
            AuditLog(id=2, timestamp=datetime.now(),
                     event_type="LOGIN_FAILED",  description="bad", success=False),
        ]
        audit_model.load(logs)
        assert audit_model.rowCount() == 2

    def test_data_roles(self, audit_model):
        from models import AuditLog
        from bridge import AuditLogModel
        from datetime import datetime
        log = AuditLog(id=1, timestamp=datetime.now(),
                       event_type="ENTRY_ADDED", description="Added X", success=True)
        audit_model.load([log])
        idx = audit_model.index(0, 0)
        assert audit_model.data(idx, AuditLogModel.EventTypeRole) == "ENTRY_ADDED"
        assert audit_model.data(idx, AuditLogModel.SuccessRole) is True


# ── Worker classes ────────────────────────────────────────────────────

class TestWorkers:

    def test_unlock_worker_success(self, db_path):
        """UnlockWorker emits finished(True, '') on correct password."""
        from app_logic import VaultManager
        from bridge import UnlockWorker
        v = VaultManager(db_path=db_path)
        v.setup_vault("W0rk3rP@ss!")
        v.lock()

        results = []
        w = UnlockWorker(v, "W0rk3rP@ss!")
        w.finished.connect(lambda ok, msg: results.append((ok, msg)))
        w.run()   # run synchronously in test thread
        assert results[0][0] is True
        assert results[0][1] == ""

    def test_unlock_worker_wrong_password(self, db_path):
        from app_logic import VaultManager
        from bridge import UnlockWorker
        v = VaultManager(db_path=db_path)
        v.setup_vault("C0rrectP@ss!")
        v.lock()

        results = []
        w = UnlockWorker(v, "wr0ngP@ss!")
        w.finished.connect(lambda ok, msg: results.append((ok, msg)))
        w.run()
        assert results[0][0] is False

    def test_setup_worker_success(self, db_path):
        from app_logic import VaultManager
        from bridge import SetupWorker
        v = VaultManager(db_path=db_path)
        results = []
        w = SetupWorker(v, "S3tupP@ss99!")
        w.finished.connect(lambda ok, msg: results.append((ok, msg)))
        w.run()
        assert results[0][0] is True
        assert not v.is_locked

    def test_setup_worker_weak_password(self, db_path):
        from app_logic import VaultManager
        from bridge import SetupWorker
        v = VaultManager(db_path=db_path)
        results = []
        w = SetupWorker(v, "short")
        w.finished.connect(lambda ok, msg: results.append((ok, msg)))
        w.run()
        assert results[0][0] is False
