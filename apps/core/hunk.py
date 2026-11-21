#this belongs in apps/core/hunk.py - Version: 1
# X-Seti - November 17 2026 - Morosa - Morosa Hunk Loader.

"""
Morosa Hunk Loader - loads Amiga hunk executables into emulated memory as a segment list.
"""

##Methods list -
# is_hunk
# load

import struct

HUNK_UNIT, HUNK_NAME, HUNK_CODE, HUNK_DATA, HUNK_BSS = 0x3E7, 0x3E8, 0x3E9, 0x3EA, 0x3EB
HUNK_RELOC32, HUNK_RELOC16, HUNK_RELOC8, HUNK_EXT, HUNK_SYMBOL = 0x3EC, 0x3ED, 0x3EE, 0x3EF, 0x3F0
HUNK_DEBUG, HUNK_END, HUNK_HEADER, HUNK_OVERLAY, HUNK_BREAK = 0x3F1, 0x3F2, 0x3F3, 0x3F5, 0x3F6
HUNK_DREL32, HUNK_DREL16, HUNK_DREL8, HUNK_RELOC32SHORT, HUNK_RELRELOC32 = 0x3F7, 0x3F8, 0x3F9, 0x3FC, 0x3FD


class HunkError(Exception):
    """The file is not a loadable hunk executable."""


def is_hunk(data: bytes) -> bool:  #vers 1
    return len(data) >= 4 and struct.unpack(">I", data[:4])[0] == HUNK_HEADER


def load(data: bytes, bus, alloc):  #vers 1
    """Place the hunks; alloc(size) gives a free address. Returns (first segment BPTR, segment addresses)."""
    pos = 0

    def u32():
        nonlocal pos
        if pos + 4 > len(data):
            raise HunkError("truncated file")
        v = struct.unpack(">I", data[pos:pos + 4])[0]
        pos += 4
        return v

    if u32() != HUNK_HEADER:
        raise HunkError("not a hunk executable")
    while True:
        n = u32()
        if n == 0:
            break
        pos += n * 4
    table = u32()
    first, last = u32(), u32()
    count = last - first + 1
    sizes = []
    for _ in range(count):
        s = u32()
        if s >> 30 == 3:
            u32()
        sizes.append((s & 0x3FFFFFFF) * 4)
    if count > table:
        raise HunkError("bad hunk table")
    segs = []
    for sz in sizes:
        base = alloc(sz + 8)
        bus.w32(base, sz + 8)
        bus.w32(base + 4, 0)
        for i in range(0, sz, 4):
            bus.w32(base + 8 + i, 0)
        segs.append(base + 8)
    for i in range(count - 1):
        bus.w32(segs[i] - 4, segs[i + 1] >> 2)
    cur = 0
    while pos < len(data) and cur < count:
        t = u32() & 0x3FFFFFFF
        if t in (HUNK_CODE, HUNK_DATA):
            n = u32() * 4
            if n > sizes[cur]:
                raise HunkError("hunk larger than header size")
            for i in range(n):
                bus.w8(segs[cur] + i, data[pos + i])
            pos += n
        elif t == HUNK_BSS:
            u32()
        elif t in (HUNK_RELOC32, HUNK_DREL32):
            while True:
                n = u32()
                if n == 0:
                    break
                tgt = u32()
                if tgt >= count:
                    raise HunkError("bad reloc target")
                for _ in range(n):
                    off = u32()
                    a = segs[cur] + off
                    bus.w32(a, (bus.r32(a) + segs[tgt]) & 0xFFFFFFFF)
        elif t == HUNK_RELOC32SHORT:
            while True:
                n = struct.unpack(">H", data[pos:pos + 2])[0]
                pos += 2
                if n == 0:
                    break
                tgt = struct.unpack(">H", data[pos:pos + 2])[0]
                pos += 2
                for _ in range(n):
                    off = struct.unpack(">H", data[pos:pos + 2])[0]
                    pos += 2
                    a = segs[cur] + off
                    bus.w32(a, (bus.r32(a) + segs[tgt]) & 0xFFFFFFFF)
            pos = (pos + 3) & ~3
        elif t == HUNK_RELRELOC32:
            raise HunkError("HUNK_RELRELOC32 not supported")
        elif t == HUNK_SYMBOL:
            while True:
                w = u32()
                if w == 0:
                    break
                pos += (w & 0xFFFFFF) * 4 + 4
        elif t == HUNK_EXT:
            raise HunkError("object file, not an executable")
        elif t == HUNK_DEBUG or t == HUNK_NAME or t == HUNK_UNIT:
            pos += u32() * 4
        elif t == HUNK_END:
            cur += 1
        elif t in (HUNK_OVERLAY, HUNK_BREAK):
            raise HunkError("overlay executables not supported")
        else:
            raise HunkError(f"unknown hunk type {t:#x}")
    return (segs[0] - 4) >> 2, segs
