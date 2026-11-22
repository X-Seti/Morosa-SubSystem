#this belongs in apps/hardware/memory.py - Version: 2
# X-Seti - November 21 2026 - Morosa - Morosa Sparse Memory.

"""
Morosa Memory - anonymous mapped RAM; the OS commits pages on first touch and the native core reads buf directly.
"""

##Methods list -
##class SparseRAM: -
# __init__
# read
# used
# write

import mmap

PAGE = 0x10000


class SparseRAM:
    """size bytes of RAM; untouched pages read as zero and take no memory."""

    def __init__(self, size: int):  #vers 2
        self.size = size
        self.buf = mmap.mmap(-1, size) if size else bytearray(0)

    def read(self, off: int, n: int) -> int:  #vers 2
        return int.from_bytes(self.buf[off:off + n], "big")

    def write(self, off: int, n: int, v: int) -> None:  #vers 2
        self.buf[off:off + n] = v.to_bytes(n, "big")

    def used(self) -> int:  #vers 2
        return sum(PAGE for i in range(0, self.size, PAGE) if any(self.buf[i:i + PAGE]))
