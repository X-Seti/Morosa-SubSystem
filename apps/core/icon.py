#this belongs in apps/core/icon.py - Version: 1
# X-Seti - November 17 2026 - Morosa - Morosa icon.library.

"""
Morosa icon.library - reads .info files into DiskObject structures; tool types and disk objects.
"""

##Methods list -
# Icon
# Icon._image
# Icon._put_str
# Icon._read
# Icon.f_DupDiskObjectA
# Icon.f_FindToolType
# Icon.f_FreeDiskObject
# Icon.f_GetDefDiskObject
# Icon.f_GetDiskObject
# Icon.f_GetDiskObjectNew
# Icon.f_GetIconTagList
# Icon.f_MatchToolValue
# Icon.f_NewDiskObject

import os
import struct

WBDISK, WBDRAWER, WBTOOL, WBPROJECT, WBGARBAGE, WBDEVICE, WBKICK, WBAPPICON = 1, 2, 3, 4, 5, 6, 7, 8
DO_SIZE = 78


class Icon:
    """icon.library functions; f_<Name> reads registers from the CPU."""

    def __init__(self, machine):  #vers 1
        self.m = machine
        self.cpu = machine.cpu
        self.bus = machine.bus
        self.ex = machine.exec

    def _put_str(self, data: bytes) -> int:  #vers 1
        a = self.ex.alloc(len(data) + 8)
        for i, c in enumerate(data):
            self.bus.w8(a + i, c)
        return a

    def _image(self, d: bytes, pos: int):  #vers 1
        """Image header and planes at pos; returns (address, next pos)."""
        left, top, w, h, depth = struct.unpack(">hhhhh", d[pos:pos + 10])
        pick, onoff = d[pos + 14], d[pos + 15]
        size = ((w + 15) >> 4) * 2 * h * depth
        im = self.ex.alloc(20)
        data = self.ex.alloc(size + 8)
        b = self.bus
        for i in range(size):
            b.w8(data + i, d[pos + 20 + i])
        b.w16(im, left & 0xFFFF)
        b.w16(im + 2, top & 0xFFFF)
        b.w16(im + 4, w)
        b.w16(im + 6, h)
        b.w16(im + 8, depth)
        b.w32(im + 10, data)
        b.w8(im + 14, pick)
        b.w8(im + 15, onoff)
        return im, pos + 20 + size

    def _read(self, path: str) -> int:  #vers 1
        """Build a DiskObject from a .info file; 0 when missing or not an icon."""
        try:
            d = open(path, "rb").read()
        except OSError:
            return 0
        if len(d) < DO_SIZE or d[:2] != b"\xe3\x10":
            return 0
        b = self.bus
        do = self.ex.alloc(DO_SIZE + 8)
        for i in range(DO_SIZE):
            b.w8(do + i, d[i])
        gr, sr = struct.unpack(">II", d[4 + 18:4 + 26])
        deftool, ttypes, drawer, toolwin = struct.unpack(">IIII", d[50:54] + d[54:58] + d[66:70] + d[70:74])
        pos = DO_SIZE
        for off in (50, 54, 66, 70):
            b.w32(do + off, 0)
        b.w32(do + 4 + 18, 0)
        b.w32(do + 4 + 22, 0)
        b.w32(do + 4, 0)
        b.w32(do + 4 + 26, 0)
        b.w32(do + 4 + 30, 0)
        if drawer:
            dd = self.ex.alloc(64)
            for i in range(56):
                b.w8(dd + i, d[pos + i])
            b.w32(do + 66, dd)
            pos += 56
        if gr:
            im, pos = self._image(d, pos)
            b.w32(do + 4 + 18, im)
        if sr:
            im, pos = self._image(d, pos)
            b.w32(do + 4 + 22, im)
        if deftool:
            n = struct.unpack(">I", d[pos:pos + 4])[0]
            b.w32(do + 50, self._put_str(d[pos + 4:pos + 4 + n]))
            pos += 4 + n
        if ttypes:
            n = struct.unpack(">I", d[pos:pos + 4])[0] // 4 - 1
            pos += 4
            arr = self.ex.alloc((n + 1) * 4 + 8)
            for i in range(n):
                ln = struct.unpack(">I", d[pos:pos + 4])[0]
                b.w32(arr + 4 * i, self._put_str(d[pos + 4:pos + 4 + ln]))
                pos += 4 + ln
            b.w32(arr + 4 * n, 0)
            b.w32(do + 54, arr)
        if toolwin:
            n = struct.unpack(">I", d[pos:pos + 4])[0]
            b.w32(do + 70, self._put_str(d[pos + 4:pos + 4 + n]))
        return do

    def f_GetDiskObject(self):  #vers 1
        cpu = self.cpu
        name = self.m.dos._cstr(cpu.a[0])
        if name.lower().endswith(".info"):
            name = name[:-5]
        path = self.m.dos.host(name + ".info")
        cpu.d[0] = self._read(path)
        if not cpu.d[0]:
            self.m.dos.set_err(205)

    f_GetDiskObjectNew = f_GetDiskObject

    def f_GetDefDiskObject(self):  #vers 1
        cpu, b = self.cpu, self.bus
        do = self.ex.alloc(DO_SIZE + 8)
        b.w16(do, 0xE310)
        b.w16(do + 2, 1)
        b.w8(do + 48, cpu.d[0])
        b.w32(do + 74, 4096)
        cpu.d[0] = do

    def f_GetIconTagList(self):  #vers 1
        self.f_GetDiskObject()

    def f_NewDiskObject(self):  #vers 1
        cpu, b = self.cpu, self.bus
        do = self.ex.alloc(DO_SIZE + 8)
        b.w16(do, 0xE310)
        b.w16(do + 2, 1)
        b.w8(do + 48, cpu.d[0])
        b.w32(do + 74, 0)
        cpu.d[0] = do

    def f_DupDiskObjectA(self):  #vers 1
        cpu, b = self.cpu, self.bus
        src = cpu.a[0]
        do = self.ex.alloc(DO_SIZE + 8)
        for i in range(DO_SIZE):
            b.w8(do + i, b.r8(src + i))
        cpu.d[0] = do

    def f_FreeDiskObject(self):  #vers 1
        pass

    def f_FindToolType(self):  #vers 1
        cpu, b = self.cpu, self.bus
        arr, want = cpu.a[0], self.m.dos._cstr(cpu.a[1]).lower()
        cpu.d[0] = 0
        while arr and b.r32(arr):
            p = b.r32(arr)
            s = self.ex.cstr(p)
            k, eq, _v = s.partition("=")
            if k.lower() == want:
                cpu.d[0] = p + len(k) + (1 if eq else len(s) - len(k))
                return
            arr += 4

    def f_MatchToolValue(self):  #vers 1
        cpu = self.cpu
        val = self.m.dos._cstr(cpu.a[0]).lower().split("|")
        want = self.m.dos._cstr(cpu.a[1]).lower()
        cpu.d[0] = 0xFFFFFFFF if want in val else 0
