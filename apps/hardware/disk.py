#this belongs in apps/hardware/disk.py - Version: 1
# X-Seti - November 17 2026 - Morosa - Morosa Paula Disk DMA.

"""
Morosa Disk - Paula disk controller: DSKPT/DSKLEN/DSKSYNC DMA between chip RAM and the spinning floppy track.
"""

##Methods list -
# DiskDMA
# DiskDMA.line
# DiskDMA.read
# DiskDMA.write

INT_DSKBLK, INT_DSKSYN = 0x0002, 0x1000
DMAEN, DSKEN = 0x200, 0x10
WORDS_PER_LINE = 2


class DiskDMA:
    """chip_read/chip_write move words; drive() gives the spinning Floppy or None; request(bits) raises interrupts."""

    def __init__(self, chip_read, chip_write, drive, request, dmacon, adkcon, index=None):  #vers 1
        self.chip_read, self.chip_write = chip_read, chip_write
        self.drive, self.request = drive, request
        self.dmacon, self.adkcon = dmacon, adkcon
        self.index = index or (lambda: None)
        self.pt = 0
        self.len = 0
        self.sync = 0x4489
        self.armed = False
        self.on = False
        self.wr = False
        self.waiting = False
        self.pos = 0
        self.last = 0
        self.out = []

    def read(self, off: int):  #vers 1
        if off == 0x008:
            return self.last
        if off == 0x01A:
            return (0x8000 | (0x4000 if self.on else 0) | (0x2000 if self.on and self.wr else 0)
                    | (0x1000 if self.last == self.sync else 0) | self.last & 0xFF)
        return None

    def write(self, off: int, v: int) -> bool:  #vers 1
        if off == 0x020:
            self.pt = self.pt & 0xFFFF | (v & 0x1F) << 16
        elif off == 0x022:
            self.pt = self.pt & 0x1F0000 | v & 0xFFFE
        elif off == 0x024:
            if not v & 0x8000:
                self.on = self.armed = False
            elif not self.armed:
                self.armed = True
            else:
                self.armed = False
                self.on, self.wr = True, bool(v & 0x4000)
                self.len = v & 0x3FFF
                self.waiting = not self.wr and bool(self.adkcon() & 0x400)
                self.out = []
                if self.len == 0:
                    self.on = False
                    self.request(INT_DSKBLK)
        elif off == 0x07E:
            self.sync = v
        else:
            return False
        return True

    def line(self) -> None:  #vers 1
        fl = self.drive()
        if fl is None:
            return
        words = fl.track_words()
        if not words:
            return
        for _ in range(WORDS_PER_LINE):
            w = words[self.pos]
            self.pos += 1
            if self.pos >= len(words):
                self.pos = 0
                self.index()
            self.last = w
            if not self.on:
                continue
            d = self.dmacon()
            if not (d & DMAEN and d & DSKEN):
                continue
            if self.wr:
                self.out.append(self.chip_read(self.pt))
                self.pt += 2
                self.len -= 1
                if self.len <= 0:
                    self.on = False
                    fl.write_track(self.out)
                    self.request(INT_DSKBLK)
                    break
            else:
                if self.waiting:
                    if w == self.sync:
                        self.waiting = False
                        self.request(INT_DSKSYN)
                    continue
                self.chip_write(self.pt, w)
                self.pt += 2
                self.len -= 1
                if self.len <= 0:
                    self.on = False
                    self.request(INT_DSKBLK)
                    break
