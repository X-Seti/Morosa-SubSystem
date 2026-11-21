#this belongs in apps/methods/hardfile.py - Version: 1
# X-Seti - November 18 2026 - Morosa - Morosa Hardfile.

"""
Morosa Hardfile - wraps an image without an RDB in a virtual RDB with one partition, UAE style.
"""

##Methods list -
# HardfileImage
# HardfileImage.__getitem__
# HardfileImage.__len__
# HardfileImage.__setitem__
# HardfileImage._rdb
# _bstr
# _seal
# has_rdb

import struct


def has_rdb(image) -> bool:  #vers 1
    """True when one of the first 16 blocks holds an RDSK block."""
    return any(bytes(image[b * 512:b * 512 + 4]) == b"RDSK" for b in range(16))


def _bstr(text: str, size: int) -> bytes:  #vers 1
    return bytes([len(text)]) + text.encode().ljust(size - 1, b"\0")[:size - 1]


def _seal(longs: list) -> bytes:  #vers 1
    """Set the checksum so all summed longs add to zero."""
    longs[2] = 0
    longs[2] = -sum(longs[:longs[1]]) & 0xFFFFFFFF
    return struct.pack(">128L", *longs)


class HardfileImage:
    """Slice access like a bytearray: a reserved cylinder with RDB and PART blocks, then the image."""

    def __init__(self, image, heads: int = 16, spt: int = 63, name: str = "DH0", dostype: int = 0):  #vers 1
        self.image = image
        self.heads, self.spt = heads, spt
        self.cylblocks = heads * spt
        data_blocks = (len(image) + 511) // 512
        self.cyls = 1 + -(-data_blocks // self.cylblocks)
        self.size = self.cyls * self.cylblocks * 512
        self.base = self.cylblocks * 512
        self.head = self._rdb(name, dostype or self._guess_dostype())
        self.name = name

    def _guess_dostype(self) -> int:  #vers 1
        t = bytes(self.image[:4])
        return struct.unpack(">I", t)[0] if t[:3] == b"DOS" else 0x444F5301

    def _rdb(self, name: str, dostype: int) -> bytes:  #vers 1
        r = [0xFFFFFFFF] * 128
        r[0], r[1], r[3], r[4], r[5] = 0x5244534B, 64, 7, 512, 0x12
        r[6], r[7], r[8], r[9] = 0xFFFFFFFF, 1, 0xFFFFFFFF, 0xFFFFFFFF
        r[16], r[17], r[18], r[19], r[20] = self.cyls, self.spt, self.heads, 0, self.cyls
        r[23] = r[24] = r[25] = 0
        r[32], r[33], r[34], r[35], r[36], r[37], r[38] = 0, self.cylblocks - 1, 1, self.cyls - 1, self.cylblocks, 0, 1
        r[39] = 0
        for i in range(40, 64):
            r[i] = 0
        vend = b"MOROSA  " + b"HARDFILE".ljust(16) + b"1.0 "
        r[40:40 + len(vend) // 4] = struct.unpack(">7L", vend)
        p = [0] * 128
        p[0], p[1], p[3], p[4], p[5] = 0x50415254, 64, 7, 0xFFFFFFFF, 1
        p[9:17] = struct.unpack(">8L", _bstr(name, 32))
        p[32:52] = [16, 128, 0, self.heads, 1, self.spt, 2, 0, 0, 1, self.cyls - 1, 30, 0,
                    0x7FFFFFFF, 0xFFFFFFFE, 0, dostype, 0, 0, 0]
        return _seal(r) + _seal(p)

    def __len__(self) -> int:  #vers 1
        return self.size

    def __getitem__(self, key):  #vers 1
        start, stop, _ = key.indices(self.size)
        out = bytearray(max(0, stop - start))
        if start < 1024:
            n = min(stop, 1024) - start
            out[:n] = self.head[start:start + n]
        lo = max(start, self.base)
        if stop > lo:
            src = self.image[lo - self.base:min(stop - self.base, len(self.image))]
            out[lo - start:lo - start + len(src)] = src
        return bytes(out)

    def __setitem__(self, key, value) -> None:  #vers 1
        start, stop, _ = key.indices(self.size)
        lo = max(start, self.base)
        hi = min(stop - self.base, len(self.image))
        if hi > lo - self.base:
            self.image[lo - self.base:hi] = value[lo - start:lo - start + hi - (lo - self.base)]
