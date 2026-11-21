#this belongs in apps/hardware/akiko_cd.py - Version: 2
# X-Seti - November 18 2026 - Morosa - Morosa Akiko CD.

"""
Morosa Akiko CD - CD32 drive interface: command and reply frames, sector slots and interrupts.
"""

##Methods list -
# AkikoCD
# AkikoCD.hsync
# AkikoCD.insert
# AkikoCD.read
# AkikoCD.write
# AkikoCD._add_byte
# AkikoCD._can_send
# AkikoCD._clear
# AkikoCD._command
# AkikoCD._internal
# AkikoCD._read_sector
# AkikoCD._return_data
# AkikoCD._run_tx
# AkikoCD._set
# AkikoCD._start_return
# AkikoCD._toc_entry

SUBCODE, DRIVEXMIT, DRIVERECV, RXDMADONE, TXDMADONE, PBX = 0x80000000, 0x40000000, 0x20000000, 0x10000000, 0x08000000, 0x04000000
F_SUBCODE, F_TXD, F_RXD, F_PBX, F_ENABLE = 0x80000000, 0x40000000, 0x20000000, 0x08000000, 0x04000000
CMD_LEN = (1, 2, 1, 1, 12, 2, 1, 1, 4, 1, 2, -1, -1, -1, -1, -1)
FIRMWARE = b"CHINON  O-658-2 24"
LINE_RATE = 15625


class AkikoCD:
    """Byte registers 0x04-0x2F of Akiko. mem_read(a) -> byte, mem_write(a, byte), irq(on)."""

    def __init__(self, irq, mem_read, mem_write):  #vers 1
        self.irq, self.r8, self.w8 = irq, mem_read, mem_write
        self.image = None
        self.intreq, self.intena, self.flags = SUBCODE, 0, 0
        self.adata = self.amisc = 0
        self.pbx = 0
        self.subofs = 0xC2
        self.txinx = self.rxinx = self.txcmp = self.rxcmp = 0
        self.tx_delay = self.rx_delay = 0
        self.cmd, self.cmd_len, self.active, self.checksum_bad, self.unknown = [], 0, 0, False, False
        self.result, self.recv_len, self.recv_off, self.last_rx = [], 0, 0, 0
        self.init = 0
        self.led = 0
        self.speed = 1
        self.offset, self.counter, self.line = -1, 0, 0
        self.toc, self.toc_counter = [], -1

    def insert(self, image) -> None:  #vers 1
        self.image = image
        self.init = 0
        self.toc, self.toc_counter = self._build_toc(), -1

    def _build_toc(self) -> list:  #vers 1
        """13 byte records: A0 first track, A1 last track, A2 lead-out, then each track."""
        bcd = lambda v: v // 10 << 4 | v % 10
        msf = lambda lba: (bcd((lba + 150) // 4500), bcd((lba + 150) // 75 % 60), bcd((lba + 150) % 75))
        rec = lambda ctl, point, m: bytes([0, 0x01 | ctl << 4, 0, point, 0, 0, 0, 0]) + bytes(m) + bytes(2)
        t = self.image.tracks
        ctl = lambda x: 0 if x["audio"] else 4
        out = [rec(ctl(t[0]), 0xA0, (bcd(t[0]["num"]), 0, 0)), rec(ctl(t[-1]), 0xA1, (bcd(t[-1]["num"]), 0, 0)),
               rec(ctl(t[-1]), 0xA2, msf(self.image.blocks))]
        return out + [rec(ctl(x), bcd(x["num"]), msf(x["start"])) for x in t]

    def _toc_entry(self) -> list:  #vers 1
        n = self.toc_counter
        bcd = lambda v: v // 10 << 4 | v % 10
        r = [6, 0x0A] + list(self.toc[n // 3])
        r[6], r[7], r[8] = bcd(99), bcd(24 + n // 75), bcd(n % 75)
        self.toc_counter += 1
        if self.toc_counter // 3 >= len(self.toc):
            self.toc_counter = -1
        return r

    # ---- interrupts ----
    def _set(self, bits: int) -> None:  #vers 1
        self.intreq |= bits
        self.irq(bool(self.intreq & self.intena))

    def _clear(self, bits: int) -> None:  #vers 1
        self.intreq &= ~bits
        self.irq(bool(self.intreq & self.intena))

    # ---- command frames ----
    def _can_send(self) -> bool:  #vers 1
        return bool(self.init) and not self.active and not self.recv_len

    def _add_byte(self, v: int) -> None:  #vers 1
        self.cmd.append(v & 0xFF)
        n = CMD_LEN[self.cmd[0] & 15]
        if n < 0:
            self.unknown, self.active = True, 1
        elif len(self.cmd) >= n + 1:
            self.checksum_bad = sum(self.cmd[:n + 1]) & 0xFF != 0xFF
            self.active = 1

    def _start_return(self, data: list) -> None:  #vers 1
        if self.recv_len or not data:
            return
        self.result = list(data) + [(0xFF - sum(data)) & 0xFF]
        self.recv_len, self.recv_off = len(self.result), 0
        self._set(DRIVERECV)

    def _command(self) -> None:  #vers 1
        c = self.cmd
        door = 1
        cmd, op = c[0], c[0] & 15
        self.cmd, self.active = [], 0
        bad, unk = self.checksum_bad, self.unknown
        self.checksum_bad = self.unknown = False
        if bad or unk:
            return self._start_return([(cmd & 0xF0) | 5, (0x88 if bad else 0x80) | door])
        if op == 0:
            out = [cmd]
        elif op in (1, 2, 3):
            out = [cmd, 0 if op == 1 else door]
            if op == 1:
                self.offset = -1
            if op == 2:
                self.toc_counter = -1
        elif op == 4:
            out = [cmd, 0]
            if self.image is None:
                out[1] = 1
            else:
                bcd = lambda v: (v >> 4) * 10 + (v & 15)
                lsn = (bcd(c[1]) * 60 + bcd(c[2])) * 75 + bcd(c[3]) - 150
                if c[7] & 0x80:
                    self.offset = lsn
                    self.speed = 2 if c[8] & 0x40 else 1
                    out[1] = 2
                elif lsn < 0:
                    self.toc_counter = 0
        elif op == 5:
            self.led = c[1] & 1
            out = [cmd, self.led] if c[1] & 0x80 else []
        elif op == 6:
            out = [cmd, 0] + [0] * 13
        elif op == 7:
            out = [cmd, door] + list(FIRMWARE.ljust(18, b" ")) 
            self.init = 2
            self.toc_counter = -1
        else:
            out = []
        if out:
            self._start_return(out)
        else:
            self._set(DRIVEXMIT)

    # ---- DMA engines ----
    def _return_data(self) -> None:  #vers 1
        if not (self.recv_len and self.flags & F_RXD and self.rxinx != self.rxcmp and not self.rx_delay):
            return
        base = self.amisc
        while self.recv_off < self.recv_len and self.rxinx != self.rxcmp:
            self.w8(base + self.rxinx, self.result[self.recv_off])
            self.recv_off += 1
            self.rxinx = self.rxinx + 1 & 0xFF
            if self.rxinx == self.rxcmp:
                self._set(RXDMADONE)
        if self.recv_off >= self.recv_len:
            self.recv_len = 0
            self._clear(DRIVERECV)
            self._set(DRIVEXMIT)

    def _run_tx(self) -> None:  #vers 1
        base = self.amisc | 0x200
        while (self.flags & F_TXD and not self.flags & F_ENABLE and self.txinx != self.txcmp
               and not self.tx_delay and self._can_send()):
            self._add_byte(self.r8(base + self.txinx))
            self.txinx = self.txinx + 1 & 0xFF
            if self.txinx == self.txcmp:
                self._set(TXDMADONE)

    def _internal(self) -> None:  #vers 1
        self._return_data()
        self._run_tx()
        if self.active:
            self._command()

    def _read_sector(self) -> None:  #vers 1
        if not (self.flags & F_ENABLE and self.pbx and self.flags & F_PBX and self.offset >= 0 and self.image):
            return
        slot = next(i for i in range(15, -1, -1) if self.pbx >> i & 1)
        raw = self.image.read_raw(self.offset + self.counter)
        if raw is None:
            return
        buf = bytearray(raw)
        buf[3] = self.counter & 31
        base = self.adata + slot * 4096
        for i, v in enumerate(buf):
            self.w8(base + i, v)
        for i in range(146):
            self.w8(base + 0xC00 + i, 0)
        self.pbx &= ~(1 << slot)
        self.counter += 1
        self._set(PBX)
        if self.flags & F_SUBCODE:
            self.subofs = 0 if self.subofs >= 128 else 128
            sb = (self.amisc | 0x100) + self.subofs
            for i in range(96):
                self.w8(sb + i, 0)
            for i, v in enumerate((0xFF, 0xFF, 0, 0)):
                self.w8(sb + 96 + i, v)
            self.subofs += 100
            self._set(SUBCODE)

    def hsync(self) -> None:  #vers 1
        """Called once per scanline."""
        if self.tx_delay:
            self.tx_delay -= 1
        if self.rx_delay:
            self.rx_delay -= 1
        if not self.init and not self.recv_len:
            if self.image:
                self._start_return([0x0A, 1])
            self.init = 1
            return
        self._internal()
        self.line += 1
        if self.line >= 104 * (2 // self.speed):
            self.line = 0
            self._read_sector()
            if self.toc_counter >= 0 and not self.active and not self.recv_len:
                self._start_return(self._toc_entry())

    # ---- registers ----
    def read(self, off: int) -> int:  #vers 1
        lane = lambda v, o: v >> (8 * (3 - (off - o))) & 0xFF
        if 4 <= off < 8:
            return lane(self.intreq, 4)
        if 8 <= off < 16:
            return lane(self.intena, 8 if off < 12 else 12)
        if off == 0x18:
            return self.subofs & 0xFF
        if off in (0x11, 0x15, 0x19, 0x1D):
            return self.txinx
        if off in (0x12, 0x16, 0x1A, 0x1E):
            return self.rxinx
        if 0x20 <= off < 0x22:
            return self.pbx >> (8 * (0x21 - off)) & 0xFF
        if 0x24 <= off < 0x28:
            return lane(self.flags, 0x24)
        if off == 0x28:
            if not self.flags & F_RXD and self.recv_len:
                self.last_rx = self.result[self.recv_off]
                self.recv_off += 1
                if self.recv_off >= self.recv_len:
                    self.recv_len = 0
                    self._clear(DRIVERECV)
                    self._set(DRIVEXMIT)
            else:
                self._clear(DRIVERECV)
            return self.last_rx
        return 0

    def write(self, off: int, v: int) -> None:  #vers 1
        v &= 0xFF
        sh = 8 * (3 - (off & 3))
        put = lambda cur: cur & ~(0xFF << sh) | v << sh
        if 8 <= off < 12:
            self.intena = put(self.intena) & 0xFF000000
            self.irq(bool(self.intreq & self.intena))
        elif 0x10 <= off < 0x14:
            self.adata = put(self.adata) & 0x00FFF000
        elif 0x14 <= off < 0x18:
            self.amisc = put(self.amisc) & 0x00FFFC00
        elif off == 0x18:
            self._clear(SUBCODE)
        elif off == 0x1D:
            self.txcmp = v
            self.tx_delay = 3
            self._clear(TXDMADONE)
        elif off == 0x1F:
            self.rxcmp = v
            self.rx_delay = 3
            self._clear(RXDMADONE)
        elif 0x20 <= off < 0x22:
            s2 = 8 * (0x21 - off)
            self.pbx |= v << s2
            if not self.flags & F_PBX:
                self.pbx = 0
            self._clear(PBX)
        elif 0x24 <= off < 0x28:
            old = self.flags
            self.flags = put(self.flags)
            if self.flags & F_ENABLE and not old & F_ENABLE:
                self.counter = 0
        elif off == 0x28:
            if not self.flags & F_TXD:
                self._clear(DRIVEXMIT)
                if self._can_send():
                    self._add_byte(v)
                    if self._can_send():
                        self._set(DRIVEXMIT)
        self._internal()
