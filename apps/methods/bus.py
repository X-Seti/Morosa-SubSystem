#this belongs in apps/methods/bus.py - Version: 1
# X-Seti - November 21 2026 - Morosa - Memory bus shared by the 68k cores.

"""
Morosa Bus - flat RAM plus hooked address ranges, with bus and address errors; used by the Python and native 68k cores.
"""

##Methods list -
# AddressError
# AddressError.__init__
# Bus
# Bus.__init__
# Bus._hook
# Bus.hook_range
# Bus.r16
# Bus.r32
# Bus.r8
# Bus.read
# Bus.w16
# Bus.w32
# Bus.w8
# Bus.write


class BusError(Exception):
    """Access outside memory with no hook, or an MMU fault."""

    def __init__(self, msg="", addr=0, write=False):  #vers 1
        super().__init__(msg)
        self.addr = addr
        self.write = write


class AddressError(Exception):
    """Word or long access at an odd address on a 68000 or 68010."""

    def __init__(self, addr, write=False):
        super().__init__(f"address error at {addr:08x}")
        self.addr, self.write = addr, write


class Bus:
    """Flat RAM plus hooked address ranges for chips and library stubs."""

    def __init__(self, size: int = 16 * 1024 * 1024):  #vers 1
        self.ram = bytearray(size)
        self.size = size
        self.ranges = []
        self.amask = 0xFFFFFFFF
        self.strict = False
        self.mmu = None
        self.xl = False
        self.sup = True
        self.open_bus = False
        self.open_ranges = []
        self.open_value = 0
        self.berr_on = None
        self.pcache = {}
        self.rom, self.rom_lo, self.rom_n = b"", 0, 0

    def hook_range(self, start: int, end: int, read=None, write=None) -> None:  #vers 1
        """read(addr, size) -> int and write(addr, size, value) cover [start, end)."""
        self.ranges.append((start, end, read, write))
        self.pcache.clear()

    def _hook(self, a, write):  #vers 4
        k = (a >> 12) * 2 + write
        f = self.pcache.get(k)
        if f:
            return f
        for s, e, r, w in self.ranges:
            if s <= a < e:
                f = w if write else r
                if f:
                    p = a & ~0xFFF
                    if sum(1 for s2, e2, r2, w2 in self.ranges if s2 < p + 0x1000 and p < e2) == 1 and not (s | e) & 0xFFF:
                        self.pcache[k] = f
                    return f
        if self.open_bus or any(s <= a < e for s, e in self.open_ranges) or (self.berr_on and not self.berr_on()):
            return (lambda a, size, v=0: None) if write else (lambda a, size: self.open_value)
        raise BusError(f"bus error at {a:08x}")

    def r8(self, a):  #vers 2
        a &= self.amask
        if self.xl:
            a = self.mmu.xlate(a, False, self.sup) & self.amask
        if a < self.size:
            return self.ram[a]
        return self._hook(a, False)(a, 0) & 0xFF

    def r16(self, a):  #vers 3
        a &= self.amask
        if self.xl:
            if (a & self.mmu.pmask) == self.mmu.pmask:
                return (self.r8(a) << 8) | self.r8(a + 1)
            a = self.mmu.xlate(a, False, self.sup) & self.amask
        if self.strict and a & 1:
            raise AddressError(a)
        if a + 1 < self.size:
            r = self.ram
            return (r[a] << 8) | r[a + 1]
        o = a - self.rom_lo
        if 0 <= o < self.rom_n - 1:
            return (self.rom[o] << 8) | self.rom[o + 1]
        return self._hook(a, False)(a, 1) & 0xFFFF

    def r32(self, a):  #vers 3
        a &= self.amask
        if self.xl:
            if (a & self.mmu.pmask) > self.mmu.pmask - 3:
                return (self.r16(a) << 16) | self.r16(a + 2)
            a = self.mmu.xlate(a, False, self.sup) & self.amask
        if self.strict and a & 1:
            raise AddressError(a)
        if a + 3 < self.size:
            r = self.ram
            return (r[a] << 24) | (r[a + 1] << 16) | (r[a + 2] << 8) | r[a + 3]
        o = a - self.rom_lo
        if 0 <= o < self.rom_n - 3:
            return int.from_bytes(self.rom[o:o + 4], "big")
        return self._hook(a, False)(a, 2) & 0xFFFFFFFF

    def w8(self, a, v):  #vers 2
        a &= self.amask
        if self.xl:
            a = self.mmu.xlate(a, True, self.sup) & self.amask
        if a < self.size:
            self.ram[a] = v & 0xFF
        else:
            self._hook(a, True)(a, 0, v & 0xFF)

    def w16(self, a, v):  #vers 2
        a &= self.amask
        if self.xl:
            if (a & self.mmu.pmask) == self.mmu.pmask:
                self.w8(a, v >> 8)
                self.w8(a + 1, v)
                return
            a = self.mmu.xlate(a, True, self.sup) & self.amask
        if self.strict and a & 1:
            raise AddressError(a, True)
        if a + 1 < self.size:
            self.ram[a] = (v >> 8) & 0xFF
            self.ram[a + 1] = v & 0xFF
        else:
            self._hook(a, True)(a, 1, v & 0xFFFF)

    def w32(self, a, v):  #vers 2
        a &= self.amask
        if self.xl:
            if (a & self.mmu.pmask) > self.mmu.pmask - 3:
                self.w16(a, v >> 16)
                self.w16(a + 2, v)
                return
            a = self.mmu.xlate(a, True, self.sup) & self.amask
        if self.strict and a & 1:
            raise AddressError(a, True)
        if a + 3 < self.size:
            r = self.ram
            r[a] = (v >> 24) & 0xFF
            r[a + 1] = (v >> 16) & 0xFF
            r[a + 2] = (v >> 8) & 0xFF
            r[a + 3] = v & 0xFF
        else:
            self._hook(a, True)(a, 2, v & 0xFFFFFFFF)

    def read(self, a, size):  #vers 1
        return (self.r8, self.r16, self.r32)[size](a)

    def write(self, a, size, v):  #vers 1
        (self.w8, self.w16, self.w32)[size](a, v)
