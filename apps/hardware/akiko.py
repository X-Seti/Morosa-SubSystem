#this belongs in apps/hardware/akiko.py - Version: 2
# X-Seti - November 17 2026 - Morosa - Morosa Akiko.

"""
Morosa Akiko - CD32 custom chip at 0xB80000: ID, chunky to planar converter, 24C08 NVRAM and CD drive interface in akiko_cd.py.
"""

##Methods list -
# Akiko
# Akiko._fall
# Akiko._line
# Akiko._load
# Akiko._rise
# Akiko.c2p
# Akiko.read
# Akiko.write

from apps.hardware.akiko_cd import AkikoCD

AKIKO_BASE = 0xB80000
NVRAM_SIZE = 1024


class Akiko:
    """Byte-addressed registers (off = address - 0xB80000); the CD registers are handled by AkikoCD."""

    def __init__(self, irq=None, mem_read=None, mem_write=None):  #vers 2
        self.cd = AkikoCD(irq or (lambda on: None), mem_read or (lambda a: 0), mem_write or (lambda a, v: None))
        self.buf = [0] * 8
        self.res = [0] * 8
        self.widx = 0
        self.ridx = -1
        self.nvram = bytearray(b"\xFF" * NVRAM_SIZE)
        self.regs = {}
        self.sda_out = self.scl_out = 1
        self.sda_dir = self.scl_dir = 0
        self.sda_dev = 1
        self.scl = self.sda = 1
        self.phase, self.role, self.after = "idle", "ctl", "rx"
        self.shift = self.nbits = self.addr = self.page = self.pos = 0
        self.hsda = 1
        self.hostack = 1

    def c2p(self) -> None:  #vers 1
        self.res = [0] * 8
        for i in range(256):
            if self.buf[7 - (i >> 5)] >> (i & 31) & 1:
                self.res[i & 7] |= 1 << (i >> 3)

    # ---- 24C08 on SCL/SDA ----
    def _line(self) -> None:  #vers 1
        scl = self.scl_out if self.scl_dir else 1
        host = self.sda_out if self.sda_dir else 1
        sda = host & self.sda_dev
        if scl and self.scl and host != self.hsda:
            if not host:
                self.phase, self.role, self.nbits, self.shift = "rx", "ctl", 0, 0
            else:
                self.phase = "idle"
            self.sda_dev = 1
        elif scl and not self.scl:
            self._rise(host)
        elif not scl and self.scl:
            self._fall()
        self.hsda = host
        self.scl = scl
        self.sda = self.sda_out & self.sda_dev if self.sda_dir else self.sda_dev

    def _rise(self, host: int) -> None:  #vers 1
        if self.phase == "rx" and self.nbits < 8:
            self.shift = self.shift << 1 | host
            self.nbits += 1
        elif self.phase == "txack":
            self.hostack = host

    def _fall(self) -> None:  #vers 1
        ph = self.phase
        if ph == "rx" and self.nbits == 8:
            v = self.shift
            self.phase, self.sda_dev = "ack", 0
            if self.role == "ctl":
                if v >> 4 != 0xA:
                    self.phase, self.sda_dev = "idle", 1
                    return
                self.page = (v >> 1 & 3) << 8
                if v & 1:
                    self.addr = self.page | self.addr & 0xFF
                    self.after = "tx"
                else:
                    self.role, self.after = "addr", "rx"
            elif self.role == "addr":
                self.addr = self.page | v
                self.role, self.after = "data", "rx"
            else:
                self.nvram[self.addr] = v
                self.addr = self.addr & ~15 | (self.addr + 1) & 15
                self.after = "rx"
        elif ph == "ack":
            if self.after == "tx":
                self._load()
            else:
                self.phase, self.sda_dev, self.nbits, self.shift = "rx", 1, 0, 0
        elif ph == "tx":
            self.pos += 1
            if self.pos < 8:
                self.sda_dev = self.nvram[self.addr] >> (7 - self.pos) & 1
            else:
                self.phase, self.sda_dev, self.hostack = "txack", 1, 1
        elif ph == "txack":
            if self.hostack == 0:
                self.addr = self.addr + 1 & 0x3FF
                self._load()
            else:
                self.phase, self.sda_dev = "idle", 1

    def _load(self) -> None:  #vers 1
        self.phase, self.pos = "tx", 0
        self.sda_dev = self.nvram[self.addr] >> 7 & 1

    def read(self, off: int) -> int:  #vers 2
        """Byte read."""
        if off < 4:
            return (0xC0, 0xCA, 0xCA, 0xFE)[off]
        if 0x38 <= off < 0x3C:
            if self.ridx < 0:
                self.c2p()
                self.ridx = 0
            self.widx = 0
            v = self.res[self.ridx] >> (8 * (3 - (off - 0x38))) & 0xFF
            if off == 0x3B:
                self.ridx = self.ridx + 1 & 7
            return v
        if off == 0x30:
            return self.scl << 7 | self.sda << 6
        if off == 0x32:
            return self.scl_dir << 7 | self.sda_dir << 6
        if 4 <= off < 0x30:
            return self.cd.read(off)
        return self.regs.get(off, 0)

    def write(self, off: int, v: int) -> None:  #vers 2
        v &= 0xFF
        if 0x38 <= off < 0x3C:
            i = off - 0x38
            if i == 0:
                self.buf[self.widx] = 0
            self.buf[self.widx] |= v << (8 * (3 - i))
            if i == 3:
                self.widx = self.widx + 1 & 7
            self.ridx = -1
        elif off == 0x30:
            self.scl_out, self.sda_out = v >> 7 & 1, v >> 6 & 1
            self._line()
        elif off == 0x32:
            self.scl_dir, self.sda_dir = v >> 7 & 1, v >> 6 & 1
            self._line()
        elif 4 <= off < 0x30:
            self.cd.write(off, v)
        elif off >= 4:
            self.regs[off] = v
