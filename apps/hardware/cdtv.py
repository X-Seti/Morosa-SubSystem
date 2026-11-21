#this belongs in apps/hardware/cdtv.py - Version: 2
# X-Seti - November 17 2026 - Morosa - Morosa CDTV DMAC and TPI.

"""
Morosa CDTV - DMAC register file, 6525 TPI and the CD controller command port at 0xE90000.
"""

##Methods list -
# DMAC
# DMACBoard
# DMACBoard.config_rom
# DMACBoard.read
# DMACBoard.write
# DMAC._lines
# DMAC._raise
# DMAC._start_dma
# DMAC._tpi_irq
# DMAC.hsync
# DMAC.insert
# DMAC.read
# DMAC.write
# TPI
# TPI.raise_line
# TPI.read
# TPI.write

from apps.hardware.cdtv_cd import CDTVDrive

DMAC_BASE = 0xE90000
ISTR_INT_P, ISTR_FE_FLG, ISTR_FF_FLG, ISTR_E_INT = 0x10, 0x01, 0x02, 0x20
CNTR_INTEN, CNTR_PREST, CNTR_PDMD, CNTR_TCEN = 0x10, 0x40, 0x20, 0x80
LINES_PER_SECTOR = 208


class DMACBoard:
    """AutoConfig face of the DMAC: Zorro II, 64K, Commodore product 3; the OS places it, normally at 0xE90000."""

    zorro, kb, base = 2, 64, None

    def __init__(self, dmac):  #vers 1
        self.dmac = dmac

    def config_rom(self) -> bytes:  #vers 1
        return bytes([0xC1, 0x03, 0x40, 0, 0x02, 0x02]) + bytes(10)

    def read(self, a: int, size: int) -> int:  #vers 1
        o, n = a - self.base, (1, 2, 4)[size]
        return int.from_bytes(bytes(self.dmac.read(o + i) for i in range(n)), "big")

    def write(self, a: int, size: int, v: int) -> None:  #vers 1
        o, n = a - self.base, (1, 2, 4)[size]
        for i, byte in enumerate(v.to_bytes(4, "big")[4 - n:]):
            self.dmac.write(o + i, byte)


class TPI:
    """6525: ports A, B, C with direction registers, mode 1 interrupt latch and mask."""

    def __init__(self, irq=None):  #vers 1
        self.pa = self.pb = self.pc = 0
        self.da = self.db = self.dc = 0
        self.cr = 0
        self.imask = 0
        self.latch = 0
        self.air = 0
        self.irq = irq or (lambda on: None)
        self.pins_a = self.pins_b = 0xFF
        self.pins_c = 0xFF

    def _update(self) -> None:  #vers 2
        act = self.latch & self.imask
        if self.cr & 1 and act:
            self.air = 1 << act.bit_length() - 1
        self.irq(bool(self.cr & 1 and act))

    def raise_line(self, n: int) -> None:  #vers 1
        """Input line n (0..4) fired; latched when mode 1."""
        if self.cr & 1:
            self.latch |= 1 << n
            self._update()

    def read(self, reg: int) -> int:  #vers 2
        if reg == 0:
            return self.pa & self.da | self.pins_a & ~self.da & 0xFF
        if reg == 1:
            return self.pb & self.db | self.pins_b & ~self.db & 0xFF
        if reg == 2:
            if self.cr & 1:
                return self.latch & 0x1F | (0x20 if self.latch & self.imask else 0) | self.pc & 0xC0
            return self.pc & self.dc | self.pins_c & ~self.dc & 0xFF
        if reg == 3:
            return self.da
        if reg == 4:
            return self.db
        if reg == 5:
            return self.imask if self.cr & 1 else self.dc
        if reg == 6:
            return self.cr
        if reg == 7:
            if self.cr & 1:
                v = self.air
                self.latch &= ~v
                self.air = 0
                self._update()
                return v
            return 0
        return 0

    def write(self, reg: int, v: int) -> None:  #vers 1
        v &= 0xFF
        if reg == 0:
            self.pa = v
        elif reg == 1:
            self.pb = v
        elif reg == 2:
            self.pc = v
        elif reg == 3:
            self.da = v
        elif reg == 4:
            self.db = v
        elif reg == 5:
            if self.cr & 1:
                self.imask = v & 0x1F
            else:
                self.dc = v
        elif reg == 6:
            self.cr = v
        self._update()


class DMAC:
    """Register offsets from the card base. CD data moves by DMA to mem_write(addr, bytes)."""

    def __init__(self, irq=None, mem_write=None):  #vers 2
        self.drive = CDTVDrive()
        self.mem_write = mem_write or (lambda a, d: None)
        self.dma_wait = 0
        self.pending = b""
        self.istr = 0
        self.cntr = 0
        self.wtc = self.acr = self.dawr = 0
        self.dma_on = False
        self.cmd = []
        self.irq = irq or (lambda on: None)
        self.tpi = TPI(self._tpi_irq)
        self._lines()

    def insert(self, image) -> None:  #vers 1
        self.drive.insert(image)

    def _lines(self) -> None:  #vers 1
        """TPI port C inputs, active low: bit 2 STCH, bits 3-4 STEN."""
        d = self.drive
        self.tpi.pins_c = 0xFF & ~(0x04 if d.stch else 0) & ~(0x18 if d.sten else 0)
        if d.stch and self.tpi.cr & 1:
            self.tpi.raise_line(2)
            d.stch = False
        if d.sten:
            self.tpi.raise_line(3)

    def _start_dma(self) -> None:  #vers 2
        d = self.drive
        if self.cntr & CNTR_PDMD:
            return
        if not self.pending and d.count:
            self.pending = d.read_sectors()
        if not self.pending:
            return
        n = min(len(self.pending), self.wtc * 2)
        self.mem_write(self.acr, self.pending[:n])
        self.pending = self.pending[n:]
        self.acr += n
        self.wtc = 0
        self.dma_wait = max(1, n // 2048) * LINES_PER_SECTOR
        self._lines()

    def hsync(self) -> None:  #vers 2
        if self.dma_wait:
            self.dma_wait -= 1
            if not self.dma_wait and self.cntr & CNTR_INTEN and self.cntr & CNTR_TCEN:
                self.istr |= ISTR_INT_P | ISTR_E_INT
                self._raise()
        d = self.drive
        if d.stch and self.tpi.cr & 1:
            self._lines()
        if d.image is not None and not d.media and self.tpi.cr & 1:
            d.media = d.stch = True
            self._lines()

    def _tpi_irq(self, on: bool) -> None:  #vers 2
        self.istr = self.istr | ISTR_INT_P if on else self.istr & ~ISTR_INT_P
        self.irq(on)

    def _raise(self) -> None:  #vers 1
        self.irq(bool(self.istr & ISTR_INT_P and self.cntr & CNTR_INTEN))

    def read(self, off: int) -> int:  #vers 2
        off &= 0xFFFF
        if off == 0x41:
            v = self.istr
            self.istr &= ~0x0F
            return v
        if off == 0x43:
            return self.cntr
        if 0x80 <= off < 0x84:
            return self.wtc >> (8 * (0x83 - off)) & 0xFF
        if 0x84 <= off < 0x88:
            return self.acr >> (8 * (0x87 - off)) & 0xFF
        if off in (0x8E, 0x8F):
            return self.dawr >> (8 * (0x8F - off)) & 0xFF
        if 0xB0 <= off < 0xC0:
            if not off & 1:
                return 0xFF
            v = self.tpi.read((off - 0xB0) >> 1)
            if off == 0xB5:
                self.drive.stch = self.drive.sten = False
                self._lines()
            return v
        if off in (0xA3, 0xA5, 0xA7):
            return 0xFF
        if off == 0xA1:
            v = self.drive.read()
            self._lines()
            return v
        return 0

    def write(self, off: int, v: int) -> None:  #vers 2
        off &= 0xFFFF
        v &= 0xFF
        if off == 0x43:
            self.cntr = v
            if v & CNTR_PREST:
                self.istr = 0
                self.dma_on = False
                self.drive.error = self.drive.media = self.drive.motor = self.drive.finished = False
                self.drive.stch = True
                self._lines()
            self._raise()
        elif 0x80 <= off < 0x84:
            sh = 8 * (0x83 - off)
            self.wtc = self.wtc & ~(0xFF << sh) | v << sh
        elif 0x84 <= off < 0x88:
            sh = 8 * (0x87 - off)
            self.acr = self.acr & ~(0xFF << sh) | v << sh
            if off == 0x87:
                self.acr &= ~1
        elif off in (0x8E, 0x8F):
            sh = 8 * (0x8F - off)
            self.dawr = self.dawr & ~(0xFF << sh) | v << sh
        elif 0xB0 <= off < 0xC0:
            if off & 1:
                self.tpi.write((off - 0xB0) >> 1, v)
        elif off in (0xE0, 0xE1):
            self.dma_on = True
            self._start_dma()
        elif off in (0xE2, 0xE3):
            self.dma_on = False
        elif off in (0xE4, 0xE5):
            self.istr = 0
            self._raise()
        elif off in (0xE8, 0xE9):
            self.istr |= ISTR_FE_FLG
        elif off == 0xA1:
            self.drive.write(v)
            self._lines()
