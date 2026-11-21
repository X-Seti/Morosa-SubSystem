#this belongs in apps/gui/display.py - Version: 1
# X-Seti - November 17 2026 - Morosa - Morosa Display.

"""
Morosa Display - shows Amiga windows as Qt windows and sends mouse and key events back to the program.
"""

##Methods list -
# Display
# Display._sync
# Display.attach
# Display.request
# _View
# _View.closeEvent
# _View.keyPressEvent
# _View.mouseMoveEvent
# _View.mousePressEvent
# _View.mouseReleaseEvent
# _View.paintEvent

import threading

from PyQt6.QtCore import QObject, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtWidgets import QMessageBox, QWidget

IDCMP_MOUSEBUTTONS, IDCMP_MOUSEMOVE, IDCMP_CLOSEWINDOW, IDCMP_VANILLAKEY = 0x8, 0x10, 0x200, 0x200000
SELECTDOWN, SELECTUP, MENUDOWN, MENUUP = 0x68, 0xE8, 0x69, 0xE9


class _View(QWidget):
    """One Amiga window drawn from its bitmap."""

    def __init__(self, display, win: int):  #vers 1
        super().__init__()
        self.display, self.win, self.img, self.stamp = display, win, None, None
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def paintEvent(self, _e) -> None:  #vers 1
        if self.img is not None:
            p = QPainter(self)
            p.drawImage(0, 0, self.img)

    def _post(self, cls: int, code: int, ev) -> None:  #vers 1
        m, win = self.display.machine, self.win
        x, y = int(ev.position().x()), int(ev.position().y())
        m.events.put(lambda: m.owners["intuition"].post(win, cls, code, 0, 0, x, y))

    def mousePressEvent(self, ev) -> None:  #vers 1
        self._post(IDCMP_MOUSEBUTTONS, SELECTDOWN if ev.button() == Qt.MouseButton.LeftButton else MENUDOWN, ev)

    def mouseReleaseEvent(self, ev) -> None:  #vers 1
        self._post(IDCMP_MOUSEBUTTONS, SELECTUP if ev.button() == Qt.MouseButton.LeftButton else MENUUP, ev)

    def mouseMoveEvent(self, ev) -> None:  #vers 1
        self._post(IDCMP_MOUSEMOVE, 0, ev)

    def keyPressEvent(self, ev) -> None:  #vers 1
        t = ev.text()
        if t:
            m, win, code = self.display.machine, self.win, ord(t[0]) & 0xFF
            m.events.put(lambda: m.owners["intuition"].post(win, IDCMP_VANILLAKEY, code))

    def closeEvent(self, ev) -> None:  #vers 1
        m, win = self.display.machine, self.win
        if m is not None and win in m.owners["intuition"].windows:
            m.events.put(lambda: m.owners["intuition"].post(win, IDCMP_CLOSEWINDOW))
            ev.ignore()
        else:
            ev.accept()


class Display(QObject):
    """Bridges a Machine to Qt; poll runs in the GUI thread, request is called from the machine thread."""

    ask = pyqtSignal(object)

    def __init__(self, parent=None):  #vers 1
        super().__init__(parent)
        self.machine, self.views = None, {}
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._sync)
        self.ask.connect(self._ask)

    def attach(self, machine) -> None:  #vers 1
        self.machine = machine
        machine.ui = self
        machine.live = True
        self.timer.start(40)

    def _sync(self) -> None:  #vers 1
        m = self.machine
        if m is None:
            return
        it, g = m.owners["intuition"], m.owners["graphics"]
        wins = list(it.windows)
        for win in wins:
            b = m.bus
            view = self.views.get(win)
            if view is None:
                view = _View(self, win)
                self.views[win] = view
                w, h = b.r16(win + 8), b.r16(win + 10)
                title = m.exec.cstr(b.r32(win + 32)) if b.r32(win + 32) else "Amiga"
                view.setWindowTitle(title)
                view.setFixedSize(w, h)
                view.move(b.r16(win + 4) + 40, b.r16(win + 6) + 40)
                view.show()
            rp = b.r32(win + 50)
            bm = b.r32(rp + 4)
            st = g.stamp(bm)
            if st != view.stamp:
                view.stamp = st
                w, h, data = g.image_bytes(bm, b.r32(win + 46) + 44)
                view.img = QImage(data, w, h, w * 4, QImage.Format.Format_RGB32).copy()
                view.update()
        for win in [w for w in self.views if w not in wins]:
            self.views.pop(win).deleteLater()

    def request(self, title: str, text: str, buttons: list) -> int:  #vers 1
        job = {"title": title, "text": text, "buttons": buttons, "ev": threading.Event(), "pick": len(buttons) - 1}
        self.ask.emit(job)
        while not job["ev"].wait(0.05):
            if self.machine is not None and self.machine.abort:
                break
        return job["pick"]

    def _ask(self, job: dict) -> None:  #vers 1
        box = QMessageBox()
        box.setWindowTitle(job["title"])
        box.setText(job["text"])
        btns = [box.addButton(t, QMessageBox.ButtonRole.ActionRole) for t in job["buttons"]]
        box.exec()
        if box.clickedButton() in btns:
            job["pick"] = btns.index(box.clickedButton())
        job["ev"].set()
