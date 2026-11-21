#this belongs in apps/core/font.py - Version: 1
# X-Seti - November 17 2026 - Morosa - Morosa Font Glyphs.

"""
Morosa font glyphs - fixed-cell bitmap glyphs rasterised with Qt for the topaz.font stand-in.
"""

##Methods list -
# GlyphSet
# GlyphSet.__init__
# GlyphSet.rows
# _app

import os

_keep = []


def _app():  #vers 2
    from PyQt6.QtGui import QGuiApplication
    app = QGuiApplication.instance()
    if app is None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        app = QGuiApplication([])
        _keep.append(app)
    return app


class GlyphSet:
    """Glyph cells of width x height pixels for characters 32..255."""

    def __init__(self, height: int):  #vers 1
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QColor, QFont, QImage, QPainter
        _app()
        self.height = height
        self.width = max(4, height)
        self.baseline = max(1, height - 2)
        self.cache = {}
        self._ctx = (Qt, QColor, QFont, QImage, QPainter)

    def rows(self, ch: int) -> list:  #vers 1
        """Row bit masks, leftmost pixel in the highest bit of the cell width."""
        if ch in self.cache:
            return self.cache[ch]
        Qt, QColor, QFont, QImage, QPainter = self._ctx
        img = QImage(self.width, self.height, QImage.Format.Format_RGB32)
        img.fill(QColor(0, 0, 0))
        p = QPainter(img)
        f = QFont("Monospace")
        f.setStyleHint(QFont.StyleHint.TypeWriter)
        f.setPixelSize(self.height)
        f.setStyleStrategy(QFont.StyleStrategy.NoAntialias)
        p.setFont(f)
        p.setPen(QColor(255, 255, 255))
        p.drawText(0, self.baseline, chr(ch) if ch >= 32 else " ")
        p.end()
        out = []
        for y in range(self.height):
            v = 0
            for x in range(self.width):
                v = v << 1 | (1 if img.pixelColor(x, y).red() > 127 else 0)
            out.append(v)
        self.cache[ch] = out
        return out
