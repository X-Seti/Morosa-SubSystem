#this belongs in apps/hardware/gary.py - Version: 1
# X-Seti - November 17 2026 - Morosa - Morosa Gary, Ramsey and Gayle.

"""
Morosa Gary - system glue registers: Gary timeout and Ramsey control (A3000/A4000), Gayle ID and status (A600/A1200).
"""

##Methods list -
# Gary
# Gary.read
# Gary.write
# Gayle
# Gayle.read
# Gayle.write
# Gayle.ide_irq
# Ramsey
# Ramsey.read
# Ramsey.write

RAMSEY_VERSION = {"A3000": 0x0D, "A4000": 0x0F, "A4000D": 0x0F, "A4000T": 0x0F}


class Gary:
    """Bus control at 0xDE0000: timeout enable bit 7 at 0xDE0000, toggle bit 7 at 0xDE0001, coldstart at 0xDE0002."""

    def __init__(self):  #vers 1
        self.timeout = self.toggle = 0
        self.coldstart = 0x80

    def read(self, off: int) -> int:  #vers 1
        if off == 0:
            return self.timeout
        if off == 1:
            return self.toggle
        if off == 2:
            return self.coldstart
        return 0

    def write(self, off: int, v: int) -> None:  #vers 1
        if off == 0:
            self.timeout = v & 0x80
        elif off == 1:
            self.toggle = v & 0x80
        elif off == 2:
            self.coldstart = v & 0x80


class Ramsey:
    """RAM controller at 0xDE0003 (control) and 0xDE0043 (version); control bits are stored, refresh is not timed."""

    def __init__(self, machine: str = "A3000"):  #vers 1
        self.ctrl = 0
        self.version = RAMSEY_VERSION[machine]

    def read(self, off: int) -> int:  #vers 1
        if off == 0x03:
            return self.ctrl
        if off == 0x43:
            return self.version
        return 0

    def write(self, off: int, v: int) -> None:  #vers 1
        if off == 0x03:
            self.ctrl = v & 0xFF


class Gayle:
    """ID at 0xDE1000 returns one bit per read on bit 7; status and control registers are stored."""

    def __init__(self, gid: int = 0xD0):  #vers 1
        self.gid = gid
        self.pos = 0
        self.regs = {}
        self.irqreg = 0
        self.inten = 0
        self.irq = lambda on: None

    def ide_irq(self, on: bool) -> None:  #vers 1
        """IDE interrupt line; sets IRQ register bit 7 and raises INT2 when enabled in the INT register."""
        if on:
            self.irqreg |= 0x80
        self.irq(bool(on and self.inten & 0x80))

    def read(self, off: int) -> int:  #vers 1
        if off == 0x1000:
            bit = 0x80 if self.gid >> (7 - self.pos) & 1 else 0
            self.pos = (self.pos + 1) & 7
            return bit
        return self.regs.get(off, 0)

    def write(self, off: int, v: int) -> None:  #vers 1
        if off == 0x1000:
            self.pos = 0
        else:
            self.regs[off] = v & 0xFF
