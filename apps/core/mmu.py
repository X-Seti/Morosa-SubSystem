#this belongs in apps/core/mmu.py - Version: 3
# X-Seti - November 17 2026 - Morosa - Morosa 68030/68040/68060 MMU.

"""
Morosa MMU - logical to physical address translation for the 68030 PMMU and the 68040/68060 MMU.
"""

##Methods list -
# MMU
# _fault
# MMU.active
# MMU.flush
# MMU.p32
# MMU.probe
# MMU.update
# MMU.walk030
# MMU.walk040
# MMU.xlate


def _fault(la, write):  #vers 1
    from apps.methods.bus import BusError
    return BusError(f"mmu fault at {la:08x}", la, write)


class MMU:
    """Table walker with an address translation cache; fed from cpu.cr registers."""

    def __init__(self, cpu):  #vers 1
        self.cpu = cpu
        self.bus = cpu.bus
        self.m40 = cpu.m40
        self.on = False
        self.pmask = 0xFFF
        self.atc = {}

    def p32(self, a: int, v: int = None):  #vers 1
        """Raw physical long access for descriptors; no translation."""
        b = self.bus
        a &= b.amask
        if v is None:
            return int.from_bytes(b.ram[a:a + 4], "big") if a + 3 < b.size else b._hook(a, False)(a, 2) & 0xFFFFFFFF
        if a + 3 < b.size:
            b.ram[a:a + 4] = v.to_bytes(4, "big")
        else:
            b._hook(a, True)(a, 2, v)

    def update(self) -> None:  #vers 1
        """Registers changed: recompute enable and page size, drop the cache."""
        cr = self.cpu.cr
        tc = cr.get("tc", 0)
        if self.m40:
            self.on = bool(tc & 0x8000)
            self.pmask = 0x1FFF if tc & 0x4000 else 0xFFF
            tt = any(cr.get(n, 0) & 0x8000 for n in ("itt0", "itt1", "dtt0", "dtt1"))
        else:
            self.on = bool(tc & 0x80000000)
            self.pmask = (1 << (tc >> 20 & 15)) - 1 if self.on else 0xFFF
            tt = any(cr.get(n, 0) & 0x8000 for n in ("tt0", "tt1"))
        self.on = self.on or tt
        self.atc.clear()
        self.bus.xl = self.on

    def flush(self) -> None:  #vers 1
        self.atc.clear()

    def active(self) -> bool:  #vers 1
        return self.on

    # ---- translation ----
    def _tt(self, la: int, write: bool, sup: bool):  #vers 1
        """Transparent translation match: None, or True when write protected."""
        cr = self.cpu.cr
        if self.m40:
            for n in ("itt0", "itt1", "dtt0", "dtt1"):
                r = cr.get(n, 0)
                if not r & 0x8000:
                    continue
                s = r >> 13 & 3
                if s < 2 and (s == 1) != sup:
                    continue
                if ((la >> 24) ^ (r >> 24)) & ~(r >> 16) & 0xFF == 0:
                    return bool(r & 4) and write
            return None
        fc = 5 if sup else 1
        for n in ("tt0", "tt1"):
            r = cr.get(n, 0)
            if not r & 0x8000:
                continue
            if ((la >> 24) ^ (r >> 24)) & ~(r >> 16) & 0xFF:
                continue
            if (fc ^ (r >> 4)) & ~r & 7:
                continue
            if not r & 0x100 and bool(r & 0x200) == write:
                continue
            return False
        return None

    def xlate(self, la: int, write: bool, sup: bool) -> int:  #vers 1
        """Physical address, or BusFault."""
        key = (la >> 12 if self.pmask == 0xFFF else la >> 13 if self.pmask == 0x1FFF else la // (self.pmask + 1), sup)
        e = self.atc.get(key)
        if e is not None and (e[1] is False or not write) and (not write or e[2]):
            return e[0] | (la & self.pmask)
        r = self.walk040(la, write, sup) if self.m40 else self.walk030(la, write, sup)
        if r[0] is None:
            raise _fault(la, write)
        phys, wp, m, fixed = r
        if wp and write:
            raise _fault(la, write)
        if not fixed:
            self.atc[key] = (phys & ~self.pmask, wp, m)
        return phys

    def probe(self, la: int, write: bool, sup: bool):  #vers 1
        """Translate without faulting: (phys or None, write_protected, transparent, supervisor_violation)."""
        t = self._tt(la, write, sup)
        if t is not None:
            return la, t, True, False
        r = self.walk040(la, write, sup, dry=True) if self.m40 else self.walk030(la, write, sup, dry=True)
        return r[0], r[1], False, r[0] is None and len(r) > 4 and r[4]

    def walk040(self, la: int, write: bool, sup: bool, dry: bool = False):  #vers 1
        t = self._tt(la, write, sup)
        if t is not None:
            return (None, True, False, True) if t else (la, False, True, True)
        cr = self.cpu.cr
        big = bool(cr.get("tc", 0) & 0x4000)
        root = cr.get("srp" if sup else "urp", 0)
        wp = False
        d = self.p32((root & ~0x1FF) + (la >> 25 & 127) * 4)
        if d & 3 < 2:
            return (None, False, False, False)
        wp |= bool(d & 4)
        if not dry:
            self.p32((root & ~0x1FF) + (la >> 25 & 127) * 4, d | 8)
        a2 = (d & ~0x1FF) + (la >> 18 & 127) * 4
        d = self.p32(a2)
        if d & 3 < 2:
            return (None, False, False, False)
        wp |= bool(d & 4)
        if not dry:
            self.p32(a2, d | 8)
        if big:
            a3 = (d & ~0x7F) + (la >> 13 & 31) * 4
        else:
            a3 = (d & ~0xFF) + (la >> 12 & 63) * 4
        d = self.p32(a3)
        pdt = d & 3
        if pdt == 0:
            return (None, False, False, False)
        if pdt == 2:
            a3 = d & ~3
            d = self.p32(a3)
            if d & 3 in (0, 2):
                return (None, False, False, False)
        if d & 0x80 and not sup:
            return (None, False, False, False, True)
        wp |= bool(d & 4)
        nd = d | 8 | (0x10 if write and not wp else 0)
        if not dry and nd != d:
            self.p32(a3, nd)
        mask = 0x1FFF if big else 0xFFF
        return ((d & ~mask) | (la & mask), wp, bool(nd & 0x10), False)

    def walk030(self, la: int, write: bool, sup: bool, dry: bool = False):  #vers 2
        t = self._tt(la, write, sup)
        if t is not None:
            return (None, True, False, True) if t else (la, False, True, True)
        cr = self.cpu.cr
        tc = cr.get("tc", 0)
        if not tc & 0x80000000:
            return la, False, False, True
        shift = tc >> 16 & 15
        widths = [tc >> 12 & 15, tc >> 8 & 15, tc >> 4 & 15, tc & 15]
        root = cr.get("srp", 0) if (tc >> 25 & 1) and sup else cr.get("crp", 0)
        hi, addr = root >> 32, root & 0xFFFFFFF0
        dt = hi & 3
        x = (la << shift) & 0xFFFFFFFF
        used = shift
        wp = bool(hi & 4)
        levels = ([0] if tc >> 24 & 1 else []) + [w for w in widths if w]
        daddr = d0 = None
        for n in levels:
            if dt in (0, 1):
                break
            if n == 0:
                idx = 5 if sup else 1
            else:
                idx = x >> (32 - n)
                x = (x << n) & 0xFFFFFFFF
                used += n
            if dt == 3:
                lim = hi >> 16 & 0x7FFF
                if (hi >> 31 and idx < lim) or (not hi >> 31 and idx > lim):
                    return (None, False, False, False)
            daddr = addr + idx * (4 if dt == 2 else 8)
            d0 = self.p32(daddr)
            if dt == 3:
                addr = self.p32(daddr + 4) & 0xFFFFFFF0
                if d0 & 0x100 and not sup:
                    return (None, False, False, False, True)
            else:
                addr = d0 & 0xFFFFFFF0
            hi = d0
            dt = d0 & 3
            wp = wp or bool(d0 & 4)
        if dt != 1:
            return (None, False, False, False)
        off = (1 << (32 - used)) - 1
        m = True
        if daddr is not None:
            nd = d0 | 8 | (0x10 if write and not wp else 0)
            m = bool(nd & 0x10)
            if not dry and nd != d0:
                self.p32(daddr, nd)
        return ((addr & ~off) | (la & off), wp, m, False)
