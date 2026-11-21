#this belongs in apps/hardware/atapi.py - Version: 1
# X-Seti - November 18 2026 - Morosa - Morosa ATAPI.

"""
Morosa ATAPI - CD-ROM drive for the IDE channel; PACKET commands run on a SCSICD target.
"""

##Methods list -
# ATAPIDrive
# ATAPIDrive.identify
# ATAPIDrive.packet

import struct


class ATAPIDrive:
    """Looks like an ATADisk to IDEChannel but has atapi set and no sectors."""

    atapi = True
    sectors = 0

    def __init__(self, target, model: str = "MOROSA CD-ROM"):  #vers 1
        self.target = target
        self.model = model
        self.multi = 0
        self.features = {}

    def identify(self) -> bytes:  #vers 1
        w = [0] * 256
        w[0] = 0x8580
        w[49] = 0x0200
        w[53] = 1
        for i, ch in enumerate(self.model.ljust(40)[:40]):
            w[27 + i // 2] |= ord(ch) << (8 if i % 2 == 0 else 0)
        for i, ch in enumerate("0001".ljust(8)):
            w[23 + i // 2] |= ord(ch) << (8 if i % 2 == 0 else 0)
        return struct.pack("<256H", *w)

    def packet(self, cdb: bytes) -> tuple:  #vers 1
        """Returns (status, data, sense_key)."""
        st, data = self.target.execute(cdb)
        return st, data, self.target.sense[0] if st else 0
