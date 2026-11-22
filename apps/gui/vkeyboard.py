#this belongs in apps/gui/vkeyboard.py - Version: 1
# X-Seti - November 22 2026 - Morosa - Virtual Keyboard.

"""
Morosa Virtual Keyboard - clickable Amiga keyboard; modifier keys stay down until clicked again.
"""

##Methods list -
# VKeyboard
# VKeyboard.__init__
# VKeyboard._click
# VKeyboard._tap

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QGridLayout, QPushButton, QWidget

# label, raw code, width in key units
ROWS = (
    (("Esc", 0x45, 2), ("F1", 0x50, 1), ("F2", 0x51, 1), ("F3", 0x52, 1), ("F4", 0x53, 1), ("F5", 0x54, 1), ("F6", 0x55, 1), ("F7", 0x56, 1),
     ("F8", 0x57, 1), ("F9", 0x58, 1), ("F10", 0x59, 1), ("Del", 0x46, 2), ("Help", 0x5F, 2)),
    (("`", 0x00, 1), ("1", 1, 1), ("2", 2, 1), ("3", 3, 1), ("4", 4, 1), ("5", 5, 1), ("6", 6, 1), ("7", 7, 1), ("8", 8, 1), ("9", 9, 1),
     ("0", 10, 1), ("-", 11, 1), ("=", 12, 1), ("\\", 13, 1), ("Bksp", 0x41, 2)),
    (("Tab", 0x42, 2), ("Q", 0x10, 1), ("W", 0x11, 1), ("E", 0x12, 1), ("R", 0x13, 1), ("T", 0x14, 1), ("Y", 0x15, 1), ("U", 0x16, 1),
     ("I", 0x17, 1), ("O", 0x18, 1), ("P", 0x19, 1), ("[", 0x1A, 1), ("]", 0x1B, 1), ("Return", 0x44, 3)),
    (("Ctrl", 0x63, 2), ("Caps", 0x62, 2), ("A", 0x20, 1), ("S", 0x21, 1), ("D", 0x22, 1), ("F", 0x23, 1), ("G", 0x24, 1), ("H", 0x25, 1),
     ("J", 0x26, 1), ("K", 0x27, 1), ("L", 0x28, 1), (";", 0x29, 1), ("'", 0x2A, 1), ("#", 0x2B, 1)),
    (("Shift", 0x60, 2), ("<", 0x30, 1), ("Z", 0x31, 1), ("X", 0x32, 1), ("C", 0x33, 1), ("V", 0x34, 1), ("B", 0x35, 1), ("N", 0x36, 1),
     ("M", 0x37, 1), (",", 0x38, 1), (".", 0x39, 1), ("/", 0x3A, 1), ("Shift", 0x61, 2), ("Up", 0x4C, 1)),
    (("Alt", 0x64, 2), ("Amiga", 0x66, 2), ("Space", 0x40, 7), ("Amiga", 0x67, 2), ("Alt", 0x65, 2), ("Left", 0x4F, 1), ("Down", 0x4D, 1), ("Right", 0x4E, 1)),
)
STICKY = {0x60, 0x61, 0x62, 0x63, 0x64, 0x65, 0x66, 0x67}


class VKeyboard(QWidget):
    """Tool window of keys; taps go to the Amiga keyboard."""

    def __init__(self, keyboard, parent=None):  #vers 1
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("Virtual Keyboard")
        self.kb = keyboard
        self.down = set()
        self.btn = {}
        grid = QGridLayout(self)
        grid.setSpacing(2)
        for r, row in enumerate(ROWS):
            c = 0
            for label, code, w in row:
                b = QPushButton(label)
                b.setMinimumHeight(30)
                b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                b.clicked.connect(lambda _=False, k=code, x=b: self._click(k, x))
                grid.addWidget(b, r, c, 1, w * 2)
                self.btn.setdefault(code, []).append(b)
                c += w * 2
        self.setMinimumWidth(720)

    def _click(self, code: int, b) -> None:  #vers 1
        """Modifiers toggle; other keys tap."""
        if code in STICKY:
            if code in self.down:
                self.down.discard(code)
                self.kb.release(code)
            else:
                self.down.add(code)
                self.kb.press(code)
            for x in self.btn[code]:
                x.setDown(code in self.down)
                x.setStyleSheet("background:#4a90d9;" if code in self.down else "")
            return
        self.kb.press(code)
        QTimer.singleShot(60, lambda: self.kb.release(code))
