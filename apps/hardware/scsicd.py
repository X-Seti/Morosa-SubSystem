#this belongs in apps/hardware/scsicd.py - Version: 1
# X-Seti - November 18 2026 - Morosa - Morosa SCSI CD.

"""
Morosa SCSI CD - CD-ROM target on a CDImage; shared by the A3000 WD33C93 and ATAPI on IDE.
"""

##Methods list -
# SCSICD
# SCSICD.execute
# SCSICD._msf
# SCSICD._sense
# SCSICD._toc

import struct

GOOD, CHECK = 0, 2


class SCSICD:
    """execute(cdb, data_out) -> (status, data_in), same contract as SCSIDisk."""

    def __init__(self, image, vendor: str = "MOROSA", product: str = "CD-ROM"):  #vers 1
        self.image = image
        self.vendor, self.product = vendor, product
        self.sense = (0, 0, 0)

    def _sense(self, key: int, asc: int = 0, ascq: int = 0) -> tuple:  #vers 1
        self.sense = (key, asc, ascq)
        return CHECK, b""

    def _msf(self, lba: int) -> bytes:  #vers 1
        lba += 150
        return bytes([0, lba // 4500, lba // 75 % 60, lba % 75])

    def _toc(self, msf: bool, first: int) -> bytes:  #vers 1
        rows = b""
        for t in self.image.tracks:
            if t["num"] < first:
                continue
            addr = self._msf(t["start"]) if msf else struct.pack(">I", t["start"])
            rows += bytes([0, 0x10 if t["audio"] else 0x14, t["num"], 0]) + addr
        end = self.image.blocks
        rows += bytes([0, 0x14, 0xAA, 0]) + (self._msf(end) if msf else struct.pack(">I", end))
        return struct.pack(">HBB", len(rows) + 2, 1, len(self.image.tracks)) + rows

    def execute(self, cdb: bytes, data_out: bytes = b"") -> tuple:  #vers 1
        op = cdb[0]
        if op == 0x00:                              # TEST UNIT READY
            self.sense = (0, 0, 0)
            return GOOD, b""
        if op == 0x03:                              # REQUEST SENSE
            k, a, q = self.sense
            self.sense = (0, 0, 0)
            d = bytes([0x70, 0, k, 0, 0, 0, 0, 10, 0, 0, 0, 0, a, q, 0, 0, 0, 0])
            return GOOD, d[:cdb[4] or 18]
        if op == 0x12:                              # INQUIRY
            d = (bytes([5, 0x80, 2, 2, 31, 0, 0, 0]) + self.vendor.ljust(8)[:8].encode()
                 + self.product.ljust(16)[:16].encode() + b"1.0 ")
            return GOOD, d[:cdb[4] or 36]
        if op == 0x25:                              # READ CAPACITY(10)
            return GOOD, struct.pack(">II", self.image.blocks - 1, 2048)
        if op in (0x08, 0x28):                      # READ(6), READ(10)
            if op == 0x08:
                lba, n = (cdb[1] & 0x1F) << 16 | cdb[2] << 8 | cdb[3], cdb[4] or 256
            else:
                lba, n = struct.unpack(">I", cdb[2:6])[0], struct.unpack(">H", cdb[7:9])[0]
            out = b""
            for i in range(n):
                s = self.image.read(lba + i)
                if s is None:
                    return self._sense(5, 0x21) if lba + i >= self.image.blocks else self._sense(5, 0x64)
                out += s
            return GOOD, out
        if op == 0x43:                              # READ TOC
            d = self._toc(bool(cdb[1] & 2), cdb[6])
            return GOOD, d[:struct.unpack(">H", cdb[7:9])[0] or len(d)]
        if op in (0x1A, 0x5A):                      # MODE SENSE(6), (10)
            d = bytes([0, 0, 0, 8]) + struct.pack(">I", self.image.blocks) + struct.pack(">I", 2048)
            return GOOD, bytes([len(d) - 1]) + d[1:][:cdb[4] - 1 if cdb[4] else 255] if op == 0x1A else \
                struct.pack(">HBBBBBB", len(d) + 2, 0, 0, 0, 0, 0, 8) + d[4:]
        if op in (0x1B, 0x1E, 0x2B, 0x35):          # START STOP, MEDIUM REMOVAL, SEEK, SYNC
            return GOOD, b""
        return self._sense(5, 0x20)                 # invalid command
