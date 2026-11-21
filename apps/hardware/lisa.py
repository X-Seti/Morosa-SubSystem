#this belongs in apps/hardware/lisa.py - Version: 1
# X-Seti - November 17 2026 - Morosa - Morosa Lisa.

"""
Morosa Lisa - AGA video: 256 colour 24-bit palette, eight bitplanes, HAM8, EHB, dual playfield and FMODE fetch width.
"""

##Methods list -
# Lisa
# Lisa._compose
# Lisa.fetch_mult
# Lisa.map_pens
# Lisa.nplanes
# Lisa.read
# Lisa.rgb
# Lisa.write

from apps.hardware.denise import Denise

PF2_OFFSET = (8, 16, 32, 64, 128, 128, 128, 128)


class Lisa(Denise):
    """Denise registers and renderer extended for AGA. Colours are 0xRRGGBB."""

    def __init__(self):  #vers 1
        super().__init__(True)
        self.color = [0] * 256
        self.hi = [0] * 256           # high nibble pairs written with LOCT clear
        self.lo = [0] * 256
        self.bplcon4 = 0x11
        self.fmode = 0

    def nplanes(self) -> int:  #vers 1
        n = self.bplcon0 >> 12 & 7
        return 8 if self.bplcon0 & 0x10 else n

    def fetch_mult(self) -> int:  #vers 1
        return (1, 2, 2, 4)[self.fmode & 3]

    def write(self, off: int, v: int) -> bool:  #vers 1
        v &= 0xFFFF
        if 0x180 <= off < 0x1C0:
            n = (self.bplcon3 >> 13 & 7) * 32 + ((off - 0x180) >> 1)
            if self.bplcon3 & 0x200:
                self.lo[n] = v & 0xFFF
            else:
                self.hi[n] = self.lo[n] = v & 0xFFF
            h, l = self.hi[n], self.lo[n]
            self.color[n] = (((h >> 8 & 15) << 4 | (l >> 8 & 15)) << 16 | ((h >> 4 & 15) << 4 | (l >> 4 & 15)) << 8
                             | (h & 15) << 4 | l & 15)
            return True
        if off == 0x10C:
            self.bplcon4 = v
            return True
        if off == 0x1FC:
            self.fmode = v
            return True
        return super().write(off, v)

    def read(self, off: int):  #vers 1
        if off == 0x07C:
            return 0xF8
        return super().read(off)

    def rgb(self, c: int) -> bytes:  #vers 1
        return bytes((c & 255, c >> 8 & 255, c >> 16 & 255, 255))

    def map_pens(self, pens: list) -> list:  #vers 1
        x = self.bplcon4 >> 8
        return [p ^ x for p in pens] if x else pens

    def _compose(self, pens: list, vpos: int, bpu: int, ham: bool, dbl: bool) -> list:  #vers 1
        res = []
        pf2pri = bool(self.bplcon2 & 0x40)
        off2 = PF2_OFFSET[self.bplcon3 >> 10 & 7]
        prev = self.color[0]
        c = self.color
        for p in pens:
            if ham and bpu >= 6:
                if bpu == 8:
                    ctl, d = p >> 6 & 3, (p & 63) << 2
                else:
                    ctl, d = p >> 4 & 3, (p & 15) * 17
                if ctl == 0:
                    prev = c[p & (63 if bpu == 8 else 15)]
                    res.append((prev, 1))
                    continue
                r, g, b = prev >> 16 & 255, prev >> 8 & 255, prev & 255
                if ctl == 1:
                    b = d
                elif ctl == 2:
                    r = d
                else:
                    g = d
                prev = r << 16 | g << 8 | b
                res.append((prev, 1))
            elif dbl:
                p1 = sum((p >> (2 * i) & 1) << i for i in range(4))
                p2 = sum((p >> (2 * i + 1) & 1) << i for i in range(4))
                a, b = (c[p1], 1) if p1 else (c[0], 0), (c[off2 + p2], 2) if p2 else (c[0], 0)
                if pf2pri:
                    res.append(b if p2 else a)
                else:
                    res.append(a if p1 else b)
            elif bpu == 6:
                v = c[p & 31]
                res.append(((v >> 1) & 0x7F7F7F if p & 32 else v, 1 if p else 0))
            else:
                res.append((c[p], 1 if p else 0))
        return res
