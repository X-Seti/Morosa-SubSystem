#this belongs in apps/core/exec.py - Version: 1
# X-Seti - November 17 2026 - Morosa - Morosa exec.library and utility.library.

"""
Morosa exec.library - memory, lists, libraries, messages and tasks for natively run Amiga programs.
"""

##Methods list -
# Exec
# Unimplemented
# Exec.alloc
# Exec.call
# Exec.cstr
# Exec.f_AddHead
# Exec.f_AddPort
# Exec.f_AddTail
# Exec.f_AllocMem
# Exec.f_AllocPooled
# Exec.f_AllocSignal
# Exec.f_AllocVec
# Exec.f_AttemptSemaphore
# Exec.f_AvailMem
# Exec.f_CacheClearU
# Exec.f_CacheControl
# Exec.f_CloseLibrary
# Exec.f_CopyMem
# Exec.f_CreateMsgPort
# Exec.f_CreatePool
# Exec.f_DeleteMsgPort
# Exec.f_DeletePool
# Exec.f_Enqueue
# Exec.f_FindName
# Exec.f_FindPort
# Exec.f_FindTask
# Exec.f_SetFunction
# Exec.f_execPrivate17
# Exec.f_Forbid
# Exec.f_FreeMem
# Exec.f_FreePooled
# Exec.f_FreeSignal
# Exec.f_FreeVec
# Exec.f_GetCC
# Exec.f_GetMsg
# Exec.f_InitSemaphore
# Exec.f_Insert
# Exec.f_ObtainSemaphore
# Exec.f_OldOpenLibrary
# Exec.f_OpenLibrary
# Exec.f_Permit
# Exec.f_PutMsg
# Exec.f_RawDoFmt
# Exec.f_ReleaseSemaphore
# Exec.f_RemHead
# Exec.f_RemPort
# Exec.f_RemTail
# Exec.f_Remove
# Exec.f_ReplyMsg
# Exec.f_SetSignal
# Exec.f_Signal
# Exec.f_SuperState
# Exec.f_TypeOfMem
# Exec.f_UserState
# Exec.f_Wait
# Exec.f_WaitPort
# Exec.format
# Exec.free
# Exec.new_list
# Exec.put_cstr

import re

from apps.core.devices import Devices

MEMF_CLEAR = 1 << 16


class Unimplemented(Exception):
    """A library function the Morosa libraries do not provide yet."""


class Exec(Devices):
    """exec.library functions; f_<Name> reads registers from the CPU."""

    def __init__(self, machine):  #vers 1
        self.m = machine
        self.cpu = machine.cpu
        self.bus = machine.bus
        self.free_list = [(0x2000, machine.bus.size - 0x1000)]
        self.sizes = {}
        self.sigalloc = 0xFFFF
        self.nest = 0
        self.pools = {}
        self.ports = {}

    # ---- helpers ----
    def alloc(self, size: int, clear: bool = True, align: int = 8) -> int:  #vers 1
        size = (size + 7) & ~7
        for i, (s, e) in enumerate(self.free_list):
            a = (s + align - 1) & ~(align - 1)
            if a + size <= e:
                rest = []
                if a > s:
                    rest.append((s, a))
                if a + size < e:
                    rest.append((a + size, e))
                self.free_list[i:i + 1] = rest
                if clear:
                    self.bus.ram[a:a + size] = bytes(size)
                return a
        return 0

    def free(self, addr: int, size: int) -> None:  #vers 1
        size = (size + 7) & ~7
        fl = self.free_list
        fl.append((addr, addr + size))
        fl.sort()
        out = [fl[0]]
        for s, e in fl[1:]:
            if s <= out[-1][1]:
                out[-1] = (out[-1][0], max(out[-1][1], e))
            else:
                out.append((s, e))
        self.free_list = out

    def cstr(self, a: int, limit: int = 4096) -> str:  #vers 1
        out = bytearray()
        while len(out) < limit:
            b = self.bus.r8(a + len(out))
            if b == 0:
                break
            out.append(b)
        return out.decode("latin-1")

    def put_cstr(self, a: int, s: str) -> None:  #vers 1
        for i, ch in enumerate(s.encode("latin-1", "replace")):
            self.bus.w8(a + i, ch)
        self.bus.w8(a + len(s), 0)

    def new_list(self, a: int) -> None:  #vers 1
        w = self.bus.w32
        w(a, a + 4)
        w(a + 4, 0)
        w(a + 8, a)

    def call(self, addr: int, d: dict = None, a: dict = None) -> int:  #vers 2
        """Run Amiga code at addr as a subroutine; returns D0."""
        cpu = self.cpu
        save = (cpu.pc, list(cpu.d), list(cpu.a))
        for k, v in (d or {}).items():
            cpu.d[k] = v & 0xFFFFFFFF
        for k, v in (a or {}).items():
            cpu.a[k] = v & 0xFFFFFFFF
        cpu.push32(self.m.sentinel)
        cpu.pc = addr
        while cpu.pc != self.m.sentinel:
            cpu.step()
            if cpu.stopped:
                return 0
        r = cpu.d[0]
        self.last_a3 = cpu.a[3]
        cpu.pc, cpu.d, cpu.a = save[0], save[1], save[2]
        cpu.d[0] = r
        return r

    # ---- memory ----
    def f_AllocMem(self):  #vers 1
        cpu = self.cpu
        cpu.d[0] = self.alloc(cpu.d[0], bool(cpu.d[1] & MEMF_CLEAR))

    def f_FreeMem(self):  #vers 1
        self.free(self.cpu.a[1], self.cpu.d[0])

    def f_AllocVec(self):  #vers 1
        cpu = self.cpu
        a = self.alloc(cpu.d[0] + 8, bool(cpu.d[1] & MEMF_CLEAR))
        if a:
            self.bus.w32(a, cpu.d[0] + 8)
            a += 8
        cpu.d[0] = a

    def f_FreeVec(self):  #vers 1
        a = self.cpu.a[1]
        if a:
            self.free(a - 8, self.bus.r32(a - 8))

    def f_AvailMem(self):  #vers 1
        cpu = self.cpu
        sizes = [e - s for s, e in self.free_list]
        cpu.d[0] = max(sizes, default=0) if cpu.d[1] & 0x20000 else sum(sizes)

    def f_TypeOfMem(self):  #vers 1
        a = self.cpu.a[1]
        self.cpu.d[0] = 5 if a < self.bus.size else 0

    def f_CopyMem(self):  #vers 1
        cpu = self.cpu
        s, d, n = cpu.a[0], cpu.a[1], cpu.d[0]
        data = bytes(self.bus.r8(s + i) for i in range(n))
        for i, b in enumerate(data):
            self.bus.w8(d + i, b)

    f_CopyMemQuick = f_CopyMem

    def f_CacheClearU(self):  #vers 1
        pass

    f_CacheClearE = f_CacheClearU

    def f_CacheControl(self):  #vers 1
        self.cpu.d[0] = 0

    def f_GetCC(self):  #vers 1
        self.cpu.d[0] = self.cpu.sr & 0xFFFF

    def f_SuperState(self):  #vers 1
        self.cpu.d[0] = self.cpu.a[7]

    def f_UserState(self):  #vers 1
        pass

    def f_Forbid(self):  #vers 1
        self.nest += 1

    def f_Permit(self):  #vers 1
        self.nest -= 1

    f_Disable = f_Forbid
    f_Enable = f_Permit

    def f_ReleaseSemaphore(self):  #vers 1
        pass

    # ---- lists ----
    def f_AddHead(self):  #vers 1
        l, n = self.cpu.a[0], self.cpu.a[1]
        b = self.bus
        h = b.r32(l)
        b.w32(n, h)
        b.w32(n + 4, l)
        b.w32(h + 4, n)
        b.w32(l, n)

    def f_AddTail(self):  #vers 1
        l, n = self.cpu.a[0], self.cpu.a[1]
        b = self.bus
        t = b.r32(l + 8)
        b.w32(n, l + 4)
        b.w32(n + 4, t)
        b.w32(t, n)
        b.w32(l + 8, n)

    def f_Remove(self):  #vers 1
        n = self.cpu.a[1]
        b = self.bus
        s, p = b.r32(n), b.r32(n + 4)
        b.w32(p, s)
        b.w32(s + 4, p)

    def f_RemHead(self):  #vers 1
        l = self.cpu.a[0]
        b = self.bus
        n = b.r32(l)
        nx = b.r32(n)
        if nx == 0:
            self.cpu.d[0] = 0
            return
        b.w32(l, nx)
        b.w32(nx + 4, l)
        self.cpu.d[0] = n

    def f_RemTail(self):  #vers 1
        l = self.cpu.a[0]
        b = self.bus
        n = b.r32(l + 8)
        p = b.r32(n + 4)
        if p == 0:
            self.cpu.d[0] = 0
            return
        b.w32(l + 8, p)
        b.w32(p, l + 4)
        self.cpu.d[0] = n

    def f_Insert(self):  #vers 1
        l, n, p = self.cpu.a[0], self.cpu.a[1], self.cpu.a[2]
        b = self.bus
        if p == 0:
            return self.f_AddHead()
        nx = b.r32(p)
        b.w32(n, nx)
        b.w32(n + 4, p)
        b.w32(p, n)
        b.w32(nx + 4, n)

    def f_Enqueue(self):  #vers 1
        l, n = self.cpu.a[0], self.cpu.a[1]
        b = self.bus
        pri = lambda x: b.r8(x + 9) - 256 if b.r8(x + 9) > 127 else b.r8(x + 9)
        cur = b.r32(l)
        while b.r32(cur) and pri(cur) >= pri(n):
            cur = b.r32(cur)
        p = b.r32(cur + 4)
        b.w32(n, cur)
        b.w32(n + 4, p)
        b.w32(p, n)
        b.w32(cur + 4, n)

    def f_FindName(self):  #vers 1
        cpu = self.cpu
        start, name = cpu.a[0], self.cstr(cpu.a[1])
        b = self.bus
        n = b.r32(start)
        while b.r32(n):
            nm = b.r32(n + 10)
            if nm and self.cstr(nm) == name:
                cpu.d[0] = n
                return
            n = b.r32(n)
        cpu.d[0] = 0

    # ---- libraries ----
    def f_OpenLibrary(self):  #vers 1
        cpu = self.cpu
        name = self.cstr(cpu.a[1]).lower()
        base = self.m.open_library(name, cpu.d[0])
        cpu.d[0] = base

    def f_OldOpenLibrary(self):  #vers 1
        self.cpu.d[0] = self.m.open_library(self.cstr(self.cpu.a[1]).lower(), 0)

    def f_CloseLibrary(self):  #vers 1
        pass

    # ---- tasks, signals, messages ----
    def f_execPrivate17(self):  #vers 1
        self.cpu.d[0] = 0

    def f_SetFunction(self):  #vers 1
        cpu, b = self.cpu, self.bus
        lib, off, new = cpu.a[1], cpu.a[0], cpu.d[0]
        off = off - (1 << 32) if off >> 31 else off
        slot = lib + off
        hook = cpu.hooks.pop(slot, None)
        if hook is not None:
            old = self.alloc(8)
            cpu.hooks[old] = hook
        else:
            old = b.r32(slot + 2)
        b.w16(slot, 0x4EF9)
        b.w32(slot + 2, new)
        cpu.d[0] = old

    def f_FindTask(self):  #vers 1
        cpu = self.cpu
        cpu.d[0] = self.m.process if cpu.a[1] == 0 else self.m.find_task(self.cstr(cpu.a[1]))

    def f_SetSignal(self):  #vers 1
        cpu = self.cpu
        t = self.m.process
        old = self.bus.r32(t + 26)
        new = (old & ~cpu.d[1]) | (cpu.d[0] & cpu.d[1])
        self.bus.w32(t + 26, new)
        cpu.d[0] = old

    def f_AllocSignal(self):  #vers 1
        cpu = self.cpu
        t = self.m.process
        alloc = self.bus.r32(t + 18)
        n = cpu.d[0]
        sn = n if n < 0x80000000 and n < 32 else next((i for i in range(16, 32) if not alloc >> i & 1), -1)
        if sn >= 0 and not alloc >> sn & 1:
            self.bus.w32(t + 18, alloc | 1 << sn)
            cpu.d[0] = sn
        else:
            cpu.d[0] = 0xFFFFFFFF

    def f_FreeSignal(self):  #vers 1
        t = self.m.process
        n = self.cpu.d[0]
        if n < 32:
            self.bus.w32(t + 18, self.bus.r32(t + 18) & ~(1 << n))

    def f_Signal(self):  #vers 1
        t = self.cpu.a[1]
        self.bus.w32(t + 26, self.bus.r32(t + 26) | self.cpu.d[0])

    def f_Wait(self):  #vers 1
        cpu = self.cpu
        t = self.m.process
        want = cpu.d[0]
        got = self.bus.r32(t + 26) & want
        if not got:
            got = self.m.wait_signals(want)
            if not got:
                raise Unimplemented("Wait would block forever: no signal source")
        self.bus.w32(t + 26, self.bus.r32(t + 26) & ~got)
        cpu.d[0] = got

    def f_CreateMsgPort(self):  #vers 2
        cpu = self.cpu
        p = self.alloc(34)
        saved = cpu.d[0]
        cpu.d[0] = 0xFFFFFFFF
        self.f_AllocSignal()
        sb = cpu.d[0] & 0xFF
        cpu.d[0] = saved
        self.bus.w8(p + 8, 4)
        self.bus.w8(p + 15, sb)
        self.bus.w32(p + 16, self.m.process)
        self.new_list(p + 20)
        self.bus.w8(p + 28, 5)
        cpu.d[0] = p

    def f_DeleteMsgPort(self):  #vers 1
        self.free(self.cpu.a[0], 34)

    def f_PutMsg(self):  #vers 2
        cpu = self.cpu
        port, msg = cpu.a[0], cpu.a[1]
        cpu.a[0], cpu.a[1] = port + 20, msg
        self.f_AddTail()
        cpu.a[0] = port
        task = self.bus.r32(port + 16)
        if task and self.bus.r8(port + 14) & 3 == 0:
            self.bus.w32(task + 26, self.bus.r32(task + 26) | 1 << (self.bus.r8(port + 15) & 31))

    def f_GetMsg(self):  #vers 1
        cpu = self.cpu
        port = cpu.a[0]
        cpu.a[0] = port + 20
        self.f_RemHead()

    def f_ReplyMsg(self):  #vers 1
        cpu = self.cpu
        msg = cpu.a[1]
        rp = self.bus.r32(msg + 14)
        if rp:
            cpu.a[0], cpu.a[1] = rp + 20, msg
            self.bus.w8(msg + 8, 7)
            self.f_AddTail()

    def f_WaitPort(self):  #vers 2
        cpu = self.cpu
        port = cpu.a[0]
        b = self.bus
        while b.r32(port + 20) == port + 24:
            if not self.m.wait_signals(1 << (b.r8(port + 15) & 31)):
                raise Unimplemented("WaitPort on an empty port: no message source")
        cpu.d[0] = b.r32(port + 20)

    # ---- formatting ----
    def f_RawDoFmt(self):  #vers 2
        cpu = self.cpu
        put, data = cpu.a[2], cpu.a[3]
        out, args = self.format(cpu.a[0], cpu.a[1])
        if put == 0:
            cpu.d[0] = data
            return
        if put == 1:
            raise Unimplemented("RawDoFmt with a2 = 1 (internal buffer)")
        for ch in out:
            self.call(put, {0: ch}, {3: data})
            data = self.last_a3
        cpu.d[0] = args

    def format(self, fmt: int, args: int):  #vers 1
        """RawDoFmt formatting: (bytes including the final NUL, end of args)."""
        out = bytearray()
        i = 0
        b = self.bus

        def nxt(size):
            nonlocal args
            if size == 2:
                v = b.r16(args)
                args += 2
                return v if v < 0x8000 else v - 0x10000
            v = b.r32(args)
            args += 4
            return v

        while True:
            ch = b.r8(fmt + i)
            i += 1
            if ch != 0x25:
                out.append(ch)
                if ch == 0:
                    break
                continue
            spec = ""
            while True:
                c = chr(b.r8(fmt + i))
                i += 1
                spec += c
                if c in "dDuUxXsScCb%":
                    break
            m = re.match(r"(-?)(0?)(\d*)(?:\.(\d+))?(l?)([dDuUxXsScCb%])$", spec)
            if not m:
                out.extend(spec.encode())
                continue
            left, zero, w, prec, ell, k = m.groups()
            if k == "%":
                out.append(0x25)
                continue
            if k in "sS":
                p = nxt(4)
                txt = self.cstr(p) if p else "(null)"
                if prec:
                    txt = txt[:int(prec)]
            elif k == "b":
                p = nxt(4) << 2
                n = b.r8(p)
                txt = bytes(b.r8(p + 1 + j) for j in range(n)).decode("latin-1")
            elif k in "cC":
                v = nxt(4 if ell else 2)
                txt = chr(v & 0xFF)
            elif k in "dD":
                v = nxt(4 if ell else 2)
                if ell and v >= 0x80000000:
                    v -= 1 << 32
                txt = str(v)
            elif k in "uU":
                v = nxt(4 if ell else 2)
                txt = str(v & (0xFFFFFFFF if ell else 0xFFFF))
            else:
                v = nxt(4 if ell else 2)
                txt = format(v & (0xFFFFFFFF if ell else 0xFFFF), "x" if k == "x" else "X")
            if w:
                n = int(w)
                txt = txt.ljust(n) if left else txt.rjust(n, "0" if zero else " ")
            out.extend(txt.encode("latin-1", "replace"))
        return out, args

    # ---- pools, semaphores, ports ----
    def f_CreatePool(self):  #vers 1
        a = self.alloc(16)
        self.pools[a] = []
        self.cpu.d[0] = a

    def f_DeletePool(self):  #vers 1
        for addr, size in self.pools.pop(self.cpu.a[0], []):
            self.free(addr, size)
        self.free(self.cpu.a[0], 16)

    def f_AllocPooled(self):  #vers 1
        cpu = self.cpu
        a = self.alloc(cpu.d[0], True)
        if a:
            self.pools[cpu.a[0]].append((a, cpu.d[0]))
        cpu.d[0] = a

    def f_FreePooled(self):  #vers 1
        cpu = self.cpu
        pool = self.pools.get(cpu.a[0], [])
        for i, (a, n) in enumerate(pool):
            if a == cpu.a[1]:
                self.free(a, n)
                del pool[i]
                break

    def f_InitSemaphore(self):  #vers 1
        a = self.cpu.a[0]
        for i in range(0, 46, 2):
            self.bus.w16(a + i, 0)
        self.bus.w16(a + 14, 0xFFFF)

    def f_ObtainSemaphore(self):  #vers 1
        pass

    f_ObtainSemaphoreShared = f_ObtainSemaphore

    def f_AttemptSemaphore(self):  #vers 1
        self.cpu.d[0] = 1

    def f_AddPort(self):  #vers 1
        cpu = self.cpu
        self.ports[self.cstr(self.bus.r32(cpu.a[1] + 10))] = cpu.a[1] if self.bus.r32(cpu.a[1] + 10) else 0

    def f_RemPort(self):  #vers 1
        for k, v in list(self.ports.items()):
            if v == self.cpu.a[1]:
                del self.ports[k]

    def f_FindPort(self):  #vers 1
        self.cpu.d[0] = self.ports.get(self.cstr(self.cpu.a[1]), 0)
