#this belongs in apps/core/fpu.py - Version: 1
# X-Seti - November 17 2026 - Morosa - Morosa 68881/68882/68040/68060 FPU.

"""
Morosa FPU - floating point unit for the Morosa 68k core. Values are Python doubles, not 80-bit extended.
"""

##Methods list -
# FPU
# FPU.cond
# FPU.exec
# FPU.fmovecr
# FPU.from_ext
# FPU.from_packed
# FPU.get_ctl
# FPU.load
# FPU.monadic
# FPU.reset
# FPU.round_int
# FPU.set_cc
# FPU.set_ctl
# FPU.store
# FPU.to_ext
# FPU.to_packed
# FpuTrap

import math
import struct
from decimal import Decimal, getcontext

BSUN, SNAN, OPERR, OVFL, UNFL, DZ, INEX2, INEX1 = (1 << n for n in (15, 14, 13, 12, 11, 10, 9, 8))
_TRAP_VEC = ((BSUN, 48), (SNAN, 54), (OPERR, 52), (OVFL, 53), (UNFL, 51), (DZ, 50), (INEX2 | INEX1, 49))
_FMT_BYTES = {0: 4, 1: 4, 2: 12, 3: 12, 4: 2, 5: 8, 6: 1, 7: 12}

_ROM = {0x00: math.pi, 0x0B: math.log10(2), 0x0C: math.e, 0x0D: math.log2(math.e), 0x0E: math.log10(math.e),
        0x0F: 0.0, 0x30: math.log(2), 0x31: math.log(10), 0x32: 1.0}
for _i, _p in enumerate((1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096)):
    _ROM[0x33 + _i] = 10.0 ** _p if _p < 309 else math.inf

_MONO = {0x00: "move", 0x01: "int", 0x02: "sinh", 0x03: "intrz", 0x04: "sqrt", 0x06: "lognp1", 0x08: "etoxm1",
         0x09: "tanh", 0x0A: "atan", 0x0C: "asin", 0x0D: "atanh", 0x0E: "sin", 0x0F: "tan", 0x10: "etox",
         0x11: "twotox", 0x12: "tentox", 0x14: "logn", 0x15: "log10", 0x16: "log2", 0x18: "abs", 0x19: "cosh",
         0x1A: "neg", 0x1C: "acos", 0x1D: "cos", 0x1E: "getexp", 0x1F: "getman"}
_DYAD = {0x20: "div", 0x21: "mod", 0x22: "add", 0x23: "mul", 0x24: "sgldiv", 0x25: "rem", 0x26: "scale",
         0x27: "sglmul", 0x28: "sub"}
# 68040/68060 forced precision forms: opmode -> (base opmode, precision 1 single / 2 double)
_FORCED = {0x40: (0x00, 1), 0x41: (0x04, 1), 0x44: (0x00, 2), 0x45: (0x04, 2), 0x58: (0x18, 1), 0x5A: (0x1A, 1),
           0x5C: (0x18, 2), 0x5E: (0x1A, 2), 0x60: (0x20, 1), 0x62: (0x22, 1), 0x63: (0x23, 1), 0x64: (0x20, 2),
           0x66: (0x22, 2), 0x67: (0x23, 2), 0x68: (0x28, 1), 0x6C: (0x28, 2)}


class FpuTrap(Exception):
    """An enabled FPU exception: take this vector."""

    def __init__(self, vec):
        super().__init__(vec)
        self.vec = vec


def _sext(v, bits):
    return v - (1 << bits) if v & (1 << (bits - 1)) else v


class FPU:
    """FP0-FP7, FPCR, FPSR, FPIAR; double precision arithmetic."""

    def __init__(self, model=68040):  #vers 1
        self.model = model
        self.reset()

    def reset(self) -> None:  #vers 1
        self.fp = [math.nan] * 8
        self.fpcr = 0
        self.fpsr = 0
        self.fpiar = 0

    # ---- conversions ----
    def to_ext(self, x: float) -> bytes:  #vers 1
        sign = 0x8000 if math.copysign(1.0, x) < 0 else 0
        if math.isnan(x):
            return struct.pack(">HHQ", sign | 0x7FFF, 0, 0xC000000000000000)
        if math.isinf(x):
            return struct.pack(">HHQ", sign | 0x7FFF, 0, 0)
        if x == 0:
            return struct.pack(">HHQ", sign, 0, 0)
        m, e = math.frexp(abs(x))
        return struct.pack(">HHQ", sign | (e - 1 + 0x3FFF), 0, int(m * (1 << 64)) & 0xFFFFFFFFFFFFFFFF)

    def from_ext(self, b: bytes) -> float:  #vers 1
        se, _, mant = struct.unpack(">HHQ", b)
        neg = se & 0x8000
        e = se & 0x7FFF
        if e == 0x7FFF:
            v = math.inf if mant << 1 & 0xFFFFFFFFFFFFFFFF == 0 else math.nan
        elif mant == 0:
            v = 0.0
        else:
            try:
                v = math.ldexp(mant, e - 0x3FFF - 63)
            except OverflowError:
                v = math.inf
        return -v if neg else v

    def to_packed(self, x: float, k: int) -> bytes:  #vers 1
        neg = math.copysign(1.0, x) < 0
        if math.isnan(x) or math.isinf(x):
            hi = 0x7FFF0000 | (0x80000000 if neg else 0)
            return struct.pack(">IQ", hi, 0 if math.isinf(x) else 0xFFFFFFFFFFFFFFFF)
        getcontext().prec = 40
        d = abs(Decimal(x))
        if d == 0:
            exp = 0
            digs = "0" * 17
        else:
            exp = d.adjusted()
            nd = 17 if k >= 0 or k < -64 else 17
            if 0 < k <= 17:
                nd = k
            q = d.scaleb(-exp)
            digs = format(q, f".{max(nd - 1, 0)}f").replace(".", "")
            if len(digs) > 17:
                exp += 1
                digs = digs[:17]
            digs = digs.ljust(17, "0")
        ex = abs(exp)
        word = (0x8 if neg else 0) | (0x4 if exp < 0 else 0)
        hi = word << 28 | (ex // 100 % 10) << 24 | (ex // 10 % 10) << 20 | (ex % 10) << 16 | (ex // 1000 % 10) << 12
        hi |= int(digs[0])
        lo = int(digs[1:], 16)
        return struct.pack(">IQ", hi, lo)

    def from_packed(self, b: bytes) -> float:  #vers 1
        hi, lo = struct.unpack(">IQ", b)
        neg = hi >> 31 & 1
        eneg = hi >> 30 & 1
        if hi >> 16 & 0x7FFF == 0x7FFF:
            v = math.inf if lo == 0 else math.nan
            return -v if neg else v
        ex = (hi >> 12 & 0xF) * 1000 + (hi >> 24 & 0xF) * 100 + (hi >> 20 & 0xF) * 10 + (hi >> 16 & 0xF)
        digs = str(hi & 0xF) + format(lo, "016x")
        try:
            v = float(Decimal(digs[0] + "." + digs[1:]).scaleb(-ex if eneg else ex))
        except Exception:
            v = math.nan
        return -v if neg else v

    # ---- status ----
    def set_cc(self, x: float) -> None:  #vers 1
        n = math.copysign(1.0, x) < 0
        fl = 0
        if math.isnan(x):
            fl = 1 << 24
        elif x == 0:
            fl = 1 << 26
        elif math.isinf(x):
            fl = 1 << 25
        if n:
            fl |= 1 << 27
        self.fpsr = (self.fpsr & 0x00FFFFFF) | fl

    def cond(self, cc: int) -> bool:  #vers 1
        n, z, i, nan = (self.fpsr >> 27 & 1, self.fpsr >> 26 & 1, self.fpsr >> 25 & 1, self.fpsr >> 24 & 1)
        k = cc & 15
        r = (False, z, not (nan or z or n), z or not (nan or n), n and not (nan or z), z or (n and not nan),
             not (nan or z), not nan, nan, nan or z, nan or not (n or z), nan or z or not n, nan or (n and not z),
             nan or z or n, not z, True)[k]
        if cc & 16 and nan:
            self.fpsr |= BSUN
            self._accrue()
        return bool(r)

    def _accrue(self) -> None:  #vers 1
        s = self.fpsr
        a = 0
        if s & (BSUN | SNAN | OPERR):
            a |= 0x80
        if s & OVFL:
            a |= 0x40
        if s & UNFL:
            a |= 0x20
        if s & DZ:
            a |= 0x10
        if s & (INEX2 | INEX1 | OVFL):
            a |= 0x08
        self.fpsr |= a

    def _check(self) -> None:  #vers 1
        self._accrue()
        en = self.fpcr & 0xFF00
        hit = self.fpsr & en
        if hit:
            for bit, vec in _TRAP_VEC:
                if hit & bit:
                    raise FpuTrap(vec)

    def get_ctl(self, n: int) -> int:  #vers 1
        return (self.fpcr, self.fpsr, self.fpiar)[n] & 0xFFFFFFFF

    def set_ctl(self, n: int, v: int) -> None:  #vers 1
        if n == 0:
            self.fpcr = v & 0xFFFF
        elif n == 1:
            self.fpsr = v & 0x0FFFFFFF
        else:
            self.fpiar = v & 0xFFFFFFFF

    def round_int(self, x: float, mode: int = None) -> float:  #vers 1
        if math.isnan(x) or math.isinf(x):
            return x
        mode = (self.fpcr >> 4 & 3) if mode is None else mode
        r = (round, math.trunc, math.floor, math.ceil)[mode](x)
        return math.copysign(float(r), x) if r == 0 else float(r)

    def fmovecr(self, off: int) -> float:  #vers 1
        return _ROM.get(off, 0.0)

    # ---- arithmetic ----
    def _prec(self, x: float, prec: int) -> float:  #vers 1
        if prec == 1 and not (math.isnan(x) or math.isinf(x)):
            try:
                y = struct.unpack(">f", struct.pack(">f", x))[0]
            except OverflowError:
                self.fpsr |= OVFL | INEX2
                return math.copysign(math.inf, x)
            if y != x:
                self.fpsr |= INEX2
            return y
        if prec == 2 and abs(x) < 5e-324 and x != 0:
            self.fpsr |= UNFL
        return x

    def monadic(self, name: str, x: float) -> float:  #vers 1
        if name == "move":
            return x
        if math.isnan(x):
            return x
        try:
            if name == "int":
                return self.round_int(x)
            if name == "intrz":
                return self.round_int(x, 1)
            if name == "abs":
                return abs(x)
            if name == "neg":
                return -x
            if name == "sqrt":
                if x < 0:
                    self.fpsr |= OPERR
                    return math.nan
                return math.sqrt(x)
            if name == "getexp":
                if math.isinf(x):
                    self.fpsr |= OPERR
                    return math.nan
                return 0.0 if x == 0 else float(math.frexp(x)[1] - 1)
            if name == "getman":
                if math.isinf(x):
                    self.fpsr |= OPERR
                    return math.nan
                return x if x == 0 else math.frexp(x)[0] * 2.0
            if name in ("logn", "log10", "log2", "lognp1"):
                lim = -1.0 if name == "lognp1" else 0.0
                if x == lim:
                    self.fpsr |= DZ
                    return -math.inf
                if x < lim:
                    self.fpsr |= OPERR
                    return math.nan
                return {"logn": math.log, "log10": math.log10, "log2": math.log2, "lognp1": math.log1p}[name](x)
            if name in ("asin", "acos") and abs(x) > 1:
                self.fpsr |= OPERR
                return math.nan
            if name == "atanh":
                if abs(x) == 1:
                    self.fpsr |= DZ
                    return math.copysign(math.inf, x)
                if abs(x) > 1:
                    self.fpsr |= OPERR
                    return math.nan
            if name in ("sin", "cos", "tan") and math.isinf(x):
                self.fpsr |= OPERR
                return math.nan
            if name == "twotox":
                return 2.0 ** x
            if name == "tentox":
                return 10.0 ** x
            f = {"sinh": math.sinh, "tanh": math.tanh, "atan": math.atan, "asin": math.asin, "atanh": math.atanh,
                 "sin": math.sin, "tan": math.tan, "etox": math.exp, "etoxm1": math.expm1, "cosh": math.cosh,
                 "acos": math.acos, "cos": math.cos}[name]
            return f(x)
        except OverflowError:
            self.fpsr |= OVFL | INEX2
            return math.inf if name != "sinh" or x > 0 else -math.inf

    def _dyadic(self, name: str, src: float, dst: float) -> float:  #vers 1
        nan = math.isnan(src) or math.isnan(dst)
        if nan and name != "cmp":
            return math.nan
        try:
            if name in ("add",):
                if math.isinf(src) and math.isinf(dst) and src != dst:
                    self.fpsr |= OPERR
                    return math.nan
                return dst + src
            if name == "sub":
                if math.isinf(src) and math.isinf(dst) and src == dst:
                    self.fpsr |= OPERR
                    return math.nan
                return dst - src
            if name in ("mul", "sglmul"):
                if (math.isinf(src) and dst == 0) or (math.isinf(dst) and src == 0):
                    self.fpsr |= OPERR
                    return math.nan
                return dst * src
            if name in ("div", "sgldiv"):
                if src == 0:
                    if dst == 0:
                        self.fpsr |= OPERR
                        return math.nan
                    self.fpsr |= DZ
                    return math.copysign(math.inf, dst) * math.copysign(1.0, src)
                if math.isinf(src) and math.isinf(dst):
                    self.fpsr |= OPERR
                    return math.nan
                return dst / src
            if name in ("mod", "rem"):
                if src == 0 or math.isinf(dst):
                    self.fpsr |= OPERR
                    return math.nan
                if math.isinf(src):
                    return dst
                r = math.fmod(dst, src) if name == "mod" else math.remainder(dst, src)
                q = int(round((dst - r) / src)) if name == "rem" else math.trunc(dst / src)
                self.fpsr = (self.fpsr & 0xFF00FFFF) | (abs(q) & 0x7F) << 16 | (0x800000 if (dst < 0) != (src < 0) else 0)
                return r
            if name == "scale":
                if math.isinf(src):
                    self.fpsr |= OPERR
                    return math.nan
                return math.ldexp(dst, max(-100000, min(100000, math.trunc(src))))
        except OverflowError:
            self.fpsr |= OVFL | INEX2
            return math.inf
        raise ValueError(name)

    # ---- memory transfers ----
    def load(self, c, fmt: int, kind, mode: int, reg: int) -> float:  #vers 1
        """Read a source operand of format fmt from the effective address."""
        n = _FMT_BYTES[fmt]
        if mode == 0:
            if fmt not in (0, 1, 4, 6):
                raise ValueError("dn")
            return self._conv_in(fmt, c.d[reg].to_bytes(4, "big")[4 - n:])
        if mode == 7 and reg == 4:
            raw = b"".join(c.f16().to_bytes(2, "big") for _ in range(max(n // 2, 1)))
            return self._conv_in(fmt, raw[1:] if n == 1 else raw)
        if mode == 3:
            ad = c.a[reg]
            c.a[reg] = (ad + (2 if reg == 7 and n == 1 else n)) & 0xFFFFFFFF
        elif mode == 4:
            c.a[reg] = (c.a[reg] - (2 if reg == 7 and n == 1 else n)) & 0xFFFFFFFF
            ad = c.a[reg]
        else:
            ad = c.ea(mode, reg, 2)[1]
        raw = bytes(c.bus.r8(ad + i) for i in range(n))
        return self._conv_in(fmt, raw)

    def _conv_in(self, fmt: int, raw: bytes) -> float:  #vers 1
        if fmt == 0:
            return float(_sext(int.from_bytes(raw, "big"), 32))
        if fmt == 4:
            return float(_sext(int.from_bytes(raw, "big"), 16))
        if fmt == 6:
            return float(_sext(raw[0], 8))
        if fmt == 1:
            return struct.unpack(">f", raw)[0]
        if fmt == 5:
            return struct.unpack(">d", raw)[0]
        if fmt == 2:
            return self.from_ext(raw)
        return self.from_packed(raw)

    def store(self, c, fmt: int, x: float, kind, mode: int, reg: int, k: int = 0) -> None:  #vers 1
        n = _FMT_BYTES[fmt]
        raw = self._conv_out(fmt, x, k)
        if mode == 0:
            m = (1 << 8 * n) - 1
            v = int.from_bytes(raw, "big")
            c.d[reg] = (c.d[reg] & ~m & 0xFFFFFFFF) | v if fmt in (4, 6) else v
            return
        if mode == 3:
            ad = c.a[reg]
            c.a[reg] = (ad + (2 if reg == 7 and n == 1 else n)) & 0xFFFFFFFF
        elif mode == 4:
            c.a[reg] = (c.a[reg] - (2 if reg == 7 and n == 1 else n)) & 0xFFFFFFFF
            ad = c.a[reg]
        else:
            ad = c.ea(mode, reg, 2)[1]
        for i, b in enumerate(raw):
            c.bus.w8(ad + i, b)

    def _conv_out(self, fmt: int, x: float, k: int) -> bytes:  #vers 1
        if fmt in (0, 4, 6):
            bits = {0: 32, 4: 16, 6: 8}[fmt]
            hi, lo = (1 << bits - 1) - 1, -(1 << bits - 1)
            if math.isnan(x):
                self.fpsr |= OPERR
                v = hi
            elif math.isinf(x):
                self.fpsr |= OPERR
                v = hi if x > 0 else lo
            else:
                r = int(self.round_int(x))
                if r != x:
                    self.fpsr |= INEX2
                v = r
                if v > hi or v < lo:
                    self.fpsr |= OPERR
                    v = hi if v > 0 else lo
            return (v & ((1 << bits) - 1)).to_bytes(bits // 8, "big")
        if fmt == 1:
            try:
                return struct.pack(">f", x)
            except OverflowError:
                self.fpsr |= OVFL | INEX2
                return struct.pack(">f", math.copysign(math.inf, x))
        if fmt == 5:
            return struct.pack(">d", x)
        if fmt == 2:
            return self.to_ext(x)
        return self.to_packed(x, _sext(k & 0x7F, 7))

    # ---- instruction decode ----
    def exec(self, c, op: int) -> bool:  #vers 1
        """Run one coprocessor-1 instruction; False if illegal."""
        kind = (op >> 6) & 7
        if kind == 0:
            return self._general(c, op)
        if kind == 1:
            return self._scc_group(c, op)
        if kind in (2, 3):
            self._branch(c, op)
            return True
        if kind == 4:
            return self._save(c, op)
        if kind == 5:
            return self._restore(c, op)
        return False

    def _branch(self, c, op: int) -> None:  #vers 1
        start = c.pc
        disp = _sext(c.f16(), 16) if (op >> 6) & 1 == 0 else _sext(c.f32(), 32)
        if self.cond(op & 0x3F):
            c.pc = (start + disp) & 0xFFFFFFFF
        self._check()

    def _scc_group(self, c, op: int) -> bool:  #vers 1
        mode, reg = (op >> 3) & 7, op & 7
        ext = c.f16()
        cc = ext & 0x3F
        if mode == 1:
            base = c.pc
            disp = _sext(c.f16(), 16)
            if not self.cond(cc):
                c.d[reg] = (c.d[reg] & 0xFFFF0000) | ((c.d[reg] - 1) & 0xFFFF)
                if c.d[reg] & 0xFFFF != 0xFFFF:
                    c.pc = (base + disp) & 0xFFFFFFFF
            self._check()
            return True
        if mode == 7 and reg in (2, 3, 4):
            if reg == 2:
                c.f16()
            elif reg == 3:
                c.f32()
            if self.cond(cc):
                from apps.core.cpu import ExcVector
                raise ExcVector(7)
            self._check()
            return True
        if mode == 1 or (mode == 7 and reg > 1):
            return False
        t = 0xFF if self.cond(cc) else 0
        dst = c.ea(mode, reg, 0)
        c.wr(dst, 0, t)
        self._check()
        return True

    def _save(self, c, op: int) -> bool:  #vers 1
        mode, reg = (op >> 3) & 7, op & 7
        if mode in (0, 1, 3) or (mode == 7 and reg > 1):
            return False
        frame = (0x41000000,) if c.m40 and not c.m60 else (0x60000000,) if c.m60 else \
            (0x1F180000,) + (0,) * 6
        if mode == 4:
            for v in frame[::-1]:
                c.a[reg] = (c.a[reg] - 4) & 0xFFFFFFFF
                c.bus.w32(c.a[reg], v)
        else:
            ad = c.ea(mode, reg, 2)[1]
            for i, v in enumerate(frame):
                c.bus.w32(ad + 4 * i, v)
        return True

    def _restore(self, c, op: int) -> bool:  #vers 1
        mode, reg = (op >> 3) & 7, op & 7
        if mode in (0, 1, 4) or (mode == 7 and reg == 4):
            return False
        if mode == 3:
            ad = c.a[reg]
        else:
            ad = c.ea(mode, reg, 2)[1]
        head = c.bus.r32(ad)
        size = 4 if c.m40 else 4 + (head >> 16 & 0xFF)
        if head >> 24 == 0:
            size = 4
            self.reset()
        if mode == 3:
            c.a[reg] = (c.a[reg] + size) & 0xFFFFFFFF
        return True

    def _general(self, c, op: int) -> bool:  #vers 1
        mode, reg = (op >> 3) & 7, op & 7
        ext = c.f16()
        cls = ext >> 13
        self.fpsr &= ~0xFF00
        if cls in (0, 2):
            ok = self._arith(c, ext, cls, mode, reg)
            if ok:
                self._check()
            return ok
        if cls == 3:
            fmt = ext >> 10 & 7
            x = self.fp[ext >> 7 & 7]
            if mode == 1 or (mode == 0 and fmt not in (0, 1, 4, 6)):
                return False
            if mode == 7 and reg in (2, 3, 4):
                return False
            self.store(c, fmt, x, None, mode, reg, ext & 0x7F if fmt == 3 else c.d[ext >> 4 & 7] if fmt == 7 else 0)
            self._check()
            return True
        if cls in (4, 5):
            return self._ctlregs(c, ext, cls, mode, reg)
        return self._movem(c, ext, cls, mode, reg)

    def _arith(self, c, ext: int, cls: int, mode: int, reg: int) -> bool:  #vers 1
        dst = ext >> 7 & 7
        opm = ext & 0x7F
        if cls == 0:
            src = self.fp[ext >> 10 & 7]
        else:
            fmt = ext >> 10 & 7
            if (ext & 0x1C00) == 0x1C00 and mode == 0 and reg == 0:
                self.fp[dst] = self.fmovecr(opm)
                self.set_cc(self.fp[dst])
                return True
            if mode == 1:
                return False
            try:
                src = self.load(c, fmt, None, mode, reg)
            except ValueError:
                return False
        prec = self.fpcr >> 6 & 3
        if opm in _FORCED:
            if not c.m40:
                return False
            opm, prec = _FORCED[opm]
        if opm in _MONO:
            r = self.monadic(_MONO[opm], src)
            r = self._prec(r, prec)
            self.fp[dst] = r
            self.set_cc(r)
            return True
        if 0x30 <= opm <= 0x37:
            s = self.monadic("sin", src)
            self.fp[opm & 7] = self.monadic("cos", src)
            self.fp[dst] = s
            self.set_cc(s)
            return True
        if opm in _DYAD:
            r = self._dyadic(_DYAD[opm], src, self.fp[dst])
            if opm == 0x24 or opm == 0x27:
                prec = 1
            r = self._prec(r, prec)
            self.fp[dst] = r
            self.set_cc(r)
            return True
        if opm == 0x38:
            d = self.fp[dst]
            if math.isnan(src) or math.isnan(d):
                self.set_cc(math.nan)
                return True
            r = d - src if not (math.isinf(d) and d == src) else 0.0
            self.set_cc(r)
            return True
        if opm == 0x3A:
            self.set_cc(src)
            return True
        return False

    def _ctlregs(self, c, ext: int, cls: int, mode: int, reg: int) -> bool:  #vers 1
        regs = [i for i, m in enumerate((4, 2, 1)) if ext >> 10 & 7 & m]
        n = len(regs)
        if n == 0 or (mode in (0, 1) and n != 1) :
            return False
        if mode == 1 and regs[0] != 2:
            return False
        if cls == 5 and mode == 7 and reg in (2, 3, 4):
            return False
        if cls == 4 and mode == 7 and reg == 4:
            for r in regs:
                self.set_ctl(r, c.f32())
            return True
        if mode in (0, 1):
            if cls == 4:
                self.set_ctl(regs[0], c.d[reg] if mode == 0 else c.a[reg])
            else:
                (c.d if mode == 0 else c.a)[reg] = self.get_ctl(regs[0])
            return True
        if mode == 3:
            ad = c.a[reg]
            c.a[reg] = (ad + 4 * n) & 0xFFFFFFFF
        elif mode == 4:
            c.a[reg] = (c.a[reg] - 4 * n) & 0xFFFFFFFF
            ad = c.a[reg]
        else:
            ad = c.ea(mode, reg, 2)[1]
        for r in regs:
            if cls == 4:
                self.set_ctl(r, c.bus.r32(ad))
            else:
                c.bus.w32(ad, self.get_ctl(r))
            ad += 4
        return True

    def _movem(self, c, ext: int, cls: int, mode: int, reg: int) -> bool:  #vers 1
        if mode in (0, 1) or (cls == 6 and mode == 4) or (cls == 7 and mode == 3):
            return False
        if cls == 7 and mode == 7 or (cls == 6 and mode == 7 and reg == 4):
            return False
        lst = c.d[ext >> 4 & 7] & 0xFF if ext >> 11 & 1 else ext & 0xFF
        if cls == 7 and mode == 4:
            regs = [i for i in range(8) if lst & (1 << i)]
        else:
            regs = [i for i in range(8) if lst & (0x80 >> i)]
        n = len(regs)
        if mode == 3:
            ad = c.a[reg]
            c.a[reg] = (ad + 12 * n) & 0xFFFFFFFF
        elif mode == 4:
            c.a[reg] = (c.a[reg] - 12 * n) & 0xFFFFFFFF
            ad = c.a[reg]
        else:
            ad = c.ea(mode, reg, 2)[1]
        for r in regs:
            if cls == 6:
                self.fp[r] = self.from_ext(bytes(c.bus.r8(ad + i) for i in range(12)))
            else:
                for i, b in enumerate(self.to_ext(self.fp[r])):
                    c.bus.w8(ad + i, b)
            ad += 12
        return True
