#this belongs in apps/core/locale.py - Version: 1
# X-Seti - November 17 2026 - Morosa - Morosa locale.library.

"""
Morosa locale.library - the built-in English locale: character classes, strings, date formatting.
"""

##Methods list -
# LocaleLib
# LocaleLib._emit
# LocaleLib.f
# LocaleLib.f_CloseCatalog
# LocaleLib.f_CloseLocale
# LocaleLib.f_ConvToLower
# LocaleLib.f_ConvToUpper
# LocaleLib.f_FormatDate
# LocaleLib.f_FormatString
# LocaleLib.f_GetCatalogStr
# LocaleLib.f_GetLocaleStr
# LocaleLib.f_OpenCatalogA
# LocaleLib.f_OpenLocale
# LocaleLib.f_StrConvert
# LocaleLib.f_StrnCmp
# _mk
# strings

import datetime

from apps.core.utility import days_to_ymd

_DAYS = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")
_MONS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
         "November", "December")


def strings() -> dict:  #vers 1
    """GetLocaleStr numbers to the English text."""
    t = {}
    for i, d in enumerate(_DAYS):
        t[1 + i], t[8 + i] = d, d[:3]
    for i, m in enumerate(_MONS):
        t[15 + i], t[27 + i] = m, m[:3]
    t.update({39: "Yes", 40: "No", 41: "AM", 42: "PM", 43: "\xad", 44: "-", 45: "\"", 46: "\"", 47: "Yesterday",
              48: "Tomorrow", 49: "Today", 50: "Future"})
    return t


_CHARS = {
    "IsAlNum": lambda c: chr(c).isalnum(), "IsAlpha": lambda c: chr(c).isalpha(),
    "IsCntrl": lambda c: c < 32 or 127 <= c < 160, "IsDigit": lambda c: 48 <= c <= 57,
    "IsGraph": lambda c: 33 <= c <= 126 or c >= 161, "IsLower": lambda c: chr(c).islower(),
    "IsPrint": lambda c: 32 <= c <= 126 or c >= 160, "IsPunct": lambda c: 33 <= c <= 126 and not chr(c).isalnum(),
    "IsSpace": lambda c: c in (9, 10, 11, 12, 13, 32), "IsUpper": lambda c: chr(c).isupper(),
    "IsXDigit": lambda c: chr(c) in "0123456789abcdefABCDEF",
}


def _mk(fn):  #vers 1
    def f(self):
        self.cpu.d[0] = 0xFFFFFFFF if fn(self.cpu.d[0] & 0xFF) else 0
    return f


class LocaleLib:
    """locale.library functions."""

    def __init__(self, machine):  #vers 1
        self.m = machine
        self.cpu = machine.cpu
        self.bus = machine.bus
        self.ex = machine.exec
        self.str = strings()
        self.loc = 0

    def f_OpenLocale(self):  #vers 1
        cpu = self.cpu
        if not self.loc:
            p = self.ex.alloc(0x100)
            for off, text in ((0, "english"), (4, "english"), (72, "%A %e %B %Y %H:%M:%S"), (76, "%A %e %B %Y"),
                              (80, "%H:%M:%S"), (84, "%d-%b-%y %H:%M"), (88, "%d-%b-%y"), (92, "%H:%M"),
                              (96, "."), (100, ","), (104, ",")):
                s = self.ex.alloc(len(text) + 8)
                self.ex.put_cstr(s, text)
                self.bus.w32(p + off, s)
            g = self.ex.alloc(8)
            self.bus.w8(g, 3)
            self.bus.w32(p + 108, g)
            self.bus.w32(p + 112, g)
            self.bus.w32(p + 52, 0)
            self.loc = p
        cpu.d[0] = self.loc

    def f_CloseLocale(self):  #vers 1
        pass

    def f_OpenCatalogA(self):  #vers 1
        self.cpu.d[0] = 0

    def f_CloseCatalog(self):  #vers 1
        pass

    def f_GetCatalogStr(self):  #vers 1
        self.cpu.d[0] = self.cpu.a[1]

    def f_GetLocaleStr(self):  #vers 1
        cpu = self.cpu
        key = ("s", cpu.d[0])
        if key not in self.ex.m.strcache:
            text = self.str.get(cpu.d[0], "")
            a = self.ex.alloc(len(text) + 8)
            self.ex.put_cstr(a, text)
            self.ex.m.strcache[key] = a
        cpu.d[0] = self.ex.m.strcache[key]

    def f_ConvToUpper(self):  #vers 1
        c = self.cpu.d[0] & 0xFF
        self.cpu.d[0] = c - 32 if 97 <= c <= 122 or 0xE0 <= c <= 0xFE and c != 0xF7 else c

    def f_ConvToLower(self):  #vers 1
        c = self.cpu.d[0] & 0xFF
        self.cpu.d[0] = c + 32 if 65 <= c <= 90 or 0xC0 <= c <= 0xDE and c != 0xD7 else c

    def f_StrnCmp(self):  #vers 1
        cpu = self.cpu
        n = cpu.d[0]
        a, b = self.ex.cstr(cpu.a[1]), self.ex.cstr(cpu.a[2])
        a, b = (a[:n], b[:n]) if n != 0xFFFFFFFF else (a, b)
        if cpu.d[1] >= 2:
            a, b = a.lower(), b.lower()
        cpu.d[0] = ((a > b) - (a < b)) & 0xFFFFFFFF

    def f_StrConvert(self):  #vers 1
        cpu = self.cpu
        s = self.ex.cstr(cpu.a[1])
        out = s.lower() if cpu.d[1] in (2, 3) else s
        out = out[: max(0, cpu.d[0] - 1)] if cpu.d[0] != 0xFFFFFFFF else out
        self.ex.put_cstr(cpu.a[2], out)
        cpu.d[0] = len(out)

    def _emit(self, hook: int, text: str) -> None:  #vers 1
        entry = self.bus.r32(hook + 8)
        for ch in text.encode("latin-1", "replace") + b"\0":
            self.ex.call(entry, {}, {0: hook, 1: ch, 2: self.loc})

    def f_FormatString(self):  #vers 1
        cpu = self.cpu
        out, _ = self.ex.format(cpu.a[1], cpu.a[2])
        for ch in out:
            self.ex.call(self.bus.r32(cpu.a[3] + 8), {}, {0: cpu.a[3], 1: ch, 2: cpu.a[0]})
        cpu.d[0] = cpu.a[2]

    def f_FormatDate(self):  #vers 1
        cpu = self.cpu
        fmt = self.ex.cstr(cpu.a[1])
        days, mins, ticks = self.bus.r32(cpu.a[2]), self.bus.r32(cpu.a[2] + 4), self.bus.r32(cpu.a[2] + 8)
        y, m, d, wd = days_to_ymd(days)
        hh, mm, ss = mins // 60, mins % 60, ticks // 50
        yday = (datetime.date(y, m, d) - datetime.date(y, 1, 1)).days + 1
        subs = {
            "a": _DAYS[wd][:3], "A": _DAYS[wd], "b": _MONS[m - 1][:3], "B": _MONS[m - 1], "h": _MONS[m - 1][:3],
            "c": f"{_DAYS[wd][:3]} {_MONS[m - 1][:3]} {d:2d} {hh:02d}:{mm:02d}:{ss:02d} {y}", "C": "",
            "d": f"{d:02d}", "D": f"{m:02d}/{d:02d}/{y % 100:02d}", "e": f"{d:2d}", "H": f"{hh:02d}",
            "I": f"{(hh % 12) or 12:02d}", "j": f"{yday:03d}", "m": f"{m:02d}", "M": f"{mm:02d}", "n": "\n",
            "p": "AM" if hh < 12 else "PM", "q": f"{hh}", "Q": f"{(hh % 12) or 12}", "S": f"{ss:02d}", "t": "\t",
            "T": f"{hh:02d}:{mm:02d}:{ss:02d}", "U": f"{(yday + 6 - wd) // 7:02d}", "w": str(wd),
            "W": f"{(yday + 6 - (wd - 1) % 7) // 7:02d}", "x": f"{m:02d}/{d:02d}/{y % 100:02d}",
            "X": f"{hh:02d}:{mm:02d}:{ss:02d}", "y": f"{y % 100:02d}", "Y": str(y), "%": "%",
        }
        out, i = [], 0
        while i < len(fmt):
            if fmt[i] == "%" and i + 1 < len(fmt):
                i += 1
                out.append(subs.get(fmt[i], "%" + fmt[i]))
            else:
                out.append(fmt[i])
            i += 1
        if cpu.a[3]:
            entry = self.bus.r32(cpu.a[3] + 8)
            hook, loc = cpu.a[3], cpu.a[0]
            for ch in "".join(out).encode("latin-1", "replace") + b"\0":
                self.ex.call(entry, {}, {0: hook, 1: ch, 2: loc})
        cpu.d[0] = 0xFFFFFFFF


for _n, _f in _CHARS.items():
    setattr(LocaleLib, "f_" + _n, _mk(_f))
