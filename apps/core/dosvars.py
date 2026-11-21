#this belongs in apps/core/dosvars.py - Version: 1
# X-Seti - November 17 2026 - Morosa - Morosa dos.library Variables and Text.

"""
Morosa dos.library variables and text - local and global variables, error text, dates and BCPL formatting.
"""

##Methods list -
# DosVars
# DosVars.f_DateToStr
# DosVars.f_DeleteVar
# DosVars.f_Fault
# DosVars.f_FindVar
# DosVars.f_GetVar
# DosVars.f_PrintFault
# DosVars.f_SetVar
# DosVars.f_StrToDate
# DosVars.f_VFWritef
# fault_text

import re

from apps.core.utility import days_to_ymd, ymd_to_days

FAULTS = {
    103: "not enough memory available", 114: "bad template", 115: "bad number", 116: "required argument missing",
    117: "value after keyword missing", 118: "wrong number of arguments", 119: "unmatched quotes",
    120: "argument line invalid or too long", 121: "file is not executable", 122: "invalid resident library",
    202: "object in use", 203: "object already exists", 204: "directory not found", 205: "object not found",
    206: "invalid window description", 209: "packet request type unknown", 210: "stream member name invalid",
    211: "invalid object lock", 212: "object not of required type", 213: "disk not validated",
    214: "disk write-protected", 215: "rename across devices attempted", 216: "directory not empty",
    217: "too many levels", 218: "device (or volume) is not mounted", 219: "seek failure", 220: "comment too big",
    221: "disk full", 222: "file is protected from deletion", 223: "file is write protected",
    224: "file is read protected", 225: "not a valid DOS disk", 226: "no disk in drive", 232: "no more entries in directory",
    233: "object is soft link", 234: "object is linked", 235: "bad loadfile hunk", 236: "function not implemented",
    240: "record not locked", 241: "record lock collision", 242: "record lock timeout", 243: "record unlock error",
}
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_DAYS = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")


def fault_text(code: int) -> str:  #vers 1
    return FAULTS.get(code, f"Unknown error {code}" if code else "")


class DosVars:
    """Mixed into Dos: f_<Name> functions from dos.library."""

    def f_Fault(self):  #vers 1
        cpu = self.cpu
        hdr = self._cstr(cpu.d[2]) if cpu.d[2] else ""
        txt = fault_text(cpu.d[1])
        s = (hdr + ": " if hdr else "") + txt
        s = s[: max(0, cpu.d[4] - 1)]
        self.ex.put_cstr(cpu.d[3], s)
        cpu.d[0] = len(s)

    def f_PrintFault(self):  #vers 1
        cpu = self.cpu
        hdr = self._cstr(cpu.d[2]) if cpu.d[2] else ""
        s = (hdr + "; " if hdr else "") + fault_text(cpu.d[1]) + "\n"
        self._write(self._h(self.stdout), s.encode("latin-1"))
        cpu.d[0] = DOSTRUE_

    def f_GetVar(self):  #vers 1
        cpu = self.cpu
        name = self._cstr(cpu.d[1]).lower()
        flags = cpu.d[4]
        val = None
        if not flags & 0x100:
            val = self.localvars.get(name)
        if val is None and not flags & 0x200:
            val = self.shell.env.get(name)
        if val is None:
            self.set_err(205)
            cpu.d[0] = 0xFFFFFFFF
            return
        data = val.encode("latin-1")
        size = cpu.d[3]
        out = data[: max(0, size - 1)]
        for i, c in enumerate(out):
            self.bus.w8(cpu.d[2] + i, c)
        if size:
            self.bus.w8(cpu.d[2] + len(out), 0)
        cpu.d[0] = len(out)

    def f_SetVar(self):  #vers 1
        cpu = self.cpu
        name = self._cstr(cpu.d[1]).lower()
        data = bytes(self.bus.r8(cpu.d[2] + i) for i in range(cpu.d[3] if cpu.d[3] != 0xFFFFFFFF else len(self._cstr(cpu.d[2]))))
        val = data.decode("latin-1")
        if cpu.d[4] & 0x100:
            self.shell.env[name] = val
        else:
            self.localvars[name] = val
        cpu.d[0] = 0xFFFFFFFF

    def f_DeleteVar(self):  #vers 1
        cpu = self.cpu
        name = self._cstr(cpu.d[1]).lower()
        found = self.localvars.pop(name, None) is not None or self.shell.env.pop(name, None) is not None
        cpu.d[0] = 0xFFFFFFFF if found else 0

    def f_FindVar(self):  #vers 1
        cpu = self.cpu
        cpu.d[0] = 0

    def f_DateToStr(self):  #vers 1
        cpu = self.cpu
        dt = cpu.d[1]
        b = self.bus
        days, mins, ticks = b.r32(dt), b.r32(dt + 4), b.r32(dt + 8)
        fmt = b.r8(dt + 12)
        y, m, d, wd = days_to_ymd(days)
        if fmt == 1:
            ds = f"{y % 100:02d}-{m:02d}-{d:02d}"
        elif fmt == 2:
            ds = f"{m:02d}-{d:02d}-{y % 100:02d}"
        elif fmt == 3:
            ds = f"{d:02d}-{m:02d}-{y % 100:02d}"
        else:
            ds = f"{d:02d}-{_MONTHS[m - 1]}-{y % 100:02d}"
        for off, val in ((14, _DAYS[wd]), (18, ds), (22, f"{mins // 60:02d}:{mins % 60:02d}:{ticks // 50:02d}")):
            p = b.r32(dt + off)
            if p:
                self.ex.put_cstr(p, val)
        cpu.d[0] = 0xFFFFFFFF

    def f_StrToDate(self):  #vers 1
        cpu = self.cpu
        dt, b = cpu.d[1], self.bus
        cpu.d[0] = 0
        ds = self._cstr(b.r32(dt + 18)) if b.r32(dt + 18) else ""
        ts = self._cstr(b.r32(dt + 22)) if b.r32(dt + 22) else ""
        fmt = b.r8(dt + 12)
        days = mins = ticks = 0
        if ds:
            p = ds.split("-")
            if len(p) != 3:
                return
            try:
                if p[1][:3].capitalize() in _MONTHS:
                    d, m, y = int(p[0]), _MONTHS.index(p[1][:3].capitalize()) + 1, int(p[2])
                else:
                    a, c, e = int(p[0]), int(p[1]), int(p[2])
                    d, m, y = {1: (e, c, a), 2: (c, a, e)}.get(fmt, (a, c, e))
            except ValueError:
                return
            y += 0 if y > 99 else (1900 if y >= 78 else 2000)
            days = ymd_to_days(y, m, d)
        if ts:
            try:
                t = [int(x) for x in ts.split(":")]
            except ValueError:
                return
            mins, ticks = t[0] * 60 + t[1], (t[2] if len(t) > 2 else 0) * 50
        b.w32(dt, days)
        b.w32(dt + 4, mins)
        b.w32(dt + 8, ticks)
        cpu.d[0] = 0xFFFFFFFF

    def f_VFWritef(self):  #vers 1
        cpu = self.cpu
        fmt = self._cstr(cpu.d[2])
        av = cpu.d[3]
        b = self.bus
        out = []
        i = 0

        def arg():
            nonlocal av
            v = b.r32(av)
            av += 4
            return v

        def bstr(p):
            p <<= 2
            return bytes(b.r8(p + 1 + j) for j in range(b.r8(p))).decode("latin-1")

        while i < len(fmt):
            c = fmt[i]
            i += 1
            if c == "*" and i < len(fmt):
                out.append({"n": "\n", "N": "\n", "e": "\x1b", "E": "\x1b", "t": "\t", "T": "\t"}.get(fmt[i], fmt[i]))
                i += 1
                continue
            if c != "%":
                out.append(c)
                continue
            k = fmt[i]
            i += 1
            w = 0
            if k.upper() in "TOXIUC" and i < len(fmt) and fmt[i] in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ" and k.upper() != "C":
                w = int(fmt[i], 36)
                i += 1
            ku = k.upper()
            if ku == "S":
                out.append(bstr(arg()))
            elif ku == "T":
                out.append(bstr(arg()).ljust(w))
            elif ku == "C":
                out.append(chr(arg() & 0xFF))
            elif ku == "N":
                v = arg()
                out.append(str(v - (1 << 32) if v >> 31 else v))
            elif ku == "I":
                v = arg()
                out.append(str(v - (1 << 32) if v >> 31 else v).rjust(w))
            elif ku == "U":
                out.append(str(arg()).rjust(w))
            elif ku == "O":
                out.append(format(arg(), "o").rjust(w, "0"))
            elif ku == "X":
                out.append(format(arg(), "X").rjust(w, "0"))
            else:
                out.append("%" + k)
        cpu.d[0] = self._write(self._h(cpu.d[1]), "".join(out).encode("latin-1", "replace"))


DOSTRUE_ = 0xFFFFFFFF
