#this belongs in apps/hardware/denise.py - Version: 8
# X-Seti - November 17 2026 - Morosa - Morosa Denise.

"""
Morosa Denise - OCS/ECS video: bitplane lines to pixels with dual playfield, HAM, EHB and eight sprites.
"""

##Methods list -
# Denise
# Denise.fetch_mult
# Denise.set_color
# Denise.pens_xor
# Denise.pf2_offset
# Denise.nplanes
# Denise.read
# Denise.render_line
# Denise.rgb
# Denise.write

import numpy as np

from apps.core import video_ext

LEFT_ABS = 0x40          # lowres x of framebuffer column 0
FB_WIDTH = 832           # hires pixels
FB_LINES = 626
HIRES, HAM, DBLPF, LACE = 0x8000, 0x0800, 0x0400, 0x0004


class Denise:
    """Register file and line renderer; Agnus feeds plane words and sprite data."""

    aga = 0

    def __init__(self, ecs: bool = False):  #vers 1
        self.ecs = ecs
        self.bplcon0 = self.bplcon1 = self.bplcon2 = self.bplcon3 = 0
        self.color = [0] * 32
        self.spr = [dict(pos=0, ctl=0, a=0, b=0, armed=False) for _ in range(8)]
        self.spr_width = 16
        self.fb = bytearray(FB_WIDTH * FB_LINES * 4)
        self.bpldat = [0] * 6
        self.joy = [0, 0]
        self.clxcon = self.clxdat = 0
        self.clx_mask = 0x7FFF
        self.diw = (0x2C81, 0x2CC1)
        self.rec = False              # Agnus sets while the copper runs
        self.cw = []                  # (x, index, value) colour changes this line
        self.cw0 = {}                 # index -> value at line start
        self.agnus = None
        self.pver = id(self) & 0x3FFFFFFF

    def set_color(self, n: int, val: int) -> None:  #vers 1
        """Store a palette entry; copper writes are logged with beam x for mid-line changes."""
        if self.rec and self.agnus is not None:
            self.cw0.setdefault(n, self.color[n])
            self.cw.append((2 * self.agnus.hpos, n, val))
        self.color[n] = val
        self.pver = self.pver + 1 & 0x3FFFFFFF

    # ---- registers ----
    def write(self, off: int, v: int) -> bool:  #vers 1
        v &= 0xFFFF
        if off == 0x100:
            self.bplcon0 = v
        elif off == 0x102:
            self.bplcon1 = v
        elif off == 0x104:
            self.bplcon2 = v
        elif off == 0x106 and self.ecs:
            self.bplcon3 = v
        elif 0x180 <= off < 0x1C0:
            self.set_color((off - 0x180) >> 1, v & 0xFFF)
        elif 0x110 <= off <= 0x11A:
            self.bpldat[(off - 0x110) >> 1] = v
        elif 0x140 <= off < 0x180:
            n, reg = (off - 0x140) >> 3, (off >> 1) & 3
            s = self.spr[n]
            if reg == 0:
                s["pos"] = v
            elif reg == 1:
                s["ctl"] = v
                s["armed"] = False
            elif reg == 2:
                s["a"] = v
                s["armed"] = True
            else:
                s["b"] = v
        elif off == 0x098:
            self.clxcon = v
        elif off in (0x02A, 0x02C, 0x036):
            pass
        else:
            return False
        return True

    def read(self, off: int):  #vers 1
        if off in (0x00A, 0x00C):
            return self.joy[(off - 0x00A) >> 1]
        if off == 0x00E:
            v, self.clxdat = self.clxdat & self.clx_mask, 0
            return v
        if off == 0x07C:
            return 0xFC if self.ecs else 0xFF
        return None

    def nplanes(self) -> int:  #vers 1
        return self.bplcon0 >> 12 & 7

    def fetch_mult(self) -> int:  #vers 1
        return 1

    def pens_xor(self) -> int:  #vers 1
        return 0

    def pf2_offset(self) -> int:  #vers 1
        return 8

    def rgb(self, c: int) -> bytes:  #vers 1
        return bytes(((c & 15) * 17, (c >> 4 & 15) * 17, (c >> 8 & 15) * 17, 255))

    # ---- rendering ----
    def render_line(self, vpos: int, planes, x_abs: int, diw_h: tuple, diw_v: tuple) -> None:  #vers 6
        """planes: per-plane words for the fetched region from lowres x_abs; drawn in C, clipped to the window."""
        if not isinstance(planes, tuple):
            planes = [p if isinstance(p, np.ndarray) else np.asarray(p, dtype=">u2") for p in planes]
        spr = [(s["armed"], s["pos"], s["ctl"], s["a"], s["b"]) for s in self.spr]
        pal, pv = self.color, self.pver
        if self.cw0:
            pal, pv = list(pal), -1
            for n, v in self.cw0.items():
                pal[n] = v
        chg = self.cw
        self.cw, self.cw0 = [], {}
        lace = self.bplcon0 & 4
        dbl = self.agnus.lines > 450
        row = vpos if dbl else 2 * vpos + (0 if self.agnus.lof else 1) if lace else 2 * vpos
        self.clxdat |= video_ext.render_line(self.fb, row, planes, x_abs, diw_h[0], diw_h[1], diw_v[0], diw_v[1], self.bplcon0,
                              self.bplcon1, self.bplcon2, self.nplanes(), self.aga, self.pens_xor(),
                              self.pf2_offset(), pal, spr, chg, 0 if lace or dbl else 1, self.clxcon,
                              self.spr_width, self.bplcon3, getattr(self, "bplcon4", 0x11), pv)
