#this belongs in apps/core/doslib.py - Version: 1
# X-Seti - November 17 2026 - Morosa - Morosa dos.library.

"""
Morosa dos.library - files, locks, streams, ReadArgs and segment loading mapped onto host files.
"""

##Methods list -
# Dos
# Dos._abs
# Dos._cstr
# Dos._fill_fib
# Dos._h
# Dos._read
# Dos._write
# Dos.args_parse
# Dos.f_AddPart
# Dos.f_AllocDosObject
# Dos.f_CheckSignal
# Dos.f_Cli
# Dos.f_Close
# Dos.f_CreateDir
# Dos.f_CurrentDir
# Dos.f_DateStamp
# Dos.f_Delay
# Dos.f_DeleteFile
# Dos.f_DupLock
# Dos.f_GetProgramDir
# Dos.f_DupLockFromFH
# Dos.f_ExamineFH
# Dos.f_ExNext
# Dos.f_Examine
# Dos.f_Exit
# Dos.f_FGetC
# Dos.f_FGets
# Dos.f_FPutC
# Dos.f_FPuts
# Dos.f_FRead
# Dos.f_FWrite
# Dos.f_FilePart
# Dos.f_Flush
# Dos.f_FreeArgs
# Dos.f_FreeDosObject
# Dos.f_GetArgStr
# Dos.f_GetConsoleTask
# Dos.f_GetFileSysTask
# Dos.f_GetProgramName
# Dos.f_Input
# Dos.f_IoErr
# Dos.f_IsFileSystem
# Dos.f_IsInteractive
# Dos.f_LoadSeg
# Dos.f_Lock
# Dos.f_MaxCli
# Dos.f_NameFromFH
# Dos.f_Open
# Dos.f_Output
# Dos.f_ParentDir
# Dos.f_PathPart
# Dos.f_PutStr
# Dos.f_Read
# Dos.f_ReadArgs
# Dos.f_Rename
# Dos.f_Seek
# Dos.f_SetFileSysTask
# Dos.f_SetIoErr
# Dos.f_SetVBuf
# Dos.f_StrToLong
# Dos.f_UnGetC
# Dos.f_UnLoadSeg
# Dos.f_UnLock
# Dos.f_VFPrintf
# Dos.f_VPrintf
# Dos.f_WaitForChar
# Dos.f_Write
# Dos.f_WriteChars
# Dos.host
# Dos.new_handle
# Dos.new_lock
# Dos.set_err

import os
import re
import sys
import time

from apps.core import hunk as morosa_hunk
from apps.core.doslist import DosList
from apps.core.dosmatch import DosMatch
from apps.core.dosvars import DosVars
from apps.core.exec import Unimplemented

ST_USERDIR, ST_FILE = 2, -3
DOSTRUE = 0xFFFFFFFF
EPOCH_OFFSET = 252460800  # seconds from 1970-01-01 to 1978-01-01


class _Handle:
    def __init__(self, kind, f=None, path=""):
        self.kind, self.f, self.path, self.unget = kind, f, path, []
        self.apath = path


class Dos(DosList, DosMatch, DosVars):
    """dos.library functions; f_<Name> reads registers from the CPU."""

    def __init__(self, machine, shell, out=None, inp=None):  #vers 1
        self.m = machine
        self.cpu = machine.cpu
        self.bus = machine.bus
        self.ex = machine.exec
        self.shell = shell
        self.out = out or (lambda b: sys.stdout.buffer.write(b) or sys.stdout.flush())
        self.inp = inp or (lambda: sys.stdin.buffer.readline())
        self.handles = {}
        self.conbuf = []
        self.locks = {}
        self.iters = {}
        self.rdargs = {}
        self.matches = {}
        self.devport = 0
        self.ports = {}
        self.dlist = []
        self.dltype = {}
        self.dlhead = 0
        self.devprocs = set()
        self.localvars = {}
        self.cur = None
        self.args = ""
        self.progname = ""
        self.progdir = ""
        self.sleep = time.sleep
        self.stdin = self.new_handle(_Handle("con"))
        self.stdout = self.new_handle(_Handle("con"))
        self.cur = self.new_lock("sys:")

    # ---- helpers ----
    def new_handle(self, h: _Handle) -> int:  #vers 1
        a = self.ex.alloc(44)
        if h.kind == "con":
            h.unget = self.conbuf
        self.bus.w32(a + 36, id(h) & 0xFFFFFFFF)
        self.handles[a >> 2] = h
        return a >> 2

    def new_lock(self, path: str) -> int:  #vers 1
        a = self.ex.alloc(20)
        self.locks[a >> 2] = path
        return a >> 2

    def set_err(self, n: int) -> None:  #vers 1
        self.bus.w32(self.m.process + 148, n)

    def host(self, name: str) -> str:  #vers 1
        """Host path for an Amiga name; relative names follow the current lock."""
        if name.lower() in ("nil:", "*", "console:"):
            return os.devnull
        return self.shell.to_host(self._abs(name))

    def _h(self, bptr):  #vers 1
        return self.handles.get(bptr)

    def _write(self, h, data: bytes) -> int:  #vers 2
        if h.kind == "con":
            self.out(data)
            if b"\x9b0 q" in data or b"\x1b[0 q" in data:
                self.conbuf.extend(b"\x9b1;1;24;80 r")
        elif h.kind == "nil":
            pass
        else:
            h.f.write(data)
        return len(data)

    def _read(self, h, n: int) -> bytes:  #vers 1
        if h.kind == "con":
            if not h.unget:
                h.unget.extend(self.inp())
            out = bytes(h.unget[:n])
            del h.unget[:n]
            return out
        if h.kind == "nil":
            return b""
        out = bytes(h.unget[:n])
        del h.unget[:n]
        if len(out) < n:
            out += h.f.read(n - len(out))
        return out

    def _cstr(self, a):  #vers 1
        return self.ex.cstr(a)

    # ---- files ----
    def f_Open(self):  #vers 1
        cpu = self.cpu
        name, mode = self._cstr(cpu.d[1]), cpu.d[2]
        if name.lower() in ("*", "console:") or name.lower().startswith("con:") or name.lower().startswith("raw:"):
            cpu.d[0] = self.new_handle(_Handle("con"))
            return
        if name.lower() == "nil:":
            cpu.d[0] = self.new_handle(_Handle("nil"))
            return
        path = self.host(name)
        try:
            if mode == 1005:
                f = open(path, "rb")
            elif mode == 1006:
                f = open(path, "w+b")
            else:
                f = open(path, "r+b") if os.path.exists(path) else open(path, "w+b")
        except FileNotFoundError:
            self.set_err(205)
            cpu.d[0] = 0
            return
        except IsADirectoryError:
            self.set_err(212)
            cpu.d[0] = 0
            return
        except OSError:
            self.set_err(202)
            cpu.d[0] = 0
            return
        h = _Handle("file", f, path)
        h.apath = self._abs(name)
        cpu.d[0] = self.new_handle(h)
        self.bus.w32((cpu.d[0] << 2) + 8, self.port_for(h.apath))
        self.bus.w32((cpu.d[0] << 2) + 36, cpu.d[0])

    def f_Close(self):  #vers 1
        cpu = self.cpu
        b = cpu.d[1]
        h = self.handles.pop(b, None)
        if h is None:
            cpu.d[0] = 0
            return
        if h.f:
            h.f.close()
        self.ex.free(b << 2, 44)
        cpu.d[0] = DOSTRUE

    def f_Read(self):  #vers 1
        cpu = self.cpu
        h = self._h(cpu.d[1])
        if h is None:
            cpu.d[0] = 0xFFFFFFFF
            return
        data = self._read(h, cpu.d[3])
        for i, c in enumerate(data):
            self.bus.w8(cpu.d[2] + i, c)
        cpu.d[0] = len(data)

    def f_Write(self):  #vers 1
        cpu = self.cpu
        h = self._h(cpu.d[1])
        if h is None:
            cpu.d[0] = 0xFFFFFFFF
            return
        data = bytes(self.bus.r8(cpu.d[2] + i) for i in range(cpu.d[3]))
        cpu.d[0] = self._write(h, data)

    def f_Seek(self):  #vers 1
        cpu = self.cpu
        h = self._h(cpu.d[1])
        if h is None or h.kind != "file":
            self.set_err(219)
            cpu.d[0] = 0xFFFFFFFF
            return
        old = h.f.tell() - len(h.unget)
        h.unget = []
        pos, mode = cpu.d[2], cpu.d[3]
        pos = pos - (1 << 32) if pos >> 31 else pos
        mode = mode - (1 << 32) if mode >> 31 else mode
        h.f.seek(pos, {-1: 0, 0: 1, 1: 2}.get(mode, 0))
        cpu.d[0] = old

    def f_Input(self):  #vers 1
        self.cpu.d[0] = self.stdin

    def f_Output(self):  #vers 1
        self.cpu.d[0] = self.stdout

    def f_IsInteractive(self):  #vers 1
        h = self._h(self.cpu.d[1])
        self.cpu.d[0] = DOSTRUE if h is not None and h.kind == "con" else 0

    def f_SetVBuf(self):  #vers 1
        self.cpu.d[0] = 0

    def f_FWrite(self):  #vers 1
        cpu = self.cpu
        h = self._h(cpu.d[1])
        n = cpu.d[3] * cpu.d[4]
        self._write(h, bytes(self.bus.r8(cpu.d[2] + i) for i in range(n)))
        cpu.d[0] = cpu.d[4]

    def f_FRead(self):  #vers 1
        cpu = self.cpu
        h = self._h(cpu.d[1])
        size, num = cpu.d[3], cpu.d[4]
        data = self._read(h, size * num)
        whole = len(data) // size if size else 0
        for i, c in enumerate(data[: whole * size]):
            self.bus.w8(cpu.d[2] + i, c)
        cpu.d[0] = whole

    def f_Flush(self):  #vers 1
        self.cpu.d[0] = DOSTRUE

    def f_WaitForChar(self):  #vers 1
        self.cpu.d[0] = DOSTRUE

    def f_IoErr(self):  #vers 1
        self.cpu.d[0] = self.bus.r32(self.m.process + 148)

    def f_SetIoErr(self):  #vers 1
        old = self.bus.r32(self.m.process + 148)
        self.set_err(self.cpu.d[1])
        self.cpu.d[0] = old

    def f_Delay(self):  #vers 1
        self.sleep(self.cpu.d[1] / 50.0)

    def f_Exit(self):  #vers 1
        self.m.finish(self.cpu.d[1])

    def f_DeleteFile(self):  #vers 1
        cpu = self.cpu
        p = self.host(self._cstr(cpu.d[1]))
        try:
            os.rmdir(p) if os.path.isdir(p) else os.remove(p)
            cpu.d[0] = DOSTRUE
        except FileNotFoundError:
            self.set_err(205)
            cpu.d[0] = 0
        except OSError:
            self.set_err(216)
            cpu.d[0] = 0

    def f_Rename(self):  #vers 1
        cpu = self.cpu
        try:
            os.rename(self.host(self._cstr(cpu.d[1])), self.host(self._cstr(cpu.d[2])))
            cpu.d[0] = DOSTRUE
        except OSError:
            self.set_err(205)
            cpu.d[0] = 0

    def f_CreateDir(self):  #vers 1
        cpu = self.cpu
        name = self._cstr(cpu.d[1])
        p = self.host(name)
        if os.path.exists(p):
            self.set_err(203)
            cpu.d[0] = 0
            return
        try:
            os.mkdir(p)
        except OSError:
            self.set_err(205)
            cpu.d[0] = 0
            return
        cpu.d[0] = self.new_lock(self._abs(name))

    def _abs(self, name: str) -> str:  #vers 1
        """Full path of a name relative to the current directory lock."""
        if ":" in name:
            return name
        base = self.locks.get(self.cur, "sys:")
        if name.startswith("/"):
            return base.rstrip("/") + name
        return base + ("" if base.endswith((":", "/")) else "/") + name

    # ---- locks ----
    def f_Lock(self):  #vers 1
        cpu = self.cpu
        name = self._cstr(cpu.d[1])
        if not os.path.exists(self.host(name)):
            self.set_err(205)
            cpu.d[0] = 0
            return
        cpu.d[0] = self.new_lock(self._abs(name))

    def f_UnLock(self):  #vers 1
        b = self.cpu.d[1]
        if b in self.locks and b != self.cur:
            del self.locks[b]
            self.ex.free(b << 2, 20)

    def f_DupLock(self):  #vers 1
        b = self.cpu.d[1]
        self.cpu.d[0] = self.new_lock(self.locks[b]) if b in self.locks else 0

    def f_GetProgramDir(self):  #vers 1
        self.cpu.d[0] = self.new_lock(self.progdir) if self.progdir else 0

    def f_DupLockFromFH(self):  #vers 1
        h = self._h(self.cpu.d[1])
        self.cpu.d[0] = self.new_lock(h.apath) if h is not None and h.kind == "file" else 0

    def f_ExamineFH(self):  #vers 1
        cpu = self.cpu
        h = self._h(cpu.d[1])
        if h is None or h.kind != "file":
            self.set_err(212)
            cpu.d[0] = 0
            return
        self._fill_fib(cpu.d[2], h.path, os.path.basename(h.apath), False)
        cpu.d[0] = DOSTRUE

    def f_CurrentDir(self):  #vers 1
        old = self.cur
        self.cur = self.cpu.d[1] if self.cpu.d[1] in self.locks else self.cur
        self.cpu.d[0] = old

    def f_ParentDir(self):  #vers 1
        cpu = self.cpu
        p = self.locks.get(cpu.d[1])
        if p is None:
            cpu.d[0] = 0
            return
        if p.endswith(":"):
            cpu.d[0] = 0
            return
        q = p.rstrip("/")
        head = q.rsplit("/", 1)[0] if "/" in q else q.split(":", 1)[0] + ":"
        cpu.d[0] = self.new_lock(head)

    def f_Examine(self):  #vers 1
        cpu = self.cpu
        p = self.locks.get(cpu.d[1])
        fib = cpu.d[2]
        if p is None:
            cpu.d[0] = 0
            return
        h = self.host(p)
        self._fill_fib(fib, h, p.rstrip("/").rsplit("/", 1)[-1].rsplit(":", 1)[-1] or p.rstrip(":"), True)
        self.iters[fib] = sorted(os.listdir(h), key=str.lower) if os.path.isdir(h) else []
        cpu.d[0] = DOSTRUE

    def f_ExNext(self):  #vers 1
        cpu = self.cpu
        fib = cpu.d[2]
        it = self.iters.get(fib)
        if not it:
            self.set_err(232)
            cpu.d[0] = 0
            return
        name = it.pop(0)
        lockpath = self.locks[cpu.d[1]]
        self._fill_fib(fib, os.path.join(self.host(lockpath), name), name, False)
        cpu.d[0] = DOSTRUE

    def _fill_fib(self, fib: int, host: str, name: str, is_lock: bool) -> None:  #vers 1
        b = self.bus
        for i in range(0, 260, 4):
            b.w32(fib + i, 0)
        st = os.stat(host)
        isdir = os.path.isdir(host)
        b.w32(fib + 4, ST_USERDIR if isdir else ST_FILE)
        b.w32(fib + 120, ST_USERDIR if isdir else ST_FILE)
        self.ex.put_cstr(fib + 8, name[:106])
        b.w32(fib + 124, 0 if isdir else st.st_size)
        b.w32(fib + 128, (st.st_size + 511) // 512)
        secs = max(0, int(st.st_mtime) - EPOCH_OFFSET)
        b.w32(fib + 132, secs // 86400)
        b.w32(fib + 136, secs % 86400 // 60)
        b.w32(fib + 140, secs % 60 * 50)

    def f_DateStamp(self):  #vers 1
        a = self.cpu.d[1]
        secs = max(0, int(time.time()) - EPOCH_OFFSET)
        self.bus.w32(a, secs // 86400)
        self.bus.w32(a + 4, secs % 86400 // 60)
        self.bus.w32(a + 8, secs % 60 * 50)
        self.cpu.d[0] = a

    # ---- strings and streams ----
    def f_PutStr(self):  #vers 1
        cpu = self.cpu
        self._write(self._h(self.stdout), self._cstr(cpu.d[1]).encode("latin-1"))
        cpu.d[0] = 0

    def f_WriteChars(self):  #vers 1
        cpu = self.cpu
        s = bytes(self.bus.r8(cpu.d[1] + i) for i in range(cpu.d[2]))
        cpu.d[0] = self._write(self._h(self.stdout), s)

    def f_FPuts(self):  #vers 1
        cpu = self.cpu
        h = self._h(cpu.d[1])
        self._write(h, self._cstr(cpu.d[2]).encode("latin-1"))
        cpu.d[0] = 0

    def f_FPutC(self):  #vers 1
        cpu = self.cpu
        self._write(self._h(cpu.d[1]), bytes([cpu.d[2] & 0xFF]))
        cpu.d[0] = cpu.d[2] & 0xFF

    def f_FGetC(self):  #vers 1
        cpu = self.cpu
        d = self._read(self._h(cpu.d[1]), 1)
        cpu.d[0] = d[0] if d else 0xFFFFFFFF

    def f_UnGetC(self):  #vers 1
        cpu = self.cpu
        h = self._h(cpu.d[1])
        if cpu.d[2] != 0xFFFFFFFF:
            h.unget.insert(0, cpu.d[2] & 0xFF)
        cpu.d[0] = cpu.d[2]

    def f_FGets(self):  #vers 1
        cpu = self.cpu
        h = self._h(cpu.d[1])
        buf, n = cpu.d[2], cpu.d[3]
        out = bytearray()
        while len(out) < n - 1:
            c = self._read(h, 1)
            if not c:
                break
            out += c
            if c == b"\n":
                break
        if not out:
            cpu.d[0] = 0
            return
        for i, c in enumerate(out):
            self.bus.w8(buf + i, c)
        self.bus.w8(buf + len(out), 0)
        cpu.d[0] = buf

    def f_VFPrintf(self):  #vers 1
        cpu = self.cpu
        out, _ = self.ex.format(cpu.d[2], cpu.d[3])
        cpu.d[0] = self._write(self._h(cpu.d[1]), bytes(out[:-1]))

    def f_VPrintf(self):  #vers 1
        cpu = self.cpu
        out, _ = self.ex.format(cpu.d[1], cpu.d[2])
        cpu.d[0] = self._write(self._h(self.stdout), bytes(out[:-1]))

    def f_StrToLong(self):  #vers 1
        cpu = self.cpu
        s = self._cstr(cpu.d[1])
        m = re.match(r"\s*([+-]?\d+)", s)
        if not m:
            cpu.d[0] = 0xFFFFFFFF
            return
        self.bus.w32(cpu.d[2], int(m.group(1)) & 0xFFFFFFFF)
        cpu.d[0] = m.end()

    def f_FilePart(self):  #vers 1
        cpu = self.cpu
        s = self._cstr(cpu.d[1])
        i = max(s.rfind("/"), s.rfind(":")) + 1
        cpu.d[0] = cpu.d[1] + i

    def f_PathPart(self):  #vers 1
        cpu = self.cpu
        s = self._cstr(cpu.d[1])
        i = s.rfind("/")
        if i < 0:
            i = s.rfind(":") + 1
        cpu.d[0] = cpu.d[1] + i

    def f_AddPart(self):  #vers 1
        cpu = self.cpu
        d, f = self._cstr(cpu.d[1]), self._cstr(cpu.d[2])
        if ":" in f:
            r = f
        elif not d or d.endswith((":", "/")):
            r = d + f
        else:
            r = d + "/" + f
        if len(r) + 1 > cpu.d[3]:
            cpu.d[0] = 0
            return
        self.ex.put_cstr(cpu.d[1], r)
        cpu.d[0] = DOSTRUE

    # ---- process info ----
    def f_Cli(self):  #vers 1
        self.cpu.d[0] = self.m.cli << 2 if self.m.cli else 0

    def f_GetArgStr(self):  #vers 1
        self.cpu.d[0] = self.m.argptr

    def f_GetProgramName(self):  #vers 1
        cpu = self.cpu
        name = self.progname[: max(0, cpu.d[2] - 1)]
        self.ex.put_cstr(cpu.d[1], name)
        cpu.d[0] = DOSTRUE

    def f_AllocDosObject(self):  #vers 1
        cpu = self.cpu
        sizes = {0: 44, 1: 20, 2: 260, 3: 8, 4: 8, 5: 32, 6: 64}
        cpu.d[0] = self.ex.alloc(sizes.get(cpu.d[1], 0)) if cpu.d[1] in sizes else 0

    def f_FreeDosObject(self):  #vers 1
        cpu = self.cpu
        sizes = {0: 44, 1: 20, 2: 260, 3: 8, 4: 8, 5: 32, 6: 64}
        if cpu.d[2] and cpu.d[1] in sizes:
            self.ex.free(cpu.d[2], sizes[cpu.d[1]])

    # ---- segments ----
    def f_LoadSeg(self):  #vers 1
        cpu = self.cpu
        path = self.host(self._cstr(cpu.d[1]))
        try:
            data = open(path, "rb").read()
        except OSError:
            self.set_err(205)
            cpu.d[0] = 0
            return
        try:
            bptr, segs = morosa_hunk.load(data, self.bus, lambda n: self.ex.alloc(n))
        except morosa_hunk.HunkError:
            self.set_err(218)
            cpu.d[0] = 0
            return
        cpu.d[0] = bptr

    def f_UnLoadSeg(self):  #vers 1
        pass

    def f_CheckSignal(self):  #vers 1
        self.cpu.d[0] = 0

    def f_IsFileSystem(self):  #vers 1
        self.cpu.d[0] = 0 if self._cstr(self.cpu.d[1]).lower() in ("nil:", "con:", "raw:", "*") else 0xFFFFFFFF

    def f_SetFileSysTask(self):  #vers 1
        self.cpu.d[0] = 0

    def f_NameFromFH(self):  #vers 1
        cpu = self.cpu
        h = self._h(cpu.d[1])
        if h is None or len(h.apath) + 1 > cpu.d[3]:
            cpu.d[0] = 0
            return
        self.ex.put_cstr(cpu.d[2], h.apath if h.kind == "file" else "CON:")
        cpu.d[0] = DOSTRUE

    def f_MaxCli(self):  #vers 1
        self.cpu.d[0] = 1

    def f_GetConsoleTask(self):  #vers 1
        self.cpu.d[0] = 0

    def f_GetFileSysTask(self):  #vers 1
        self.cpu.d[0] = 0

    # ---- ReadArgs ----
    def args_parse(self, template: str, line: str):  #vers 1
        """(values, error) for a ReadArgs template; values hold python data per item."""
        items = []
        for raw in template.split(","):
            parts = raw.strip().split("/")
            names = [n.lower() for n in parts[0].split("=")]
            flags = set(p.upper() for p in parts[1:] if p)
            if not names[0] and not names[1:]:
                return None, 114
            items.append((names, flags))
        toks = []
        i = 0
        s = line.rstrip("\n")
        while i < len(s):
            if s[i] in " \t":
                i += 1
                continue
            start = i
            if s[i] == '"':
                i += 1
                t = ""
                while i < len(s) and s[i] != '"':
                    if s[i] == "*" and i + 1 < len(s):
                        i += 1
                        t += {"n": "\n", "e": "\x1b", "N": "\n", "E": "\x1b"}.get(s[i], s[i])
                    else:
                        t += s[i]
                    i += 1
                if i >= len(s):
                    return None, 119
                i += 1
                toks.append((t, True, start))
            else:
                while i < len(s) and s[i] not in " \t":
                    i += 1
                toks.append((s[start:i], False, start))
        vals = [None] * len(items)
        for k, (names, fl) in enumerate(items):
            if "S" in fl:
                vals[k] = 0
            elif "M" in fl:
                vals[k] = []
        pos = []
        j = 0
        used = [False] * len(toks)
        # keyword pass
        for ti, (t, quoted, st) in enumerate(toks):
            if quoted:
                continue
            tl = t.lower()
            for k, (names, fl) in enumerate(items):
                if "F" in fl and "K" not in fl:
                    continue
                kw = tl.split("=", 1)[0] if "=" in tl and "S" not in fl else tl
                if kw in names:
                    if "S" in fl:
                        vals[k] = 1
                        used[ti] = True
                    elif "=" in tl:
                        vals[k] = t.split("=", 1)[1]
                        used[ti] = True
                    elif ti + 1 < len(toks) and not used[ti + 1]:
                        if "M" in fl:
                            vals[k].append(toks[ti + 1][0])
                        else:
                            vals[k] = toks[ti + 1][0]
                        used[ti] = used[ti + 1] = True
                    else:
                        return None, 117
                    break
        rest = [ti for ti in range(len(toks)) if not used[ti]]
        order = [k for k, (n, fl) in enumerate(items) if "K" not in fl and "S" not in fl]
        ri = 0
        for k in order:
            names, fl = items[k]
            if vals[k] is not None and vals[k] != []:
                continue
            if ri >= len(rest):
                break
            if "F" in fl:
                st = toks[rest[ri]][2]
                vals[k] = s[st:].strip()
                ri = len(rest)
                break
            if "M" in fl:
                reserve = sum(1 for k2 in order if k2 > k and "A" in items[k2][1] and vals[k2] is None)
                take = max(len(rest) - ri - reserve, 1 if "A" in fl else 0)
                vals[k] = [toks[t][0] for t in rest[ri:ri + take]]
                ri += take
                continue
            vals[k] = toks[rest[ri]][0]
            ri += 1
        if ri < len(rest):
            return None, 118
        for k, (names, fl) in enumerate(items):
            if "A" in fl and (vals[k] is None or vals[k] == []):
                return None, 116
            if "N" in fl and vals[k] is not None:
                try:
                    if isinstance(vals[k], list):
                        vals[k] = [int(v) for v in vals[k]]
                    else:
                        vals[k] = int(vals[k])
                except ValueError:
                    return None, 115
        return (items, vals), 0

    def f_ReadArgs(self):  #vers 1
        cpu = self.cpu
        template = self._cstr(cpu.d[1])
        arr = cpu.d[2]
        line = self._cstr(self.m.argptr) if not cpu.d[3] else ""
        res, err = self.args_parse(template, line)
        if res is None:
            self.set_err(err)
            cpu.d[0] = 0
            return
        items, vals = res
        mem = []
        for k, (names, fl) in enumerate(items):
            v = vals[k]
            if "S" in fl:
                out = 1 if v else 0
            elif v is None or v == []:
                out = 0
            elif "M" in fl:
                ptrs = self.ex.alloc(4 * (len(v) + 1))
                mem.append((ptrs, 4 * (len(v) + 1)))
                for q, e in enumerate(v):
                    if "N" in fl:
                        ea = self.ex.alloc(8)
                        self.bus.w32(ea, e & 0xFFFFFFFF)
                    else:
                        ea = self.ex.alloc(len(e) + 8)
                        self.ex.put_cstr(ea, e)
                    mem.append((ea, 8 if "N" in fl else len(e) + 8))
                    self.bus.w32(ptrs + 4 * q, ea)
                out = ptrs
            elif "N" in fl:
                ea = self.ex.alloc(8)
                self.bus.w32(ea, v & 0xFFFFFFFF)
                mem.append((ea, 8))
                out = ea
            else:
                ea = self.ex.alloc(len(v) + 8)
                self.ex.put_cstr(ea, v)
                mem.append((ea, len(v) + 8))
                out = ea
            self.bus.w32(arr + 4 * k, out)
        rd = self.ex.alloc(32)
        self.rdargs[rd] = mem
        cpu.d[0] = rd

    def f_FreeArgs(self):  #vers 1
        rd = self.cpu.d[1]
        for a, n in self.rdargs.pop(rd, []):
            self.ex.free(a, n)
        if rd:
            self.ex.free(rd, 32)
