#this belongs in apps/hardware/ide.py - Version: 5
# X-Seti - November 17 2026 - Morosa - Morosa IDE.

"""
Morosa IDE - ATA channel with up to two disks on HDF images; used by Gayle (A600, A1200) and the A4000 Gary.
"""

##Methods list -
# ATADisk
# ATADisk.identify
# ATADisk.lba_of
# ATADisk.read_sector
# ATADisk.write_sector
# IDEChannel
# IDEChannel._command
# IDEChannel._irq
# IDEChannel._packet_done
# IDEChannel._packet_in
# IDEChannel._packet_out
# IDEChannel.read
# IDEChannel.write

import struct

BSY, DRDY, DSC, DRQ, ERR = 0x80, 0x40, 0x10, 0x08, 0x01
HEADS, SPT = 16, 63


class ATADisk:
    """A disk backed by a bytearray (or any object with slice access) of 512 byte sectors."""

    def __init__(self, image: bytearray, model: str = "MOROSA HDF"):  #vers 2
        self.image = image
        self.sectors = len(image) // 512
        self.cyls = max(1, min(16383, self.sectors // (getattr(image, "heads", HEADS) * getattr(image, "spt", SPT))))
        self.heads, self.spt = getattr(image, "heads", HEADS), getattr(image, "spt", SPT)
        self.model = model
        self.multi = 0
        self.features = {}

    def lba_of(self, lba_mode: bool, cyl: int, head: int, sec: int, count: int) -> int:  #vers 1
        if lba_mode:
            return cyl << 8 | sec | head << 24
        return (cyl * self.heads + head) * self.spt + sec - 1

    def read_sector(self, lba: int) -> bytes:  #vers 1
        return bytes(self.image[lba * 512:lba * 512 + 512])

    def write_sector(self, lba: int, data: bytes) -> None:  #vers 1
        self.image[lba * 512:lba * 512 + 512] = data

    def identify(self) -> bytes:  #vers 2
        w = [0] * 256
        w[0] = 0x0040
        w[1], w[3], w[6] = self.cyls, self.heads, self.spt
        w[47] = 0x8010
        w[49] = 0x0200
        w[53] = 1
        w[54], w[55], w[56] = self.cyls, self.heads, self.spt
        cur = self.cyls * self.heads * self.spt
        w[57], w[58] = cur & 0xFFFF, cur >> 16
        w[60], w[61] = self.sectors & 0xFFFF, self.sectors >> 16
        w[80] = 0x0010
        for i, ch in enumerate((self.model.ljust(40)[:40])):
            w[27 + i // 2] |= ord(ch) << (8 if i % 2 == 0 else 0)
        for i, ch in enumerate("0001".ljust(8)):
            w[23 + i // 2] |= ord(ch) << (8 if i % 2 == 0 else 0)
        return struct.pack("<256H", *w)


class IDEChannel:
    """Task file registers 0..7 plus alternate status/device control (reg 0x406). Commands complete at once."""

    def __init__(self, irq=None):  #vers 1
        self.irq = irq or (lambda on: None)
        self.disks = [None, None]
        self.err = 0
        self.feature = 0
        self.count = 1
        self.sec = 1
        self.cyl = 0
        self.dh = 0xA0
        self.status = DRDY | DSC
        self.devctl = 0
        self.buf = b""
        self.pos = 0
        self.writing = False
        self.left = 0
        self.lba = 0
        self.pending = False
        self.pkt = False
        self.pdata = b""

    def _disk(self):  #vers 1
        return self.disks[self.dh >> 4 & 1]

    def _irq(self, on: bool) -> None:  #vers 1
        self.pending = on and not self.devctl & 2
        self.irq(self.pending)

    def read(self, reg: int, size: int = 1) -> int:  #vers 3
        d = self._disk()
        if reg == 0:
            if self.status & DRQ and not self.writing:
                if size == 2:
                    return self.read(0, 1) << 16 | self.read(0, 1)
                v = self.buf[self.pos] << 8 | self.buf[self.pos + 1]
                self.pos += 2
                if self.pos >= len(self.buf):
                    self.status &= ~DRQ
                    if self.pdata:
                        self._packet_out()
                    elif getattr(d, "atapi", False):
                        self._packet_done()
                    elif self.left:
                        self._next_read()
                return v
            return 0
        if d is None and reg in (1, 2, 3, 4, 5, 7):
            return 0xFF if reg == 7 and not any(self.disks) else 0
        if reg == 1:
            return self.err
        if reg == 2:
            return self.count & 0xFF
        if reg == 3:
            return self.sec
        if reg == 4:
            return self.cyl & 0xFF
        if reg == 5:
            return self.cyl >> 8 & 0xFF
        if reg == 6:
            return self.dh
        if reg == 7:
            self._irq(False)
            return self.status if d else 0
        if reg == 0x406:
            return self.status if d else 0xFF if not any(self.disks) else 0
        return 0

    def write(self, reg: int, v: int, size: int = 1) -> None:  #vers 2
        if reg == 0:
            if self.status & DRQ and self.writing:
                if size == 2:
                    self.write(0, v >> 16 & 0xFFFF)
                    self.write(0, v & 0xFFFF)
                    return
                self.buf += bytes((v >> 8 & 255, v & 255))
                if self.pkt:
                    if len(self.buf) >= 12:
                        self.pkt = False
                        self._packet_in(self.buf[:12])
                    return
                if len(self.buf) >= 512:
                    self._disk().write_sector(self.lba, self.buf[:512])
                    self.lba += 1
                    self.left -= 1
                    self.buf = b""
                    if self.left:
                        self._irq(True)
                    else:
                        self.status &= ~DRQ
                        self._irq(True)
            return
        if reg == 1:
            self.feature = v & 0xFF
        elif reg == 2:
            self.count = v & 0xFF
        elif reg == 3:
            self.sec = v & 0xFF
        elif reg == 4:
            self.cyl = self.cyl & 0xFF00 | v & 0xFF
        elif reg == 5:
            self.cyl = self.cyl & 0xFF | (v & 0xFF) << 8
        elif reg == 6:
            self.dh = v & 0xFF
            d = self._disk()
            if getattr(d, "atapi", False) and not self.status & DRQ:
                self.cyl, self.count, self.sec = 0xEB14, 1, 1
        elif reg == 7:
            self._command(v & 0xFF)
        elif reg == 0x406:
            if v & 4 and not self.devctl & 4:
                d = self._disk()
                self.status, self.err = DRDY | DSC, 1
                self.count = self.sec = 1
                self.cyl = 0xEB14 if getattr(d, "atapi", False) else 0
            self.devctl = v & 0xFF

    def _packet_out(self) -> None:  #vers 1
        """Send the next chunk of packet data, limited by the byte count the host set."""
        lim = (self.cyl & 0xFFFE) or 0xFFFE
        chunk, self.pdata = self.pdata[:lim], self.pdata[lim:]
        self.buf, self.pos = chunk + b"\0" * (len(chunk) & 1), 0
        self.cyl, self.count = len(chunk), 2
        self.status = DRDY | DSC | DRQ
        self._irq(True)

    def _packet_done(self) -> None:  #vers 1
        self.count = 3
        self.status = DRDY | DSC
        self._irq(True)

    def _packet_in(self, cdb: bytes) -> None:  #vers 1
        st, data, key = self._disk().packet(bytes(cdb))
        self.writing = False
        if st:
            self.err, self.count, self.status = key << 4, 3, DRDY | DSC | ERR
            return self._irq(True)
        self.pdata = data
        if data:
            self._packet_out()
        else:
            self._packet_done()

    def _abort(self) -> None:  #vers 1
        self.err = 4
        self.status = DRDY | DSC | ERR
        self._irq(True)

    def _next_read(self) -> None:  #vers 1
        d = self._disk()
        if self.lba >= d.sectors:
            self._abort()
            self.left = 0
            return
        self.buf, self.pos = d.read_sector(self.lba), 0
        self.lba += 1
        self.left -= 1
        self.status = DRDY | DSC | DRQ
        self._irq(True)

    def _command(self, cmd: int) -> None:  #vers 2
        d = self._disk()
        self.err = 0
        if d is None:
            return
        n = self.count or 256
        lbam = bool(self.dh & 0x40)
        if getattr(d, "atapi", False):
            if cmd == 0xA0:
                self.pkt, self.writing, self.buf, self.pdata = True, True, b"", b""
                self.count, self.status = 1, DRDY | DSC | DRQ
            elif cmd == 0xA1:
                self.buf, self.pos, self.writing, self.pdata = d.identify(), 0, False, b""
                self.status = DRDY | DSC | DRQ
                self._irq(True)
            elif cmd == 0x08:
                self.count, self.sec, self.cyl, self.status = 1, 1, 0xEB14, 0
                self._irq(True)
            else:
                self.cyl, self.count, self.sec = 0xEB14, 1, 1
                self._abort()
            return
        if cmd == 0xEC:
            self.buf, self.pos, self.left, self.writing = d.identify(), 0, 0, False
            self.status = DRDY | DSC | DRQ
            self._irq(True)
        elif cmd in (0x20, 0x21, 0xC4):
            self.lba = d.lba_of(lbam, self.cyl, self.dh & 15, self.sec, n)
            self.left, self.writing = n, False
            if self.lba + n > d.sectors:
                return self._abort()
            self._next_read()
        elif cmd in (0x30, 0x31, 0xC5):
            self.lba = d.lba_of(lbam, self.cyl, self.dh & 15, self.sec, n)
            if self.lba + n > d.sectors:
                return self._abort()
            self.left, self.writing, self.buf = n, True, b""
            self.status = DRDY | DSC | DRQ
        elif cmd in (0x40, 0x41):
            self.status = DRDY | DSC
            self._irq(True)
        elif cmd == 0xC6:
            d.multi = self.count
            self.status = DRDY | DSC
            self._irq(True)
        elif cmd == 0x91:
            d.heads, d.spt = (self.dh & 15) + 1, self.count
            self.status = DRDY | DSC
            self._irq(True)
        elif cmd == 0xEF:
            d.features[self.feature] = self.count
            self.status = DRDY | DSC
            self._irq(True)
        elif cmd == 0x90 or 0x10 <= cmd <= 0x1F or 0x70 <= cmd <= 0x7F or cmd in (0xE0, 0xE1, 0xE2, 0xE3, 0xE5, 0xE7):
            if cmd == 0x90:
                self.err, self.count, self.sec, self.cyl = 1, 1, 1, 0
            self.status = DRDY | DSC
            self._irq(True)
        else:
            self._abort()
