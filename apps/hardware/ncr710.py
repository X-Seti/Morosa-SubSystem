#this belongs in apps/hardware/ncr710.py - Version: 1
# X-Seti - November 18 2026 - Morosa - Morosa NCR 53C710.

"""
Morosa NCR 710 - A4000T SCSI controller register file at 0xDD0040; no targets, selection times out.
"""

##Methods list -
# NCR710
# NCR710.read
# NCR710.write
# NCR710._run
# NCR710._update

NCR_BASE = 0xDD0040
NCR_SIZE = 0x40
SCNTL1, SIEN, DSTAT, SSTAT0, ISTAT, DSP, DIEN = 0x01, 0x03, 0x0C, 0x0D, 0x21, 0x2C, 0x39
ISTAT_DIP, ISTAT_SIP, ISTAT_SRST = 0x01, 0x02, 0x40
SSTAT_RST, SSTAT_STO = 0x02, 0x20
DSTAT_SIR = 0x04


class NCR710:
    """Bytes sit at offset ^ 3 from a little-endian chip on the big-endian bus."""

    def __init__(self, irq=None):  #vers 1
        self.irq = irq or (lambda on: None)
        self.r = bytearray(NCR_SIZE)
        self._line = False

    def _update(self) -> None:  #vers 1
        on = bool(self.r[SSTAT0] & self.r[SIEN]) or bool(self.r[DSTAT] & self.r[DIEN])
        if on != self._line:
            self._line = on
            self.irq(on)

    def _run(self) -> None:  #vers 1
        """SCRIPTS start: no target answers, so selection times out."""
        self.r[SSTAT0] |= SSTAT_STO
        self._update()

    def read(self, a: int, size: int) -> int:  #vers 1
        p = (a - NCR_BASE) & (NCR_SIZE - 1)
        if size == 0:
            i = p ^ 3
            if i == ISTAT:
                return (ISTAT_SIP if self.r[SSTAT0] & self.r[SIEN] else 0) | (ISTAT_DIP if self.r[DSTAT] & self.r[DIEN] else 0)
            v = self.r[i]
            if i in (DSTAT, SSTAT0):
                self.r[i] = 0
                self._update()
            return v
        base = p & ~3
        v = self.r[p ^ 3] << 8 | self.r[(p + 1) ^ 3] if size == 1 else int.from_bytes(self.r[base:base + 4], "little")
        if base == DSTAT:
            self.r[DSTAT] = self.r[SSTAT0] = 0
            self._update()
        return v

    def write(self, a: int, size: int, v: int) -> None:  #vers 1
        p = (a - NCR_BASE) & (NCR_SIZE - 1)
        if size == 0:
            i = p ^ 3
            if i == ISTAT:
                if v & ISTAT_SRST:
                    self.r[:] = bytes(NCR_SIZE)
                    self._update()
                return
            if i in (DSTAT, SSTAT0):
                return
            self.r[i] = v & 0xFF
            if i == SCNTL1 and v & 0x08:
                self.r[SSTAT0] |= SSTAT_RST
            elif i == DSP + 3:
                self._run()
            self._update()
            return
        if size == 1:
            self.r[p ^ 3], self.r[(p + 1) ^ 3] = v >> 8 & 0xFF, v & 0xFF
        elif size == 2:
            base = p & ~3
            self.r[base:base + 4] = (v & 0xFFFFFFFF).to_bytes(4, "little")
            if base == DSP:
                self._run()
