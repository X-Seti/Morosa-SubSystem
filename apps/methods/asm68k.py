#this belongs in apps/methods/asm68k.py - Version: 1
# X-Seti - November 23 2026 - Morosa - Tiny 68000 Assembler.

"""
Tiny 68000 Assembler - emits the few instructions the host filesystem boot ROM and handler need.
"""

##Methods list -
##class Asm: -
# __init__
# addr
# bcc
# bytes
# ea
# jsr
# label
# lea
# move
# moveq
# movem_load
# movem_save
# raw
# tst_l

import struct

# operand forms: ("d", n) ("a", n) ("ind", n) ("post", n) ("pre", n) ("dis", n, disp)
#                ("imm", v) ("abs", addr) ("absw", addr) ("pc", label)
SIZE = {"b": 0x1000, "w": 0x3000, "l": 0x2000}


class Asm:
    """Collects words and label fixups; bytes() resolves PC-relative references."""

    def __init__(self):  #vers 1
        self.out = bytearray()
        self.labels = {}
        self.fix = []

    def addr(self) -> int:  #vers 1
        return len(self.out)

    def label(self, name: str) -> None:  #vers 1
        self.labels[name] = len(self.out)

    def raw(self, *words: int) -> None:  #vers 1
        for w in words:
            self.out += struct.pack(">H", w & 0xFFFF)

    def ea(self, op: tuple, size: str = "l") -> tuple:  #vers 1
        """(mode/reg field, extension words or fixups)."""
        k = op[0]
        if k == "d":
            return op[1], []
        if k == "a":
            return 8 | op[1], []
        if k == "ind":
            return 16 | op[1], []
        if k == "post":
            return 24 | op[1], []
        if k == "pre":
            return 32 | op[1], []
        if k == "dis":
            return 40 | op[1], [("w", op[2])]
        if k == "absw":
            return 56, [("w", op[1])]
        if k == "abs":
            return 57, [("l", op[1])]
        if k == "pc":
            return 58, [("pc", op[1])]
        if k == "imm":
            return 60, [("l" if size == "l" else "w", op[1])]
        raise ValueError(op)

    def _ext(self, items: list) -> None:  #vers 1
        for kind, v in items:
            if kind == "w":
                self.out += struct.pack(">H", v & 0xFFFF)
            elif kind == "l":
                self.out += struct.pack(">I", v & 0xFFFFFFFF)
            else:
                self.fix.append((len(self.out), v))
                self.out += b"\0\0"

    def move(self, size: str, src: tuple, dst: tuple) -> None:  #vers 1
        s, se = self.ea(src, size)
        d, de = self.ea(dst, size)
        self.raw(SIZE[size] | ((d & 7) << 9) | ((d >> 3) << 6) | s)
        self._ext(se)
        self._ext(de)

    def moveq(self, value: int, dn: int) -> None:  #vers 1
        self.raw(0x7000 | dn << 9 | value & 0xFF)

    def lea(self, src: tuple, an: int) -> None:  #vers 1
        s, se = self.ea(src)
        self.raw(0x41C0 | an << 9 | s)
        self._ext(se)

    def jsr(self, op: tuple) -> None:  #vers 1
        s, se = self.ea(op)
        self.raw(0x4E80 | s)
        self._ext(se)

    def tst_l(self, op: tuple) -> None:  #vers 1
        s, se = self.ea(op)
        self.raw(0x4A80 | s)
        self._ext(se)

    def bcc(self, cond: str, label: str) -> None:  #vers 1
        code = {"ra": 0x6000, "eq": 0x6700, "ne": 0x6600}[cond]
        self.raw(code)
        self.fix.append((len(self.out), label))
        self.out += b"\0\0"

    def movem_save(self, mask: int) -> None:  #vers 1
        """movem.l regs,-(sp); mask bit 0 = A7 ... bit 15 = D0."""
        self.raw(0x48E7, mask)

    def movem_load(self, mask: int) -> None:  #vers 1
        """movem.l (sp)+,regs; mask bit 0 = D0 ... bit 15 = A7."""
        self.raw(0x4CDF, mask)

    def bytes(self, origin: int = 0) -> bytes:  #vers 1
        """Resolve label fixups; displacement is relative to the extension word."""
        out = bytearray(self.out)
        for at, lab in self.fix:
            struct.pack_into(">h", out, at, self.labels[lab] - at)
        return bytes(out)
