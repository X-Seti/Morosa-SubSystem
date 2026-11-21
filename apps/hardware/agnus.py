#this belongs in apps/hardware/agnus.py - Version: 6
# X-Seti - November 17 2026 - Morosa - Morosa Agnus.

"""
Morosa Agnus - beam counter, DMA control, bitplane and sprite fetch; drives Copper, Blitter, Denise and Paula.
"""

##Methods list -
# Agnus
# Agnus._fetch_planes
# Agnus._sprites
# Agnus.line
# Agnus.read
# Agnus.run_frame
# Agnus.write
# Agnus.write_reg

DMAEN, BPLEN, COPEN, BLTEN, SPREN = 0x200, 0x100, 0x80, 0x40, 0x20
CCLOCKS = 227
INT_VERTB, INT_COPER, INT_BLIT = 0x20, 0x10, 0x40
MODEL_ID = {"ocs": 0x00, "ecs": 0x30, "aga": 0x23}


class Agnus:
    """chip: bytearray of chip RAM. cpu_run(cycles) runs the CPU for one line slice (7.09 MHz clocks)."""

    def __init__(self, chip: bytearray, paula, denise, blitter, copper, ciaa=None, ciab=None, pal: bool = True, model: str = "ocs"):  #vers 2
        self.chip, self.paula, self.denise, self.blitter, self.copper = chip, paula, denise, blitter, copper
        self.ciaa, self.ciab = ciaa, ciab
        self.pal, self.model = pal, model
        self.hsync = None
        self.lines = 312 if pal else 262
        self.mask = len(chip) - 1
        self.dmacon = 0
        self.vpos = self.hpos = 0
        self.lof = True
        self.bplpt = [0] * 8
        self.bpl1mod = self.bpl2mod = 0
        self.diwstrt, self.diwstop = 0x2C81, 0x2CC1
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

    def write(self, off: int, v: int) -> None:  #vers 1
        self.write_reg(off & 0x1FE, v & 0xFFFF)

    def write_reg(self, off: int, v: int) -> None:  #vers 1
        if off == 0x096:
            self.dmacon = (self.dmacon | v & 0x7FFF) if v & 0x8000 else self.dmacon & ~v
            self.paula.sync_dma()
            self.copper.dma = bool(self.dmacon & DMAEN and self.dmacon & COPEN)
        elif off == 0x02A:
            self.vpos = (self.vpos & 0xFF) | (v & 1) << 8 if False else (self.vpos & 0xFF | (v & 1) << 8)
            self.lof = bool(v & 0x8000)
        elif off == 0x08E:
            self.diwstrt = v
        elif off == 0x090:
            self.diwstop = v
        elif off == 0x092:
            self.ddfstrt = v & 0xFE
        elif off == 0x094:
            self.ddfstop = v & 0xFE
        elif off == 0x108:
            self.bpl1mod = v - 0x10000 if v & 0x8000 else v
        elif off == 0x10A:
            self.bpl2mod = v - 0x10000 if v & 0x8000 else v
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
    def _fetch_planes(self) -> list:  #vers 2
        bpu = self.denise.nplanes()
        mult = self.denise.fetch_mult()
        hires = bool(self.denise.bplcon0 & 0x8000)
        if not (self.dmacon & DMAEN and self.dmacon & BPLEN) or not bpu:
            return []
        n = ((self.ddfstop - self.ddfstrt) // (4 * mult if hires else 8 * mult) + (2 if hires and mult == 1 else 1)) * mult
        planes = []
        for i in range(bpu):
            ptr = self.bplpt[i]
            planes.append([self.read16(ptr + 2 * w) for w in range(n)])
            self.bplpt[i] = ptr + 2 * n + (self.bpl1mod if i % 2 == 0 else self.bpl2mod)
        return planes

    def _sprites(self, vpos: int) -> None:  #vers 1
        if not (self.dmacon & DMAEN and self.dmacon & SPREN):
            for s in self.denise.spr:
                s["armed"] = False
            return
        for n in range(8):
            st, ds = self.sprstate[n], self.denise.spr[n]
            if vpos == 0:
                st.update(active=False, ended=False)
                pos, ctl = self.read16(self.sprpt[n]), self.read16(self.sprpt[n] + 2)
                self.sprpt[n] += 4
                st["vstart"], st["vstop"] = pos >> 8 | (ctl >> 2 & 1) << 8, ctl >> 8 | (ctl >> 1 & 1) << 8
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
                pos, ctl = self.read16(self.sprpt[n]), self.read16(self.sprpt[n] + 2)
                self.sprpt[n] += 4
                st["ended"] = not (pos or ctl)
                st["vstart"], st["vstop"] = pos >> 8 | (ctl >> 2 & 1) << 8, ctl >> 8 | (ctl >> 1 & 1) << 8
                ds["pos"], ds["ctl"] = pos, ctl
                continue
            if st["active"]:
                a, b = self.read16(self.sprpt[n]), self.read16(self.sprpt[n] + 2)
                self.sprpt[n] += 4
                ds["a"], ds["b"], ds["armed"] = a, b, True

    def line(self, cpu_run=None) -> None:  #vers 4
        v = self.vpos
        if v == 0:
            self.paula.request(INT_VERTB)
            self.copper.frame_start()
            if self.ciaa:
                self.ciaa.tod_tick()
        if self.ciab:
            self.ciab.tod_tick()
        self._sprites(v)
        if self.disk:
            self.disk.line()
        if self.kbd:
            self.kbd.line()
        for h in range(0, CCLOCKS, 2):
            self.hpos = h
            self.copper.step(v, h)
        vs, ve = self.diwstrt >> 8, (self.diwstop >> 8) | (0 if self.diwstop >> 8 & 0x80 else 0x100)
        hs, he = self.diwstrt & 0xFF, (self.diwstop & 0xFF) | 0x100
        planes = self._fetch_planes() if vs <= v < ve else []
        x_abs = 2 * self.ddfstrt + (9 if self.denise.bplcon0 & 0x8000 else 17) + (8 if self.denise.fetch_mult() == 4 else 0)
        self.denise.render_line(v, planes, x_abs, (hs, he), (vs, ve))
        if cpu_run:
            cpu_run(CCLOCKS * 2)
        self.paula.tick(CCLOCKS)
        for cia in (self.ciaa, self.ciab):
            if cia:
                cia.tick(CCLOCKS // 5)
        if self.hsync:
            self.hsync()
        self.vpos += 1

    def run_frame(self, cpu_run=None) -> None:  #vers 2
        self.vpos = 0
        for _ in range(self.lines):
            self.line(cpu_run)
        self.frames += 1
        if self.denise.bplcon0 & 4:
            self.lof = not self.lof
