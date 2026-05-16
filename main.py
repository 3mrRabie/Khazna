"""
main.py
───────────────
PySide6/QML entry point for khazna.

All security-critical backend modules
(encryption, storage, app_logic, models) are unchanged.

Boot sequence
─────────────
1. Validate Python ≥ 3.10 (match statement used in bridge.py)
2. Parse CLI args  (--db, --log-level, --version)
3. Resolve vault DB path
4. Configure rotating file + stderr logging
5. Install global exception hooks
6. Create QGuiApplication with metadata + high-DPI flags
7. Instantiate VaultManager and VaultBridge
8. Load QML engine, register bridge as context property
9. Start event loop
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path

__version__ = "2.0.0"
APP_NAME    = "khazna"
APP_ORG     = "KhaznaProject"


# ──────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────

def _setup_logging(log_level: str, log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    numeric = getattr(logging, log_level.upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(numeric)
    root.handlers.clear()

    file_fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)-20s  %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    fh = RotatingFileHandler(
        log_dir / "khazna.log",
        maxBytes=5 * 1024 * 1024, backupCount=3,
        encoding="utf-8", delay=True,
    )
    fh.setLevel(numeric)
    fh.setFormatter(file_fmt)
    root.addHandler(fh)

    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(logging.WARNING)
    sh.setFormatter(logging.Formatter("%(levelname)s  %(message)s"))
    root.addHandler(sh)

    return logging.getLogger(APP_NAME)


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="khazna",
        description=f"{APP_NAME} – AES-256-GCM encrypted local password manager",
    )
    p.add_argument("--db", metavar="PATH", default=None,
                   help="Path to vault SQLite database (default: ~/.khazna/vault.db)")
    p.add_argument("--log-level", metavar="LEVEL", default="INFO",
                   choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def _default_vault_dir() -> Path:
    env = os.environ.get("KHAZNA_HOME", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    xdg = os.environ.get("XDG_DATA_HOME", "").strip()
    if xdg:
        return (Path(xdg) / "khazna").resolve()
    return Path.home() / ".khazna"


def _resolve_db_path(raw: str | None) -> Path:
    db = Path(raw).expanduser().resolve() if raw else _default_vault_dir() / "vault.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    return db


# ──────────────────────────────────────────────
# Exception hooks
# ──────────────────────────────────────────────

def _install_hooks(logger: logging.Logger) -> None:
    def _main(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        logger.critical(
            "Unhandled exception:\n%s",
            "".join(traceback.format_exception(exc_type, exc_value, exc_tb)),
        )
    sys.excepthook = _main

    try:
        import threading
        def _bg(args):
            if args.exc_type is SystemExit:
                return
            logger.critical(
                "Unhandled exception in thread '%s':\n%s",
                getattr(args.thread, "name", "<unknown>"),
                "".join(traceback.format_exception(
                    args.exc_type, args.exc_value, args.exc_traceback)),
            )
        threading.excepthook = _bg  # type: ignore[attr-defined]
    except AttributeError:
        pass


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main() -> None:
    if sys.version_info < (3, 10):
        print(f"Error: {APP_NAME} requires Python 3.10+", file=sys.stderr)
        sys.exit(1)

    args    = _build_parser().parse_args()
    db_path = _resolve_db_path(args.db)
    log_dir = db_path.parent
    logger  = _setup_logging(args.log_level, log_dir)

    logger.info("Starting %s v%s | db=%s", APP_NAME, __version__, db_path)
    _install_hooks(logger)

    # ── Qt bootstrap ───────────────────────────
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtCore import QUrl
    from PySide6.QtQuickControls2 import QQuickStyle  # type: ignore

    app = QGuiApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName(APP_ORG)
    # Use the Basic style as a neutral base; our QML overrides all visuals
    QQuickStyle.setStyle("Basic")

    # ── Backend + bridge ───────────────────────
    from app_logic import VaultManager
    from bridge import VaultBridge

    vault  = VaultManager(db_path=str(db_path))
    bridge = VaultBridge(vault, app)

    # Start browser extension sync server
    from extension_server import ExtensionServer
    ext_server = ExtensionServer(vault, app)
    ext_server.start()

    # ── QML engine ─────────────────────────────
    engine = QQmlApplicationEngine()
    ctx    = engine.rootContext()
    ctx.setContextProperty("vault", bridge)
    ctx.setContextProperty("appVersion", __version__)

    # Register favicon image provider
    from favicon_provider import FaviconProvider
    engine.addImageProvider("favicon", FaviconProvider())

    # QML files live in the qml/ subdirectory.
    # addImportPath exposes the directory as a module root so that
    # qmldir (module khazna) and components/ sub-folder resolve correctly.
    root_dir = Path(__file__).resolve().parent
    qml_dir  = root_dir / "qml"

    engine.addImportPath(str(root_dir))
    engine.addImportPath(str(qml_dir))

    qml_main = qml_dir / "Main.qml"
    if not qml_main.exists():
        logger.critical(
            "Main.qml not found at %s — ensure all .qml files sit "
            "alongside main.py and components/ contains Sv*.qml",
            qml_main,
        )
        print(f"Error: {qml_main} not found.", file=sys.stderr)
        sys.exit(1)

    def handle_warnings(warnings):
        for w in warnings:
            print("QML WARNING:", w.toString(), file=sys.stderr)
            logger.error("QML Warning: %s", w.toString())
    engine.warnings.connect(handle_warnings)

    engine.load(QUrl.fromLocalFile(str(qml_main)))

    if not engine.rootObjects():
        logger.critical("QML engine failed to load root objects.")
        sys.exit(1)

    logger.info("QML engine loaded successfully.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
