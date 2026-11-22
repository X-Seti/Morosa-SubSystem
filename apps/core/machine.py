#this belongs in apps/core/machine.py - Version: 2
# X-Seti - November 17 2026 - Morosa - Morosa Machine.

"""
Morosa Machine - memory, CPU, ExecBase, libraries and a process; runs hunk executables natively.
"""

##Methods list -
# Guru
# Machine
# Machine._execbase
# Machine._finish_process
# Machine._guru
# Machine._hook
# Machine.add_library
# Machine.boot
# Machine.find_task
# Machine.finish
# Machine.load_disk_library
# Machine.make_process
# Machine.open_library
# Machine.run
# Machine.run_seg
# Machine.system
# Machine.wait_signals
# ProgramExit

import json
import os
import queue

from apps.core import hunk as morosa_hunk
from apps.core.cpu import CPU
from apps.methods.bus import Bus
from apps.core.devices import Timer
from apps.core.doslib import Dos
from apps.core.exec import Exec, Unimplemented
from apps.core.graphics import Graphics
from apps.core.icon import Icon
from apps.core.intuition import Intuition
from apps.core.locale import LocaleLib
from apps.core.utility import Util

TRACE = bool(os.environ.get("MOROSA_TRACE"))
_LVO = json.load(open(os.path.join(os.path.dirname(__file__), "lvo.json")))
_ATTN = {68010: 0x01, 68020: 0x03, 68030: 0x07, 68040: 0x0F, 68060: 0x8F}


class ProgramExit(Exception):
    """The program called Exit() with a return code."""

    def __init__(self, rc):
        super().__init__(rc)
        self.rc = rc


class Guru(Exception):
    """The program caused a CPU exception."""


class Machine:
    """One emulated Amiga with a CPU and the Morosa libraries."""

    def __init__(self, shell, model: int = 68020, ram: int = 16 * 1024 * 1024, out=None, inp=None):  #vers 1
        self.bus = Bus(ram)
        self.cpu = CPU(self.bus, model)
        self.model = model
        self.exec = Exec(self)
        self.libs = {}
        self.owners = {"exec": self.exec}
        self.done = False
        self.rc = 0
        self.abort = False
        self.process = 0
        self.cli = 0
        self.argptr = 0
        self.sentinel = self.exec.alloc(8)
        self._guru()
        self.util = Util(self)
        self.owners["utility"] = self.util
        self.owners["timer"] = Timer(self)
        self.owners["graphics"] = Graphics(self)
        self.owners["intuition"] = Intuition(self)
        self.owners["icon"] = Icon(self)
        self.events = queue.Queue()
        self.live = False
        self.ui = None
        self.strcache = {}
        self.owners["locale"] = LocaleLib(self)
        self.base = self.add_library("exec", 47, 0x240)
        self.bus.w32(4, self.base)
        self._execbase()
        self.process = self.make_process("Morosa")
        self.dos = Dos(self, shell, out, inp)
        self.owners["dos"] = self.dos
        self._finish_process()

    # ---- setup ----
    def _guru(self) -> None:  #vers 1
        a = self.exec.alloc(8)

        def trap(cpu):
            sp = cpu.a[7]
            raise Guru(f"CPU exception vector {self.bus.r16(sp + 6) >> 2} at pc {self.bus.r32(sp + 2):08x}")

        self.cpu.hooks[a] = trap
        for v in range(2, 64):
            self.bus.w32(v * 4, a)

    def _execbase(self) -> None:  #vers 1
        b, w = self.base, self.bus
        w.w32(62, 0x200000)
        w.w16(b + 296, _ATTN.get(self.model, 0) | (0x30 if self.cpu.fpu else 0) | (0x40 if self.model >= 68040 and self.cpu.fpu else 0))
        w.w8(b + 530, 50)
        w.w8(b + 531, 50)
        for off in (300, 350, 378, 392, 406, 420):
            self.exec.new_list(b + off)

    def add_library(self, name: str, version: int, pos: int = 34) -> int:  #vers 1
        """Create a library base with one hook per fd entry."""
        fns = _LVO.get(name, {})
        neg = max((-o for o, _ in fns.values()), default=6) + 6
        neg = (neg + 3) & ~3
        blk = self.exec.alloc(neg + pos + 8)
        base = blk + neg
        self.bus.w8(base + 8, 9)
        nm = self.exec.alloc(len(name) + 12)
        self.exec.put_cstr(nm, name + ".library")
        self.bus.w32(base + 10, nm)
        self.bus.w16(base + 16, neg)
        self.bus.w16(base + 18, pos)
        self.bus.w16(base + 20, version)
        ids = self.exec.alloc(len(name) + 32)
        self.exec.put_cstr(ids, f"{name}.library {version}.0 (1.1.2021)\r\n")
        self.bus.w32(base + 24, ids)
        owner = self.owners.get(name)
        for fname, (off, _regs) in fns.items():
            slot = base + off
            self.bus.w16(slot, 0x4E75)
            self.cpu.hooks[slot] = self._hook(name, fname, owner)
        self.libs[name] = base
        return base

    def _hook(self, lib: str, fname: str, owner):  #vers 1
        def h(cpu):
            fn = getattr(owner, "f_" + fname, None) if owner is not None else None
            if TRACE:
                print(f"{lib}.{fname} d0={cpu.d[0]:x} d1={cpu.d[1]:x} d2={cpu.d[2]:x} d3={cpu.d[3]:x} a0={cpu.a[0]:x} a1={cpu.a[1]:x}")
            if fn is None:
                raise Unimplemented(f"{lib}.library {fname}")
            try:
                fn()
            except Exception as e:
                if type(e).__name__ != "DosError":
                    raise
                self.dos.set_err(218)
                cpu.d[0] = 0
            if TRACE:
                print(f"   -> d0={cpu.d[0]:x}")
            if not cpu.stopped:
                cpu.pc = cpu.pop32()
        return h

    def open_library(self, name: str, version: int) -> int:  #vers 1
        n = name[:-8] if name.endswith(".library") else name
        n = n.rsplit(":", 1)[-1].rsplit("/", 1)[-1]
        if n in self.libs:
            return self.libs[n]
        if n not in _LVO:
            return self.load_disk_library(n)
        return self.add_library(n, 47)

    def load_disk_library(self, n: str) -> int:  #vers 1
        """Load LIBS:<n>.library, build its base from the RomTag and call its Open."""
        path = self.dos.host("libs:" + n + ".library")
        if not os.path.isfile(path):
            return 0
        data = open(path, "rb").read()
        if not morosa_hunk.is_hunk(data):
            return 0
        bptr, segs = morosa_hunk.load(data, self.bus, lambda k: self.exec.alloc(k))
        b = self.bus
        start = segs[0]
        end = start + (b.r32(start - 8) - 8)
        tag = next((a for a in range(start, end - 26, 2) if b.r16(a) == 0x4AFC and b.r32(a + 2) == a), 0)
        if not tag or not b.r8(tag + 10) & 0x80:
            return 0
        tbl = b.r32(tag + 22)
        dsize, vec, init = b.r32(tbl), b.r32(tbl + 4), b.r32(tbl + 12)
        fns, rel = [], b.r16(vec) == 0xFFFF
        a = vec + (2 if rel else 0)
        while True:
            v = b.r16(a) if rel else b.r32(a)
            if (v == 0xFFFF) if rel else (v == 0xFFFFFFFF):
                break
            fns.append(vec + (v - 0x10000 if v >> 15 else v) if rel else v)
            a += 2 if rel else 4
        neg = (len(fns) * 6 + 3) & ~3
        blk = self.exec.alloc(neg + dsize + 8)
        base = blk + neg
        for i, f in enumerate(fns):
            slot = base - 6 * (i + 1)
            b.w16(slot, 0x4EF9)
            b.w32(slot + 2, f)
        b.w8(base + 8, 9)
        b.w32(base + 10, b.r32(tag + 14))
        b.w8(base + 14, 6)
        b.w16(base + 16, neg)
        b.w16(base + 18, dsize)
        b.w16(base + 20, b.r8(tag + 11))
        b.w32(base + 24, b.r32(tag + 18))
        if init:
            r = self.exec.call(init, {0: base}, {0: bptr, 6: self.base})
            base = r or base
        self.libs[n] = base
        return base

    def make_process(self, name: str) -> int:  #vers 1
        p = self.exec.alloc(0xE4)
        nm = self.exec.alloc(len(name) + 8)
        self.exec.put_cstr(nm, name)
        w = self.bus
        w.w8(p + 8, 13)
        w.w32(p + 10, nm)
        w.w32(p + 18, 0xFFFF)
        stack = 64 * 1024
        sb = self.exec.alloc(stack)
        w.w32(p + 58, sb)
        w.w32(p + 62, sb + stack)
        w.w32(p + 54, sb + stack)
        w.w32(p + 132, stack)
        w.w32(p + 144, sb >> 2)
        self.exec.new_list(p + 92 + 20)
        w.w32(self.base + 276, p)
        return p

    def _finish_process(self) -> None:  #vers 1
        w, p = self.bus, self.process
        w.w32(p + 156, self.dos.stdin)
        w.w32(p + 160, self.dos.stdout)
        w.w32(p + 152, self.dos.cur)
        self.cli = self.exec.alloc(64) >> 2
        w.w32(p + 172, self.cli)
        cli = self.cli << 2
        w.w32(cli + 28, self.dos.stdin)
        w.w32(cli + 32, self.dos.stdin)
        w.w32(cli + 48, self.dos.stdout)
        w.w32(cli + 56, self.dos.stdout)
        w.w32(cli + 52, 4096)

    def find_task(self, name: str) -> int:  #vers 1
        return self.process if name == self.exec.cstr(self.bus.r32(self.process + 10)) else 0

    def wait_signals(self, mask: int) -> int:  #vers 2
        """Block until a signal in mask arrives; GUI events run here. 0 when nothing can arrive."""
        t = self.process
        while True:
            got = self.bus.r32(t + 26) & mask
            if got:
                return got
            if self.abort:
                raise Guru("stopped")
            try:
                self.events.get(timeout=0.05)()
            except queue.Empty:
                if not self.live:
                    return 0

    def finish(self, rc: int) -> None:  #vers 2
        raise ProgramExit(rc - (1 << 32) if rc >> 31 else rc)

    def run_seg(self, bptr: int, args: str) -> int:  #vers 1
        """Run a loaded segment list as a nested program; returns its return code."""
        cpu, dos = self.cpu, self.dos
        saved = (cpu.pc, list(cpu.d), list(cpu.a), self.argptr, dos.args, dos.progname)
        line = args + "\n"
        self.argptr = self.exec.alloc(len(line) + 8)
        self.exec.put_cstr(self.argptr, line)
        dos.args = args
        cli = self.cli << 2
        old_mod, old_name = self.bus.r32(cli + 60), self.bus.r32(cli + 16)
        self.bus.w32(cli + 60, bptr)
        self.bus.w32(cli + 16, dos._bstr(dos.progname.lower()))
        try:
            rc = self.exec.call((bptr << 2) + 4, {0: len(line)}, {0: self.argptr, 6: self.base})
        except ProgramExit as e:
            rc = e.rc
        self.exec.free(self.argptr, len(line) + 8)
        self.bus.w32(cli + 60, old_mod)
        self.bus.w32(cli + 16, old_name)
        cpu.pc, cpu.d, cpu.a, self.argptr, dos.args, dos.progname = saved
        return rc

    def system(self, line: str) -> int:  #vers 1
        """Run a command line: an Amiga program from the current directory or C:, else a Shell command."""
        parts = line.strip().split(None, 1)
        if not parts:
            return 0
        name, args = parts[0], parts[1] if len(parts) > 1 else ""
        dos = self.dos
        for cand in (name, "c:" + name):
            path = dos.host(cand)
            if os.path.isfile(path):
                data = open(path, "rb").read()
                if morosa_hunk.is_hunk(data):
                    bptr, _ = morosa_hunk.load(data, self.bus, lambda n: self.exec.alloc(n))
                    old, olddir = dos.progname, dos.progdir
                    dos.progname = os.path.basename(path)
                    full = dos._abs(cand)
                    dos.progdir = full.rsplit("/", 1)[0] if "/" in full else full.split(":")[0] + ":"
                    rc = self.run_seg(bptr, args)
                    dos.progname, dos.progdir = old, olddir
                    return rc
        fn = getattr(dos.shell, "cmd_" + name.lower(), None)
        if fn is None:
            dos._write(dos._h(dos.stdout), f"Unknown command {name}\n".encode())
            return 20
        saved = dos.shell.out
        dos.shell.out = lambda s: dos._write(dos._h(dos.stdout), (s + "\n").encode("latin-1", "replace"))
        try:
            dos.shell._command(name, args.split())
        finally:
            dos.shell.out = saved
        return dos.shell.rc

    # ---- running ----
    def boot(self, pc: int = 0) -> None:  #vers 1
        """Put the CPU in user mode on the process stack."""
        cpu = self.cpu
        top = self.bus.r32(self.process + 62) - 16
        cpu.reset(pc, top)
        cpu.sp["u"] = top
        cpu.set_sr(0)
        cpu.a[7] = top

    def run(self, path: str, args: str = "", max_steps: int = 500_000_000) -> int:  #vers 1
        """Load and run a hunk executable; returns the return code."""
        data = open(path, "rb").read()
        bptr, segs = morosa_hunk.load(data, self.bus, lambda n: self.exec.alloc(n))
        line = args + "\n"
        self.argptr = self.exec.alloc(len(line) + 8)
        self.exec.put_cstr(self.argptr, line)
        self.bus.w32(self.process + 204, self.argptr)
        self.dos.args = args
        self.dos.progname = os.path.basename(path)
        cpu = self.cpu
        self.boot(segs[0])
        cpu.push32(self.sentinel)
        cpu.d[0] = len(line)
        cpu.a[0] = self.argptr
        cpu.a[6] = self.base
        self.done = False
        self.rc = 0
        cpu.stopped = False
        n = 0
        try:
            while True:
                if cpu.pc == self.sentinel:
                    self.finish(cpu.d[0])
                cpu.step()
                n += 1
                if n & 0xFFF == 0 and self.abort:
                    raise Guru("stopped")
                if n >= max_steps:
                    raise Guru("step limit reached")
        except ProgramExit as e:
            self.rc = e.rc
        return self.rc
