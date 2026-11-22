#this belongs in apps/hardware/lisa.py - Version: 4
# X-Seti - November 17 2026 - Morosa - Morosa Lisa.

"""
Morosa Lisa - AGA video: 256 colour 24-bit palette, eight bitplanes, HAM8, EHB, dual playfield and FMODE fetch width.
"""

##Methods list -
# Lisa
# Lisa.fetch_mult
# Lisa.nplanes
# Lisa.pens_xor
# Lisa.pf2_offset
# Lisa.read
# Lisa.rgb
# Lisa.write

from apps.hardware.denise import Denise

PF2_OFFSET = (8, 16, 32, 64, 128, 128, 128, 128)


class Lisa(Denise):
    """Denise registers and renderer extended for AGA. Colours are 0xRRGGBB."""

    aga = 1

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
            self.set_color(n, ((h >> 8 & 15) << 4 | (l >> 8 & 15)) << 16 | ((h >> 4 & 15) << 4 | (l >> 4 & 15)) << 8
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

    def pens_xor(self) -> int:  #vers 1
        return self.bplcon4 >> 8

    def pf2_offset(self) -> int:  #vers 1
        return PF2_OFFSET[self.bplcon3 >> 10 & 7]
