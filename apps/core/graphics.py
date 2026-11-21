#this belongs in apps/core/graphics.py - Version: 1
# X-Seti - November 17 2026 - Morosa - Morosa graphics.library.

"""
Morosa graphics.library - planar bitmaps, rastport drawing and colour tables in emulated memory.
"""

##Methods list -
# Graphics
# Graphics._bm
# Graphics._get
# Graphics._font
# Graphics._line
# Graphics._set_font
# Graphics._put
# Graphics._rp
# Graphics.f_AllocBitMap
# Graphics.f_AllocRaster
# Graphics.f_BltClear
# Graphics.f_Draw
# Graphics.f_EraseRect
# Graphics.f_FreeBitMap
# Graphics.f_FreeRaster
# Graphics.f_GetAPen
# Graphics.f_GetBitMapAttr
# Graphics.f_GetRGB4
# Graphics.f_InitBitMap
# Graphics.f_InitRastPort
# Graphics.f_LoadRGB32
# Graphics.f_LoadRGB4
# Graphics.f_Move
# Graphics.f_ReadPixel
# Graphics.f_RectFill
# Graphics.f_SetAPen
# Graphics.f_SetABPenDrMd
# Graphics.f_SetBPen
# Graphics.f_SetDrMd
# Graphics.f_SetRGB32
# Graphics.f_SetRGB4
# Graphics.f_SetRast
# Graphics.f_SetWriteMask
# Graphics.f_WaitTOF
# Graphics.f_Text
# Graphics.f_TextLength
# Graphics.f_WritePixel
# Graphics.f_OpenFont
# Graphics.f_CloseFont
# Graphics.f_SetFont
# Graphics.palette_rgb
# Graphics.image_bytes
# Graphics.snapshot
# Graphics.stamp

JAM1, JAM2, COMPLEMENT, INVERSVID = 0, 1, 2, 4
BMF_CLEAR = 2
RP_SIZE = 100


class Graphics:
    """graphics.library functions; f_<Name> reads registers from the CPU."""

    def __init__(self, machine):  #vers 1
        self.m = machine
        self.cpu = machine.cpu
        self.bus = machine.bus
        self.ex = machine.exec
        self.palettes = {}
        self.fonts = {}
        self.glyphs = {}

    # ---- helpers ----
    def _bm(self, bm: int):  #vers 1
        """(bytes per row, rows, depth, plane addresses)."""
        b = self.bus
        depth = b.r8(bm + 5)
        return b.r16(bm), b.r16(bm + 2), depth, [b.r32(bm + 8 + 4 * i) for i in range(min(depth, 8))]

    def _rp(self, rp: int):  #vers 1
        b = self.bus
        return b.r32(rp + 4), b.r8(rp + 25), b.r8(rp + 26), b.r8(rp + 28), b.r8(rp + 24)

    def _put(self, bm: int, x: int, y: int, pen: int, mask: int = 0xFF, mode: int = JAM1) -> None:  #vers 1
        bpr, rows, depth, planes = self._bm(bm)
        if x < 0 or y < 0 or x >= bpr * 8 or y >= rows:
            return
        off, bit = y * bpr + (x >> 3), 0x80 >> (x & 7)
        b = self.bus
        for i, pl in enumerate(planes):
            if not pl or not mask >> i & 1:
                continue
            v = b.r8(pl + off)
            if mode == COMPLEMENT:
                v ^= bit
            elif pen >> i & 1:
                v |= bit
            else:
                v &= ~bit
            b.w8(pl + off, v)

    def _get(self, bm: int, x: int, y: int) -> int:  #vers 1
        bpr, rows, depth, planes = self._bm(bm)
        if x < 0 or y < 0 or x >= bpr * 8 or y >= rows:
            return 0xFFFFFFFF
        off, bit = y * bpr + (x >> 3), 0x80 >> (x & 7)
        return sum(1 << i for i, pl in enumerate(planes) if pl and self.bus.r8(pl + off) & bit)

    def _line(self, rp: int, x0: int, y0: int, x1: int, y1: int) -> None:  #vers 1
        bm, fg, bg, mode, mask = self._rp(rp)
        if not bm:
            return
        pat = self.bus.r16(rp + 34)
        n = 0
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx + dy
        while True:
            if pat >> (15 - (n & 15)) & 1:
                self._put(bm, x0, y0, bg if mode & INVERSVID else fg, mask, mode & 3)
            elif mode & 3 == JAM2:
                self._put(bm, x0, y0, fg if mode & INVERSVID else bg, mask)
            n += 1
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    # ---- rastport and pens ----
    def f_InitRastPort(self):  #vers 1
        rp = self.cpu.a[1]
        for i in range(0, RP_SIZE, 4):
            self.bus.w32(rp + i, 0)
        b = self.bus
        b.w8(rp + 24, 0xFF)
        b.w8(rp + 25, 1)
        b.w8(rp + 28, JAM2)
        b.w16(rp + 34, 0xFFFF)
        b.w8(rp + 31, 0)
        self._set_font(rp, self._font(8))

    def f_SetAPen(self):  #vers 1
        self.bus.w8(self.cpu.a[1] + 25, self.cpu.d[0])

    def f_SetBPen(self):  #vers 1
        self.bus.w8(self.cpu.a[1] + 26, self.cpu.d[0])

    def f_SetDrMd(self):  #vers 1
        self.bus.w8(self.cpu.a[1] + 28, self.cpu.d[0])

    def f_SetABPenDrMd(self):  #vers 1
        cpu = self.cpu
        rp = cpu.a[1]
        self.bus.w8(rp + 25, cpu.d[0])
        self.bus.w8(rp + 26, cpu.d[1])
        self.bus.w8(rp + 28, cpu.d[2])

    def f_GetAPen(self):  #vers 1
        self.cpu.d[0] = self.bus.r8(self.cpu.a[0] + 25)

    def f_SetWriteMask(self):  #vers 1
        self.bus.w8(self.cpu.a[0] + 24, self.cpu.d[0])
        self.cpu.d[0] = 0xFFFFFFFF

    def f_Move(self):  #vers 1
        cpu = self.cpu
        s = lambda v: v - 65536 if v & 0x8000 else v & 0xFFFF
        self.bus.w16(cpu.a[1] + 36, s(cpu.d[0]) & 0xFFFF)
        self.bus.w16(cpu.a[1] + 38, s(cpu.d[1]) & 0xFFFF)

    def f_Draw(self):  #vers 1
        cpu, b = self.cpu, self.bus
        s = lambda v: v - 65536 if v & 0x8000 else v & 0xFFFF
        rp = cpu.a[1]
        x0, y0 = s(b.r16(rp + 36)), s(b.r16(rp + 38))
        x1, y1 = s(cpu.d[0]), s(cpu.d[1])
        self._line(rp, x0, y0, x1, y1)
        b.w16(rp + 36, x1 & 0xFFFF)
        b.w16(rp + 38, y1 & 0xFFFF)

    def f_WritePixel(self):  #vers 1
        cpu = self.cpu
        bm, fg, bg, mode, mask = self._rp(cpu.a[1])
        s = lambda v: v - (1 << 32) if v >> 31 else v
        x, y = s(cpu.d[0]), s(cpu.d[1])
        cpu.d[0] = 0xFFFFFFFF if x < 0 or y < 0 else 0
        if bm:
            self._put(bm, x, y, fg, mask, mode & 3)

    def f_ReadPixel(self):  #vers 1
        cpu = self.cpu
        bm = self.bus.r32(cpu.a[1] + 4)
        s = lambda v: v - (1 << 32) if v >> 31 else v
        cpu.d[0] = self._get(bm, s(cpu.d[0]), s(cpu.d[1])) if bm else 0xFFFFFFFF

    def _fill(self, rp: int, x0: int, y0: int, x1: int, y1: int, pen: int, mode: int) -> None:  #vers 1
        bm, fg, bg, _, mask = self._rp(rp)
        if not bm:
            return
        for y in range(max(y0, 0), y1 + 1):
            for x in range(max(x0, 0), x1 + 1):
                self._put(bm, x, y, pen, mask, mode)

    def f_RectFill(self):  #vers 1
        cpu = self.cpu
        s = lambda v: v - 65536 if v & 0x8000 else v & 0xFFFF
        rp = cpu.a[1]
        _, fg, bg, mode, _ = self._rp(rp)
        self._fill(rp, s(cpu.d[0]), s(cpu.d[1]), s(cpu.d[2]), s(cpu.d[3]), bg if mode & INVERSVID else fg, mode & 3)

    def f_EraseRect(self):  #vers 1
        cpu = self.cpu
        s = lambda v: v - 65536 if v & 0x8000 else v & 0xFFFF
        rp = cpu.a[1]
        self._fill(rp, s(cpu.d[0]), s(cpu.d[1]), s(cpu.d[2]), s(cpu.d[3]), self.bus.r8(rp + 26), JAM1)

    def f_SetRast(self):  #vers 1
        cpu = self.cpu
        rp = cpu.a[1]
        bm = self.bus.r32(rp + 4)
        if not bm:
            return
        bpr, rows, depth, planes = self._bm(bm)
        for i, pl in enumerate(planes):
            if pl:
                fill = 0xFF if cpu.d[0] >> i & 1 else 0
                for o in range(bpr * rows):
                    self.bus.w8(pl + o, fill)

    # ---- text ----
    def _font(self, size: int) -> int:  #vers 1
        """TextFont structure for a pixel height; created once."""
        if size not in self.fonts:
            from apps.core.font import GlyphSet
            gs = GlyphSet(size)
            self.glyphs[size] = gs
            f = self.ex.alloc(64)
            nm = self.ex.alloc(16)
            self.ex.put_cstr(nm, "topaz.font")
            b = self.bus
            b.w32(f + 10, nm)
            b.w16(f + 20, size)
            b.w16(f + 24, gs.width)
            b.w16(f + 26, gs.baseline)
            b.w8(f + 22, 0)
            b.w8(f + 23, 1)
            b.w8(f + 32, 32)
            b.w8(f + 33, 255)
            self.fonts[size] = f
        return self.fonts[size]

    def _set_font(self, rp: int, f: int) -> None:  #vers 1
        b = self.bus
        b.w32(rp + 52, f)
        b.w16(rp + 58, b.r16(f + 20))
        b.w16(rp + 60, b.r16(f + 24))
        b.w16(rp + 62, b.r16(f + 26))

    def f_OpenFont(self):  #vers 1
        ta = self.cpu.a[0]
        self.cpu.d[0] = self._font(self.bus.r16(ta + 4) or 8)

    def f_CloseFont(self):  #vers 1
        pass

    def f_SetFont(self):  #vers 1
        self._set_font(self.cpu.a[1], self.cpu.a[0])

    def f_TextLength(self):  #vers 1
        cpu = self.cpu
        f = self.bus.r32(cpu.a[1] + 52) or self._font(8)
        cpu.d[0] = self.bus.r16(f + 24) * cpu.d[0]

    def f_Text(self):  #vers 1
        cpu, b = self.cpu, self.bus
        rp, s, n = cpu.a[1], cpu.a[0], cpu.d[0]
        if not b.r32(rp + 52):
            self._set_font(rp, self._font(8))
        f = b.r32(rp + 52)
        size = b.r16(f + 20)
        gs = self.glyphs.get(size) or (self._font(size) and self.glyphs[size])
        bm, fg, bg, mode, mask = self._rp(rp)
        sg = lambda v: v - 65536 if v & 0x8000 else v
        x, y = sg(b.r16(rp + 36)), sg(b.r16(rp + 38))
        base = b.r16(f + 26)
        for i in range(n):
            rows = gs.rows(b.r8(s + i))
            for ry, bits in enumerate(rows):
                for cx in range(gs.width):
                    on = bits >> (gs.width - 1 - cx) & 1
                    px, py = x + i * gs.width + cx, y - base + ry
                    if on:
                        self._put(bm, px, py, bg if mode & INVERSVID else fg, mask, mode & 3)
                    elif mode & 3 == JAM2:
                        self._put(bm, px, py, fg if mode & INVERSVID else bg, mask)
        b.w16(rp + 36, (x + n * gs.width) & 0xFFFF)

    # ---- bitmaps ----
    def f_InitBitMap(self):  #vers 1
        cpu, b = self.cpu, self.bus
        bm = cpu.a[0]
        for i in range(0, 40, 4):
            b.w32(bm + i, 0)
        b.w16(bm, ((cpu.d[1] + 15) >> 4) << 1)
        b.w16(bm + 2, cpu.d[2] & 0xFFFF)
        b.w8(bm + 5, cpu.d[0])

    def f_AllocRaster(self):  #vers 1
        cpu = self.cpu
        size = (((cpu.d[0] + 15) >> 4) << 1) * cpu.d[1]
        cpu.d[0] = self.ex.alloc(size + 8)

    def f_FreeRaster(self):  #vers 1
        cpu = self.cpu
        self.ex.free(cpu.a[0], (((cpu.d[0] + 15) >> 4) << 1) * cpu.d[1] + 8)

    def f_AllocBitMap(self):  #vers 1
        cpu, b = self.cpu, self.bus
        w, h, depth, flags = cpu.d[0], cpu.d[1], cpu.d[2], cpu.d[3]
        bm = self.ex.alloc(40)
        bpr = ((w + 15) >> 4) << 1
        b.w16(bm, bpr)
        b.w16(bm + 2, h)
        b.w8(bm + 5, depth)
        for i in range(min(depth, 8)):
            b.w32(bm + 8 + 4 * i, self.ex.alloc(bpr * h + 8))
        cpu.d[0] = bm

    def f_FreeBitMap(self):  #vers 1
        bm = self.cpu.a[0]
        bpr, rows, depth, planes = self._bm(bm)
        for pl in planes:
            self.ex.free(pl, bpr * rows + 8)
        self.ex.free(bm, 40)

    def f_GetBitMapAttr(self):  #vers 1
        cpu = self.cpu
        bpr, rows, depth, _ = self._bm(cpu.a[0])
        cpu.d[0] = {0: bpr * 8, 1: rows, 2: depth, 3: 0}.get(cpu.d[1], 0)

    def f_BltClear(self):  #vers 1
        cpu = self.cpu
        n = (cpu.d[0] & 0xFFFF) * 2 if not cpu.d[1] & 2 else ((cpu.d[0] >> 16) * (cpu.d[0] & 0xFFFF) * 2)
        if not cpu.d[1] & 2:
            n = cpu.d[0]
        for i in range(n):
            self.bus.w8(cpu.a[1] + i, 0)

    def f_WaitTOF(self):  #vers 1
        pass

    # ---- colours ----
    def _pal(self, vp: int) -> dict:  #vers 1
        return self.palettes.setdefault(vp, {})

    def f_SetRGB4(self):  #vers 1
        cpu = self.cpu
        self._pal(cpu.a[0])[cpu.d[0]] = (cpu.d[1] & 15) * 17, (cpu.d[2] & 15) * 17, (cpu.d[3] & 15) * 17

    def f_LoadRGB4(self):  #vers 1
        cpu = self.cpu
        for i in range(cpu.d[0]):
            v = self.bus.r16(cpu.a[1] + 2 * i)
            self._pal(cpu.a[0])[i] = (v >> 8 & 15) * 17, (v >> 4 & 15) * 17, (v & 15) * 17

    def f_GetRGB4(self):  #vers 1
        cpu = self.cpu
        r, g, bl = self.palette_rgb(cpu.a[0]).get(cpu.d[0], (0, 0, 0))
        cpu.d[0] = (r // 17) << 8 | (g // 17) << 4 | bl // 17

    def f_SetRGB32(self):  #vers 1
        cpu = self.cpu
        self._pal(cpu.a[0])[cpu.d[0]] = cpu.d[1] >> 24, cpu.d[2] >> 24, cpu.d[3] >> 24

    def f_LoadRGB32(self):  #vers 1
        cpu, b = self.cpu, self.bus
        t = cpu.a[1]
        while True:
            hd = b.r32(t)
            if hd == 0:
                break
            n, first = hd >> 16, hd & 0xFFFF
            for i in range(n):
                self._pal(cpu.a[0])[first + i] = tuple(b.r32(t + 4 + 12 * i + 4 * c) >> 24 for c in range(3))
            t += 4 + 12 * n

    def palette_rgb(self, vp: int) -> dict:  #vers 1
        return self._pal(vp)

    def image_bytes(self, bm: int, vp: int = 0):  #vers 1
        """(width, height, BGRA bytes) of a bitmap with the viewport palette; fast path per byte."""
        bpr, rows, depth, planes = self._bm(bm)
        pal = self._pal(vp)
        n = 1 << depth
        lut = []
        for p in range(256):
            c = pal.get(p) or ((0, 0, 0), (255, 255, 255))[p] if p < 2 else pal.get(p) or ((p * 255 // max(1, n - 1)) & 255,) * 3
            lut.append(bytes((c[2], c[1], c[0], 255)))
        bits = [[v >> (7 - k) & 1 for k in range(8)] for v in range(256)]
        ram, out = self.bus.ram, bytearray()
        for y in range(rows):
            for xb in range(bpr):
                cols = [bits[ram[pl + y * bpr + xb]] if pl else bits[0] for pl in planes]
                for k in range(8):
                    pen = 0
                    for i, c in enumerate(cols):
                        pen |= c[k] << i
                    out += lut[pen]
        return bpr * 8, rows, bytes(out)

    def stamp(self, bm: int) -> int:  #vers 1
        """Cheap change marker over all planes."""
        bpr, rows, depth, planes = self._bm(bm)
        return hash(tuple(bytes(self.bus.ram[pl:pl + bpr * rows]) for pl in planes if pl))

    def snapshot(self, bm: int, vp: int = 0):  #vers 1
        """(width, height, rows of RGB tuples) for a bitmap with the viewport palette."""
        bpr, rows, depth, planes = self._bm(bm)
        pal = self._pal(vp)
        default = [(0, 0, 0), (255, 255, 255)]
        out = []
        for y in range(rows):
            row = []
            for x in range(bpr * 8):
                p = self._get(bm, x, y)
                row.append(pal.get(p, default[p] if p < 2 else (p * 255 // max(1, (1 << depth) - 1),) * 3))
            out.append(row)
        return bpr * 8, rows, out
