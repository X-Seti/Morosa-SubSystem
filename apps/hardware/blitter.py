#this belongs in apps/hardware/blitter.py - Version: 5
# X-Seti - November 17 2026 - Morosa - Morosa Blitter.

"""
Morosa Blitter - Agnus blitter: area copy with minterms, shifts, masks and fill; line drawing.
"""

##Methods list -
# Blitter
# Blitter._area
# Blitter._line
# Blitter._minterm
# Blitter.read
# Blitter.start
# Blitter.write

from apps.core import video_ext

REGS = {0x040: "con0", 0x042: "con1", 0x044: "afwm", 0x046: "alwm", 0x060: "cmod", 0x062: "bmod", 0x064: "amod",
        0x066: "dmod", 0x070: "cdat", 0x072: "bdat", 0x074: "adat"}
PTRS = {0x048: ("cpt", True), 0x04A: ("cpt", False), 0x04C: ("bpt", True), 0x04E: ("bpt", False),
        0x050: ("apt", True), 0x052: ("apt", False), 0x054: ("dpt", True), 0x056: ("dpt", False)}


class Blitter:
    """read16(addr)/write16(addr, v) access chip RAM; done() is called when a blit finishes."""

    def __init__(self, read16, write16, done=None, ecs: bool = False):  #vers 1
        self.read16, self.write16 = read16, write16
        self.chip, self.mask = bytearray(8), 0
        self.done = done or (lambda: None)
        self.ecs = ecs
        self.con0 = self.con1 = self.afwm = self.alwm = 0
        self.cmod = self.bmod = self.amod = self.dmod = 0
        self.cdat = self.bdat = self.adat = 0
        self.cpt = self.bpt = self.apt = self.dpt = 0
        self.busy = False
        self.zero = True
        self.sizv = 0
        self.mode, self.wait = 0, 0

    def write(self, off: int, v: int) -> bool:  #vers 1
        v &= 0xFFFF
        if off in REGS:
            if REGS[off] in ("cmod", "bmod", "amod", "dmod"):
                v = v - 0x10000 if v & 0x8000 else v
            setattr(self, REGS[off], v)
        elif off in PTRS:
            name, high = PTRS[off]
            cur = getattr(self, name)
            setattr(self, name, (cur & 0xFFFF | (v & (0x1F if self.ecs else 7)) << 16) if high else (cur & 0x1F0000 | v & 0xFFFE))
        elif off == 0x058:
            self.start(v & 0x3F or 64, v >> 6 or 1024)
        elif off == 0x05C and self.ecs:
            self.sizv = v & 0x7FFF
        elif off == 0x05E and self.ecs:
            self.start(v & 0x7FF or 2048, self.sizv or 32768)
        elif off == 0x05A and self.ecs:
            self.con0 = self.con0 & 0xFF00 | v & 0xFF
        else:
            return False
        return True

    def read(self, off: int):  #vers 1
        if off == 0x002:
            return (0x4000 if self.busy else 0) | (0x2000 if self.zero else 0)
        return None

    @staticmethod
    def _minterm(lf: int, a: int, b: int, c: int) -> int:  #vers 1
        out = 0
        for i in range(8):
            if lf >> i & 1:
                out |= (a if i & 4 else ~a) & (b if i & 2 else ~b) & (c if i & 1 else ~c)
        return out & 0xFFFF

    def start(self, width: int, height: int) -> None:  #vers 2
        self.busy = True
        self.zero = True
        if self.con1 & 1:
            self._line(height)
        else:
            self._area(width, height)
        if self.mode == 1:
            n = bin(self.con0 >> 8 & 15).count("1")
            self.wait = max(1, (height * 8) if self.con1 & 1 else width * height * (4 if n >= 3 else 2))
            return
        self.busy = False
        self.done()

    def tick(self, cclocks: int) -> None:  #vers 1
        """Normal mode: busy and the interrupt follow the estimated blit time."""
        if self.wait:
            self.wait -= cclocks
            if self.wait <= 0:
                self.wait = 0
                self.busy = False
                self.done()

    def _area(self, width: int, height: int) -> None:  #vers 3
        """Area mode runs in video_ext; pointers and data registers come back."""
        r = video_ext.blit_area(self.chip, self.mask, self.con0, self.con1, self.afwm, self.alwm, self.adat, self.bdat, self.cdat,
                                self.apt, self.bpt, self.cpt, self.dpt, self.amod, self.bmod, self.cmod, self.dmod, width, height)
        self.apt, self.bpt, self.cpt, self.dpt, self.adat, self.bdat, self.cdat = r[:7]
        if not r[7]:
            self.zero = False

    def _line(self, length: int) -> None:  #vers 3
        """Line mode: pixel at bit ash of the word at cpt; SUD set means X major."""
        c0, c1 = self.con0, self.con1
        ash, lf = c0 >> 12, c0 & 0xFF
        sud, sul, aul = c1 >> 4 & 1, c1 >> 3 & 1, c1 >> 2 & 1
        sign = c1 >> 6 & 1
        bsh = c1 >> 12
        err = (self.apt & 0xFFFF) - 0x10000 if self.apt & 0x8000 else self.apt & 0xFFFF
        cpt = self.cpt
        row = self.cmod

        def move(x_axis: bool, neg: int) -> None:
            nonlocal ash, cpt, dot
            if x_axis:
                if neg:
                    ash -= 1
                    if ash < 0:
                        ash, cpt = 15, cpt - 2
                else:
                    ash += 1
                    if ash > 15:
                        ash, cpt = 0, cpt + 2
            else:
                cpt += -row if neg else row
                dot = False

        one_dot, dot = bool(c1 & 2), False
        for _ in range(length):
            c = self.read16(cpt)
            a = 0 if one_dot and dot else (self.adat & self.afwm) >> ash
            dot = True
            b = 0xFFFF if self.bdat >> (bsh & 15) & 1 else 0
            d = self._minterm(lf, a, b, c)
            if d:
                self.zero = False
            if c0 & 0x200 or True:
                self.write16(cpt, d)
            bsh = (bsh - 1) & 15
            major_x = bool(sud)
            if not sign:
                err += self.amod
                move(major_x, aul)
                move(not major_x, sul)
            else:
                err += self.bmod
                move(major_x, aul)
            sign = 1 if err < 0 else 0
        self.apt = err & 0xFFFF
        self.cpt = self.dpt = cpt
        self.con0 = self.con0 & 0x0FFF | ash << 12
