#this belongs in apps/core/m68k.py - Version: 3
# X-Seti - November 21 2026 - Morosa - Native 68k CPU via Musashi.

"""
Native 68k CPU - binds the compiled Musashi core to the Morosa bus; apps/core/cpu.py stays as the Python reference.
"""

##Methods list -
##class M68K: -
# __init__
# _read
# _write
# add_ram
# execute
# irq_level
# pc
# reset
# set_rom
# stopped
# sync
# touches

from apps.methods.bus import BusError
from apps.core import musashi_ext

SIZES = (0xFF, 0xFFFF, 0xFFFFFFFF)


class M68K:
    """Same surface the Amiga needs: irq_level, stopped, pc, reset, execute."""

    def __init__(self, bus, model: int = 68020):  #vers 1
        self.bus, self.model = bus, model
        self.core = musashi_ext.Core(model, bus.ram, self._read, self._write)

    def _read(self, a: int, size: int) -> int:  #vers 1
        """Hooked read; unmapped space returns the bus open value."""
        try:
            return self.bus._hook(a, False)(a, size) & SIZES[size]
        except BusError:
            return self.bus.open_value & SIZES[size]

    def _write(self, a: int, size: int, v: int) -> None:  #vers 1
        try:
            self.bus._hook(a, True)(a, size, v)
        except BusError:
            pass

    def set_rom(self, rom: bytes, base: int) -> None:  #vers 1
        self.core.set_rom(rom, base)

    def add_ram(self, base: int, buf) -> None:  #vers 1
        """Map a writable buffer at base for direct access."""
        self.core.add_ram(base, buf)

    @property
    def touches(self) -> int:  #vers 1
        return self.core.touches

    def sync(self, fn) -> None:  #vers 1
        """fn(cycles_done) runs before every hooked access."""
        self.core.set_sync(fn)

    def reset(self, pc: int, sp: int) -> None:  #vers 1
        self.core.reset(pc, sp)

    def execute(self, cycles: int) -> int:  #vers 1
        return self.core.execute(cycles)

    @property
    def irq_level(self) -> int:  #vers 1
        return self.core.irq_level

    @irq_level.setter
    def irq_level(self, v: int) -> None:
        self.core.irq_level = v

    @property
    def stopped(self) -> bool:  #vers 1
        return self.core.stopped

    @property
    def pc(self) -> int:  #vers 1
        return self.core.reg(musashi_ext.REG_PC)
