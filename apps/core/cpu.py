#this belongs in apps/core/cpu.py - Version: 5
# X-Seti - November 17 2026 - Morosa - Morosa 68k CPU Core.

"""
Morosa 68k CPU Core - interpreter for the Motorola 68000, 68010, 68020, 68030, 68040 and 68060 integer sets; FPU in morosa_fpu.py, MMU in morosa_mmu.py.
"""

##Methods list -
# AddressError
# AddressError.__init__
# Bus
# Bus.__init__
# Bus._hook
# Bus.hook_range
# Bus.r16
# Bus.r32
# Bus.r8
# Bus.read
# Bus.w16
# Bus.w32
# Bus.w8
# Bus.write
# BusError
# BusError.__init__
# CPU
# CPU.__init__
# CPU._bank
# CPU._frame0
# CPU.add_op
# CPU.address_error
# CPU.bus_error
# CPU.ccr
# CPU.cond
# CPU.ea
# CPU.exception
# CPU.f16
# CPU.f32
# CPU.fimm
# CPU.index_ea
# CPU.logic_flags
# CPU.nz
# CPU.pop16
# CPU.pop32
# CPU.push16
# CPU.push32
# CPU.rd
# CPU.reset
# CPU.rte_frame
# CPU.run
# CPU.set_ccr
# CPU.set_sr
# CPU.sr
# CPU.ssp
# CPU.step
# CPU.sub_op
# CPU.usp
# CPU.wr
# CpuStop
# ExcVector
# ExcVector.__init__
# IllegalInstruction
# _addsub
# _bcd_add
# _bcd_sub
# _bitfield
# _cas
# _cas2
# _chk2
# _chk_trap
# _cr_name
# _div
# _divl
# _key
# _legal
# _legal4
# _line0
# _line0_misc
# _line4
# _line5
# _line6
# _line7
# _line8
# _line9
# _lineA
# _lineB
# _lineC
# _lineD
# _lineE
# _lineF
# _line_f_040
# _move
# _move16
# _movec
# _movem
# _movep
# _moves
# _mull
# _pack
# _pmmu
# _ptest040
# _shift
# _supervisor
# sext

from apps.core.fpu import FPU, FpuTrap
from apps.core.mmu import MMU

SIZE_MASK = (0xFF, 0xFFFF, 0xFFFFFFFF)
SIZE_MSB = (0x80, 0x8000, 0x80000000)
SIZE_BYTES = (1, 2, 4)


class CpuStop(Exception):
    """The CPU stopped: STOP, a halt hook or the step limit."""


class IllegalInstruction(Exception):
    """An opcode the core cannot run."""


class BusError(Exception):
    """Access outside memory with no hook, or an MMU fault."""

    def __init__(self, msg="", addr=0, write=False):  #vers 1
        super().__init__(msg)
        self.addr = addr
        self.write = write


class AddressError(Exception):
    """Word or long access at an odd address on a 68000 or 68010."""

    def __init__(self, addr, write=False):
        super().__init__(f"address error at {addr:08x}")
        self.addr, self.write = addr, write


def sext(v: int, size: int) -> int:  #vers 1
    """Signed value of v in size (0 byte, 1 word, 2 long)."""
    m, s = SIZE_MASK[size], SIZE_MSB[size]
    v &= m
    return v - (m + 1) if v & s else v


class Bus:
    """Flat RAM plus hooked address ranges for chips and library stubs."""

    def __init__(self, size: int = 16 * 1024 * 1024):  #vers 1
        self.ram = bytearray(size)
        self.size = size
        self.ranges = []
        self.amask = 0xFFFFFFFF
        self.strict = False
        self.mmu = None
        self.xl = False
        self.sup = True
        self.open_bus = False
        self.open_ranges = []
        self.open_value = 0
        self.berr_on = None

    def hook_range(self, start: int, end: int, read=None, write=None) -> None:  #vers 1
        """read(addr, size) -> int and write(addr, size, value) cover [start, end)."""
        self.ranges.append((start, end, read, write))

    def _hook(self, a, write):  #vers 3
        for s, e, r, w in self.ranges:
            if s <= a < e:
                f = w if write else r
                if f:
                    return f
        if self.open_bus or any(s <= a < e for s, e in self.open_ranges) or (self.berr_on and not self.berr_on()):
            return (lambda a, size, v=0: None) if write else (lambda a, size: self.open_value)
        raise BusError(f"bus error at {a:08x}")

    def r8(self, a):  #vers 2
        a &= self.amask
        if self.xl:
            a = self.mmu.xlate(a, False, self.sup) & self.amask
        if a < self.size:
            return self.ram[a]
        return self._hook(a, False)(a, 0) & 0xFF

    def r16(self, a):  #vers 2
        a &= self.amask
        if self.xl:
            if (a & self.mmu.pmask) == self.mmu.pmask:
                return (self.r8(a) << 8) | self.r8(a + 1)
            a = self.mmu.xlate(a, False, self.sup) & self.amask
        if self.strict and a & 1:
            raise AddressError(a)
        if a + 1 < self.size:
            r = self.ram
            return (r[a] << 8) | r[a + 1]
        return self._hook(a, False)(a, 1) & 0xFFFF

    def r32(self, a):  #vers 2
        a &= self.amask
        if self.xl:
            if (a & self.mmu.pmask) > self.mmu.pmask - 3:
                return (self.r16(a) << 16) | self.r16(a + 2)
            a = self.mmu.xlate(a, False, self.sup) & self.amask
        if self.strict and a & 1:
            raise AddressError(a)
        if a + 3 < self.size:
            r = self.ram
            return (r[a] << 24) | (r[a + 1] << 16) | (r[a + 2] << 8) | r[a + 3]
        return self._hook(a, False)(a, 2) & 0xFFFFFFFF

    def w8(self, a, v):  #vers 2
        a &= self.amask
        if self.xl:
            a = self.mmu.xlate(a, True, self.sup) & self.amask
        if a < self.size:
            self.ram[a] = v & 0xFF
        else:
            self._hook(a, True)(a, 0, v & 0xFF)

    def w16(self, a, v):  #vers 2
        a &= self.amask
        if self.xl:
            if (a & self.mmu.pmask) == self.mmu.pmask:
                self.w8(a, v >> 8)
                self.w8(a + 1, v)
                return
            a = self.mmu.xlate(a, True, self.sup) & self.amask
        if self.strict and a & 1:
            raise AddressError(a, True)
        if a + 1 < self.size:
            self.ram[a] = (v >> 8) & 0xFF
            self.ram[a + 1] = v & 0xFF
        else:
            self._hook(a, True)(a, 1, v & 0xFFFF)

    def w32(self, a, v):  #vers 2
        a &= self.amask
        if self.xl:
            if (a & self.mmu.pmask) > self.mmu.pmask - 3:
                self.w16(a, v >> 16)
                self.w16(a + 2, v)
                return
            a = self.mmu.xlate(a, True, self.sup) & self.amask
        if self.strict and a & 1:
            raise AddressError(a, True)
        if a + 3 < self.size:
            r = self.ram
            r[a] = (v >> 24) & 0xFF
            r[a + 1] = (v >> 16) & 0xFF
            r[a + 2] = (v >> 8) & 0xFF
            r[a + 3] = v & 0xFF
        else:
            self._hook(a, True)(a, 2, v & 0xFFFFFFFF)

    def read(self, a, size):  #vers 1
        return (self.r8, self.r16, self.r32)[size](a)

    def write(self, a, size, v):  #vers 1
        (self.w8, self.w16, self.w32)[size](a, v)


class CPU:
    """68000/68020 integer core. Operand sizes: 0 byte, 1 word, 2 long."""

    MODELS = (68000, 68010, 68020, 68030, 68040, 68060)

    def __init__(self, bus: Bus, model: int = 68020, fpu: bool = True):  #vers 3
        if model not in self.MODELS:
            raise ValueError(f"unknown 68k model {model}")
        self.bus = bus
        self.model = model
        self.m10, self.m20, self.m30 = model >= 68010, model >= 68020, model >= 68030
        self.m40, self.m60 = model >= 68040, model >= 68060
        self.has_m = self.m20 and not self.m60
        bus.amask = 0xFFFFFFFF if self.m20 else 0x00FFFFFF
        bus.strict = not self.m20
        self.d = [0] * 8
        self.a = [0] * 8
        self.pc = 0
        self.x = self.n = self.z = self.v = self.c = 0
        self.s = 1
        self.m = 0
        self.t = 0
        self.t0 = 0
        self.im = 7
        self.sp = {"u": 0, "i": 0, "m": 0}
        self.vbr = 0
        self.cr = {}
        self.sfc = self.dfc = 0
        self.hooks = {}
        self.steps = 0
        self.stopped = False
        self.irq_level = 0
        self.irq_vector = None
        self.legal = {}
        self.ctx = {}
        self.fpu = FPU(model) if fpu and self.m20 else None
        self.mmu = MMU(self) if self.m30 else None
        bus.mmu = self.mmu
        bus.xl = False

    @property
    def usp(self):  #vers 1
        return self.a[7] if not self.s else self.sp["u"]

    @usp.setter
    def usp(self, v):
        if not self.s:
            self.a[7] = v
        else:
            self.sp["u"] = v

    @property
    def ssp(self):  #vers 1
        return self.sp["i"]

    @ssp.setter
    def ssp(self, v):
        self.sp["i"] = v

    # ---- state ----
    def _bank(self) -> str:  #vers 1
        return "u" if not self.s else ("m" if self.m else "i")

    @property
    def sr(self) -> int:  #vers 2
        return (self.t << 15) | (self.t0 << 14) | (self.s << 13) | (self.m << 12) | (self.im << 8) | self.ccr

    @sr.setter
    def sr(self, v: int) -> None:
        self.set_sr(v)

    @property
    def ccr(self) -> int:  #vers 1
        return (self.x << 4) | (self.n << 3) | (self.z << 2) | (self.v << 1) | self.c

    def set_ccr(self, v: int) -> None:  #vers 1
        self.x, self.n, self.z, self.v, self.c = (v >> 4) & 1, (v >> 3) & 1, (v >> 2) & 1, (v >> 1) & 1, v & 1

    def set_sr(self, v: int) -> None:  #vers 2
        """Writes SR; swaps the stack pointer when S or M change."""
        old = self._bank()
        self.s = (v >> 13) & 1
        self.bus.sup = bool(self.s)
        self.m = (v >> 12) & 1 if self.has_m else 0
        new = self._bank()
        if new != old:
            self.sp[old] = self.a[7]
            self.a[7] = self.sp[new]
        self.t = (v >> 15) & 1 if self.m10 else 0
        self.t0 = (v >> 14) & 1 if self.m20 else 0
        self.im = (v >> 8) & 7
        self.set_ccr(v)

    def reset(self, pc: int, sp: int) -> None:  #vers 1
        self.pc, self.a[7] = pc, sp
        self.s, self.im, self.stopped = 1, 7, False

    def push16(self, v):  #vers 1
        self.a[7] = (self.a[7] - 2) & 0xFFFFFFFF
        self.bus.w16(self.a[7], v)

    def push32(self, v):  #vers 1
        self.a[7] = (self.a[7] - 4) & 0xFFFFFFFF
        self.bus.w32(self.a[7], v)

    def pop16(self):  #vers 1
        v = self.bus.r16(self.a[7])
        self.a[7] = (self.a[7] + 2) & 0xFFFFFFFF
        return v

    def pop32(self):  #vers 1
        v = self.bus.r32(self.a[7])
        self.a[7] = (self.a[7] + 4) & 0xFFFFFFFF
        return v

    def _frame0(self, old, ret, vec):  #vers 1
        if self.m10:
            self.push16(vec * 4)
        self.push32(ret)
        self.push16(old)

    def exception(self, vec: int, pc: int = None, interrupt: bool = False) -> None:  #vers 3
        """Push the frame (format 0 on 68010 and up) and jump through the vector table."""
        old = self.sr
        ret = self.pc if pc is None else pc
        self.set_sr((old | 0x2000) & ~0xC000)
        self._frame0(old, ret, vec)
        if interrupt and self.has_m and self.m:
            self.set_sr(self.sr & ~0x1000)
            self.push16((1 << 12) | (vec * 4))
            self.push32(ret)
            self.push16(self.sr | 0x1000)
        self.pc = self.bus.r32(self.vbr + vec * 4)

    def address_error(self, e, start: int, op: int) -> None:  #vers 1
        """68000 and 68010 address error frame."""
        old = self.sr
        self.set_sr((old | 0x2000) & ~0xC000)
        if self.m10:
            for _ in range(22):
                self.push16(0)
            self.push16((8 << 12) | 12)
        else:
            self.push32(start)
            self.push16(old)
            self.push16(op)
            self.push32(e.addr)
            self.push16((0x10 if not e.write else 0) | (5 if old & 0x2000 else 1))
            self.pc = self.bus.r32(self.vbr + 12)
            return
        self.push32(start)
        self.push16(old)
        self.pc = self.bus.r32(self.vbr + 12)

    def bus_error(self, e, start: int, op: int) -> None:  #vers 1
        """Bus error: not restartable; 68000 style frame below the 68020, format 0 above."""
        if not self.m20:
            self.address_error(e, start, op)
            self.pc = self.bus.r32(self.vbr + 8)
            return
        self.exception(2, start)

    def rte_frame(self) -> None:  #vers 1
        """RTE: pop the frame according to its format."""
        sr = self.pop16()
        pc = self.pop32()
        words = 0
        if self.m10:
            fw = self.pop16()
            words = {0: 0, 1: 0, 2: 2, 3: 2, 4: 4, 7: 26, 8: 25, 9: 6, 10: 12, 11: 42}.get(fw >> 12, 0)
            if fw >> 12 == 1 and self.has_m and sr & 0x1000:
                self.set_sr(sr)
                return self.rte_frame()
        self.a[7] = (self.a[7] + 2 * words) & 0xFFFFFFFF
        self.set_sr(sr)
        self.pc = pc

    # ---- fetch ----
    def f16(self) -> int:  #vers 1
        v = self.bus.r16(self.pc)
        self.pc = (self.pc + 2) & 0xFFFFFFFF
        return v

    def f32(self) -> int:  #vers 1
        v = self.bus.r32(self.pc)
        self.pc = (self.pc + 4) & 0xFFFFFFFF
        return v

    def fimm(self, size) -> int:  #vers 1
        if size == 2:
            return self.f32()
        v = self.f16()
        return v & 0xFF if size == 0 else v

    # ---- operands: ('d', n) ('a', n) ('m', addr) ('i', value) ----
    def index_ea(self, base: int) -> int:  #vers 1
        """Brief or full extension word with an index register."""
        ext = self.f16()
        r = (ext >> 12) & 7
        reg = self.a[r] if ext & 0x8000 else self.d[r]
        if not ext & 0x800:
            reg = sext(reg, 1)
        reg = (reg << ((ext >> 9) & 3)) if self.m20 else reg
        if not ext & 0x100 or not self.m20:
            return (base + sext(ext, 0) + reg) & 0xFFFFFFFF
        bs, is_ = (ext >> 7) & 1, (ext >> 6) & 1
        bd = 0
        bds = (ext >> 4) & 3
        if bds == 2:
            bd = sext(self.f16(), 1)
        elif bds == 3:
            bd = sext(self.f32(), 2)
        base = 0 if bs else base
        idx = 0 if is_ else reg
        io = ext & 7
        od = 0
        if io & 3 == 2:
            od = sext(self.f16(), 1)
        elif io & 3 == 3:
            od = sext(self.f32(), 2)
        if io == 0:
            return (base + bd + idx) & 0xFFFFFFFF
        if io < 4:
            return (self.bus.r32((base + bd + idx) & 0xFFFFFFFF) + od) & 0xFFFFFFFF
        return (self.bus.r32((base + bd) & 0xFFFFFFFF) + idx + od) & 0xFFFFFFFF

    def ea(self, mode: int, reg: int, size: int):  #vers 1
        """Resolve an effective address once; applies pre/post modification."""
        if mode == 0:
            return ("d", reg)
        if mode == 1:
            return ("a", reg)
        if mode == 2:
            return ("m", self.a[reg])
        if mode == 3:
            ad = self.a[reg]
            self.a[reg] = (ad + (2 if reg == 7 and size == 0 else SIZE_BYTES[size])) & 0xFFFFFFFF
            return ("m", ad)
        if mode == 4:
            self.a[reg] = (self.a[reg] - (2 if reg == 7 and size == 0 else SIZE_BYTES[size])) & 0xFFFFFFFF
            return ("m", self.a[reg])
        if mode == 5:
            return ("m", (self.a[reg] + sext(self.f16(), 1)) & 0xFFFFFFFF)
        if mode == 6:
            return ("m", self.index_ea(self.a[reg]))
        if reg == 0:
            return ("m", sext(self.f16(), 1) & 0xFFFFFFFF)
        if reg == 1:
            return ("m", self.f32())
        if reg == 2:
            base = self.pc
            return ("m", (base + sext(self.f16(), 1)) & 0xFFFFFFFF)
        if reg == 3:
            base = self.pc
            return ("m", self.index_ea(base))
        if reg == 4:
            return ("i", self.fimm(size))
        raise IllegalInstruction(f"ea {mode}.{reg}")

    def rd(self, op, size: int) -> int:  #vers 1
        k, v = op
        if k == "d":
            return self.d[v] & SIZE_MASK[size]
        if k == "a":
            return self.a[v] & SIZE_MASK[size]
        if k == "i":
            return v & SIZE_MASK[size]
        return self.bus.read(v, size)

    def wr(self, op, size: int, val: int) -> None:  #vers 1
        k, v = op
        val &= SIZE_MASK[size]
        if k == "d":
            m = SIZE_MASK[size]
            self.d[v] = (self.d[v] & ~m & 0xFFFFFFFF) | val
        elif k == "a":
            self.a[v] = sext(val, size) & 0xFFFFFFFF if size < 2 else val
        elif k == "m":
            self.bus.write(v, size, val)
        else:
            raise IllegalInstruction("write to immediate")

    # ---- flags ----
    def nz(self, r: int, size: int) -> None:  #vers 1
        r &= SIZE_MASK[size]
        self.n = 1 if r & SIZE_MSB[size] else 0
        self.z = 1 if r == 0 else 0

    def logic_flags(self, r: int, size: int) -> None:  #vers 1
        self.nz(r, size)
        self.v = self.c = 0

    def add_op(self, s, d, size, carry_in=0, x_flag=True, keep_z=False):  #vers 1
        m, msb = SIZE_MASK[size], SIZE_MSB[size]
        t = s + d + carry_in
        r = t & m
        c = 1 if t > m else 0
        self.v = 1 if ((s ^ r) & (d ^ r) & msb) else 0
        self.c = c
        if x_flag:
            self.x = c
        self.n = 1 if r & msb else 0
        if keep_z:
            if r:
                self.z = 0
        else:
            self.z = 1 if r == 0 else 0
        return r

    def sub_op(self, s, d, size, carry_in=0, x_flag=True, keep_z=False):  #vers 1
        m, msb = SIZE_MASK[size], SIZE_MSB[size]
        t = d - s - carry_in
        r = t & m
        c = 1 if t < 0 else 0
        self.v = 1 if ((s ^ d) & (r ^ d) & msb) else 0
        self.c = c
        if x_flag:
            self.x = c
        self.n = 1 if r & msb else 0
        if keep_z:
            if r:
                self.z = 0
        else:
            self.z = 1 if r == 0 else 0
        return r

    def cond(self, cc: int) -> bool:  #vers 1
        n, z, v, c = self.n, self.z, self.v, self.c
        return (True, False, not (c or z), bool(c or z), not c, bool(c), not z, bool(z), not v, bool(v),
                not n, bool(n), n == v, n != v, (not z) and n == v, bool(z) or n != v)[cc]

    # ---- running ----
    def step(self) -> None:  #vers 2
        """Run one instruction, or the hook sitting at pc; takes pending interrupts and trace first."""
        if self.irq_level and (self.irq_level > self.im or self.irq_level == 7):
            lvl = self.irq_level
            vec = self.irq_vector if self.irq_vector is not None else 24 + lvl
            self.stopped = False
            self.exception(vec, interrupt=True)
            self.im = lvl
            return
        h = self.hooks.get(self.pc)
        if h is not None:
            h(self)
            return
        start = self.pc
        trace = self.t
        op = 0
        try:
            op = self.f16()
            ok = self.legal.get(op)
            if ok is None:
                ok = self.legal[op] = _legal(self, op)
            if not ok:
                raise IllegalInstruction(f"{op:04x}")
            _LINES[op >> 12](self, op)
        except IllegalInstruction:
            self.exception(4, start)
        except ExcVector as e:
            self.exception(e.vec, start)
        except AddressError as e:
            self.address_error(e, start, op)
        except BusError as e:
            self.bus_error(e, start, op)
        self.steps += 1
        if trace and not self.stopped:
            self.exception(9)

    def run(self, max_steps: int = 1000000) -> int:  #vers 1
        """Run until stop or the limit; returns the instruction count."""
        n = 0
        try:
            while n < max_steps and not self.stopped:
                self.step()
                n += 1
        except CpuStop:
            pass
        return n


class ExcVector(Exception):
    """Take exception vector n with the stacked pc at the instruction start."""

    def __init__(self, vec):
        super().__init__(vec)
        self.vec = vec


def _supervisor(c):  #vers 1
    if not c.s:
        raise ExcVector(8)


_ALL = frozenset((0, 1, 2, 3, 4, 5, 6, 70, 71, 72, 73, 74))
_DATA = _ALL - {1}
_MEM = _ALL - {0, 1}
_ALTER = _ALL - {72, 73, 74}
_DALTER = _ALTER - {1}
_MALTER = _ALTER - {0, 1}
_CTRL = frozenset((2, 5, 6, 70, 71, 72, 73))
_CTRLALT = frozenset((2, 5, 6, 70, 71))
_BTSTI = _ALL - {1, 74}
_BFR = frozenset((0, 2, 5, 6, 70, 71, 72, 73))
_BFW = frozenset((0, 2, 5, 6, 70, 71))


def _key(mode: int, reg: int) -> int:  #vers 1
    return mode if mode < 7 else 70 + reg


def _legal(c, op: int) -> bool:  #vers 1
    """True when op is a valid instruction for this model and its effective address is allowed."""
    line = op >> 12
    k = _key((op >> 3) & 7, op & 7)
    mode = (op >> 3) & 7
    size = (op >> 6) & 3
    if line == 0:
        if (op & 0xF138) == 0x0108:
            return True
        if op & 0xF100 == 0x0100:
            return k in (_DATA if size == 0 else _DALTER)
        if op & 0xFF00 == 0x0800:
            return k in (_BTSTI if size == 0 else _DALTER)
        grp = (op >> 9) & 7
        if op in (0x0CFC, 0x0EFC):
            return c.m20
        if size == 3:
            if grp in (0, 1, 2):
                return c.m20 and k in _CTRL
            if grp in (5, 6, 7):
                return c.m20 and k in _MALTER
            return False
        if op & 0xFF00 == 0x0E00:
            return c.m10 and k in _MALTER
        if op in (0x0CFC, 0x0EFC):
            return c.m20
        if op & 0xFF == 0x3C and grp in (0, 1, 5) and size < 2:
            return True
        if op & 0xFF == 0x7C and grp in (0, 1, 5) and size == 1:
            return True
        if grp == 4 or grp == 7:
            return False
        if grp == 6:
            return k in (_DALTER | ({72, 73} if c.m20 else set()))
        return k in _DALTER
    if line in (1, 2, 3):
        sz = {1: 0, 3: 1, 2: 2}[line]
        if sz == 0 and k == 1:
            return False
        dk = _key((op >> 6) & 7, (op >> 9) & 7)
        if dk == 1:
            return sz > 0
        return k in _ALL and dk in _DALTER
    if line == 4:
        return _legal4(c, op, k, mode, size)
    if line == 5:
        if size == 3:
            if mode == 1:
                return True
            if mode == 7 and (op & 7) in (2, 3, 4):
                return c.m20
            return k in _DALTER
        return k in _ALTER and not (size == 0 and k == 1)
    if line == 6:
        return True
    if line == 7:
        return not op & 0x100
    opm = (op >> 6) & 7
    if line == 8:
        if opm in (3, 7):
            return k in _DATA
        if opm == 4:
            return mode in (0, 1) or k in _MALTER
        if opm in (5, 6) and mode in (0, 1):
            return c.m20
        return k in (_DATA if opm < 3 else _MALTER)
    if line in (9, 13):
        if opm in (3, 7):
            return k in _ALL
        if opm >= 4 and mode in (0, 1):
            return True
        if opm < 3:
            return k in _ALL and not (opm == 0 and k == 1)
        return k in _MALTER
    if line == 11:
        if opm in (3, 7):
            return k in _ALL
        if opm < 3:
            return k in _ALL and not (opm == 0 and k == 1)
        if mode == 1:
            return True
        return k in _DALTER
    if line == 12:
        if opm in (3, 7):
            return k in _DATA
        if opm in (4, 5, 6) and (op & 0x1F0) in (0x100, 0x140, 0x180) and mode in (0, 1):
            return (op & 0x1F8) in (0x100, 0x108, 0x140, 0x148, 0x188)
        return k in (_DATA if opm < 3 else _MALTER)
    if line == 14:
        if size == 3:
            if op & 0x0800:
                if not c.m20:
                    return False
                return k in (_BFR if ((op >> 8) & 7) in (0, 1, 3, 5) else _BFW)
            return k in _MALTER
        return True
    return True


def _legal4(c, op, k, mode, size):  #vers 3
    if op & 0xFFF8 == 0x49C0:
        return c.m20
    if op & 0xFF80 == 0x4880 and mode != 0:
        return k in (_CTRLALT | {4})
    if op & 0xF1C0 == 0x41C0:
        return k in _CTRL
    if op & 0xF1C0 == 0x4180:
        return k in _DATA
    if op & 0xF1C0 == 0x4100:
        return c.m20 and k in _DATA
    if op & 0xFFF8 == 0x49C0:
        return c.m20
    hi = op & 0xFF00
    if hi in (0x4000, 0x4200, 0x4400, 0x4600):
        if size < 3:
            return k in _DALTER
        if hi == 0x4000:
            return k in _DALTER
        if hi == 0x4200:
            return c.m10 and k in _DALTER
        return k in _DATA
    if hi == 0x4800:
        if op & 0xFFC0 == 0x4800:
            return k in _DALTER
        if op & 0xFFF8 == 0x4808:
            return c.m20
        if op & 0xFFF8 == 0x4840:
            return True
        if op & 0xFFF8 == 0x4848:
            return c.m10
        if op & 0xFFC0 == 0x4840:
            return k in _CTRL
        if op & 0xFFF8 in (0x4880, 0x48C0):
            return True
        return False
    if op & 0xFF80 == 0x4880:
        return k in (_CTRLALT | {4})
    if hi == 0x4A00:
        if size == 3:
            return op == 0x4AFC or k in _DALTER
        if c.m20:
            return k in _ALL and not (size == 0 and k == 1)
        return k in _DALTER
    if op & 0xFF80 == 0x4C80:
        return k in ((_CTRL | {3}) - {74})
    if op & 0xFF80 == 0x4C00:
        return c.m20 and k in _DATA
    if hi == 0x4E00:
        if op & 0xFFF0 == 0x4E40 or op & 0xFFF8 in (0x4E50, 0x4E58, 0x4E60, 0x4E68):
            return True
        if op in (0x4E70, 0x4E71, 0x4E72, 0x4E73, 0x4E75, 0x4E76, 0x4E77):
            return True
        if op in (0x4E74, 0x4E7A, 0x4E7B):
            return c.m10
        if op & 0xFF80 == 0x4E80:
            return k in _CTRL
    return False


def _line0(c, op):  #vers 1
    mode, reg = (op >> 3) & 7, op & 7
    if op & 0x0100 and mode == 1:
        return _movep(c, op)
    if op & 0x0100 or (op & 0x0F00) == 0x0800:
        kind = (op >> 6) & 3
        if op & 0x0100:
            bit = c.d[(op >> 9) & 7]
        else:
            bit = c.f16() & 0xFF
        if mode == 0:
            bit &= 31
            val = c.d[reg]
            m = 1 << bit
            c.z = 0 if val & m else 1
            if kind == 1:
                c.d[reg] = val ^ m
            elif kind == 2:
                c.d[reg] = val & ~m
            elif kind == 3:
                c.d[reg] = val | m
        else:
            bit &= 7
            o = c.ea(mode, reg, 0)
            val = c.rd(o, 0)
            m = 1 << bit
            c.z = 0 if val & m else 1
            if kind == 1:
                c.wr(o, 0, val ^ m)
            elif kind == 2:
                c.wr(o, 0, val & ~m)
            elif kind == 3:
                c.wr(o, 0, val | m)
        return
    group = (op >> 9) & 7
    size = (op >> 6) & 3
    if size == 3 or op in (0x0CFC, 0x0EFC) or (op & 0xFF00) == 0x0E00:
        return _line0_misc(c, op)
    if op & 0xFF == 0x3C:
        v = c.f16() & 0xFF
        if group == 0:
            c.set_ccr(c.ccr | v)
        elif group == 1:
            c.set_ccr(c.ccr & v)
        elif group == 5:
            c.set_ccr(c.ccr ^ v)
        else:
            raise IllegalInstruction("ccr")
        return
    if op & 0xFF == 0x7C:
        _supervisor(c)
        v = c.f16()
        if group == 0:
            c.set_sr(c.sr | v)
        elif group == 1:
            c.set_sr(c.sr & v)
        elif group == 5:
            c.set_sr(c.sr ^ v)
        else:
            raise IllegalInstruction("sr")
        return
    imm = c.fimm(size)
    m = SIZE_MASK[size]
    if group == 6:
        o = c.ea(mode, reg, size)
        c.sub_op(imm, c.rd(o, size), size, x_flag=False)
        return
    o = c.ea(mode, reg, size)
    d = c.rd(o, size)
    if group == 0:
        r = d | imm
    elif group == 1:
        r = d & imm
    elif group == 5:
        r = d ^ imm
    elif group == 2:
        c.wr(o, size, c.sub_op(imm, d, size))
        return
    elif group == 3:
        c.wr(o, size, c.add_op(imm, d, size))
        return
    else:
        raise IllegalInstruction("imm op")
    c.logic_flags(r & m, size)
    c.wr(o, size, r)


def _movep(c, op):  #vers 2
    if c.m60:
        raise ExcVector(61)
    dn, an = (op >> 9) & 7, op & 7
    ad = (c.a[an] + sext(c.f16(), 1)) & 0xFFFFFFFF
    opm = (op >> 6) & 7
    n = 4 if opm in (5, 7) else 2
    if opm in (4, 5):
        v = 0
        for i in range(n):
            v = (v << 8) | c.bus.r8(ad + 2 * i)
        c.d[dn] = v if n == 4 else (c.d[dn] & 0xFFFF0000) | v
    else:
        v = c.d[dn]
        for i in range(n):
            c.bus.w8(ad + 2 * i, (v >> (8 * (n - 1 - i))) & 0xFF)


_MOVE_SIZE = {1: 0, 3: 1, 2: 2}


def _move(c, op):  #vers 1
    size = _MOVE_SIZE[op >> 12]
    s = c.ea((op >> 3) & 7, op & 7, size)
    v = c.rd(s, size)
    dm, dr = (op >> 6) & 7, (op >> 9) & 7
    if dm == 1:
        c.a[dr] = sext(v, size) & 0xFFFFFFFF
        return
    c.logic_flags(v, size)
    c.wr(c.ea(dm, dr, size), size, v)


def _chk_trap(c, vec):  #vers 1
    c.exception(vec)


def _line4(c, op):  #vers 1
    mode, reg = (op >> 3) & 7, op & 7
    if op == 0x4AFC:
        raise IllegalInstruction("illegal")
    if op & 0xFFF0 == 0x4E40:
        return c.exception(32 + (op & 15))
    if op & 0xFFF8 == 0x4E50:
        d = sext(c.f16(), 1)
        c.a[7] = (c.a[7] - 4) & 0xFFFFFFFF
        c.bus.w32(c.a[7], c.a[reg])
        c.a[reg] = c.a[7]
        c.a[7] = (c.a[7] + d) & 0xFFFFFFFF
        return
    if op & 0xFFF8 == 0x4808:
        d = c.f32()
        c.a[7] = (c.a[7] - 4) & 0xFFFFFFFF
        c.bus.w32(c.a[7], c.a[reg])
        c.a[reg] = c.a[7]
        c.a[7] = (c.a[7] + d) & 0xFFFFFFFF
        return
    if op & 0xFFF8 == 0x4E58:
        c.a[7] = c.a[reg]
        c.a[reg] = c.bus.r32(c.a[7])
        c.a[7] = (c.a[7] + 4) & 0xFFFFFFFF
        return
    if op & 0xFFF0 == 0x4E60:
        _supervisor(c)
        if op & 8:
            c.a[reg] = c.usp
        else:
            c.usp = c.a[reg]
        return
    if op == 0x4E70:
        _supervisor(c)
        return
    if op == 0x4E71:
        return
    if op == 0x4E72:
        _supervisor(c)
        c.set_sr(c.f16())
        c.stopped = True
        return
    if op == 0x4E73:
        _supervisor(c)
        return c.rte_frame()
    if op == 0x4E75:
        c.pc = c.bus.r32(c.a[7])
        c.a[7] = (c.a[7] + 4) & 0xFFFFFFFF
        return
    if op == 0x4E76:
        if c.v:
            c.exception(7)
        return
    if op == 0x4E77:
        c.set_ccr(c.bus.r16(c.a[7]))
        c.pc = c.bus.r32(c.a[7] + 2)
        c.a[7] = (c.a[7] + 6) & 0xFFFFFFFF
        return
    if op == 0x4E74:
        d = sext(c.f16(), 1)
        c.pc = c.pop32()
        c.a[7] = (c.a[7] + d) & 0xFFFFFFFF
        return
    if op & 0xFFF8 == 0x4848:
        raise IllegalInstruction("bkpt")
    if op in (0x4E7A, 0x4E7B):
        return _movec(c, op)
    if op & 0xFFC0 == 0x4E80:
        t = c.ea(mode, reg, 2)[1]
        c.a[7] = (c.a[7] - 4) & 0xFFFFFFFF
        c.bus.w32(c.a[7], c.pc)
        c.pc = t
        return
    if op & 0xFFC0 == 0x4EC0:
        c.pc = c.ea(mode, reg, 2)[1]
        return
    if op & 0xFF80 == 0x4C00 and op & 0x0040 == 0:
        return _mull(c, op)
    if op & 0xFF80 == 0x4C00:
        return _divl(c, op)
    if op & 0xFB80 == 0x4880 and mode != 0:
        return _movem(c, op)
    if op & 0xFFF8 in (0x4880, 0x48C0, 0x49C0):
        if op & 0xFFF8 == 0x4880:
            c.d[reg] = (c.d[reg] & 0xFFFF0000) | (sext(c.d[reg], 0) & 0xFFFF)
            c.logic_flags(c.d[reg], 1)
        elif op & 0xFFF8 == 0x48C0:
            c.d[reg] = sext(c.d[reg], 1) & 0xFFFFFFFF
            c.logic_flags(c.d[reg], 2)
        else:
            c.d[reg] = sext(c.d[reg], 0) & 0xFFFFFFFF
            c.logic_flags(c.d[reg], 2)
        return
    if op & 0xFB80 == 0x4C80:
        return _movem(c, op)
    if op & 0xF1C0 == 0x41C0:
        c.a[(op >> 9) & 7] = c.ea(mode, reg, 2)[1]
        return
    if op & 0xF1C0 == 0x4180 or op & 0xF1C0 == 0x4100:
        size = 1 if op & 0xF1C0 == 0x4180 else 2
        b = sext(c.rd(c.ea(mode, reg, size), size), size)
        d = sext(c.d[(op >> 9) & 7], size)
        if d < 0:
            c.n = 1
            c.exception(6)
        elif d > b:
            c.n = 0
            c.exception(6)
        return
    if op & 0xFFF8 == 0x4840:
        v = c.d[reg]
        c.d[reg] = ((v << 16) | (v >> 16)) & 0xFFFFFFFF
        c.logic_flags(c.d[reg], 2)
        return
    if op & 0xFFC0 == 0x4840:
        a = c.ea(mode, reg, 2)[1]
        c.a[7] = (c.a[7] - 4) & 0xFFFFFFFF
        c.bus.w32(c.a[7], a)
        return
    size = (op >> 6) & 3
    kind = op & 0x0F00
    if size == 3:
        if kind == 0x000:
            if c.m10:
                _supervisor(c)
            return c.wr(c.ea(mode, reg, 1), 1, c.sr)
        if kind == 0x200:
            return c.wr(c.ea(mode, reg, 1), 1, c.ccr)
        if kind == 0x400:
            c.set_ccr(c.rd(c.ea(mode, reg, 1), 1))
            return
        if kind == 0x600:
            _supervisor(c)
            c.set_sr(c.rd(c.ea(mode, reg, 1), 1))
            return
        if kind == 0xA00:
            o = c.ea(mode, reg, 0)
            v = c.rd(o, 0)
            c.logic_flags(v, 0)
            c.wr(o, 0, v | 0x80)
            return
        raise IllegalInstruction("line4")
    if kind == 0x800 and size == 0:
        o = c.ea(mode, reg, 0)
        v = c.rd(o, 0)
        r = _bcd_sub(c, v, 0)
        c.wr(o, 0, r)
        return
    o = c.ea(mode, reg, size)
    if kind == 0x000:
        d = c.rd(o, size)
        c.wr(o, size, c.sub_op(d, 0, size, carry_in=c.x, keep_z=True))
    elif kind == 0x200:
        c.wr(o, size, 0)
        c.n, c.z, c.v, c.c = 0, 1, 0, 0
    elif kind == 0x400:
        c.wr(o, size, c.sub_op(c.rd(o, size), 0, size))
    elif kind == 0x600:
        r = ~c.rd(o, size)
        c.logic_flags(r, size)
        c.wr(o, size, r)
    elif kind == 0xA00:
        c.logic_flags(c.rd(o, size), size)
    else:
        raise IllegalInstruction("line4")


def _bcd_sub(c, s, d):  #vers 1
    """d - s - x in packed BCD; sets X, C and clears Z on a non-zero result."""
    lo = (d & 0xF) - (s & 0xF) - c.x
    borrow_lo = lo < 0
    if borrow_lo:
        lo += 10
    hi = (d >> 4) - (s >> 4) - (1 if borrow_lo else 0)
    borrow = hi < 0
    if borrow:
        hi += 10
    r = ((hi & 0xF) << 4) | (lo & 0xF)
    c.x = c.c = 1 if borrow else 0
    if r:
        c.z = 0
    return r


def _bcd_add(c, s, d):  #vers 1
    lo = (d & 0xF) + (s & 0xF) + c.x
    carry_lo = lo > 9
    if carry_lo:
        lo -= 10
    hi = (d >> 4) + (s >> 4) + (1 if carry_lo else 0)
    carry = hi > 9
    if carry:
        hi -= 10
    r = ((hi & 0xF) << 4) | (lo & 0xF)
    c.x = c.c = 1 if carry else 0
    if r:
        c.z = 0
    return r


def _movem(c, op):  #vers 1
    mode, reg = (op >> 3) & 7, op & 7
    size = 2 if op & 0x40 else 1
    n = SIZE_BYTES[size]
    mask = c.f16()
    to_reg = bool(op & 0x0400)
    if not to_reg:
        if mode == 4:
            ad = c.a[reg]
            regs = [c.a[7 - i] if i < 8 else c.d[15 - i] for i in range(16)]
            for i in range(16):
                if mask & (1 << i):
                    ad = (ad - n) & 0xFFFFFFFF
                    c.bus.write(ad, size, regs[i])
            c.a[reg] = ad
        else:
            ad = c.ea(mode, reg, size)[1]
            for i in range(16):
                if mask & (1 << i):
                    v = c.d[i] if i < 8 else c.a[i - 8]
                    c.bus.write(ad, size, v)
                    ad = (ad + n) & 0xFFFFFFFF
    else:
        if mode == 3:
            ad = c.a[reg]
        else:
            ad = c.ea(mode, reg, size)[1]
        for i in range(16):
            if mask & (1 << i):
                v = c.bus.read(ad, size)
                if size == 1:
                    v = sext(v, 1) & 0xFFFFFFFF
                if i < 8:
                    c.d[i] = v
                else:
                    c.a[i - 8] = v
                ad = (ad + n) & 0xFFFFFFFF
        if mode == 3:
            c.a[reg] = ad


def _mull(c, op):  #vers 1
    ext = c.f16()
    s = c.rd(c.ea((op >> 3) & 7, op & 7, 2), 2)
    dl = (ext >> 12) & 7
    signed = bool(ext & 0x800)
    big = bool(ext & 0x400)
    if big and c.m60:
        raise ExcVector(61)
    if signed:
        r = sext(s, 2) * sext(c.d[dl], 2)
    else:
        r = s * c.d[dl]
    c.d[dl] = r & 0xFFFFFFFF
    if big:
        c.d[ext & 7] = (r >> 32) & 0xFFFFFFFF
        c.v = 0
        c.n = 1 if (r >> 63) & 1 else 0
        c.z = 1 if r & 0xFFFFFFFFFFFFFFFF == 0 else 0
    else:
        lo = r & 0xFFFFFFFF
        c.v = 1 if (sext(lo, 2) != r if signed else lo != r) else 0
        c.n = 1 if lo & 0x80000000 else 0
        c.z = 1 if lo == 0 else 0
    c.c = 0


def _divl(c, op):  #vers 1
    ext = c.f16()
    s = c.rd(c.ea((op >> 3) & 7, op & 7, 2), 2)
    dq, dr = (ext >> 12) & 7, ext & 7
    signed = bool(ext & 0x800)
    big = bool(ext & 0x400)
    if big and c.m60:
        raise ExcVector(61)
    if s == 0:
        return c.exception(5)
    if big:
        dividend = (c.d[dr] << 32) | c.d[dq]
        if signed and dividend & (1 << 63):
            dividend -= 1 << 64
    else:
        dividend = sext(c.d[dq], 2) if signed else c.d[dq]
    div = sext(s, 2) if signed else s
    q = abs(dividend) // abs(div)
    rem = abs(dividend) % abs(div)
    if signed:
        if (dividend < 0) != (div < 0):
            q = -q
        if dividend < 0:
            rem = -rem
        lim = q < -(1 << 31) or q > (1 << 31) - 1
    else:
        lim = q > 0xFFFFFFFF
    if lim:
        c.v = 1
        return
    c.d[dq] = q & 0xFFFFFFFF
    if dr != dq or big:
        c.d[dr] = rem & 0xFFFFFFFF
    c.v = c.c = 0
    c.n = 1 if q & 0x80000000 else 0
    c.z = 1 if q & 0xFFFFFFFF == 0 else 0


def _line5(c, op):  #vers 1
    mode, reg = (op >> 3) & 7, op & 7
    size = (op >> 6) & 3
    if size == 3:
        cc = (op >> 8) & 15
        if mode == 1:
            disp = sext(c.f16(), 1)
            if not c.cond(cc):
                n = (c.d[reg] - 1) & 0xFFFF
                c.d[reg] = (c.d[reg] & 0xFFFF0000) | n
                if n != 0xFFFF:
                    c.pc = (c.pc - 2 + disp) & 0xFFFFFFFF
            return
        if mode == 7 and reg in (2, 3, 4):
            if reg == 2:
                c.f16()
            elif reg == 3:
                c.f32()
            if c.cond(cc):
                c.exception(7)
            return
        o = c.ea(mode, reg, 0)
        c.wr(o, 0, 0xFF if c.cond(cc) else 0)
        return
    q = (op >> 9) & 7 or 8
    o = c.ea(mode, reg, size)
    if o[0] == "a":
        c.a[reg] = (c.a[reg] + q if not op & 0x100 else c.a[reg] - q) & 0xFFFFFFFF
        return
    d = c.rd(o, size)
    c.wr(o, size, c.sub_op(q, d, size) if op & 0x100 else c.add_op(q, d, size))


def _line6(c, op):  #vers 1
    cc = (op >> 8) & 15
    base = c.pc
    disp = op & 0xFF
    if disp == 0:
        disp = sext(c.f16(), 1)
    elif disp == 0xFF and c.m20:
        disp = sext(c.f32(), 2)
    else:
        disp = sext(disp, 0)
    if cc == 1:
        c.a[7] = (c.a[7] - 4) & 0xFFFFFFFF
        c.bus.w32(c.a[7], c.pc)
        c.pc = (base + disp) & 0xFFFFFFFF
    elif c.cond(cc):
        c.pc = (base + disp) & 0xFFFFFFFF


def _line7(c, op):  #vers 1
    if op & 0x100:
        raise IllegalInstruction("moveq")
    v = sext(op & 0xFF, 0) & 0xFFFFFFFF
    c.d[(op >> 9) & 7] = v
    c.logic_flags(v, 2)


def _div(c, op, signed):  #vers 1
    s = c.rd(c.ea((op >> 3) & 7, op & 7, 1), 1)
    dn = (op >> 9) & 7
    if s == 0:
        return c.exception(5)
    if signed:
        dv, ds = sext(c.d[dn], 2), sext(s, 1)
        q = abs(dv) // abs(ds)
        r = abs(dv) % abs(ds)
        if (dv < 0) != (ds < 0):
            q = -q
        if dv < 0:
            r = -r
        if q < -32768 or q > 32767:
            c.v, c.c = 1, 0
            return
    else:
        dv = c.d[dn]
        q, r = dv // s, dv % s
        if q > 0xFFFF:
            c.v, c.c = 1, 0
            return
    c.d[dn] = ((r & 0xFFFF) << 16) | (q & 0xFFFF)
    c.n = 1 if q & 0x8000 else 0
    c.z = 1 if q & 0xFFFF == 0 else 0
    c.v = c.c = 0


def _line8(c, op):  #vers 1
    mode, reg = (op >> 3) & 7, op & 7
    dn = (op >> 9) & 7
    if op & 0x1C0 == 0xC0:
        return _div(c, op, False)
    if op & 0x1C0 == 0x1C0:
        return _div(c, op, True)
    if op & 0x1F0 == 0x100:
        if op & 8:
            c.a[reg] = (c.a[reg] - 1) & 0xFFFFFFFF
            c.a[dn] = (c.a[dn] - 1) & 0xFFFFFFFF
            s, dd = c.bus.r8(c.a[reg]), c.bus.r8(c.a[dn])
            c.bus.w8(c.a[dn], _bcd_sub(c, s, dd))
        else:
            c.d[dn] = (c.d[dn] & ~0xFF) | _bcd_sub(c, c.d[reg] & 0xFF, c.d[dn] & 0xFF)
        return
    if op & 0x1F0 in (0x140, 0x180):
        return _pack(c, op, op & 0x1F0 == 0x180)
    size = (op >> 6) & 3
    o = c.ea(mode, reg, size)
    if op & 0x100:
        d = c.ea(0, dn, size)
        r = c.rd(o, size) | c.rd(d, size)
        c.logic_flags(r, size)
        c.wr(o, size, r)
    else:
        r = c.rd(o, size) | c.d[dn]
        c.logic_flags(r, size)
        c.wr(("d", dn), size, r)


def _pack(c, op, unpack):  #vers 1
    reg, dn = op & 7, (op >> 9) & 7
    adj = c.f16()
    if op & 8:
        n_in, n_out = (1, 2) if unpack else (2, 1)
        c.a[reg] = (c.a[reg] - n_in) & 0xFFFFFFFF
        v = c.bus.read(c.a[reg], 0 if unpack else 1)
    else:
        v = c.d[reg] & (0xFF if unpack else 0xFFFF)
    if unpack:
        t = (((v & 0xF0) << 4) | (v & 0x0F)) + adj
        r, osz = t & 0xFFFF, 1
    else:
        t = (v + adj) & 0xFFFF
        r, osz = ((t >> 4) & 0xF0) | (t & 0x0F), 0
    if op & 8:
        c.a[dn] = (c.a[dn] - n_out) & 0xFFFFFFFF
        c.bus.write(c.a[dn], osz, r)
    else:
        c.wr(("d", dn), osz, r)


def _addsub(c, op, add):  #vers 1
    mode, reg = (op >> 3) & 7, op & 7
    dn = (op >> 9) & 7
    opm = (op >> 6) & 7
    f = c.add_op if add else c.sub_op
    if opm in (3, 7):
        size = 1 if opm == 3 else 2
        s = sext(c.rd(c.ea(mode, reg, size), size), size) & 0xFFFFFFFF
        c.a[dn] = (c.a[dn] + s if add else c.a[dn] - s) & 0xFFFFFFFF
        return
    size = opm & 3
    if opm >= 4 and mode in (0, 1):
        if mode == 0:
            c.wr(("d", dn), size, f(c.d[reg] & SIZE_MASK[size], c.d[dn] & SIZE_MASK[size], size, c.x, True, True))
        else:
            n = 2 if size == 0 and reg == 7 else SIZE_BYTES[size]
            c.a[reg] = (c.a[reg] - n) & 0xFFFFFFFF
            s = c.bus.read(c.a[reg], size)
            n = 2 if size == 0 and dn == 7 else SIZE_BYTES[size]
            c.a[dn] = (c.a[dn] - n) & 0xFFFFFFFF
            c.bus.write(c.a[dn], size, f(s, c.bus.read(c.a[dn], size), size, c.x, True, True))
        return
    o = c.ea(mode, reg, size)
    if opm < 4:
        c.wr(("d", dn), size, f(c.rd(o, size), c.d[dn] & SIZE_MASK[size], size))
    else:
        c.wr(o, size, f(c.d[dn] & SIZE_MASK[size], c.rd(o, size), size))


def _line9(c, op):  #vers 1
    _addsub(c, op, False)


def _lineD(c, op):  #vers 1
    _addsub(c, op, True)


def _lineB(c, op):  #vers 1
    mode, reg = (op >> 3) & 7, op & 7
    dn = (op >> 9) & 7
    opm = (op >> 6) & 7
    if opm in (3, 7):
        size = 1 if opm == 3 else 2
        s = sext(c.rd(c.ea(mode, reg, size), size), size) & 0xFFFFFFFF
        c.sub_op(s, c.a[dn], 2, x_flag=False)
        return
    size = opm & 3
    if opm < 3:
        c.sub_op(c.rd(c.ea(mode, reg, size), size), c.d[dn] & SIZE_MASK[size], size, x_flag=False)
    elif mode == 1:
        n = 2 if size == 0 and reg == 7 else SIZE_BYTES[size]
        s = c.bus.read(c.a[reg], size)
        c.a[reg] = (c.a[reg] + n) & 0xFFFFFFFF
        n = 2 if size == 0 and dn == 7 else SIZE_BYTES[size]
        d = c.bus.read(c.a[dn], size)
        c.a[dn] = (c.a[dn] + n) & 0xFFFFFFFF
        c.sub_op(s, d, size, x_flag=False)
    else:
        o = c.ea(mode, reg, size)
        r = c.rd(o, size) ^ (c.d[dn] & SIZE_MASK[size])
        c.logic_flags(r, size)
        c.wr(o, size, r)


def _lineC(c, op):  #vers 1
    mode, reg = (op >> 3) & 7, op & 7
    dn = (op >> 9) & 7
    if op & 0x1C0 == 0xC0:
        r = (c.rd(c.ea(mode, reg, 1), 1) * (c.d[dn] & 0xFFFF)) & 0xFFFFFFFF
        c.d[dn] = r
        c.logic_flags(r, 2)
        return
    if op & 0x1C0 == 0x1C0:
        r = (sext(c.rd(c.ea(mode, reg, 1), 1), 1) * sext(c.d[dn], 1)) & 0xFFFFFFFF
        c.d[dn] = r
        c.logic_flags(r, 2)
        return
    if op & 0x1F0 == 0x100:
        if op & 8:
            c.a[reg] = (c.a[reg] - 1) & 0xFFFFFFFF
            c.a[dn] = (c.a[dn] - 1) & 0xFFFFFFFF
            c.bus.w8(c.a[dn], _bcd_add(c, c.bus.r8(c.a[reg]), c.bus.r8(c.a[dn])))
        else:
            c.d[dn] = (c.d[dn] & ~0xFF) | _bcd_add(c, c.d[reg] & 0xFF, c.d[dn] & 0xFF)
        return
    k = op & 0x1F8
    if k == 0x140:
        c.d[dn], c.d[reg] = c.d[reg], c.d[dn]
        return
    if k == 0x148:
        c.a[dn], c.a[reg] = c.a[reg], c.a[dn]
        return
    if k == 0x188:
        c.d[dn], c.a[reg] = c.a[reg], c.d[dn]
        return
    size = (op >> 6) & 3
    o = c.ea(mode, reg, size)
    if op & 0x100:
        r = c.rd(o, size) & c.d[dn]
        c.logic_flags(r, size)
        c.wr(o, size, r)
    else:
        r = c.rd(o, size) & c.d[dn]
        c.logic_flags(r, size)
        c.wr(("d", dn), size, r)


def _shift(c, kind, left, val, count, size):  #vers 1
    """Shift or rotate val by count; returns the result and sets the flags."""
    bits = 8 << size
    m = SIZE_MASK[size]
    val &= m
    if kind == 0:
        if count == 0:
            c.v = c.c = 0
            r = val
        elif left:
            r = (val << count) & m
            c.c = c.x = (val >> (bits - count)) & 1 if count <= bits else 0
            if count < bits:
                ones = (1 << (count + 1)) - 1
                top = (val >> (bits - count - 1)) & ones
                c.v = 0 if top == 0 or top == ones else 1
            else:
                c.v = 1 if val else 0
        else:
            sv = sext(val, size)
            r = (sv >> min(count, bits)) & m
            c.c = c.x = (sv >> (count - 1)) & 1 if count <= bits else (1 if sv < 0 else 0)
            c.v = 0
    elif kind == 1:
        c.v = 0
        if count == 0:
            c.c = 0
            r = val
        elif left:
            r = (val << count) & m if count < bits else 0
            c.c = c.x = (val >> (bits - count)) & 1 if count <= bits else 0
        else:
            r = val >> count if count < bits else 0
            c.c = c.x = (val >> (count - 1)) & 1 if count <= bits else 0
    elif kind == 2:
        c.v = 0
        if count == 0:
            c.c = c.x
            r = val
        else:
            n = bits + 1
            comb = (c.x << bits) | val
            k = count % n
            if left:
                comb = ((comb << k) | (comb >> (n - k))) & ((1 << n) - 1)
            else:
                comb = ((comb >> k) | (comb << (n - k))) & ((1 << n) - 1)
            c.x = c.c = (comb >> bits) & 1
            r = comb & m
    else:
        c.v = 0
        if count == 0:
            c.c = 0
            r = val
        else:
            k = count % bits
            if left:
                r = ((val << k) | (val >> (bits - k))) & m if k else val
                c.c = r & 1
            else:
                r = ((val >> k) | (val << (bits - k))) & m if k else val
                c.c = (r >> (bits - 1)) & 1
    c.nz(r, size)
    return r


def _lineE(c, op):  #vers 1
    mode, reg = (op >> 3) & 7, op & 7
    if op & 0xF8C0 == 0xE8C0:
        return _bitfield(c, op)
    size = (op >> 6) & 3
    if size == 3:
        o = c.ea(mode, reg, 1)
        c.wr(o, 1, _shift(c, (op >> 9) & 3, bool(op & 0x100), c.rd(o, 1), 1, 1))
        return
    kind = (op >> 3) & 3
    if op & 0x20:
        count = c.d[(op >> 9) & 7] & 63
    else:
        count = (op >> 9) & 7 or 8
    c.wr(("d", reg), size, _shift(c, kind, bool(op & 0x100), c.d[reg], count, size))


def _bitfield(c, op):  #vers 1
    mode, reg = (op >> 3) & 7, op & 7
    ext = c.f16()
    kind = (op >> 8) & 7
    dn = (ext >> 12) & 7
    off = c.d[(ext >> 6) & 7] if ext & 0x800 else (ext >> 6) & 31
    off = sext(off, 2) if ext & 0x800 else off
    w = c.d[ext & 7] if ext & 0x20 else ext & 31
    w = (w & 31) or 32
    if mode == 0:
        sh = off & 31
        v = c.d[reg]
        rot = ((v << sh) | (v >> (32 - sh))) & 0xFFFFFFFF if sh else v
        field = rot >> (32 - w)
        mem = None
    else:
        o = c.ea(mode, reg, 2)[1]
        byte = o + (off >> 3)
        bo = off & 7
        nb = (bo + w + 7) // 8
        raw = 0
        for i in range(nb):
            raw = (raw << 8) | c.bus.r8(byte + i)
        shift = nb * 8 - bo - w
        field = (raw >> shift) & ((1 << w) - 1)
        mem = (byte, nb, shift, raw)
    c.n = (field >> (w - 1)) & 1
    c.z = 1 if field == 0 else 0
    c.v = c.c = 0
    fm = (1 << w) - 1
    if kind == 1:
        c.d[dn] = field
    elif kind == 3:
        c.d[dn] = (field - (1 << w) if field >> (w - 1) else field) & 0xFFFFFFFF
    elif kind == 5:
        r = 0
        for i in range(w):
            if (field >> (w - 1 - i)) & 1:
                break
            r += 1
        c.d[dn] = (off + r) & 0xFFFFFFFF
    if kind in (2, 4, 6, 7):
        new = {2: field ^ fm, 4: 0, 6: fm, 7: c.d[dn] & fm}[kind]
        if kind == 7:
            c.n = (new >> (w - 1)) & 1
            c.z = 1 if new == 0 else 0
        if mem is None:
            sh = off & 31
            v = c.d[reg]
            rot = ((v << sh) | (v >> (32 - sh))) & 0xFFFFFFFF if sh else v
            rot = (rot & ~(fm << (32 - w)) & 0xFFFFFFFF) | (new << (32 - w))
            c.d[reg] = ((rot >> sh) | (rot << (32 - sh))) & 0xFFFFFFFF if sh else rot
        else:
            byte, nb, shift, raw = mem
            raw = (raw & ~(fm << shift)) | (new << shift)
            for i in range(nb):
                c.bus.w8(byte + i, (raw >> (8 * (nb - 1 - i))) & 0xFF)


def _lineA(c, op):  #vers 1
    raise ExcVector(10)


def _lineF(c, op):  #vers 3
    if (op >> 9) & 7 == 1 and c.fpu is not None:
        try:
            if c.fpu.exec(c, op):
                return
        except FpuTrap as e:
            raise ExcVector(e.vec)
        raise ExcVector(11)
    if c.m40 and _line_f_040(c, op):
        return
    if c.m30 and not c.m40 and (op >> 9) & 7 == 0 and _pmmu(c, op):
        return
    raise ExcVector(11)


_LINES = [_line0, _move, _move, _move, _line4, _line5, _line6, _line7,
          _line8, _line9, _lineA, _lineB, _lineC, _lineD, _lineE, _lineF]


# ---- control registers, 68010 and up ----
_CR = {
    68010: {0x000: "sfc", 0x001: "dfc", 0x800: "usp", 0x801: "vbr"},
    68020: {0x002: "cacr", 0x802: "caar", 0x803: "msp", 0x804: "isp"},
    68040: {0x003: "tc", 0x004: "itt0", 0x005: "itt1", 0x006: "dtt0", 0x007: "dtt1", 0x805: "mmusr",
            0x806: "urp", 0x807: "srp"},
    68060: {0x008: "buscr", 0x808: "pcr"},
}


def _cr_name(c, num):  #vers 1
    for mdl, tab in _CR.items():
        if c.model >= mdl and num in tab:
            n = tab[num]
            if n == "caar" and c.m40:
                return None
            if n in ("msp",) and c.m60:
                return None
            if n == "isp" and c.m60:
                return None
            if n in ("cacr",) or n in ("usp", "vbr", "sfc", "dfc", "msp", "isp"):
                return n
            if n in ("tc", "itt0", "itt1", "dtt0", "dtt1", "mmusr", "urp", "srp") and not c.m40:
                return None
            if n in ("buscr", "pcr") and not c.m60:
                return None
            return n
    return None


def _movec(c, op):  #vers 1
    _supervisor(c)
    ext = c.f16()
    name = _cr_name(c, ext & 0xFFF)
    if name is None:
        raise IllegalInstruction("movec")
    r = (ext >> 12) & 7
    regs = c.a if ext & 0x8000 else c.d
    if op & 1:
        v = regs[r]
        if name == "vbr":
            c.vbr = v
        elif name == "sfc":
            c.sfc = v & 7
        elif name == "dfc":
            c.dfc = v & 7
        elif name == "usp":
            c.usp = v
        elif name in ("msp", "isp"):
            key = name[0]
            if c._bank() == key:
                c.a[7] = v
            else:
                c.sp[key] = v
        else:
            c.cr[name] = v
            if c.mmu is not None:
                c.mmu.update()
    else:
        if name == "vbr":
            v = c.vbr
        elif name == "sfc":
            v = c.sfc
        elif name == "dfc":
            v = c.dfc
        elif name == "usp":
            v = c.usp
        elif name in ("msp", "isp"):
            v = c.a[7] if c._bank() == name[0] else c.sp[name[0]]
        else:
            v = c.cr.get(name, 0)
        regs[r] = v & 0xFFFFFFFF


# ---- 68010 and 68020 additions on line 0 ----
def _line0_misc(c, op):  #vers 1
    if (op & 0xFF00) == 0x0E00 and ((op >> 6) & 3) != 3:
        return _moves(c, op)
    if op in (0x0CFC, 0x0EFC):
        return _cas2(c, op)
    group = (op >> 9) & 7
    if group in (5, 6, 7):
        return _cas(c, op)
    if group in (0, 1, 2) and (op & 0xF1C0) in (0x00C0, 0x02C0, 0x04C0):
        return _chk2(c, op)
    raise IllegalInstruction("line0")


def _moves(c, op):  #vers 1
    _supervisor(c)
    size = (op >> 6) & 3
    ext = c.f16()
    o = c.ea((op >> 3) & 7, op & 7, size)
    regs = c.a if ext & 0x8000 else c.d
    r = (ext >> 12) & 7
    if ext & 0x800:
        c.wr(o, size, regs[r])
    else:
        v = c.rd(o, size)
        if ext & 0x8000:
            regs[r] = sext(v, size) & 0xFFFFFFFF
        else:
            c.wr(("d", r), size, v)


def _cas(c, op):  #vers 1
    size = {5: 0, 6: 1, 7: 2}[(op >> 9) & 7]
    ext = c.f16()
    dc, du = ext & 7, (ext >> 6) & 7
    o = c.ea((op >> 3) & 7, op & 7, size)
    mem = c.rd(o, size)
    c.sub_op(c.d[dc] & SIZE_MASK[size], mem, size, x_flag=False)
    if c.z:
        c.wr(o, size, c.d[du])
    else:
        c.wr(("d", dc), size, mem)


def _cas2(c, op):  #vers 1
    if c.m60:
        raise ExcVector(61)
    size = 1 if op == 0x0CFC else 2
    e1, e2 = c.f16(), c.f16()
    rn1 = (c.a if e1 & 0x8000 else c.d)[(e1 >> 12) & 7]
    rn2 = (c.a if e2 & 0x8000 else c.d)[(e2 >> 12) & 7]
    dc1, du1, dc2, du2 = e1 & 7, (e1 >> 6) & 7, e2 & 7, (e2 >> 6) & 7
    m1, m2 = c.bus.read(rn1, size), c.bus.read(rn2, size)
    c.sub_op(c.d[dc1] & SIZE_MASK[size], m1, size, x_flag=False)
    if c.z:
        c.sub_op(c.d[dc2] & SIZE_MASK[size], m2, size, x_flag=False)
        if c.z:
            c.bus.write(rn1, size, c.d[du1])
            c.bus.write(rn2, size, c.d[du2])
            return
    c.wr(("d", dc1), size, m1)
    c.wr(("d", dc2), size, m2)


def _chk2(c, op):  #vers 1
    if c.m60:
        raise ExcVector(61)
    size = (op >> 9) & 3
    ext = c.f16()
    ad = c.ea((op >> 3) & 7, op & 7, size)[1]
    n = SIZE_BYTES[size]
    lo, hi = c.bus.read(ad, size), c.bus.read(ad + n, size)
    r = (c.a if ext & 0x8000 else c.d)[(ext >> 12) & 7]
    if ext & 0x8000:
        cmp_v, lo, hi = r, sext(lo, size) & 0xFFFFFFFF, sext(hi, size) & 0xFFFFFFFF
        slo, shi, sv = sext(lo, 2), sext(hi, 2), sext(r, 2)
    else:
        cmp_v = r & SIZE_MASK[size]
        slo, shi, sv = sext(lo, size), sext(hi, size), sext(cmp_v, size)
    if lo <= hi:
        inside = lo <= cmp_v <= hi
    else:
        inside = slo <= sv <= shi
    c.z = 1 if cmp_v == lo or cmp_v == hi else 0
    c.c = 0 if inside else 1
    if ext & 0x800 and c.c:
        c.exception(6)


# ---- 68030 PMMU registers (no address translation yet) ----
def _pmmu(c, op):  #vers 2
    """PMOVE, PFLUSH, PLOAD, PTEST: values kept in c.cr; privileged."""
    _supervisor(c)
    ext = c.f16()
    top = ext >> 13
    mode, reg = (op >> 3) & 7, op & 7
    preg = (ext >> 10) & 7
    if top in (0, 2, 3) and (top, preg) in ((0, 2), (0, 3), (2, 0), (2, 2), (2, 3), (3, 0)):
        name = {(0, 2): "tt0", (0, 3): "tt1", (2, 0): "tc", (2, 2): "srp", (2, 3): "crp", (3, 0): "mmusr"}[(top, preg)]
        quad = name in ("srp", "crp")
        size = 1 if name == "mmusr" else 2
        o = c.ea(mode, reg, size)
        if ext & 0x200:
            v = c.cr.get(name, 0)
            if quad:
                c.bus.w32(o[1], v >> 32)
                c.bus.w32(o[1] + 4, v & 0xFFFFFFFF)
            else:
                c.wr(o, size, v)
        elif quad:
            c.cr[name] = (c.bus.r32(o[1]) << 32) | c.bus.r32(o[1] + 4)
        else:
            c.cr[name] = c.rd(o, size)
        if not ext & 0x200 and name != "mmusr":
            c.mmu.update()
        return True
    if top == 1:
        if (ext >> 10) & 7 in (0, 1, 2) and mode > 1:
            c.ea(mode, reg, 2)
        c.mmu.flush()
        return True
    if top == 4:
        fcf = ext & 31
        fc = (c.sfc if fcf == 0 else c.dfc if fcf == 1 else c.d[fcf & 7] if fcf >> 3 == 1 else fcf & 7) & 7
        la = c.ea(mode, reg, 2)[1] if mode > 1 else c.a[reg]
        phys, wp, tt, sv = c.mmu.probe(la, not ext & 0x200, bool(fc & 4)) if c.mmu.on else (la, False, True, False)
        psr = (0x8000 if phys is None and not sv else 0) | (0x2000 if sv else 0) | (0x800 if wp else 0) | \
              (0x400 if phys is None else 0) | (0x100 if tt else 0)
        c.cr["mmusr"] = psr
        return True
    return False


# ---- 68040 and 68060 line F: cache, MMU maintenance, MOVE16, LPSTOP ----
def _line_f_040(c, op):  #vers 2
    hi = op & 0xFF00
    if hi == 0xF400 and (op & 0x00C0) and (op & 0x0018):
        _supervisor(c)
        return True
    if op & 0xFFF8 in (0xF508, 0xF510, 0xF518, 0xF520):
        _supervisor(c)
        c.mmu.flush()
        return True
    if op & 0xFFF8 in (0xF548, 0xF568):
        _supervisor(c)
        _ptest040(c, op)
        return True
    if c.m60 and op & 0xFFF8 in (0xF588, 0xF5C8):
        _supervisor(c)
        phys, wp, tt, sv = c.mmu.probe(c.a[op & 7], op & 0x40 == 0, bool(c.dfc & 4))
        if phys is not None:
            c.a[op & 7] = phys
        return True
    if op & 0xFFF8 == 0xF620 or op & 0xFFE0 == 0xF600:
        return _move16(c, op)
    if op == 0xF800 and c.m60:
        _supervisor(c)
        if c.f16() != 0x01C0:
            raise IllegalInstruction("lpstop")
        c.set_sr(c.f16())
        c.stopped = True
        return True
    return False


def _ptest040(c, op):  #vers 1
    """PTESTR/PTESTW: result in MMUSR."""
    la = c.a[op & 7]
    phys, wp, tt, sv = c.mmu.probe(la, op & 0x20 == 0, bool(c.dfc & 4))
    r = 0
    if phys is None:
        r = 0x800 | (0x80 if sv else 0)
    else:
        r = (phys & ~0xFFF) | 1 | (2 if tt else 0) | (4 if wp else 0)
    c.cr["mmusr"] = r


def _move16(c, op):  #vers 1
    reg = op & 7
    if op & 0xFFF8 == 0xF620:
        ay = (c.f16() >> 12) & 7
        src, dst = c.a[reg] & ~15, c.a[ay] & ~15
        c.a[reg] = (c.a[reg] + 16) & 0xFFFFFFFF
        if ay != reg:
            c.a[ay] = (c.a[ay] + 16) & 0xFFFFFFFF
    else:
        ad = c.f32() & ~15
        kind = (op >> 3) & 3
        an = c.a[reg] & ~15
        src, dst = [(an, ad), (ad, an), (an, ad), (ad, an)][kind]
        if kind < 2:
            c.a[reg] = (c.a[reg] + 16) & 0xFFFFFFFF
    buf = [c.bus.r32(src + i) for i in range(0, 16, 4)]
    for i, v in enumerate(buf):
        c.bus.w32(dst + 4 * i, v)
    return True
