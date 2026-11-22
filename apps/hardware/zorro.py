#this belongs in apps/hardware/zorro.py - Version: 1
# X-Seti - November 17 2026 - Morosa - Morosa Zorro AutoConfig.

"""
Morosa Zorro - Zorro II (0xE80000) and Zorro III (0xFF000000) autoconfig chain with RAM boards.
"""

##Methods list -
# AutoConfig
# AutoConfig.add
# AutoConfig.current
# AutoConfig.read
# AutoConfig.write
# RamBoard
# RamBoard.config_rom
# RamBoard.read
# RamBoard.write

from apps.hardware.memory import SparseRAM

Z2_CONFIG, Z3_CONFIG = 0xE80000, 0xFF000000
Z2_SIZE = {64: 1, 128: 2, 256: 3, 512: 4, 1024: 5, 2048: 6, 4096: 7, 8192: 0}
Z3_SIZE = {16384: 0, 32768: 1, 65536: 2, 131072: 3, 262144: 4, 524288: 5, 1048576: 6}


class RamBoard:
    """A memory expansion; kb of RAM, zorro 2 or 3. Reports itself in config_rom() and maps itself once configured."""

    def __init__(self, kb: int, zorro: int = 2, manufacturer: int = 0x0202, product: int = 0x01, serial: int = 1):  #vers 1
        if kb not in (Z2_SIZE if zorro == 2 else Z3_SIZE):
            raise ValueError(f"Zorro {'I' * zorro} RAM board size {kb}K is not valid")
        self.kb, self.zorro = kb, zorro
        self.mfr, self.product, self.serial = manufacturer, product, serial
        self.ram = SparseRAM(kb * 1024)
        self.base = None

    def config_rom(self) -> bytes:  #vers 1
        """16 bytes: type, product, flags, reserved, manufacturer(2), serial(4), diag vector(2), reserved(4)."""
        code = (Z2_SIZE if self.zorro == 2 else Z3_SIZE)[self.kb]
        typ = (0xC0 if self.zorro == 2 else 0x80) | 0x20 | 0x10 | code     # memory, chain to next, size
        flags = 0x80 if self.zorro == 2 else 0x00                           # Z2: may be shut up, Z3: none
        return bytes([typ, self.product, flags, 0, self.mfr >> 8, self.mfr & 255]) + self.serial.to_bytes(4, "big") + bytes(6)

    def read(self, a: int, size: int) -> int:  #vers 1
        return self.ram.read(a - self.base, (1, 2, 4)[size])

    def write(self, a: int, size: int, v: int) -> None:  #vers 1
        n = (1, 2, 4)[size]
        self.ram.write(a - self.base, n, v & (1 << 8 * n) - 1)


class AutoConfig:
    """One chain per zorro generation. map(board, base, size) is called when the OS assigns an address."""

    def __init__(self, zorro: int, map_board):  #vers 1
        self.zorro = zorro
        self.map_board = map_board
        self.boards = []
        self.pos = 0
        self.lo = 0

    def add(self, board) -> None:  #vers 1
        self.boards.append(board)

    def current(self):  #vers 1
        return self.boards[self.pos] if self.pos < len(self.boards) else None

    def read(self, off: int, size: int = 0) -> int:  #vers 1
        b = self.current()
        if size == 0:
            return self._byte(b, off & 0xFFFF)
        if size == 1:
            return self._byte(b, off & 0xFFFF) << 8 | self._byte(b, off + 1 & 0xFFFF)
        return self.read(off, 1) << 16 | self.read(off + 2, 1)

    def _byte(self, b, off: int) -> int:  #vers 2
        if b is None:
            return 0xFF
        rom = b.config_rom()
        if self.zorro == 3:
            if off & 3 or off & 0xFF >= 0x40:
                return 0
            n = (off & 0xFF) >> 2
            v = rom[n] if n < len(rom) else 0
            nib = v & 15 if off & 0x100 else v >> 4
        else:
            if off >= 0x40 or off & 1:
                return 0
            n = off >> 2
            v = rom[n] if n < len(rom) else 0
            nib = v >> 4 if not off & 2 else v & 15
        if n != 0:
            nib ^= 15
        return nib << 4

    def write(self, off: int, size: int, v: int) -> None:  #vers 1
        b = self.current()
        if b is None:
            return
        off &= 0xFFFF
        if size == 1 and off == 0x48 and self.zorro == 2:
            self._place(b, (v >> 8 & 0xFF) << 16)
        elif size == 0 and off == 0x4A:
            self.lo = v >> 4 & 15
        elif size == 0 and off == 0x48 and self.zorro == 2:
            self._place(b, ((v & 0xF0) | self.lo) << 16)
        elif off == 0x44 and self.zorro == 3:
            self._place(b, (v & 0xFFFF) << 16 if size else (v & 0xFF) << 24)
        elif off == 0x4C:
            self.pos += 1

    def _place(self, b, base: int) -> None:  #vers 1
        b.base = base
        self.map_board(b, base, b.kb * 1024)
        self.pos += 1
