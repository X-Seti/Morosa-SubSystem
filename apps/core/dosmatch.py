#this belongs in apps/core/dosmatch.py - Version: 1
# X-Seti - November 17 2026 - Morosa - Morosa dos.library Patterns and Commands.

"""
Morosa dos.library patterns and commands - MatchFirst walk, pattern matching, volume info, running programs.
"""

##Methods list -
# DosMatch
# DosMatch._anchor_next
# DosMatch.expand
# DosMatch.f_Execute
# DosMatch.f_FindArg
# DosMatch.f_FindSegment
# DosMatch.f_FreeDeviceProc
# DosMatch.f_GetCurrentDirName
# DosMatch.f_GetDeviceProc
# DosMatch.f_GetPrompt
# DosMatch.f_Info
# DosMatch.f_MatchEnd
# DosMatch.f_MatchFirst
# DosMatch.f_MatchNext
# DosMatch.f_MatchPattern
# DosMatch.f_NameFromLock
# DosMatch.f_ParsePattern
# DosMatch.f_RunCommand
# DosMatch.f_SelectInput
# DosMatch.f_SelectOutput
# DosMatch.f_SetMode
# DosMatch.f_SetProtection
# DosMatch.f_SystemTagList
# DosMatch.lock_for

import os
import re
import shutil

from apps.methods.shell import pattern_regex

WILD = set("#?()|~[]%'")
APF_ITSWILD, APF_DODIR, APF_DIDDIR = 2, 4, 8
TRUE = 0xFFFFFFFF


class DosMatch:
    """Mixed into Dos: pattern walking, volume info and program running."""

    def expand(self, pat: str):  #vers 1
        """Amiga paths matching pat, one level of wildcards per component, sorted."""
        if ":" in pat:
            vol, rest = pat.split(":", 1)
            heads = [vol + ":"]
        else:
            base = self.locks.get(self.cur, "sys:")
            heads, rest = [base if base.endswith((":", "/")) else base + "/"], pat
        parts = [p for p in rest.split("/")]
        for k, p in enumerate(parts):
            last = k == len(parts) - 1
            nxt = []
            for h in heads:
                if p == "":
                    nxt.append(h)
                    continue
                if not (set(p) & WILD):
                    full = h + p
                    if os.path.exists(self.host(full)):
                        nxt.append(full + ("" if last else "/"))
                    continue
                d = self.host(h if h.endswith(":") else h.rstrip("/") or h)
                if not os.path.isdir(d):
                    continue
                rx = pattern_regex(p)
                for n in sorted(os.listdir(d), key=str.lower):
                    if rx.fullmatch(n):
                        full = h + n
                        if last or os.path.isdir(self.host(full)):
                            nxt.append(full + ("" if last else "/"))
            heads = nxt
        return heads

    def _anchor_next(self, ap: int):  #vers 4
        b = self.bus
        st = self.matches.get(ap)
        if st is None:
            self.set_err(232)
            return 0
        flags = b.r8(ap + 16)
        if st["last_dir"] is not None and flags & APF_DODIR:
            d = st["last_dir"]
            h = self.host(d)
            kids = [d + ("" if d.endswith((":", "/")) else "/") + n for n in sorted(os.listdir(h), key=str.lower)]
            st["q"][0:0] = kids + [("end", d)]
            b.w8(ap + 16, b.r8(ap + 16) & ~APF_DODIR)
        st["last_dir"] = None
        if not st["q"]:
            self.set_err(232)
            return 0
        item = st["q"].pop(0)
        end = False
        if isinstance(item, tuple):
            item, end = item[1], True
        h = self.host(item)
        name = item.rstrip("/").rsplit("/", 1)[-1].rsplit(":", 1)[-1] or item
        try:
            self._fill_fib(ap + 20, h, name, False)
        except OSError:
            return self._anchor_next(ap)
        fl = b.r8(ap + 16)
        b.w8(ap + 16, (fl | APF_DIDDIR) if end else (fl & ~APF_DIDDIR))
        chain = b.r32(ap)
        if chain:
            self._fill_fib(chain + 12, h, name, False)
            q = self._abs(item).rstrip("/")
            par = q.rsplit("/", 1)[0] if "/" in q else q.split(":", 1)[0] + ":"
            b.w32(chain + 8, self.lock_for(par if par.endswith(":") or "/" in par or ":" in par else par + ":"))
        room = b.r16(ap + 18)
        if room:
            self.ex.put_cstr(ap + 280, item[: room - 1])
        isdir = os.path.isdir(h)
        if isdir and not end:
            st["last_dir"] = item
        return TRUE

    def f_MatchFirst(self):  #vers 1
        cpu = self.cpu
        pat, ap = self._cstr(cpu.d[1]), cpu.d[2]
        wild = bool(set(pat) & WILD)
        found = self.expand(pat) if wild else ([pat] if os.path.exists(self.host(pat)) else [])
        b = self.bus
        b.w8(ap + 16, (b.r8(ap + 16) & ~APF_ITSWILD & ~APF_DIDDIR) | (APF_ITSWILD if wild else 0))
        if not b.r32(ap):
            chain = self.ex.alloc(0x120)
            b.w32(ap, chain)
            b.w32(ap + 4, chain)
        self.matches[ap] = {"q": [f.rstrip("/") if not f.endswith(":") else f for f in found], "last_dir": None}
        if not found:
            self.set_err(232 if wild else 205)
            cpu.d[0] = 232 if wild else 205
            return
        self._anchor_next(ap)
        cpu.d[0] = 0

    def f_MatchNext(self):  #vers 1
        cpu = self.cpu
        ok = self._anchor_next(cpu.d[1])
        cpu.d[0] = 0 if ok else 232

    def lock_for(self, path: str) -> int:  #vers 1
        """A shared lock for a path, created on first use."""
        for k, v in self.locks.items():
            if v == path:
                return k
        return self.new_lock(path)

    def f_MatchEnd(self):  #vers 1
        ap = self.cpu.d[1]
        self.matches.pop(ap, None)
        chain = self.bus.r32(ap)
        if chain:
            self.ex.free(chain, 0x120)
            self.bus.w32(ap, 0)
            self.bus.w32(ap + 4, 0)

    def f_ParsePattern(self):  #vers 1
        cpu = self.cpu
        s = self._cstr(cpu.d[1])
        if len(s) + 2 > cpu.d[3]:
            cpu.d[0] = 0xFFFFFFFF
            return
        self.ex.put_cstr(cpu.d[2], s)
        cpu.d[0] = 1 if set(s) & WILD else 0

    f_ParsePatternNoCase = f_ParsePattern

    def f_MatchPattern(self):  #vers 1
        cpu = self.cpu
        rx = pattern_regex(self._cstr(cpu.d[1]))
        cpu.d[0] = TRUE if rx.fullmatch(self._cstr(cpu.d[2])) else 0

    f_MatchPatternNoCase = f_MatchPattern

    def f_FindArg(self):  #vers 1
        cpu = self.cpu
        tmpl, kw = self._cstr(cpu.d[1]).lower(), self._cstr(cpu.d[2]).lower()
        for i, item in enumerate(tmpl.split(",")):
            if kw in item.split("/")[0].split("="):
                cpu.d[0] = i
                return
        cpu.d[0] = 0xFFFFFFFF

    # ---- locks, volumes, misc ----
    def f_NameFromLock(self):  #vers 1
        cpu = self.cpu
        p = self.locks.get(cpu.d[1])
        if p is None or len(p) + 1 > cpu.d[3]:
            cpu.d[0] = 0
            return
        self.ex.put_cstr(cpu.d[2], p)
        cpu.d[0] = TRUE

    def f_GetCurrentDirName(self):  #vers 1
        cpu = self.cpu
        self.ex.put_cstr(cpu.d[1], self.locks.get(self.cur, "sys:")[: max(0, cpu.d[2] - 1)])
        cpu.d[0] = TRUE

    def f_GetDeviceProc(self):  #vers 1
        cpu = self.cpu
        name = self._cstr(cpu.d[1])
        if cpu.d[2]:
            self.set_err(232)
            cpu.d[0] = 0
            return
        vol = name.split(":", 1)[0] if ":" in name else self.locks.get(self.cur, "sys:").split(":", 1)[0]
        if not os.path.isdir(self.host(vol + ":")):
            self.set_err(205)
            cpu.d[0] = 0
            return
        if not self.devport:
            self.devport = self.ex.alloc(40)
        dp = self.ex.alloc(16)
        self.bus.w32(dp, self.devport)
        self.bus.w32(dp + 4, self.lock_for(vol + ":"))
        self.devprocs.add(dp)
        cpu.d[0] = dp

    def f_FreeDeviceProc(self):  #vers 1
        dp = self.cpu.d[1]
        if dp in self.devprocs:
            self.devprocs.discard(dp)
            self.ex.free(dp, 16)

    def f_GetPrompt(self):  #vers 1
        cpu = self.cpu
        self.ex.put_cstr(cpu.d[1], "%N> "[: max(0, cpu.d[2] - 1)])
        cpu.d[0] = TRUE

    def f_Info(self):  #vers 1
        cpu = self.cpu
        p = self.locks.get(cpu.d[1])
        if p is None:
            cpu.d[0] = 0
            return
        try:
            u = shutil.disk_usage(self.host(p))
        except OSError:
            cpu.d[0] = 0
            return
        b, a = self.bus, cpu.d[2]
        for i in range(0, 36, 4):
            b.w32(a + i, 0)
        b.w32(a + 8, 82)
        b.w32(a + 12, min(u.total // 512, 0x7FFFFFFF))
        b.w32(a + 16, min(u.used // 512, 0x7FFFFFFF))
        b.w32(a + 20, 512)
        b.w32(a + 24, 0x444F5301)
        cpu.d[0] = TRUE

    def f_SetProtection(self):  #vers 1
        self.cpu.d[0] = TRUE

    f_SetComment = f_SetProtection
    f_SetFileDate = f_SetProtection

    def f_SetMode(self):  #vers 1
        self.cpu.d[0] = TRUE

    def f_FindSegment(self):  #vers 1
        self.cpu.d[0] = 0

    def f_SelectInput(self):  #vers 1
        old, self.stdin = self.stdin, self.cpu.d[1]
        self.cpu.d[0] = old

    def f_SelectOutput(self):  #vers 1
        old, self.stdout = self.stdout, self.cpu.d[1]
        self.cpu.d[0] = old

    # ---- running programs ----
    def f_SystemTagList(self):  #vers 1
        cpu = self.cpu
        cpu.d[0] = self.m.system(self._cstr(cpu.d[1])) & 0xFFFFFFFF

    def f_Execute(self):  #vers 1
        cpu = self.cpu
        line = self._cstr(cpu.d[1])
        if line.strip():
            self.m.system(line)
        cpu.d[0] = TRUE

    def f_RunCommand(self):  #vers 1
        cpu = self.cpu
        seg, n, p = cpu.d[1], cpu.d[3], cpu.d[4]
        args = bytes(self.bus.r8(p + i) for i in range(n)).decode("latin-1").rstrip("\n")
        cpu.d[0] = self.m.run_seg(seg, args) & 0xFFFFFFFF
