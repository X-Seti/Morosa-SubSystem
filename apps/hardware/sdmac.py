#this belongs in apps/hardware/sdmac.py - Version: 4
# X-Seti - November 18 2026 - Morosa - Morosa A3000 SDMAC.

"""
Morosa SDMAC - A3000 SCSI DMA controller registers at 0xDD0000 around a WD33C93 bus controller.
"""

##Methods list -
# SDMAC
# SDMAC.read
# SDMAC.write
# SDMAC.pull
# SDMAC.push
# SDMAC._update

from apps.hardware.wd33c93 import WD33C93

SDMAC_BASE = 0xDD0000
ISTR_INTS, ISTR_INT_P, ISTR_FIFOE = 0x40, 0x10, 0x01
CNTR_INTEN = 0x04
ACR, WTC, CNTR = 0x0C, 0x04, 0x0B


class SDMAC:
    """Byte/word/long access to DMAC registers (0x00-0x3F) and the WD33C93 ports (0x41 address, 0x43 data)."""

    def __init__(self, irq=None, mem_read=None, mem_write=None):  #vers 3
        self.irq = irq or (lambda on: None)
        self.mem_read, self.mem_write = mem_read, mem_write
        self.cntr = self.dawr = self.wtc = self.acr = 0
        self.sasr = 0
        self._line = False
        self.wd = WD33C93(irq=lambda on: self._update(), dma=self)

    def _update(self) -> None:  #vers 2
        on = self.wd.pending and bool(self.cntr & CNTR_INTEN)
        if on != self._line:
            self._line = on
            self.irq(on)

    def pull(self, n: int) -> bytes:  #vers 1
        """Device reads n bytes from memory at ACR."""
        d = self.mem_read(self.acr, n) if self.mem_read else bytes(n)
        self.acr = (self.acr + n) & 0xFFFFFFFF
        return d

    def push(self, data: bytes) -> None:  #vers 1
        """Device writes data to memory at ACR."""
        if self.mem_write:
            self.mem_write(self.acr, data)
        self.acr = (self.acr + len(data)) & 0xFFFFFFFF

    def read(self, a: int, size: int) -> int:  #vers 4
        off = (a - SDMAC_BASE) & 0xFFFF
        if off >= 0x40:
            off += (0, 1, 1)[size]
            if off & 3 == 1:
                return self.wd.aux()
            v = self.wd.read_reg(self.sasr)
            if self.sasr not in (0x17, 0x18, 0x19):
                self.sasr = (self.sasr + 1) & 31
            self._update()
            return v
        if off in (0x1E, 0x1F):
            return ISTR_FIFOE | (ISTR_INTS if self.wd.pending else 0) | (ISTR_INT_P if self._line else 0)
        if off & ~1 == 0x0A:
            return self.cntr
        if WTC <= off < WTC + 4:
            return self.wtc >> (8 * (WTC + 3 - off)) & 0xFF
        if ACR <= off < ACR + 4:
            return self.acr >> (8 * (ACR + 3 - off)) & 0xFF
        return 0

    def write(self, a: int, size: int, v: int) -> None:  #vers 3
        off = (a - SDMAC_BASE) & 0xFFFF
        if off >= 0x40:
            off += (0, 1, 1)[size]
            if off & 3 == 1:
                self.sasr = v & 31
                return
            r = self.sasr & 31
            self.wd.write_reg(r, v & 0xFF)
            if r not in (0x17, 0x18, 0x19):
                self.sasr = (r + 1) & 31
            self._update()
            return
        if off & ~1 == 0x0A:
            self.cntr = v & 0xFF
            self._update()
        elif off & ~1 == 0x02:
            self.dawr = v & 0xFF
        elif size == 2 and off == WTC:
            self.wtc = v & 0xFFFFFFFF
        elif size == 2 and off == ACR:
            self.acr = v & 0xFFFFFFFF
        elif size < 2 and WTC <= off < WTC + 4:
            sh = 8 * (WTC + 3 - off)
            self.wtc = self.wtc & ~(0xFF << sh) | (v & 0xFF) << sh
        elif size < 2 and ACR <= off < ACR + 4:
            sh = 8 * (ACR + 3 - off)
            self.acr = self.acr & ~(0xFF << sh) | (v & 0xFF) << sh
