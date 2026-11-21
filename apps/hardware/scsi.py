#this belongs in apps/hardware/scsi.py - Version: 1
# X-Seti - November 17 2026 - Morosa - Morosa SCSI Disk.

"""
Morosa SCSI - direct access disk target on an HDF image; shared by the A3000 SDMAC and A4000T 53C710.
"""

##Methods list -
# SCSIDisk
# SCSIDisk.execute
# SCSIDisk._sense

import struct

GOOD, CHECK = 0, 2


class SCSIDisk:
    """execute(cdb, data_out) -> (status, data_in). Sense data is kept for REQUEST SENSE."""

    def __init__(self, image: bytearray, vendor: str = "MOROSA", product: str = "HDF DISK"):  #vers 1
        self.image = image
        self.blocks = len(image) // 512
        self.vendor, self.product = vendor, product
        self.sense = (0, 0, 0)
        self.heads, self.spt = getattr(image, "heads", 16), getattr(image, "spt", 63)

    def _sense(self, key: int, asc: int = 0, ascq: int = 0) -> tuple:  #vers 1
        self.sense = (key, asc, ascq)
        return CHECK, b""

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
            d = (bytes([0, 0, 2, 2, 31, 0, 0, 0]) + self.vendor.ljust(8)[:8].encode()
                 + self.product.ljust(16)[:16].encode() + b"1.0 ")
            return GOOD, d[:cdb[4] or 36]
        if op == 0x25:                              # READ CAPACITY(10)
            return GOOD, struct.pack(">II", self.blocks - 1, 512)
        if op in (0x08, 0x28):                      # READ(6), READ(10)
            lba, n = (((cdb[1] & 0x1F) << 16 | cdb[2] << 8 | cdb[3]), cdb[4] or 256) if op == 0x08 else \
                (struct.unpack(">I", cdb[2:6])[0], struct.unpack(">H", cdb[7:9])[0])
            if lba + n > self.blocks:
                return self._sense(5, 0x21)
            return GOOD, bytes(self.image[lba * 512:(lba + n) * 512])
        if op in (0x0A, 0x2A):                      # WRITE(6), WRITE(10)
            lba, n = (((cdb[1] & 0x1F) << 16 | cdb[2] << 8 | cdb[3]), cdb[4] or 256) if op == 0x0A else \
                (struct.unpack(">I", cdb[2:6])[0], struct.unpack(">H", cdb[7:9])[0])
            if lba + n > self.blocks:
                return self._sense(5, 0x21)
            self.image[lba * 512:(lba + n) * 512] = data_out[:n * 512].ljust(n * 512, b"\0")
            return GOOD, b""
        if op == 0x1A:                              # MODE SENSE(6): header, block descriptor
            d = bytes([0, 0, 0, 8]) + struct.pack(">I", min(self.blocks, 0xFFFFFF)) + struct.pack(">I", 512)
            pg = cdb[2] & 0x3F
            if pg in (3, 4, 0x3F):
                cyl = max(1, self.blocks // (self.heads * self.spt))
                d += bytes([4, 22, cyl >> 16 & 255, cyl >> 8 & 255, cyl & 255, self.heads]) + bytes(16)
            return GOOD, bytes([len(d) - 1]) + d[1:][:cdb[4] - 1 if cdb[4] else 255]
        if op in (0x1B, 0x1E, 0x35, 0x2F):          # START STOP, MEDIUM REMOVAL, SYNC CACHE, VERIFY
            return GOOD, b""
        return self._sense(5, 0x20)                 # invalid command
