#this belongs in apps/gui/screen.py - Version: 17
# X-Seti - November 17 2026 - Morosa - Morosa Machine Screen.

"""
Morosa Screen - Qt window that runs a hardware Amiga: video, keyboard, mouse, audio and disk insert.
"""

##Methods list -
# KEYMAP
# MachineScreen
# MachineScreen._audio
# MachineScreen._busy
# MachineScreen._crop
# MachineScreen._due
# MachineScreen._frame
# MachineScreen._pipewire
# MachineScreen._pump
# MachineScreen._target
# MachineScreen._send
# MachineScreen._paint_fps
# MachineScreen._paint_hint
# MachineScreen._paint_note
# MachineScreen._paint_status
# MachineScreen.capture
# MachineScreen.closeEvent
# MachineScreen.focusInEvent
# MachineScreen.focusOutEvent
# MachineScreen.keyPressEvent
# MachineScreen.keyReleaseEvent
# MachineScreen.mouseMoveEvent
# MachineScreen.mousePressEvent
# MachineScreen.mouseReleaseEvent
# MachineScreen.paintEvent
# MachineScreen.pause
# MachineScreen.set_status
# MachineScreen.set_trim
# MachineScreen.snapshot
# MachineScreen.profile_start
# MachineScreen._profile_end
# MachineScreen.state_dump
# MachineScreen.start
# MachineScreen.stop
# MachineScreen.toggle_vkeyboard

import math
import struct

from PyQt6.QtCore import QPoint, QRect, QTimer, Qt
import time
from PyQt6.QtGui import QColor, QCursor, QFont, QFontMetrics, QImage, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from apps.hardware.denise import FB_LINES, FB_WIDTH
from apps.methods import config

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

    def __init__(self, machine, audio: bool = True, status: bool = True, joykeys: dict = None, trim: bool = False, snd_out: str = "qt", view: dict = None, parent=None):  #vers 7
        super().__init__(parent)
        self.m = machine
        self.status, self.paused, self.hold = status, False, {}
        self.trim, self.boxes = trim, []
        self.note, self.note_until = "", 0.0
        self.hud, self.settings = True, None
        self.fps, self.fcount, self.ftime = 0, 0, time.monotonic()
        self.joystick = dict(up=False, down=False, left=False, right=False, fire=False, fire2=False)
        self.joymap = {k: a for a, k in (joykeys or {}).items()}
        self.img = None
        self.sink = self.out = self.pw = None
        self.snd_out = snd_out
        self.auto_paused = False
        self.vk = None
        self.view = {"line": 0, "filter": 0, "aspect": 0, "scale": 0, **(view or {})}
        self.last = None
        self.captured = False
        self.mx = self.my = 0.0
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setMinimumSize(FB_WIDTH, FB_LINES // 2)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._frame)
        if audio:
            self._audio()

    def _audio(self) -> None:  #vers 3
        rate = self.m.paula.rate
        if self.snd_out == "pipewire":
            return self._pipewire(rate)
        try:
            from PyQt6.QtMultimedia import QAudioFormat, QAudioSink, QMediaDevices
            fmt = QAudioFormat()
            fmt.setSampleRate(rate)
            fmt.setChannelCount(2)
            fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
            self.sink = QAudioSink(QMediaDevices.defaultAudioOutput(), fmt, self)
            self.sink.setBufferSize(rate * 4 * 15 // 100)
            self.out = self.sink.start()
        except ImportError:
            self.sink = self.out = None

    def _pipewire(self, rate: int) -> None:  #vers 1
        """Pass audio straight to PipeWire through pw-cat; 24 and 32 bit Paula Plus sends s32."""
        import shutil
        import subprocess
        exe = shutil.which("pw-cat")
        if exe is None:
            self.note, self.note_until = "pw-cat not found, no sound", time.monotonic() + 4
            return
        self.pw_fmt = "s32" if self.m.paula.maxfmt >= 2 else "s16"
        self.pw = subprocess.Popen([exe, "--playback", "--rate", str(rate), "--channels", "2", "--format", self.pw_fmt, "-"],
                                   stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def _pump(self) -> None:  #vers 1
        """Send the samples of the last frame to the audio output."""
        s = self.m.paula.take_samples()
        if (self.out is not None or self.pw is not None) and s:
            self._send(s)
        else:
            self.m.paula.samples.clear()

    def _send(self, s: list) -> None:  #vers 1
        """Write mixed frames to PipeWire or the Qt sink."""
        wide = self.pw is not None and self.pw_fmt == "s32"
        vals = [max(-32768, min(32767, v * 2)) << (16 if wide else 0) for f in s for v in f]
        data = struct.pack(f"<{len(vals)}{'i' if wide else 'h'}", *vals)
        if self.pw is not None:
            try:
                self.pw.stdin.write(data)
                self.pw.stdin.flush()
            except OSError:
                self.pw = None
                self.note, self.note_until = "PipeWire closed, no sound", time.monotonic() + 4
        else:
            self.out.write(data)

    def toggle_vkeyboard(self) -> None:  #vers 1
        """Show or hide the virtual keyboard window (Scroll Lock)."""
        from apps.gui.vkeyboard import VKeyboard
        if self.vk is None:
            self.vk = VKeyboard(self.m.keyboard, self)
        self.vk.setVisible(not self.vk.isVisible())

    def start(self) -> None:  #vers 3
        self.timer.start(10 if self.sink is not None else 20)
        if self.view.get("vkeyboard"):
            self.toggle_vkeyboard()

    def stop(self) -> None:  #vers 4
        self.timer.stop()
        self.m.flush_disks()
        if self.pw is not None:
            self.pw.terminate()
            self.pw = None
        if self.sink is not None:
            self.sink.stop()

    def pause(self) -> bool:  #vers 1
        """Toggle pause; returns True while paused."""
        self.paused = not self.paused
        if self.paused:
            self.timer.stop()
            if self.sink is not None:
                self.sink.suspend()
        else:
            self.timer.start(20)
            if self.sink is not None:
                self.sink.resume()
        self.update()
        return self.paused

    def snapshot(self) -> None:  #vers 1
        """Save the Amiga picture, no overlays, as snaps/snapNN.png in the program folder."""
        if self.img is None:
            return
        d = config.ROOT / "snaps"
        d.mkdir(exist_ok=True)
        n = 1
        while (d / f"snap{n:02d}.png").exists():
            n += 1
        name = f"snap{n:02d}.png"
        ok = self.img.copy(self._crop()).save(str(d / name))
        self.note, self.note_until = (f"Saved {name}" if ok else "Snapshot failed"), time.monotonic() + 2.0
        self.update()

    def profile_start(self) -> None:  #vers 2
        """Shift+F10: profile 100 ticks, sampling guest PC; save dumps/profNN.txt."""
        import cProfile
        if getattr(self, "_prof", None) is not None:
            return
        m = self.m
        self._pcs, self._pstop, self._pirq, self._pn_s = {}, 0, 0, 0
        self._pact = (m.act_hd, m.act_hfs, m.act_ram + m.cpu.touches)
        orig = m._run_cpu

        def sample(cycles):
            r = orig(cycles)
            pc = m.cpu.pc
            self._pn_s += 1
            self._pcs[pc & ~0xFF] = self._pcs.get(pc & ~0xFF, 0) + 1
            self._pstop += m.cpu.stopped
            self._pirq += m.paula.level != 0
            return r
        m._run_cpu = sample
        self._prof, self._pn, self._pt, self._pf = cProfile.Profile(), 0, time.monotonic(), self.fcount
        self._prof.enable()
        self.note, self.note_until = "Profiling 100 ticks", time.monotonic() + 2.0

    def _profile_end(self) -> None:  #vers 3
        """Stop the profile and write the busiest functions."""
        import io
        import pstats
        prof, self._prof = self._prof, None
        prof.disable()
        out = io.StringIO()
        secs, frames = time.monotonic() - self._pt, self.fcount - self._pf
        out.write(f"ticks {self._pn} frames {frames} seconds {secs:.2f} fps {frames / secs:.1f}\n")
        m = self.m
        del m._run_cpu
        n = max(1, self._pn_s)
        out.write(f"guest samples {n} stopped {100 * self._pstop / n:.0f}% irq pending {100 * self._pirq / n:.0f}% model {m.cpu.model} ratio {m.ratio}\n")
        out.write(f"hd {m.act_hd - self._pact[0]} hostfs {m.act_hfs - self._pact[1]} ram {m.act_ram + m.cpu.touches - self._pact[2]}\n")
        out.write("guest pc 256-byte blocks:\n")
        for pc, c in sorted(self._pcs.items(), key=lambda t: -t[1])[:20]:
            out.write(f"  {pc:08X} {100 * c / n:5.1f}%\n")
        for key in ("tottime", "cumulative"):
            out.write(f"\nsorted by {key}\n")
            pstats.Stats(prof, stream=out).sort_stats(key).print_stats(28)
        from apps.methods import debugdump
        d = config.ROOT / "dumps"
        d.mkdir(exist_ok=True)
        n = 1
        while (d / f"prof{n:02d}.txt").exists():
            n += 1
        (d / f"prof{n:02d}.txt").write_text(out.getvalue(), encoding="utf-8")
        self.note, self.note_until = f"Saved prof{n:02d}", time.monotonic() + 2.0

    def state_dump(self) -> None:  #vers 1
        """Save the picture and display state as dumps/dumpNN.png and .txt."""
        from apps.methods import debugdump
        d = config.ROOT / "dumps"
        stem = debugdump.next_name(d)
        if self.img is not None:
            self.img.save(str(d / f"{stem}.png"))
        (d / f"{stem}.txt").write_text(debugdump.dump_text(self.m), encoding="utf-8")
        self.note, self.note_until = f"Saved {stem}", time.monotonic() + 2.0
        self.update()

    def _paint_note(self, p) -> None:  #vers 1
        """Short message, top centre."""
        if time.monotonic() > self.note_until:
            return
        f = QFont("monospace", 9)
        p.setFont(f)
        fm = QFontMetrics(f)
        w = fm.horizontalAdvance(self.note) + 16
        p.setPen(QColor(30, 90, 30, 220))
        p.setBrush(QColor(0, 12, 0, 170))
        p.drawRoundedRect((self.width() - w) // 2, 10, w, fm.height() + 8, 4, 4)
        p.setPen(QColor(140, 255, 140))
        p.drawText((self.width() - w) // 2 + 8, 10 + 4 + fm.ascent(), self.note)

    def set_trim(self, on: bool) -> None:  #vers 1
        self.trim = on
        self.update()

    def _crop(self) -> QRect:  #vers 2
        """Union of the display window over the last 25 frames; steady in games and WB."""
        if self.img is not None and (self.img.width(), self.img.height()) != (FB_WIDTH, FB_LINES):
            return QRect(0, 0, self.img.width(), self.img.height())
        if not self.trim or not self.boxes:
            return QRect(0, 0, FB_WIDTH, FB_LINES)
        x0 = min(b[0] for b in self.boxes)
        y0 = min(b[1] for b in self.boxes)
        x1 = max(b[0] + b[2] for b in self.boxes)
        y1 = max(b[1] + b[3] for b in self.boxes)
        return QRect(x0, y0, x1 - x0, y1 - y0)

    def set_status(self, on: bool) -> None:  #vers 1
        self.status = on
        self.update()

    def closeEvent(self, e) -> None:  #vers 2
        self.stop()
        if self.vk is not None:
            self.vk.close()
        super().closeEvent(e)

    def _due(self) -> int:  #vers 1
        """Frames to run now; the Qt audio buffer level sets the pace."""
        if self.sink is None or self.out is None or not self.sink.bufferSize():
            return 1
        buf = self.sink.bufferSize() - self.sink.bytesFree()
        want = self.m.paula.rate * 4 * 6 // 100
        return 0 if buf >= want else min(3, -(-(want - buf) // (self.m.paula.rate * 4 // 50)))

    def _busy(self) -> bool:  #vers 1
        """True when the guest read the hard disk or host folders since the last check."""
        now = (self.m.act_hd, self.m.act_hfs)
        last, self._wlast = getattr(self, "_wlast", now), now
        return now != last

    def _frame(self) -> None:  #vers 5
        n = self._due()
        if not n:
            return
        t0 = time.monotonic()
        for i in range(n - 1):
            self.m.run_frame(True)
            self.fcount += 1
            self._pump()
        if self._busy():
            while time.monotonic() - t0 < 0.012:
                self.m.run_frame(True)
                self.fcount += 1
                self.m.paula.samples.clear()
                if not self._busy():
                    break
        self.m.run_frame()
        self.fcount += 1
        if getattr(self, "_prof", None) is not None:
            self._pn += 1
            if self._pn >= 100:
                self._profile_end()
        now = time.monotonic()
        if now - self.ftime >= 1.0:
            self.fps, self.fcount, self.ftime = round(self.fcount / (now - self.ftime)), 0, now
        if self.status:
            for k, v in self.m.activity().items():
                self.hold[k] = 8 if v else max(0, self.hold.get(k, 0) - 1)
        w, h, data = self.m.framebuffer()
        if self.trim:
            self.boxes = (self.boxes + [self.m.display_box()])[-25:]
        self.img = QImage(data, w, h, w * 4, QImage.Format.Format_RGB32).copy()
        self._pump()
        n = self.view.get("scale", 0)
        if n and not (self.isMaximized() or self.isFullScreen()):
            c = self._crop()
            d = 1 if self.img is not None and (self.img.width(), self.img.height()) != (FB_WIDTH, FB_LINES) else 2
            w = c.width() * n // d
            ratio = (0, 4 / 3, 16 / 9)[self.view["aspect"]]
            sz = (w, int(w / ratio) if ratio else c.height() * n // d)
            if sz != getattr(self, "_fitsz", None):
                self._fitsz = sz
                self.resize(*sz)
        self.update()

    def _target(self) -> QRect:  #vers 2
        """Where the picture goes: whole window, or 4:3 or 16:9 fitted and centred."""
        ratio = (0, 4 / 3, 16 / 9)[self.view["aspect"]]
        r = self.rect()
        n = self.view.get("scale", 0)
        if n:
            c = self._crop()
            d = 1 if self.img is not None and (self.img.width(), self.img.height()) != (FB_WIDTH, FB_LINES) else 2
            w = c.width() * n // d
            h = int(w / ratio) if ratio else c.height() * n // d
            return QRect((r.width() - w) // 2, (r.height() - h) // 2, w, h)
        if not ratio:
            return r
        w = min(r.width(), int(r.height() * ratio))
        h = int(w / ratio)
        return QRect((r.width() - w) // 2, (r.height() - h) // 2, w, h)

    def paintEvent(self, e) -> None:  #vers 5
        p = QPainter(self)
        if self.img is not None:
            c = self._crop()
            t = self._target()
            p.fillRect(self.rect(), QColor(0, 0, 0))
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, bool(self.view["filter"]))
            p.drawImage(t, self.img, c)
            if self.view["line"] == 1:
                rowh = t.height() / c.height()
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(0, 0, 0, 90))
                for r in range(1, c.height(), 2):
                    p.drawRect(QRect(t.x(), t.y() + int(r * rowh), t.width(), max(1, int(rowh))))
        if self.status and self.hud:
            self._paint_status(p)
            self._paint_fps(p)
        self._paint_note(p)
        if self.hud and not self.captured and not self.paused:
            self._paint_hint(p)
        if self.paused:
            p.setFont(QFont("monospace", 16, QFont.Weight.Bold))
            p.setPen(QColor(0, 0, 0, 200))
            p.drawText(self.rect().adjusted(2, 12, 2, 12), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, "PAUSE")
            p.setPen(QColor(120, 255, 120))
            p.drawText(self.rect().adjusted(0, 10, 0, 10), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, "PAUSE")

    def _paint_hint(self, p) -> None:  #vers 1
        """Mouse capture hint, bottom left."""
        f = QFont("monospace", 9)
        p.setFont(f)
        fm = QFontMetrics(f)
        t = "Click to capture mouse"
        p.setPen(QColor(30, 90, 30, 220))
        p.setBrush(QColor(0, 12, 0, 170))
        p.drawRoundedRect(10, self.height() - fm.height() - 18, fm.horizontalAdvance(t) + 16, fm.height() + 8, 4, 4)
        p.setPen(QColor(140, 255, 140))
        p.drawText(18, self.height() - 14 - fm.descent(), t)

    def capture(self, on: bool) -> None:  #vers 1
        """Grab or release the pointer; Left Control + Alt releases."""
        if on == self.captured:
            return
        self.captured = on
        self.mx = self.my = 0.0
        if on:
            self.setCursor(Qt.CursorShape.BlankCursor)
            self.grabMouse()
            QCursor.setPos(self.mapToGlobal(QPoint(self.width() // 2, self.height() // 2)))
        else:
            self.releaseMouse()
            self.unsetCursor()
            self.m.ports.mouse_button(left=False, right=False)
        self.update()

    def focusOutEvent(self, e) -> None:  #vers 2
        self.capture(False)
        if self.view.get("pause_unfocus") and not self.paused:
            self.pause()
            self.auto_paused = True
        super().focusOutEvent(e)

    def focusInEvent(self, e) -> None:  #vers 1
        if self.auto_paused and self.paused:
            self.pause()
        self.auto_paused = False
        super().focusInEvent(e)

    def _paint_fps(self, p) -> None:  #vers 1
        """FPS readout, top left."""
        f = QFont("monospace", 9, QFont.Weight.Bold)
        p.setFont(f)
        t = f"{self.fps} FPS"
        fm = QFontMetrics(f)
        w, h = fm.horizontalAdvance(t) + 16, fm.height() + 8
        p.setPen(QColor(30, 90, 30, 220))
        p.setBrush(QColor(0, 12, 0, 170))
        p.drawRoundedRect(10, 10, w, h, 4, 4)
        p.setPen(QColor(140, 255, 140))
        p.drawText(18, 14 + fm.ascent(), t)

    def _paint_status(self, p) -> None:  #vers 3
        """CRT style on screen display, bottom right."""
        names = ("FD", "HD", "CD", "RAM", "CPU") + (("HostFS",) if getattr(self.m, "hostfs", False) else ())
        f = QFont("monospace", 9, QFont.Weight.Bold)
        p.setFont(f)
        fm = QFontMetrics(f)
        gap = fm.horizontalAdvance(" | ")
        widths = [fm.horizontalAdvance(n) for n in names]
        w = sum(widths) + gap * (len(names) - 1) + 16
        h = fm.height() + 8
        x, y = self.width() - w - 10, self.height() - h - 10
        p.setPen(QColor(30, 90, 30, 220))
        p.setBrush(QColor(0, 12, 0, 170))
        p.drawRoundedRect(x, y, w, h, 4, 4)
        cx = x + 8
        for i, n in enumerate(names):
            lit = self.hold.get(n, 0) > 0
            p.setPen(QColor(140, 255, 140) if lit else QColor(35, 85, 35))
            p.drawText(cx, y + 4 + fm.ascent(), n)
            if lit:
                a = int(150 + 105 * math.sin(time.monotonic() * 14))
                p.setPen(QPen(QColor(255, 30, 30, a), 2))
                uy = y + 5 + fm.ascent() + 2
                p.drawLine(cx, uy, cx + widths[i], uy)
            cx += widths[i]
            if i < len(names) - 1:
                p.setPen(QColor(35, 85, 35))
                p.drawText(cx, y + 4 + fm.ascent(), " | ")
                cx += gap

    def keyPressEvent(self, e) -> None:  #vers 9
        mod = e.modifiers()
        if e.key() in (Qt.Key.Key_Print, Qt.Key.Key_F10, Qt.Key.Key_F11, Qt.Key.Key_F12, Qt.Key.Key_ScrollLock):
            if e.isAutoRepeat():
                return
            if e.key() == Qt.Key.Key_Print:
                self.snapshot()
            elif e.key() == Qt.Key.Key_F10:
                self.profile_start() if mod & Qt.KeyboardModifier.ShiftModifier else self.state_dump()
            elif e.key() == Qt.Key.Key_ScrollLock:
                self.toggle_vkeyboard()
            elif e.key() == Qt.Key.Key_F11:
                self.hud = not self.hud
                self.update()
            else:
                self.capture(False)
                if self.settings is not None:
                    self.settings.show()
                    self.settings.raise_()
                    self.settings.activateWindow()
            return
        if self.view.get("rctrl") and e.key() == Qt.Key.Key_Control and e.nativeVirtualKey() == 0xFFE4:
            if not e.isAutoRepeat():
                self.m.keyboard.press(0x66)
            return
        if self.captured and ((e.key() == Qt.Key.Key_Alt and mod & Qt.KeyboardModifier.ControlModifier)
                              or (e.key() == Qt.Key.Key_Control and mod & Qt.KeyboardModifier.AltModifier)):
            self.capture(False)
            return
        if e.key() in self.joymap:
            self.joystick[self.joymap[e.key()]] = True
            self.m.ports.joy(**self.joystick)
        c = KEYMAP.get(e.key())
        if c is not None and not e.isAutoRepeat():
            self.m.keyboard.press(c)

    def keyReleaseEvent(self, e) -> None:  #vers 3
        if self.view.get("rctrl") and e.key() == Qt.Key.Key_Control and e.nativeVirtualKey() == 0xFFE4:
            if not e.isAutoRepeat():
                self.m.keyboard.release(0x66)
            return
        if e.key() in self.joymap:
            self.joystick[self.joymap[e.key()]] = False
            self.m.ports.joy(**self.joystick)
        c = KEYMAP.get(e.key())
        if c is not None and not e.isAutoRepeat():
            self.m.keyboard.release(c)

    def mouseMoveEvent(self, e) -> None:  #vers 3
        if not self.captured:
            return
        c = QPoint(self.width() // 2, self.height() // 2)
        p = e.position().toPoint()
        dx, dy = p.x() - c.x(), p.y() - c.y()
        if dx or dy:
            cr = self._crop()
            self.mx += dx * cr.width() / max(1, self.width()) / 2
            self.my += dy * cr.height() / 2 / max(1, self.height())
            ix, iy = int(self.mx), int(self.my)
            self.mx, self.my = self.mx - ix, self.my - iy
            self.m.ports.mouse_move(ix, iy)
            QCursor.setPos(self.mapToGlobal(c))

    def mousePressEvent(self, e) -> None:  #vers 2
        if not self.captured:
            self.capture(True)
            return
        self.m.ports.mouse_button(left=True if e.button() == Qt.MouseButton.LeftButton else None,
                                  right=True if e.button() == Qt.MouseButton.RightButton else None)

    def mouseReleaseEvent(self, e) -> None:  #vers 2
        if not self.captured:
            return
        self.m.ports.mouse_button(left=False if e.button() == Qt.MouseButton.LeftButton else None,
                                  right=False if e.button() == Qt.MouseButton.RightButton else None)
