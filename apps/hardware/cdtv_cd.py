#this belongs in apps/hardware/cdtv_cd.py - Version: 1
# X-Seti - November 18 2026 - Morosa - Morosa CDTV CD.

"""
Morosa CDTV CD - CDTV drive command set behind DMAC register 0xA1: status, TOC, sector reads.
"""

##Methods list -
# CDTVDrive
# CDTVDrive.insert
# CDTVDrive.read
# CDTVDrive.read_sectors
# CDTVDrive.write
# CDTVDrive._accept
# CDTVDrive._msf
# CDTVDrive._run

MODEL = b"MATSHITA0.96"
ONE_BYTE = (0x81,)
KNOWN = (0x01, 0x02, 0x04, 0x05, 0x09, 0x0A, 0x0B, 0x82, 0x83, 0x84, 0x87, 0x89, 0x8A, 0x8B, 0xA3)


class CDTVDrive:
    """write(byte) collects commands; read() returns reply bytes. stch/sten are status lines for the TPI."""

    def __init__(self):  #vers 1
        self.image = None
        self.media = self.motor = self.error = self.finished = False
        self.size = 2048
        self.inbuf, self.out, self.out_pos = [], b"", 0
        self.sten = self.stch = False
        self.lba, self.count = 0, 0

    def insert(self, image) -> None:  #vers 1
        self.image = image
        self.media = False

    def _msf(self, lba: int) -> bytes:  #vers 1
        lba += 150
        return bytes([lba // 4500, lba // 75 % 60, lba % 75])

    def _accept(self, out: bytes = b"") -> None:  #vers 1
        self.inbuf = []
        self.out, self.out_pos = out, 0
        self.sten = True

    def _run(self) -> None:  #vers 1
        c = self.inbuf
        op, im = c[0], self.image
        out = b""
        if op == 0x81:
            st = 1 | (self.finished << 3) | (self.error << 4) | (self.motor << 5) | (self.media << 6)
            self.finished = False
            return self._accept(bytes([st]))
        if op not in KNOWN:
            self.error = True
            return self._accept()
        if op == 0x01:
            self.finished, self.stch = True, True
        elif op == 0x02:
            self.lba, self.count, self.motor = c[1] << 16 | c[2] << 8 | c[3], c[4] << 8 | c[5], True
        elif op in (0x04, 0x05):
            self.motor, self.finished = op == 0x04, True
        elif op in (0x09, 0x0A, 0x0B):
            self.error, self.stch = True, True
        elif op == 0x82:
            out = bytes(6)
            if self.error:
                out = bytes([0, 0, 0x10, 0, 0, 0])
            self.error, self.finished = False, True
        elif op == 0x83:
            out, self.finished = MODEL, True
        elif op == 0x84:
            sz = c[2] << 8 | c[3]
            self.size = sz if sz in (2048, 2328, 2336, 2352) else 2048
            self.finished = True
        elif op == 0x87:
            out = bytes(13)
        elif op == 0x89:
            if im is None:
                out = b""
            else:
                t = im.tracks
                out = bytes([t[0]["num"], t[-1]["num"]]) + self._msf(im.blocks)
                self.motor = self.finished = True
        elif op == 0x8A:
            if im is not None:
                t = next((x for x in im.tracks if x["num"] == c[2]), None)
                if t is not None:
                    out = bytes([0, 1 << 4 | (0 if t["audio"] else 4), c[2],
                                 len(im.tracks), 0]) + self._msf(t["start"])
                    self.motor = self.finished = True
        elif op in (0x8B, 0xA3):
            self.finished = True
        self._accept(out)

    def write(self, v: int) -> None:  #vers 1
        self.inbuf.append(v & 0xFF)
        if self.inbuf[0] in ONE_BYTE or self.inbuf[0] not in KNOWN or len(self.inbuf) >= 7:
            self._run()

    def read(self) -> int:  #vers 1
        v = self.out[self.out_pos] if self.out_pos < len(self.out) else 0
        self.out_pos += 1
        self.sten = self.out_pos < len(self.out)
        return v

    def read_sectors(self) -> bytes:  #vers 1
        """Data for the pending READ command; marks it complete."""
        out = b""
        for i in range(self.count):
            raw = self.image.read_raw(self.lba + i) if self.image else None
            if raw is None:
                self.error, self.stch = True, True
                break
            out += raw[16:16 + 2048] if self.size == 2048 else raw[:self.size] if self.size == 2352 else raw[16:16 + self.size]
        self.count = 0
        self.finished = True
        return out
