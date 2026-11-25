#this belongs in apps/hardware/agnus.py - Version: 15
# X-Seti - November 17 2026 - Morosa - Morosa Agnus.

"""
Morosa Agnus - beam counter, DMA control, bitplane and sprite fetch; drives Copper, Blitter, Denise and Paula.
"""

##Methods list -
# Agnus
# Agnus._cop_write
# Agnus._fetch_planes
# Agnus._sprites
# Agnus.line
# Agnus.window
# Agnus.read
# Agnus.run_frame
# Agnus.write
# Agnus.write_reg

import os

import numpy as np

DMAEN, BPLEN, COPEN, BLTEN, SPREN = 0x200, 0x100, 0x80, 0x40, 0x20
CCLOCKS = 227
INT_VERTB, INT_COPER, INT_BLIT = 0x20, 0x10, 0x40
MODEL_ID = {"ocs": 0x00, "ecs": 0x30, "aga": 0x23}


class Agnus:
    """chip: bytearray of chip RAM. cpu_run(cycles) runs the CPU for one line slice (7.09 MHz clocks)."""

    def __init__(self, chip: bytearray, paula, denise, blitter, copper, ciaa=None, ciab=None, pal: bool = True, model: str = "ocs"):  #vers 2
        self.chip, self.paula, self.denise, self.blitter, self.copper = chip, paula, denise, blitter, copper
        denise.agnus = self
        self.ciaa, self.ciab = ciaa, ciab
        self.pal, self.model = pal, model
        self.hsync = None
        self.lines = 312 if pal else 262
        self.beamcon, self.vtotal, self.htotal = (0x20 if pal else 0), 0, 0
        self.ccl = CCLOCKS
        self.mask = len(chip) - 1
        self.dmacon = 0
        self.vpos = self.hpos = 0
        self.lof = True
        self.bplpt = [0] * 8
        self.bpl1mod = self.bpl2mod = 0
        self.diwstrt, self.diwstop = 0x2C81, 0x2CC1
        self.diwhigh = None
        self.skip = False
        self.nfetch = self.fetch_n = 0
        self.ddfstrt, self.ddfstop = 0x38, 0xD0
        self.sprpt = [0] * 8
        self.sprstate = [dict(vstart=0, vstop=0, active=False, ended=False) for _ in range(8)]
        self.frames = 0
        self.disk = None
        self.inp = None
        self.kbd = None
        paula.dmacon = lambda: self.dmacon
        blitter.read16, blitter.write16 = self.read16, self.write16
        copper.read16, copper.write_reg = self.read16, self.write_reg
        copper.blitter_busy = lambda: blitter.busy
        copper.chip, copper.mask = chip, self.mask
        blitter.chip, blitter.mask = chip, self.mask
        paula.chip, paula.mask = chip, self.mask
        blitter.done = lambda: paula.request(INT_BLIT)

    # ---- chip RAM ----
    def read16(self, a: int) -> int:  #vers 1
        a &= self.mask & ~1
        return self.chip[a] << 8 | self.chip[a + 1]

    def write16(self, a: int, v: int) -> None:  #vers 1
        a &= self.mask & ~1
        self.chip[a], self.chip[a + 1] = v >> 8 & 255, v & 255

    # ---- registers ----
    def read(self, off: int) -> int:  #vers 2
        off &= 0x1FE
        if off == 0x002:
            return (self.dmacon & 0x3FF) | (self.blitter.read(0x002) or 0)
        if off == 0x004:
            return (0x8000 if self.lof else 0) | MODEL_ID[self.model] << 8 | (1 if self.vpos > 255 else 0)
        if off == 0x006:
            return (self.vpos & 0xFF) << 8 | (self.hpos & 0xFF)
        for chip in (self.inp, self.disk, self.paula, self.denise):
            v = chip.read(off) if chip else None
            if v is not None:
                return v
        return 0

    def _cop_write(self, off: int, v: int, h: int) -> bool:  #vers 1
        self.hpos = h
        self.write_reg(off, v)
        return self.copper.dma

    def write(self, off: int, v: int) -> None:  #vers 1
        self.write_reg(off & 0x1FE, v & 0xFFFF)

    REGLOG = {0x100: "BPLCON0", 0x08E: "DIWSTRT", 0x090: "DIWSTOP", 0x092: "DDFSTRT", 0x094: "DDFSTOP", 0x108: "BPL1MOD", 0x10A: "BPL2MOD",
              0x1FC: "FMODE", 0x1DC: "BEAMCON0", 0x1C0: "HTOTAL", 0x1C8: "VTOTAL", 0x1E4: "DIWHIGH", 0x106: "BPLCON3"}

    def write_reg(self, off: int, v: int) -> None:  #vers 3
        if 0x180 <= off < 0x1C0:
            self.denise.write(off, v)
            return
        if off in self.REGLOG and os.environ.get("MOROSA_REGLOG") and self.__dict__.setdefault("_rl", {}).get(off) != v:
            self._rl[off] = v
            with open("morosa_reglog.txt", "a") as f:
                f.write(f"{self.frames} {self.vpos} {self.REGLOG[off]} {v:04X}\n")
        if off == 0x096:
            self.dmacon = (self.dmacon | v & 0x7FFF) if v & 0x8000 else self.dmacon & ~v
            self.paula.sync_dma()
            self.copper.dma = bool(self.dmacon & DMAEN and self.dmacon & COPEN)
        elif off == 0x02A:
            self.vpos = (self.vpos & 0xFF) | (v & 1) << 8 if False else (self.vpos & 0xFF | (v & 1) << 8)
            self.lof = bool(v & 0x8000)
        elif off == 0x08E:
            self.diwstrt, self.diwhigh = v, None
        elif off == 0x090:
            self.diwstop, self.diwhigh = v, None
        elif off == 0x1E4 and self.model != "ocs":
            self.diwhigh = v
        elif off == 0x092:
            self.ddfstrt = v & 0xFE
        elif off == 0x094:
            self.ddfstop = v & 0xFE
        elif off == 0x108:
            self.bpl1mod = v - 0x10000 if v & 0x8000 else v
        elif off == 0x10A:
            self.bpl2mod = v - 0x10000 if v & 0x8000 else v
        elif off in (0x1C0, 0x1C8, 0x1DC) and self.model != "ocs":
            self._beam(off, v)
        elif off == 0x1FC:
            self.denise.write(off, v)
        elif 0x0E0 <= off < 0x100:
            i, hi = (off - 0x0E0) >> 2, not off & 2
            cur = self.bplpt[i]
            self.bplpt[i] = (cur & 0xFFFF | (v & 0x1F) << 16) if hi else (cur & 0x1F0000 | v & 0xFFFE)
        elif 0x120 <= off < 0x140:
            i, hi = (off - 0x120) >> 2, not off & 2
            cur = self.sprpt[i]
            self.sprpt[i] = (cur & 0xFFFF | (v & 0x1F) << 16) if hi else (cur & 0x1F0000 | v & 0xFFFE)
        elif self.copper.write(off, v) or self.blitter.write(off, v):
            pass
        elif (self.inp and self.inp.write(off, v)) or (self.disk and self.disk.write(off, v)) or self.paula.write(off, v) or self.denise.write(off, v):
            pass

    # ---- frame ----
    def _fetch_planes(self):  #vers 6
        bpu = self.denise.nplanes()
        mult = self.denise.fetch_mult()
        hires = bool(self.denise.bplcon0 & 0x8040)
        if not (self.dmacon & DMAEN and self.dmacon & BPLEN) or not bpu:
            return []
        n = ((self.ddfstop - self.ddfstrt) // (4 * mult if hires else 8 * mult) + (2 if hires and mult == 1 else 1)) * mult
        if self.denise.bplcon0 & 0x40:
            n = ((self.ddfstop - self.ddfstrt) // (2 * mult) + (4 if mult == 1 else 1)) * mult
        size, chip, mask = 2 * n, self.chip, self.mask
        self.fetch_n, self.nfetch = n, self.nfetch + 1
        offs, rows = [], []
        for i in range(bpu):
            ptr = self.bplpt[i]
            a = ptr & mask & ~1
            offs.append(a)
            if a + size > len(chip):
                rows = None
            self.bplpt[i] = ptr + size + (self.bpl1mod if i % 2 == 0 else self.bpl2mod)
        if rows is not None:
            return (chip, tuple(offs), n)
        return [np.frombuffer(chip, dtype=">u2", count=n, offset=a) if a + size <= len(chip)
                else [self.read16(a + 2 * w) for w in range(n)] for a in offs]

    def _sprites(self, vpos: int) -> None:  #vers 3
        if not (self.dmacon & DMAEN and self.dmacon & SPREN):
            for s in self.denise.spr:
                s["armed"] = False
            return
        w = self.denise.spr_width
        step, words = w // 8, w // 16
        aga = getattr(self.denise, "aga", 0)

        def head(n):
            p = self.sprpt[n]
            self.sprpt[n] = p + 2 * step
            return self.read16(p), self.read16(p + 2)

        def vs(pos, ctl):
            return (pos >> 8 | (ctl >> 2 & 1) << 8 | ((ctl >> 6 & 1) << 9 if aga else 0),
                    ctl >> 8 | (ctl >> 1 & 1) << 8 | ((ctl >> 5 & 1) << 9 if aga else 0))

        def data(p):
            a = b = 0
            for i in range(words):
                a = a << 16 | self.read16(p + 2 * i)
                b = b << 16 | self.read16(p + step + 2 * i)
            return a, b

        for n in range(8):
            st, ds = self.sprstate[n], self.denise.spr[n]
            if vpos == 0:
                st.update(active=False, ended=False)
                ds["armed"] = False
                pos, ctl = head(n)
                st["vstart"], st["vstop"] = vs(pos, ctl)
                ds["pos"], ds["ctl"] = pos, ctl
                st["ended"] = not (pos or ctl)
                continue
            if st["ended"]:
                ds["armed"] = False
                continue
            if vpos == st["vstart"]:
                st["active"] = True
            if st["active"] and vpos == st["vstop"]:
                st["active"] = False
                ds["armed"] = False
                pos, ctl = head(n)
                st["ended"] = not (pos or ctl)
                st["vstart"], st["vstop"] = vs(pos, ctl)
                ds["pos"], ds["ctl"] = pos, ctl
                continue
            if st["active"]:
                p = self.sprpt[n]
                self.sprpt[n] = p + 2 * step
                ds["a"], ds["b"] = data(p)
                ds["armed"] = True

    def window(self) -> tuple:  #vers 1
        """(hstart, hstop, vstart, vstop); DIWHIGH gives the upper bits when written."""
        hs, he, vs, ve = self.diwstrt & 0xFF, self.diwstop & 0xFF, self.diwstrt >> 8, self.diwstop >> 8
        h = self.diwhigh
        if h is None:
            return hs, he | 0x100, vs, ve | (0 if ve & 0x80 else 0x100)
        return hs | (h >> 5 & 1) << 8, he | (h >> 13 & 1) << 8, vs | (h & 7) << 8, ve | (h >> 8 & 7) << 8

    def line(self, cpu_run=None) -> None:  #vers 10
        v = self.vpos
        if v == 0:
            self.paula.request(INT_VERTB)
            self.copper.frame_start()
            if self.ciaa:
                self.ciaa.tod_tick()
        if self.ciab:
            self.ciab.tod_tick()
        if v:
            self._sprites(v)
        if self.disk:
            self.disk.line()
        if self.kbd:
            self.kbd.line()
        cop = self.copper
        if cop.dma and not cop.halted and not (cop.waiting and not cop._cond(v, self.ccl - 2)):
            self.denise.rec = True
            cop.run_line(v, self.ccl, self._cop_write)
            self.denise.rec = False
        if v == 0:
            self._sprites(0)
        self.hpos = self.ccl - 2
        hs, he, vs, ve = self.window()
        if self.skip:
            self.denise.cw, self.denise.cw0 = [], {}
        else:
            planes = self._fetch_planes() if vs <= v < ve else []
            x_abs = 2 * self.ddfstrt + (9 if self.denise.bplcon0 & 0x8040 else 17) + (8 if self.denise.fetch_mult() == 4 else 0)
            self.denise.render_line(v, planes, x_abs, (hs, he), (vs, ve))
        if cpu_run:
            cpu_run(self.ccl * 2)
        self.paula.tick(self.ccl)
        self.blitter.tick(self.ccl)
        for cia in (self.ciaa, self.ciab):
            if cia:
                cia.tick(self.ccl // 5)
        if self.hsync:
            self.hsync()
        self.vpos += 1

    def _beam(self, off: int, v: int) -> None:  #vers 1
        """BEAMCON0, HTOTAL, VTOTAL: PAL/NTSC switch and variable frame size."""
        if off == 0x1C0:
            self.htotal = v & 0xFF
        elif off == 0x1C8:
            self.vtotal = v & 0x7FF
        else:
            self.beamcon = v
        if self.beamcon & 0x80:
            self.lines = max(200, self.vtotal + 1)
            self.ccl = max(40, self.htotal) if self.htotal else CCLOCKS
        elif off == 0x1DC:
            self.lines = 312 if self.beamcon & 0x20 else 262
            self.ccl = CCLOCKS

    def run_frame(self, cpu_run=None) -> None:  #vers 4
        self.vpos = 0
        self.nfetch = 0
        for _ in range(self.lines + (1 if self.lof and not self.beamcon & 0x80 else 0)):
            self.line(cpu_run)
        self.frames += 1
        if self.denise.bplcon0 & 4:
            self.lof = not self.lof
