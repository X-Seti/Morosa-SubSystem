#this belongs in apps/gui/screen.py - Version: 1
# X-Seti - November 17 2026 - Morosa - Morosa Machine Screen.

"""
Morosa Screen - Qt window that runs a hardware Amiga: video, keyboard, mouse, audio and disk insert.
"""

##Methods list -
# KEYMAP
# MachineScreen
# MachineScreen._audio
# MachineScreen._frame
# MachineScreen.keyPressEvent
# MachineScreen.keyReleaseEvent
# MachineScreen.mouseMoveEvent
# MachineScreen.mousePressEvent
# MachineScreen.mouseReleaseEvent
# MachineScreen.paintEvent
# MachineScreen.start
# MachineScreen.stop

import struct

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtWidgets import QWidget

K = Qt.Key
KEYMAP = {
    K.Key_QuoteLeft: 0x00, K.Key_1: 0x01, K.Key_2: 0x02, K.Key_3: 0x03, K.Key_4: 0x04, K.Key_5: 0x05,
    K.Key_6: 0x06, K.Key_7: 0x07, K.Key_8: 0x08, K.Key_9: 0x09, K.Key_0: 0x0A, K.Key_Minus: 0x0B,
    K.Key_Equal: 0x0C, K.Key_Backslash: 0x0D, K.Key_Q: 0x10, K.Key_W: 0x11, K.Key_E: 0x12, K.Key_R: 0x13,
    K.Key_T: 0x14, K.Key_Y: 0x15, K.Key_U: 0x16, K.Key_I: 0x17, K.Key_O: 0x18, K.Key_P: 0x19,
    K.Key_BracketLeft: 0x1A, K.Key_BracketRight: 0x1B, K.Key_A: 0x20, K.Key_S: 0x21, K.Key_D: 0x22,
    K.Key_F: 0x23, K.Key_G: 0x24, K.Key_H: 0x25, K.Key_J: 0x26, K.Key_K: 0x27, K.Key_L: 0x28,
    K.Key_Semicolon: 0x29, K.Key_Apostrophe: 0x2A, K.Key_Z: 0x31, K.Key_X: 0x32, K.Key_C: 0x33,
    K.Key_V: 0x34, K.Key_B: 0x35, K.Key_N: 0x36, K.Key_M: 0x37, K.Key_Comma: 0x38, K.Key_Period: 0x39,
    K.Key_Slash: 0x3A, K.Key_Space: 0x40, K.Key_Backspace: 0x41, K.Key_Tab: 0x42, K.Key_Return: 0x44,
    K.Key_Enter: 0x43, K.Key_Escape: 0x45, K.Key_Delete: 0x46, K.Key_Up: 0x4C, K.Key_Down: 0x4D,
    K.Key_Right: 0x4E, K.Key_Left: 0x4F, K.Key_F1: 0x50, K.Key_F2: 0x51, K.Key_F3: 0x52, K.Key_F4: 0x53,
    K.Key_F5: 0x54, K.Key_F6: 0x55, K.Key_F7: 0x56, K.Key_F8: 0x57, K.Key_F9: 0x58, K.Key_F10: 0x59,
    K.Key_Shift: 0x60, K.Key_CapsLock: 0x62, K.Key_Control: 0x63, K.Key_Alt: 0x64, K.Key_Meta: 0x66,
}


class MachineScreen(QWidget):
    """Runs machine.run_frame() on a 20 ms timer and shows its framebuffer."""

    def __init__(self, machine, audio: bool = True, parent=None):  #vers 1
        super().__init__(parent)
        self.m = machine
        self.img = None
        self.sink = self.out = None
        self.last = None
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setMinimumSize(704, 313)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._frame)
        if audio:
            self._audio()

    def _audio(self) -> None:  #vers 1
        try:
            from PyQt6.QtMultimedia import QAudioFormat, QAudioSink, QMediaDevices
            fmt = QAudioFormat()
            fmt.setSampleRate(44100)
            fmt.setChannelCount(2)
            fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
            self.sink = QAudioSink(QMediaDevices.defaultAudioOutput(), fmt, self)
            self.out = self.sink.start()
        except ImportError:
            self.sink = self.out = None

    def start(self) -> None:  #vers 1
        self.timer.start(20)

    def stop(self) -> None:  #vers 1
        self.timer.stop()

    def _frame(self) -> None:  #vers 1
        self.m.run_frame()
        w, h, data = self.m.framebuffer()
        self.img = QImage(data, w, h, w * 4, QImage.Format.Format_RGB32).copy()
        s = self.m.paula.take_samples()
        if self.out is not None and s:
            self.out.write(struct.pack(f"<{2 * len(s)}h", *[max(-32768, min(32767, v * 2)) for f in s for v in f]))
        else:
            self.m.paula.samples.clear()
        self.update()

    def paintEvent(self, e) -> None:  #vers 1
        if self.img is not None:
            QPainter(self).drawImage(self.rect(), self.img)

    def keyPressEvent(self, e) -> None:  #vers 1
        c = KEYMAP.get(e.key())
        if c is not None and not e.isAutoRepeat():
            self.m.keyboard.press(c)

    def keyReleaseEvent(self, e) -> None:  #vers 1
        c = KEYMAP.get(e.key())
        if c is not None and not e.isAutoRepeat():
            self.m.keyboard.release(c)

    def mouseMoveEvent(self, e) -> None:  #vers 1
        p = e.position()
        if self.last is not None:
            self.m.ports.mouse_move(int((p.x() - self.last.x()) * 704 / max(1, self.width()) / 2),
                                    int((p.y() - self.last.y()) * 313 / max(1, self.height())))
        self.last = p

    def mousePressEvent(self, e) -> None:  #vers 1
        self.m.ports.mouse_button(left=True if e.button() == Qt.MouseButton.LeftButton else None,
                                  right=True if e.button() == Qt.MouseButton.RightButton else None)

    def mouseReleaseEvent(self, e) -> None:  #vers 1
        self.m.ports.mouse_button(left=False if e.button() == Qt.MouseButton.LeftButton else None,
                                  right=False if e.button() == Qt.MouseButton.RightButton else None)
