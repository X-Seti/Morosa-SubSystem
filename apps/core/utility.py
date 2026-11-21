#this belongs in apps/core/utility.py - Version: 1
# X-Seti - November 17 2026 - Morosa - Morosa utility.library.

"""
Morosa utility.library - tag lists, string and arithmetic helpers, date conversion.
"""

##Methods list -
# Util
# Util.f_Amiga2Date
# Util.f_CheckDate
# Util.f_Date2Amiga
# Util.f_FindTagItem
# Util.f_GetTagData
# Util.f_NextTagItem
# Util.f_SDivMod32
# Util.f_UMult64
# Util.f_SMult32
# Util.f_Stricmp
# Util.f_Strnicmp
# Util.f_TagInArray
# Util.f_ToLower
# Util.f_ToUpper
# Util.f_SMult64
# Util.f_Strncat
# Util.f_Strncpy
# Util.f_VSNPrintf
# Util.f_CallHookPkt
# Util.f_AllocateTagItems
# Util.f_CloneTagItems
# Util.f_FreeTagItems
# Util.f_GetUniqueID
# Util.f_UDivMod32
# Util.f_UMult32
# Util.tags
# days_to_ymd
# ymd_to_days

import datetime

EPOCH = datetime.date(1978, 1, 1)


def days_to_ymd(days: int):  #vers 1
    d = EPOCH + datetime.timedelta(days=days)
    return d.year, d.month, d.day, d.isoweekday() % 7


def ymd_to_days(y: int, m: int, d: int) -> int:  #vers 1
    return (datetime.date(y, m, d) - EPOCH).days


class Util:
    """utility.library functions."""

    def __init__(self, machine):  #vers 1
        self.m = machine
        self.cpu = machine.cpu
        self.bus = machine.bus
        self.ex = machine.exec

    def tags(self, a: int):  #vers 1
        """Yield (item address, tag, data) for a tag list, following MORE, IGNORE and SKIP."""
        b = self.bus
        while a:
            tag = b.r32(a)
            data = b.r32(a + 4)
            if tag == 0:
                return
            if tag == 1:
                a += 8
            elif tag == 2:
                a = data
            elif tag == 3:
                a += 8 + 8 * data
            else:
                yield a, tag, data
                a += 8

    def f_FindTagItem(self):  #vers 1
        cpu = self.cpu
        for a, t, _ in self.tags(cpu.a[0]):
            if t == cpu.d[0]:
                cpu.d[0] = a
                return
        cpu.d[0] = 0

    def f_GetTagData(self):  #vers 1
        cpu = self.cpu
        for _, t, d in self.tags(cpu.a[0]):
            if t == cpu.d[0]:
                cpu.d[0] = d
                return
        cpu.d[0] = cpu.d[1]

    def f_NextTagItem(self):  #vers 1
        cpu = self.cpu
        pp = cpu.a[0]
        cur = self.bus.r32(pp)
        for a, t, d in self.tags(cur):
            self.bus.w32(pp, a + 8)
            cpu.d[0] = a
            return
        self.bus.w32(pp, 0)
        cpu.d[0] = 0

    def f_TagInArray(self):  #vers 1
        cpu = self.cpu
        a = cpu.a[0]
        while self.bus.r32(a):
            if self.bus.r32(a) == cpu.d[0]:
                cpu.d[0] = 0xFFFFFFFF
                return
            a += 4
        cpu.d[0] = 0

    def f_Strncpy(self):  #vers 1
        cpu, b = self.cpu, self.bus
        dst, src, n = cpu.a[1], cpu.a[0], cpu.d[0]
        text = self.ex.cstr(src).encode("latin-1")[: max(0, n - 1)]
        for i, c in enumerate(text):
            b.w8(dst + i, c)
        if n:
            b.w8(dst + len(text), 0)
        cpu.d[0] = dst

    def f_Strncat(self):  #vers 1
        cpu, b = self.cpu, self.bus
        dst, src, n = cpu.a[1], cpu.a[0], cpu.d[0]
        end = dst + len(self.ex.cstr(dst))
        text = self.ex.cstr(src).encode("latin-1")[:n]
        for i, c in enumerate(text):
            b.w8(end + i, c)
        b.w8(end + len(text), 0)
        cpu.d[0] = dst

    def f_VSNPrintf(self):  #vers 1
        cpu, b = self.cpu, self.bus
        buf, size = cpu.a[0], cpu.d[0]
        out, _ = self.ex.format(cpu.a[1], cpu.a[2])
        text = bytes(out[:-1])
        keep = text[: max(0, size - 1)]
        for i, c in enumerate(keep):
            b.w8(buf + i, c)
        if size:
            b.w8(buf + len(keep), 0)
        cpu.d[0] = len(text) + 1

    def f_CallHookPkt(self):  #vers 1
        cpu = self.cpu
        hook, obj, msg = cpu.a[0], cpu.a[2], cpu.a[1]
        cpu.d[0] = self.ex.call(self.bus.r32(hook + 8), {}, {0: hook, 1: msg, 2: obj})

    def f_AllocateTagItems(self):  #vers 1
        cpu = self.cpu
        cpu.d[0] = self.ex.alloc(cpu.d[0] * 8 + 8)

    def f_CloneTagItems(self):  #vers 1
        cpu, b = self.cpu, self.bus
        src, n = cpu.a[0], 0
        while b.r32(src + n * 8) != 0:
            n += 1
        dst = self.ex.alloc(n * 8 + 16)
        for i in range(n * 8 + 8):
            b.w8(dst + i, b.r8(src + i))
        cpu.d[0] = dst

    def f_FreeTagItems(self):  #vers 1
        pass

    def f_GetUniqueID(self):  #vers 1
        self.uid = getattr(self, "uid", 0) + 1
        self.cpu.d[0] = self.uid

    def f_Stricmp(self):  #vers 1
        a, b = self.ex.cstr(self.cpu.a[0]).lower(), self.ex.cstr(self.cpu.a[1]).lower()
        self.cpu.d[0] = ((a > b) - (a < b)) & 0xFFFFFFFF

    def f_Strnicmp(self):  #vers 1
        n = self.cpu.d[0]
        a, b = self.ex.cstr(self.cpu.a[0]).lower()[:n], self.ex.cstr(self.cpu.a[1]).lower()[:n]
        self.cpu.d[0] = ((a > b) - (a < b)) & 0xFFFFFFFF

    def f_ToUpper(self):  #vers 1
        c = self.cpu.d[0] & 0xFF
        self.cpu.d[0] = c - 32 if 97 <= c <= 122 or 0xE0 <= c <= 0xFE and c != 0xF7 else c

    def f_ToLower(self):  #vers 1
        c = self.cpu.d[0] & 0xFF
        self.cpu.d[0] = c + 32 if 65 <= c <= 90 or 0xC0 <= c <= 0xDE and c != 0xD7 else c

    def f_UMult32(self):  #vers 1
        self.cpu.d[0] = (self.cpu.d[0] * self.cpu.d[1]) & 0xFFFFFFFF

    def f_SMult32(self):  #vers 1
        s = lambda v: v - (1 << 32) if v >> 31 else v
        self.cpu.d[0] = (s(self.cpu.d[0]) * s(self.cpu.d[1])) & 0xFFFFFFFF

    def f_UMult64(self):  #vers 1
        p = self.cpu.d[0] * self.cpu.d[1]
        self.cpu.d[0], self.cpu.d[1] = p & 0xFFFFFFFF, p >> 32

    def f_SMult64(self):  #vers 1
        s = lambda v: v - (1 << 32) if v >> 31 else v
        p = (s(self.cpu.d[0]) * s(self.cpu.d[1])) & 0xFFFFFFFFFFFFFFFF
        self.cpu.d[0], self.cpu.d[1] = p & 0xFFFFFFFF, p >> 32

    def f_UDivMod32(self):  #vers 1
        n, d = self.cpu.d[0], self.cpu.d[1]
        if d == 0:
            self.cpu.d[0] = 0
            return
        self.cpu.d[0], self.cpu.d[1] = n // d, n % d

    def f_SDivMod32(self):  #vers 1
        s = lambda v: v - (1 << 32) if v >> 31 else v
        n, d = s(self.cpu.d[0]), s(self.cpu.d[1])
        if d == 0:
            self.cpu.d[0] = 0
            return
        q = abs(n) // abs(d) * (1 if (n < 0) == (d < 0) else -1)
        self.cpu.d[0], self.cpu.d[1] = q & 0xFFFFFFFF, (n - q * d) & 0xFFFFFFFF

    def f_Amiga2Date(self):  #vers 1
        cpu = self.cpu
        secs, cd = cpu.d[0], cpu.a[0]
        y, m, d, wd = days_to_ymd(secs // 86400)
        r = secs % 86400
        b = self.bus
        b.w16(cd, r % 60)
        b.w16(cd + 2, r // 60 % 60)
        b.w16(cd + 4, r // 3600)
        b.w16(cd + 6, d)
        b.w16(cd + 8, m)
        b.w16(cd + 10, y)
        b.w16(cd + 12, wd)

    def f_Date2Amiga(self):  #vers 1
        cpu = self.cpu
        b, cd = self.bus, cpu.a[0]
        try:
            days = ymd_to_days(b.r16(cd + 10), b.r16(cd + 8), b.r16(cd + 6))
        except ValueError:
            cpu.d[0] = 0
            return
        cpu.d[0] = days * 86400 + b.r16(cd + 4) * 3600 + b.r16(cd + 2) * 60 + b.r16(cd)

    def f_CheckDate(self):  #vers 1
        cpu = self.cpu
        b, cd = self.bus, cpu.a[0]
        try:
            days = ymd_to_days(b.r16(cd + 10), b.r16(cd + 8), b.r16(cd + 6))
            cpu.d[0] = days * 86400 + b.r16(cd + 4) * 3600 + b.r16(cd + 2) * 60 + b.r16(cd)
        except ValueError:
            cpu.d[0] = 0
