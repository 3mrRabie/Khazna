"""
bridge.py  — RECOVERY SECTION PATCH
─────────────────────────────────────
Drop-in replacement for the recovery slots in VaultBridge.

Root-cause fix
──────────────
The old recoverWithCode() called self._refresh_entries() and emitted
lockStateChanged / entryCountChanged BEFORE checking the new vault state.
Because app_logic.recover_with_code() now explicitly calls self.lock() at
the end (so the user must log in with their new password), the bridge was
trying to refresh entries on a locked vault, triggering StorageError and
masking the real success signal.

Additionally, the bridge emitted recoveryComplete(True, …) and then let
_refresh_entries fail silently, leaving the UI in an inconsistent state
where isLocked was True but the screen hadn't transitioned.

Fix
───
• Do NOT call _refresh_entries() after recovery — the vault is locked.
• Emit lockStateChanged so Main.qml transitions to the login screen.
• Pass a clear, actionable success message.
• On failure, include the normalised code length hint to help diagnose
  format problems during debugging.
• Expose a new hasRecoveryKeys Slot that does not require unlock.

This file shows ONLY the patched methods.  In your project, replace the
entire bridge.py with the version below (which is identical to the
original except for the three recovery methods).
"""
from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import (
    Property,
    QAbstractListModel,
    QModelIndex,
    QObject,
    Qt,
    QThread,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtGui import QGuiApplication

from app_logic import (
    CLIPBOARD_CLEAR_SECONDS,
    AuthenticationError,
    LockoutError,
    VaultManager,
)
from models import AuditLog, PasswordEntry

_log = logging.getLogger("khazna.bridge")


# ──────────────────────────────────────────────────────────────────────
# EntryListModel
# ──────────────────────────────────────────────────────────────────────

class EntryListModel(QAbstractListModel):
    """
    Exposes PasswordEntry objects to QML as a named-role list model.
    SECURITY: PasswordRole always returns "••••••••".
    """

    IdRole         = Qt.ItemDataRole.UserRole + 1
    SiteNameRole   = Qt.ItemDataRole.UserRole + 2
    UsernameRole   = Qt.ItemDataRole.UserRole + 3
    PasswordRole   = Qt.ItemDataRole.UserRole + 4
    UrlRole        = Qt.ItemDataRole.UserRole + 5
    NotesRole      = Qt.ItemDataRole.UserRole + 6
    TagsRole       = Qt.ItemDataRole.UserRole + 7
    FavoriteRole   = Qt.ItemDataRole.UserRole + 8
    ModifiedAtRole = Qt.ItemDataRole.UserRole + 9
    RevealedRole   = Qt.ItemDataRole.UserRole + 10
    CategoryRole   = Qt.ItemDataRole.UserRole + 11

    _ROLE_MAP: dict[int, bytes] = {
        IdRole:         b"entryId",
        SiteNameRole:   b"siteName",
        UsernameRole:   b"username",
        PasswordRole:   b"password",
        UrlRole:        b"url",
        NotesRole:      b"notes",
        TagsRole:       b"tags",
        FavoriteRole:   b"favorite",
        ModifiedAtRole: b"modifiedAt",
        RevealedRole:   b"revealed",
        CategoryRole:   b"category",
    }

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._entries: list[PasswordEntry] = []
        self._revealed: set[int] = set()

    def load(self, entries: list[PasswordEntry]) -> None:
        self.beginResetModel()
        self._entries = list(entries)
        self._revealed.clear()
        self.endResetModel()

    def entry_by_id(self, entry_id: int) -> Optional[PasswordEntry]:
        for e in self._entries:
            if e.id == entry_id:
                return e
        return None

    def set_revealed(self, entry_id: int, value: bool) -> None:
        for i, e in enumerate(self._entries):
            if e.id == entry_id:
                if value:
                    self._revealed.add(entry_id)
                else:
                    self._revealed.discard(entry_id)
                top = self.index(i, 0)
                self.dataChanged.emit(top, top, [self.PasswordRole, self.RevealedRole])
                return

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return len(self._entries)

    def roleNames(self) -> dict[int, bytes]:
        return self._ROLE_MAP

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._entries)):
            return None
        e = self._entries[index.row()]

        match role:
            case self.IdRole:         return e.id
            case self.SiteNameRole:   return e.site_name
            case self.UsernameRole:   return e.username
            case self.PasswordRole:
                return e.password if e.id in self._revealed else "••••••••"
            case self.UrlRole:        return e.url
            case self.NotesRole:      return e.notes
            case self.TagsRole:       return ", ".join(e.tags)
            case self.FavoriteRole:   return e.favorite
            case self.ModifiedAtRole:
                return e.modified_at.strftime("%Y-%m-%d") if e.modified_at else ""
            case self.RevealedRole:   return e.id in self._revealed
            case self.CategoryRole:   return e.category
            case _:                   return None


# ──────────────────────────────────────────────────────────────────────
# AuditLogModel
# ──────────────────────────────────────────────────────────────────────

class AuditLogModel(QAbstractListModel):

    TimestampRole   = Qt.ItemDataRole.UserRole + 1
    EventTypeRole   = Qt.ItemDataRole.UserRole + 2
    DescriptionRole = Qt.ItemDataRole.UserRole + 3
    SuccessRole     = Qt.ItemDataRole.UserRole + 4
    IconRole        = Qt.ItemDataRole.UserRole + 5

    _ROLE_MAP: dict[int, bytes] = {
        TimestampRole:   b"timestamp",
        EventTypeRole:   b"eventType",
        DescriptionRole: b"description",
        SuccessRole:     b"success",
        IconRole:        b"icon",
    }

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._logs: list[AuditLog] = []

    def load(self, logs: list[AuditLog]) -> None:
        self.beginResetModel()
        self._logs = list(logs)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return len(self._logs)

    def roleNames(self) -> dict[int, bytes]:
        return self._ROLE_MAP

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        log = self._logs[index.row()]
        match role:
            case self.TimestampRole:
                return log.timestamp.strftime("%Y-%m-%d %H:%M:%S") if log.timestamp else ""
            case self.EventTypeRole:   return log.event_type
            case self.DescriptionRole: return log.description
            case self.SuccessRole:     return log.success
            case self.IconRole:        return log.icon()
            case _:                    return None


# ──────────────────────────────────────────────────────────────────────
# Background workers
# ──────────────────────────────────────────────────────────────────────

class UnlockWorker(QObject):
    """Runs VaultManager.unlock() in a QThread."""

    finished = Signal(bool, str)
    lockout  = Signal(str, int)

    def __init__(self, vault: VaultManager, password: str) -> None:
        super().__init__()
        self._vault    = vault
        self._password = password

    @Slot()
    def run(self) -> None:
        try:
            ok = self._vault.unlock(self._password)
            self.finished.emit(ok, "" if ok else "Incorrect password. Please try again.")
        except LockoutError as exc:
            self.lockout.emit(str(exc), exc.seconds_remaining)
            self.finished.emit(False, str(exc))
        except AuthenticationError as exc:
            self.finished.emit(False, str(exc))
        except Exception as exc:
            _log.exception("Unexpected error during unlock")
            self.finished.emit(False, f"Unexpected error: {exc}")
        finally:
            self._password = "\x00" * len(self._password)
            self._password = ""


class SetupWorker(QObject):
    """Runs VaultManager.setup_vault() in a QThread."""

    finished = Signal(bool, str)

    def __init__(self, vault: VaultManager, password: str) -> None:
        super().__init__()
        self._vault    = vault
        self._password = password

    @Slot()
    def run(self) -> None:
        try:
            self._vault.setup_vault(self._password)
            self.finished.emit(True, "")
        except Exception as exc:
            _log.exception("Unexpected error during vault setup")
            self.finished.emit(False, str(exc))
        finally:
            self._password = "\x00" * len(self._password)
            self._password = ""


class AutoCategorizeWorker(QObject):
    """Iterates through all entries and attempts to assign a category."""
    finished = Signal(int, int)
    progress = Signal(int, int)

    def __init__(self, vault: VaultManager) -> None:
        super().__init__()
        self._vault = vault

    @Slot()
    def run(self) -> None:
        total = 0
        try:
            entries = self._vault.get_all_entries()
            total = len(entries)
            updated = 0
            for i, entry in enumerate(entries):
                new_cat = self._vault.detect_category(entry.url, entry.site_name)
                if new_cat != "Other" and entry.category != new_cat:
                    entry.category = new_cat
                    self._vault.update_entry(entry)
                    updated += 1
                if i % 10 == 0:
                    self.progress.emit(i + 1, total)
            self.finished.emit(updated, total)
        except Exception as exc:
            _log.exception("AutoCategorizeWorker failed")
            self.finished.emit(0, total)


class BulkNormalizeWorker(QObject):
    """Iterates through all entries and attempts to normalize their site names."""
    finished = Signal(int, int)
    progress = Signal(int, int)

    def __init__(self, vault: VaultManager) -> None:
        super().__init__()
        self._vault = vault

    @Slot()
    def run(self) -> None:
        total = 0
        try:
            from normalizer import normalize_site_name
            entries = self._vault.get_all_entries()
            total = len(entries)
            updated = 0
            for i, entry in enumerate(entries):
                new_name = normalize_site_name(entry.site_name, entry.url)
                if new_name != "Unknown" and entry.site_name != new_name:
                    entry.site_name = new_name
                    self._vault.update_entry(entry)
                    updated += 1
                if i % 10 == 0:
                    self.progress.emit(i + 1, total)
            self.finished.emit(updated, total)
        except Exception as exc:
            _log.exception("BulkNormalizeWorker failed")
            self.finished.emit(0, total)


# ──────────────────────────────────────────────────────────────────────
# VaultBridge
# ──────────────────────────────────────────────────────────────────────

class VaultBridge(QObject):
    """
    All QML-visible state, signals, and slots for khazna.
    """

    # ── Public signals ────────────────────────
    lockStateChanged          = Signal()
    entriesChanged            = Signal()
    entryCountChanged         = Signal()
    tagsChanged               = Signal()
    categoriesChanged         = Signal()
    auditLogsChanged          = Signal()
    filterChanged             = Signal()

    autoCategorizeStarted     = Signal()
    autoCategorizeProgress    = Signal(int, int)
    autoCategorizeFinished    = Signal(int, int)

    normalizeStarted          = Signal()
    normalizeProgress         = Signal(int, int)
    normalizeFinished         = Signal(int, int)

    unlockStarted             = Signal()
    unlockFinished            = Signal(bool, str)
    lockoutOccurred           = Signal(str, int)

    errorOccurred             = Signal(str)
    statusMessage             = Signal(str, str)

    autoLocked                = Signal()
    clipboardCountdownChanged = Signal(int)

    strengthResult            = Signal(int, str, str, list)
    passwordGenerated         = Signal(str)

    # Feature 4: Health dashboard
    healthChanged             = Signal()
    # Feature 7: Breach check
    breachResult              = Signal(int, bool, int, str)
    # Feature 6: Recovery
    recoveryKeysGenerated     = Signal(list)
    recoveryComplete          = Signal(bool, str)

    _threadAutoLock = Signal()

    def __init__(self, vault: VaultManager, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._vault             = vault
        self._entry_model       = EntryListModel(self)
        self._audit_model       = AuditLogModel(self)
        self._health_model      = HealthIssueModel(self)

        self._filter            = "all"
        self._tag               = ""
        self._category          = ""
        self._search            = ""
        self._clip_countdown    = 0

        self._health_score      = 100
        self._weak_count        = 0
        self._old_count         = 0
        self._issue_count       = 0

        self._clip_timer:    Optional[QTimer]   = None
        self._reveal_timers: dict[int, QTimer]  = {}
        self._worker_thread: Optional[QThread]  = None
        self._worker:        Optional[QObject]  = None

        self._threadAutoLock.connect(
            self._onAutoLockMainThread,
            Qt.ConnectionType.QueuedConnection,
        )
        self._vault.set_lock_callback(self._threadAutoLock.emit)

    # ── Read-only QML properties ──────────────

    @Property(bool, notify=lockStateChanged)
    def isLocked(self) -> bool:
        return self._vault.is_locked

    @Property(bool, notify=lockStateChanged)
    def isInitialized(self) -> bool:
        return self._vault.is_initialized

    @Property(int, notify=entryCountChanged)
    def entryCount(self) -> int:
        return self._vault.get_entry_count()

    @Property(QObject, constant=True)
    def entryModel(self) -> EntryListModel:
        return self._entry_model

    @Property(QObject, constant=True)
    def auditModel(self) -> AuditLogModel:
        return self._audit_model

    @Property(str, notify=filterChanged)
    def currentFilter(self) -> str:
        return self._filter

    @Property(str, notify=filterChanged)
    def currentTag(self) -> str:
        return self._tag

    @Property(str, notify=filterChanged)
    def currentCategory(self) -> str:
        return self._category

    @Property(int, notify=clipboardCountdownChanged)
    def clipboardCountdown(self) -> int:
        return self._clip_countdown

    @Property(QObject, constant=True)
    def healthModel(self) -> 'HealthIssueModel':
        return self._health_model

    @Property(int, notify=healthChanged)
    def healthScore(self) -> int:
        return self._health_score

    @Property(int, notify=healthChanged)
    def weakCount(self) -> int:
        return self._weak_count

    @Property(int, notify=healthChanged)
    def oldCount(self) -> int:
        return self._old_count

    @Property(int, notify=healthChanged)
    def healthIssueCount(self) -> int:
        """Total health issues — reactive property for QML binding."""
        return self._issue_count

    @Property(str, constant=True)
    def dbPath(self) -> str:
        return self._vault._storage.db_path

    # ── Auth slots ────────────────────────────

    @Slot(str)
    def unlock(self, password: str) -> None:
        if self._worker_thread and self._worker_thread.isRunning():
            return
        self._start_worker(UnlockWorker(self._vault, password))

    @Slot(str)
    def setupVault(self, password: str) -> None:
        if self._worker_thread and self._worker_thread.isRunning():
            return
        self._start_worker(SetupWorker(self._vault, password))

    @Slot()
    def lock(self) -> None:
        self._vault.lock()
        self._entry_model.load([])
        self._audit_model.load([])
        self._stop_all_reveals()
        self.lockStateChanged.emit()
        self.entriesChanged.emit()
        self.entryCountChanged.emit()

    # ── Entry CRUD ────────────────────────────

    @Slot(str, str, str, str, str, str, bool, str, result=bool)
    def addEntry(self, siteName: str, url: str, username: str,
                  password: str, notes: str, tags: str,
                  favorite: bool, category: str = "Other") -> bool:
        try:
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]
            entry = PasswordEntry(
                site_name=siteName, url=url, username=username,
                password=password, notes=notes, tags=tag_list,
                favorite=favorite, category=category or "Other",
            )
            self._vault.add_entry(entry)
            self._refresh_entries()
            self.statusMessage.emit(f"Entry '{siteName}' added.", "#a6e3a1")
            return True
        except Exception as exc:
            _log.exception("addEntry failed")
            self.errorOccurred.emit(str(exc))
            return False

    @Slot(int, str, str, str, str, str, str, bool, str, result=bool)
    def updateEntry(self, entryId: int, siteName: str, url: str,
                     username: str, password: str, notes: str,
                     tags: str, favorite: bool, category: str = "Other") -> bool:
        try:
            entry = self._vault.get_entry(entryId)
            if entry is None:
                self.errorOccurred.emit(f"Entry {entryId} not found.")
                return False
            entry.site_name = siteName
            entry.url       = url
            entry.username  = username
            entry.password  = password
            entry.notes     = notes
            entry.tags      = [t.strip() for t in tags.split(",") if t.strip()]
            entry.favorite  = favorite
            entry.category  = category or "Other"
            self._vault.update_entry(entry)
            self._refresh_entries()
            self.statusMessage.emit(f"Entry '{siteName}' updated.", "#a6e3a1")
            return True
        except Exception as exc:
            _log.exception("updateEntry failed")
            self.errorOccurred.emit(str(exc))
            return False

    @Slot(int, result=bool)
    def deleteEntry(self, entryId: int) -> bool:
        try:
            existing = self._entry_model.entry_by_id(entryId)
            site = existing.site_name if existing else str(entryId)
            self._vault.delete_entry(entryId, site)
            self._refresh_entries()
            self.statusMessage.emit(f"Entry '{site}' deleted.", "#fab387")
            return True
        except Exception as exc:
            _log.exception("deleteEntry failed")
            self.errorOccurred.emit(str(exc))
            return False

    @Slot(int, result="QVariantMap")
    def getEntry(self, entryId: int) -> dict:
        try:
            e = self._vault.get_entry(entryId)
            if e is None:
                return {}
            return {
                "id":       e.id,
                "siteName": e.site_name,
                "url":      e.url,
                "username": e.username,
                "password": e.password,
                "notes":    e.notes,
                "tags":     ", ".join(e.tags),
                "favorite": e.favorite,
                "category": e.category,
            }
        except Exception as exc:
            _log.exception("getEntry failed")
            self.errorOccurred.emit(str(exc))
            return {}

    # ── Clipboard / reveal ────────────────────

    @Slot(int)
    def copyPassword(self, entryId: int) -> None:
        e = self._vault.get_entry(entryId)
        if not e:
            return
        self._copy_to_clipboard(e.password)
        self._start_clipboard_countdown(CLIPBOARD_CLEAR_SECONDS)
        self.statusMessage.emit(
            f"Password for '{e.site_name}' copied — clears in {CLIPBOARD_CLEAR_SECONDS} s.",
            "#a6e3a1",
        )

    @Slot(str)
    def copyToClipboard(self, text: str) -> None:
        """Copy arbitrary text to clipboard (used by generator, recovery keys, etc.)."""
        self._copy_to_clipboard(text)
        self.statusMessage.emit("Copied to clipboard.", "#a6e3a1")

    @Slot(int)
    def copyUsername(self, entryId: int) -> None:
        e = self._vault.get_entry(entryId)
        if not e:
            return
        self._copy_to_clipboard(e.username)
        self.statusMessage.emit(f"Username for '{e.site_name}' copied.", "#a6e3a1")

    @Slot(int)
    def copyUrl(self, entryId: int) -> None:
        e = self._vault.get_entry(entryId)
        if not e or not e.url:
            return
        self._copy_to_clipboard(e.url)
        self.statusMessage.emit(f"URL for '{e.site_name}' copied.", "#a6e3a1")

    @Slot(int)
    def revealPassword(self, entryId: int) -> None:
        self._entry_model.set_revealed(entryId, True)
        if entryId in self._reveal_timers:
            self._reveal_timers[entryId].stop()
        t = QTimer(self)
        t.setSingleShot(True)
        t.timeout.connect(lambda: self._hide_reveal(entryId))
        t.start(5_000)
        self._reveal_timers[entryId] = t

    @Slot(int)
    def hidePassword(self, entryId: int) -> None:
        self._hide_reveal(entryId)

    # ── Filter / search ───────────────────────

    @Slot(str)
    def setFilter(self, name: str) -> None:
        self._filter   = name
        self._tag      = ""
        self._category = ""
        self._search   = ""
        self.filterChanged.emit()
        self._refresh_entries()

    @Slot(str)
    def setTagFilter(self, tag: str) -> None:
        self._filter   = "tag"
        self._tag      = tag
        self._category = ""
        self._search   = ""
        self.filterChanged.emit()
        self._refresh_entries()

    @Slot(str)
    def setCategoryFilter(self, cat: str) -> None:
        self._filter   = "category"
        self._tag      = ""
        self._category = cat
        self._search   = ""
        self.filterChanged.emit()
        self._refresh_entries()

    @Slot(str)
    def setSearchQuery(self, query: str) -> None:
        self._search = query
        self._refresh_entries()
        if not self._vault.is_locked:
            self._vault.reset_activity_timer()

    @Slot()
    def autoCategorizeAll(self) -> None:
        if self._vault.is_locked:
            return
        if self._worker_thread and self._worker_thread.isRunning():
            return
        self.autoCategorizeStarted.emit()
        self._worker_thread = QThread()
        self._worker = AutoCategorizeWorker(self._vault)
        self._worker.moveToThread(self._worker_thread)
        self._worker_thread.started.connect(self._worker.run)
        self._worker.progress.connect(self.autoCategorizeProgress)
        self._worker.finished.connect(self._on_auto_categorize_finished)
        self._worker_thread.start()

    @Slot(int, int)
    def _on_auto_categorize_finished(self, updated: int, total: int) -> None:
        self.autoCategorizeFinished.emit(updated, total)
        self.categoriesChanged.emit()
        self._refresh_entries()
        if self._worker_thread:
            self._worker_thread.quit()
            self._worker_thread.wait()
            self._worker_thread = None
        self._worker = None

    @Slot()
    def normalizeAllSiteNames(self) -> None:
        if self._vault.is_locked:
            return
        if self._worker_thread and self._worker_thread.isRunning():
            return
        self.normalizeStarted.emit()
        self._worker_thread = QThread()
        self._worker = BulkNormalizeWorker(self._vault)
        self._worker.moveToThread(self._worker_thread)
        self._worker_thread.started.connect(self._worker.run)
        self._worker.progress.connect(self.normalizeProgress)
        self._worker.finished.connect(self._on_normalize_finished)
        self._worker_thread.start()

    @Slot(int, int)
    def _on_normalize_finished(self, updated: int, total: int) -> None:
        self.normalizeFinished.emit(updated, total)
        self._refresh_entries()
        if self._worker_thread:
            self._worker_thread.quit()
            self._worker_thread.wait()
            self._worker_thread = None
        self._worker = None

    @Slot(result="QStringList")
    def getAllTags(self) -> list[str]:
        if self._vault.is_locked:
            return []
        try:
            return self._vault.get_all_tags()
        except Exception:
            _log.exception("getAllTags failed")
            return []

    @Slot(result="QStringList")
    def getAllCategories(self) -> list[str]:
        if self._vault.is_locked:
            return []
        try:
            return self._vault.get_all_categories()
        except Exception:
            _log.exception("getAllCategories failed")
            return []

    @Slot(str, str, result=str)
    def detectCategory(self, url: str, siteName: str) -> str:
        try:
            return self._vault.detect_category(url=url, site_name=siteName)
        except Exception:
            return "Other"

    # ── Password tools ────────────────────────

    @Slot(str)
    def checkStrength(self, password: str) -> None:
        if not password:
            self.strengthResult.emit(0, "—", "#6c7086", [])
            return
        r = self._vault.check_strength(password)
        self.strengthResult.emit(
            r["score"], r["level"], r["color"],
            r.get("feedback", []),
        )

    @Slot(int, bool, bool, bool, bool, bool, str, result=str)
    def generatePassword(
        self, length: int = 20,
        useUpper: bool = True, useLower: bool = True,
        useDigits: bool = True, useSymbols: bool = True,
        excludeAmbiguous: bool = False, customExclude: str = "",
    ) -> str:
        try:
            pw = self._vault.generate_password(
                length=length, use_upper=useUpper, use_lower=useLower,
                use_digits=useDigits, use_symbols=useSymbols,
                exclude_ambiguous=excludeAmbiguous, custom_exclude=customExclude,
            )
            self.passwordGenerated.emit(pw)
            return pw
        except ValueError as exc:
            self.errorOccurred.emit(str(exc))
            return ""

    # ── Master password ───────────────────────

    @Slot(str, str, result=bool)
    def changeMasterPassword(self, oldPw: str, newPw: str) -> bool:
        try:
            self._vault.change_master_password(oldPw, newPw)
            self.statusMessage.emit("Master password changed successfully.", "#a6e3a1")
            return True
        except Exception as exc:
            _log.exception("changeMasterPassword failed")
            self.errorOccurred.emit(str(exc))
            return False

    # ── CSV / backup ──────────────────────────

    @Slot(str, result="QVariantMap")
    def importCsv(self, path: str) -> dict:
        try:
            ok, skipped, errors = self._vault.import_csv(path)
            self._refresh_entries()
            self.statusMessage.emit(
                f"CSV: {ok} imported, {skipped} skipped.", "#a6e3a1"
            )
            return {"success": ok, "skipped": skipped, "errors": errors}
        except Exception as exc:
            _log.exception("importCsv failed")
            self.errorOccurred.emit(str(exc))
            return {"success": 0, "skipped": 0, "errors": [str(exc)]}

    @Slot(str, str, result=bool)
    def exportBackup(self, path: str, password: str) -> bool:
        try:
            self._vault.export_backup(path, password)
            self.statusMessage.emit("Backup saved successfully.", "#a6e3a1")
            return True
        except Exception as exc:
            _log.exception("exportBackup failed")
            self.errorOccurred.emit(str(exc))
            return False

    @Slot(str, str, result=bool)
    def importBackup(self, path: str, password: str) -> bool:
        try:
            count = self._vault.import_backup(path, password)
            self._refresh_entries()
            self.statusMessage.emit(
                f"Restore complete — {count} entries imported.", "#a6e3a1"
            )
            return True
        except Exception as exc:
            _log.exception("importBackup failed")
            self.errorOccurred.emit(str(exc))
            return False

    # ── Audit log ─────────────────────────────

    @Slot()
    def refreshAuditLogs(self) -> None:
        try:
            self._audit_model.load(self._vault.get_audit_logs(200))
            self.auditLogsChanged.emit()
        except Exception:
            _log.exception("refreshAuditLogs failed")

    @Slot(result=bool)
    def exportAuditLog(self) -> bool:
        import csv as _csv
        from datetime import datetime as _dt
        try:
            logs = self._vault.get_audit_logs(10_000)
            ts   = _dt.now().strftime("%Y%m%d_%H%M%S")
            path = str(
                __import__("pathlib").Path(self._vault._storage.db_path).parent
                / f"audit_log_{ts}.csv"
            )
            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = _csv.writer(fh)
                writer.writerow(["timestamp", "event_type", "description", "success"])
                for log in logs:
                    writer.writerow([
                        log.timestamp.isoformat() if log.timestamp else "",
                        log.event_type,
                        log.description,
                        "yes" if log.success else "no",
                    ])
            self.statusMessage.emit(f"Audit log exported: {path}", "#a6e3a1")
            return True
        except Exception as exc:
            _log.exception("exportAuditLog failed")
            self.errorOccurred.emit(str(exc))
            return False

    # ── Favourites ────────────────────────────

    @Slot(int)
    def toggleFavorite(self, entryId: int) -> None:
        try:
            e = self._vault.get_entry(entryId)
            if e:
                self._vault.toggle_favorite(e)
                self._refresh_entries()
        except Exception as exc:
            _log.exception("toggleFavorite failed")
            self.errorOccurred.emit(str(exc))

    # ── Health dashboard (Feature 4) ──────────

    @Slot()
    def refreshHealth(self) -> None:
        try:
            report = self._vault.analyze_health()
            self._health_score  = report.overall_score
            self._weak_count    = report.weak_count
            self._old_count     = report.old_count
            self._issue_count   = len(report.issues)
            self._health_model.load(report.issues)
            self.healthChanged.emit()
        except Exception:
            _log.exception("refreshHealth failed")

    # ── Breach checking (Feature 7) ───────────

    @Slot(int)
    def checkBreach(self, entryId: int) -> None:
        try:
            e = self._vault.get_entry(entryId)
            if not e:
                self.breachResult.emit(entryId, False, 0, "Entry not found")
                return
            result = self._vault.check_breach(e.password)
            self.breachResult.emit(
                entryId,
                result["is_breached"],
                result["count"],
                result["error"],
            )
        except Exception as exc:
            _log.exception("checkBreach failed")
            self.breachResult.emit(entryId, False, 0, str(exc))

    @Slot(str, result="QVariantMap")
    def checkBreachPassword(self, password: str) -> dict:
        """Direct password breach check (for entry dialog)."""
        try:
            return self._vault.check_breach(password)
        except Exception as exc:
            return {"is_breached": False, "count": 0, "error": str(exc)}

    # ── Recovery keys (Feature 6) ─────────────

    @Slot(result=list)
    def generateRecoveryKeys(self) -> list[str]:
        """
        Generate 8 recovery codes, store their derived hashes/encrypted keys
        in the database, and return the plaintext codes to display once.

        Emits recoveryKeysGenerated(codes) so the dialog can display them.
        """
        try:
            codes = self._vault.generate_recovery_keys()
            _log.info("generateRecoveryKeys: generated %d codes", len(codes))
            self.recoveryKeysGenerated.emit(codes)
            self.statusMessage.emit(
                f"8 recovery codes generated — save them somewhere safe!",
                "#fab387",
            )
            return codes
        except Exception as exc:
            _log.exception("generateRecoveryKeys failed")
            self.errorOccurred.emit(str(exc))
            return []

    @Slot(str, str, result=bool)
    def recoverWithCode(self, code: str, newPassword: str) -> bool:
        """
        Attempt vault recovery.

        Parameters
        ----------
        code        : str  – one of the 8 recovery codes (any format accepted,
                             hyphens and whitespace are stripped before use)
        newPassword : str  – the new master password (≥ 8 characters)

        On success
        ──────────
        • The vault is re-encrypted under newPassword.
        • All recovery codes are invalidated.
        • The vault is locked so the user must log in with the new password.
        • recoveryComplete(True, message) is emitted.
        • lockStateChanged is emitted so Main.qml transitions to LoginScreen.

        On failure
        ──────────
        • recoveryComplete(False, reason) is emitted with a helpful reason.
        • The vault state is unchanged.
        """
        try:
            if len(newPassword) < 8:
                self.recoveryComplete.emit(
                    False,
                    "New master password must be at least 8 characters.",
                )
                return False

            ok = self._vault.recover_with_code(code, newPassword)

            if ok:
                # The vault is now locked (app_logic calls self.lock() on success).
                # Clear the UI models and update all reactive properties.
                self._entry_model.load([])
                self._audit_model.load([])
                self._stop_all_reveals()
                self.lockStateChanged.emit()
                self.entryCountChanged.emit()
                self.recoveryComplete.emit(
                    True,
                    "Vault recovered successfully!\n"
                    "All recovery codes have been invalidated.\n"
                    "Please log in with your new master password.",
                )
                _log.info("recoverWithCode: recovery successful; vault is now locked")
            else:
                # Provide a more specific failure reason.
                from recovery import normalize_code, _CODE_LENGTH
                normalised = normalize_code(code)
                if len(normalised) != _CODE_LENGTH:
                    reason = (
                        f"Recovery code has the wrong length after removing "
                        f"hyphens and spaces ({len(normalised)} characters, "
                        f"expected {_CODE_LENGTH}). "
                        f"Please check that you copied the full code."
                    )
                else:
                    reason = (
                        "Recovery code not recognised. "
                        "Make sure you are entering a code that was generated "
                        "for this vault and that you have not already used it."
                    )
                self.recoveryComplete.emit(False, reason)
                _log.warning("recoverWithCode: code rejected (normalised len=%d)", len(normalised))

            return ok

        except ValueError as exc:
            # new_password too short — surface clearly
            self.recoveryComplete.emit(False, str(exc))
            return False
        except Exception as exc:
            _log.exception("recoverWithCode: unexpected error")
            self.recoveryComplete.emit(False, f"Unexpected error: {exc}")
            return False

    @Slot(result=bool)
    def hasRecoveryKeys(self) -> bool:
        """
        Return True if recovery keys exist in the database.
        Does NOT require the vault to be unlocked.
        """
        try:
            return self._vault.has_recovery_keys()
        except Exception:
            return False

    # ── Internal helpers ──────────────────────

    def _copy_to_clipboard(self, text: str) -> None:
        """Use Qt's native clipboard."""
        try:
            clipboard = QGuiApplication.clipboard()
            if clipboard:
                clipboard.setText(text)
        except Exception:
            _log.exception("Clipboard copy failed")

    def _start_worker(self, worker: QObject) -> None:
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._onWorkerFinished)
        worker.finished.connect(thread.quit)
        thread.finished.connect(self._onThreadFinished)
        if hasattr(worker, "lockout"):
            worker.lockout.connect(self.lockoutOccurred)
        self._worker        = worker
        self._worker_thread = thread
        self.unlockStarted.emit()
        thread.start()

    def _onThreadFinished(self) -> None:
        self._worker        = None
        self._worker_thread = None

    def _onWorkerFinished(self, success: bool, message: str) -> None:
        if success:
            try:
                migrated = self._vault.migrate_schema()
                if migrated > 0:
                    _log.info("Migrated %d entries to encrypted site_name/tags", migrated)
            except Exception:
                _log.exception("Schema migration failed")
            self._refresh_entries()
            self.refreshAuditLogs()
            self.lockStateChanged.emit()
            self.entryCountChanged.emit()
        self.unlockFinished.emit(success, message)

    def _onAutoLockMainThread(self) -> None:
        self._entry_model.load([])
        self._audit_model.load([])
        self._stop_all_reveals()
        self.lockStateChanged.emit()
        self.autoLocked.emit()

    def _refresh_entries(self) -> None:
        try:
            if self._search:
                entries = self._vault.search_entries(self._search)
            elif self._filter == "favorites":
                entries = self._vault.get_favorite_entries()
            elif self._filter == "tag" and self._tag:
                entries = self._vault.get_entries_by_tag(self._tag)
            elif self._filter == "category" and self._category:
                entries = self._vault.get_entries_by_category(self._category)
            else:
                entries = self._vault.get_all_entries()
            self._entry_model.load(entries)
            self.entriesChanged.emit()
            self.entryCountChanged.emit()
            self.tagsChanged.emit()
            self.categoriesChanged.emit()
        except Exception:
            _log.exception("_refresh_entries failed")

    def _hide_reveal(self, entry_id: int) -> None:
        self._entry_model.set_revealed(entry_id, False)
        if entry_id in self._reveal_timers:
            self._reveal_timers[entry_id].stop()
            del self._reveal_timers[entry_id]

    def _stop_all_reveals(self) -> None:
        for t in self._reveal_timers.values():
            t.stop()
        self._reveal_timers.clear()

    def _start_clipboard_countdown(self, seconds: int) -> None:
        self._clip_countdown = seconds
        self.clipboardCountdownChanged.emit(self._clip_countdown)
        if self._clip_timer:
            self._clip_timer.stop()
        self._clip_timer = QTimer(self)
        self._clip_timer.timeout.connect(self._tick_clipboard)
        self._clip_timer.start(1_000)

    def _tick_clipboard(self) -> None:
        self._clip_countdown -= 1
        self.clipboardCountdownChanged.emit(self._clip_countdown)
        if self._clip_countdown <= 0:
            if self._clip_timer:
                self._clip_timer.stop()
                self._clip_timer = None
            self._copy_to_clipboard("")


# ──────────────────────────────────────────────────────────────────────
# HealthIssueModel (Feature 4)
# ──────────────────────────────────────────────────────────────────────

class HealthIssueModel(QAbstractListModel):
    """Exposes password health issues to QML."""

    EntryIdRole     = Qt.ItemDataRole.UserRole + 1
    SiteNameRole    = Qt.ItemDataRole.UserRole + 2
    IssueTypeRole   = Qt.ItemDataRole.UserRole + 3
    SeverityRole    = Qt.ItemDataRole.UserRole + 4
    DescriptionRole = Qt.ItemDataRole.UserRole + 5
    ScoreRole       = Qt.ItemDataRole.UserRole + 6

    _ROLE_MAP: dict[int, bytes] = {
        EntryIdRole:     b"entryId",
        SiteNameRole:    b"siteName",
        IssueTypeRole:   b"issueType",
        SeverityRole:    b"severity",
        DescriptionRole: b"description",
        ScoreRole:       b"score",
    }

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._issues: list = []

    def load(self, issues: list) -> None:
        self.beginResetModel()
        self._issues = list(issues)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._issues)

    def roleNames(self) -> dict[int, bytes]:
        return self._ROLE_MAP

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._issues)):
            return None
        issue = self._issues[index.row()]
        match role:
            case self.EntryIdRole:     return issue.entry_id
            case self.SiteNameRole:    return issue.site_name
            case self.IssueTypeRole:   return issue.issue_type
            case self.SeverityRole:    return issue.severity
            case self.DescriptionRole: return issue.description
            case self.ScoreRole:       return issue.score
            case _:                    return None
