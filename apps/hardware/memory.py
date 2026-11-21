#this belongs in apps/hardware/memory.py - Version: 1
# X-Seti - November 17 2026 - Morosa - Morosa Sparse Memory.

"""
Morosa Memory - paged RAM that allocates 64K pages on first write, so large fast RAM costs only what is used.
"""

##Methods list -
# SparseRAM
# SparseRAM.read
# SparseRAM.used
# SparseRAM.write

PAGE = 0x10000


class SparseRAM:
    """size bytes of RAM; untouched pages read as zero and take no memory."""

    def __init__(self, size: int):  #vers 1
        self.size = size
        self.pages = {}

    def read(self, off: int, n: int) -> int:  #vers 1
        v = 0
        for i in range(n):
            p = self.pages.get((off + i) // PAGE)
            v = v << 8 | (p[(off + i) % PAGE] if p else 0)
        return v

    def write(self, off: int, n: int, v: int) -> None:  #vers 1
        for i in range(n):
            a = off + i
            p = self.pages.get(a // PAGE)
            b = v >> 8 * (n - 1 - i) & 255
            if p is None:
                if not b:
                    continue
                p = self.pages[a // PAGE] = bytearray(PAGE)
            p[a % PAGE] = b

    def used(self) -> int:  #vers 1
        return len(self.pages) * PAGE
