#this belongs in apps/hardware/copper.py - Version: 2
# X-Seti - November 17 2026 - Morosa - Morosa Copper.

"""
Morosa Copper - Agnus coprocessor: MOVE, WAIT and SKIP instructions run against the beam position.
"""

##Methods list -
# Copper
# Copper._cond
# Copper.frame_start
# Copper.jump
# Copper.run_line
# Copper.write

from apps.core import video_ext


class Copper:
    """read16(addr), write_reg(off, v) hit chip RAM and the custom registers; blitter_busy() for the BFD flag."""

    def __init__(self, read16, write_reg, blitter_busy=None, ecs: bool = False):  #vers 1
        self.read16, self.write_reg = read16, write_reg
        self.chip, self.mask = bytearray(8), 0
        self.blitter_busy = blitter_busy or (lambda: False)
        self.ecs = ecs
        self.lc1 = self.lc2 = 0
        self.pc = 0
        self.copcon = 0
        self.waiting = False
        self.wait = (0, 0, 0xFF, 0xFE, True)
        self.halted = False
        self.skip_next = False
        self.dma = True

    def write(self, off: int, v: int) -> bool:  #vers 1
        v &= 0xFFFF
        if off == 0x080:
            self.lc1 = self.lc1 & 0xFFFF | (v & 0x1F) << 16
        elif off == 0x082:
            self.lc1 = self.lc1 & 0x1F0000 | v & 0xFFFE
        elif off == 0x084:
            self.lc2 = self.lc2 & 0xFFFF | (v & 0x1F) << 16
        elif off == 0x086:
            self.lc2 = self.lc2 & 0x1F0000 | v & 0xFFFE
        elif off == 0x088:
            self.jump(1)
        elif off == 0x08A:
            self.jump(2)
        elif off == 0x02E:
            self.copcon = v
        else:
            return False
        return True

    def jump(self, which: int) -> None:  #vers 1
        self.pc = self.lc1 if which == 1 else self.lc2
        self.waiting = False
        self.halted = False
        self.skip_next = False

    def frame_start(self) -> None:  #vers 1
        self.jump(1)

    def _cond(self, vpos: int, hpos: int) -> bool:  #vers 1
        vp, hp, vm, hm, bfd = self.wait
        if not bfd and self.blitter_busy():
            return False
        v, h = vpos & vm, hpos & hm
        return v > (vp & vm) or (v == (vp & vm) and h >= (hp & hm))

    def run_line(self, vpos: int, ccl: int, wcb) -> None:  #vers 1
        """Run one line of slots natively; wcb(reg, v, hpos) writes a register, returns dma flag."""
        (self.pc, self.lc1, self.lc2, self.copcon, wt, ht, sk, *self.wait) = video_ext.copper_run(
            self.chip, self.mask, self.pc, self.lc1, self.lc2, self.copcon, self.waiting, self.halted, self.skip_next,
            *self.wait, vpos, ccl, wcb, self.blitter_busy)
        self.waiting, self.halted, self.skip_next = bool(wt), bool(ht), bool(sk)
        self.wait = tuple(self.wait[:4]) + (bool(self.wait[4]),)
