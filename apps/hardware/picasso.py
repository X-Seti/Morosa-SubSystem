#this belongs in apps/hardware/picasso.py - Version: 1
# X-Seti - November 22 2026 - Morosa - Morosa Picasso IV RTG Board.

"""
Morosa Picasso - Village Tronic Picasso IV (Zorro III) built on the Cirrus GD5446: registers at +$600000, VRAM at +$1000000.
"""

##Methods list -
##class PicassoIV: -
# __init__
# config_rom
# frame
# map
# read
# write
# _reg_read
# _reg_write

from apps.hardware.cirrus import Cirrus

REGS, VRAM = 0x600000, 0x1000000
MFR, PRODUCT = 0x0877, 0x18


class PicassoIV:
    """Zorro III graphics board. VRAM is direct memory for the CPU; the VGA ports are hooked."""

    def __init__(self, vram_mb: int = 4, log=None):  #vers 1
        if vram_mb not in (1, 2, 4):
            raise ValueError("Picasso IV VRAM must be 1, 2 or 4 MB")
        self.zorro, self.kb = 3, 32768
        self.mfr, self.product, self.serial = MFR, PRODUCT, 1
        self.chip = Cirrus(vram_mb * 1024)
        self.base = None
        self.ram = None
        self.log = log
        self.chip.log = (lambda p, v: log(f"io {p:04X} {v:02X}") if isinstance(p, int) else log(f"{p} {v:02X}")) if log else None

    def config_rom(self) -> bytes:  #vers 1
        """16 bytes: Zorro III board of 32 MB, no memory list."""
        return bytes([0x80 | 1, self.product, 0x00, 0, self.mfr >> 8, self.mfr & 255]) + self.serial.to_bytes(4, "big") + bytes(6)

    def map(self, bus, cpu, base: int, size: int) -> None:  #vers 1
        """Hook the whole aperture; VRAM is added as direct RAM so the CPU writes it without Python."""
        bus.hook_range(base, base + size, self.read, self.write)
        cpu.add_ram(base + VRAM, self.chip.vram)

    def _reg_read(self, off: int) -> int:  #vers 1
        return self.chip.io_read(off & 0xFFF)

    def _reg_write(self, off: int, v: int) -> None:  #vers 1
        self.chip.io_write(off & 0xFFF, v)

    def read(self, a: int, size: int) -> int:  #vers 1
        off = a - self.base
        n = (1, 2, 4)[size]
        if REGS <= off < REGS + 0x1000:
            r = off - REGS
            return int.from_bytes(bytes(self._reg_read(r + i) for i in range(n)), "big")
        if VRAM <= off < VRAM + self.chip.size:
            o = off - VRAM
            return int.from_bytes(self.chip.vram[o:o + n], "big")
        return 0

    def write(self, a: int, size: int, v: int) -> None:  #vers 1
        off = a - self.base
        n = (1, 2, 4)[size]
        if REGS <= off < REGS + 0x1000:
            r = off - REGS
            for i, b in enumerate(v.to_bytes(n, "big")):
                self._reg_write(r + i, b)
        elif VRAM <= off < VRAM + self.chip.size:
            o = off - VRAM
            self.chip.vram[o:o + n] = (v & (1 << 8 * n) - 1).to_bytes(n, "big")

    def frame(self):  #vers 1
        return self.chip.frame()
