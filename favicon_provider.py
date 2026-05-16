"""
favicon_provider.py
───────────────────
QQuickImageProvider that serves domain-derived icons for vault entries.

Primary: coloured circle with the first letter of the domain (deterministic
colour from domain hash).  Zero network requests.

Usage in QML:
    Image { source: "image://favicon/" + model.url }
"""

from __future__ import annotations

import hashlib
import logging
from typing import Optional
from urllib.parse import urlparse

from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QFont, QImage, QPainter, Qt
from PySide6.QtQuick import QQuickImageProvider

_log = logging.getLogger("khazna.favicon")

# Palette of dark-theme-friendly colours for letter circles
_PALETTE = [
    "#e74c3c", "#e67e22", "#f1c40f", "#2ecc71", "#1abc9c",
    "#3498db", "#9b59b6", "#e91e63", "#00bcd4", "#ff5722",
    "#795548", "#607d8b", "#8bc34a", "#673ab7", "#009688",
    "#ff9800", "#03a9f4", "#cddc39", "#ff4081", "#7c4dff",
]

_ICON_SIZE = 32


def _extract_domain(url: str) -> str:
    """Extract short domain from a URL."""
    if not url:
        return ""
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        host = parsed.hostname or ""
        if host.startswith("www."):
            host = host[4:]
        return host.lower()
    except Exception:
        return ""


def _letter_and_colour(domain: str) -> tuple[str, str]:
    """Return (uppercase letter, hex colour) for a domain."""
    letter = domain[0].upper() if domain else "?"
    idx = int(hashlib.md5(domain.encode()).hexdigest(), 16) % len(_PALETTE)
    return letter, _PALETTE[idx]


class FaviconProvider(QQuickImageProvider):
    """
    Image provider that generates letter-circle favicons.

    Register with:  engine.addImageProvider("favicon", FaviconProvider())
    Use in QML:     Image { source: "image://favicon/https://github.com" }
    """

    def __init__(self) -> None:
        super().__init__(QQuickImageProvider.ImageType.Image)
        self._cache: dict[str, QImage] = {}

    def requestImage(
        self, id: str, size: QSize, requestedSize: QSize
    ) -> QImage:
        domain = _extract_domain(id)
        if not domain:
            domain = id.strip("/") if id else "?"

        if domain in self._cache:
            return self._cache[domain]

        sz = requestedSize.width() if requestedSize.isValid() and requestedSize.width() > 0 else _ICON_SIZE
        img = self._generate_letter_icon(domain, sz)
        self._cache[domain] = img
        return img

    @staticmethod
    def _generate_letter_icon(domain: str, size: int = _ICON_SIZE) -> QImage:
        """Paint a coloured circle with the domain's first letter."""
        letter, colour = _letter_and_colour(domain)

        img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)

        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Circle
        p.setBrush(QColor(colour))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(1, 1, size - 2, size - 2)

        # Letter
        font = QFont("Segoe UI, Inter, sans-serif")
        font.setPixelSize(int(size * 0.55))
        font.setWeight(QFont.Weight.DemiBold)
        p.setFont(font)
        p.setPen(QColor("#ffffff"))
        p.drawText(0, 0, size, size, Qt.AlignmentFlag.AlignCenter, letter)

        p.end()
        return img
