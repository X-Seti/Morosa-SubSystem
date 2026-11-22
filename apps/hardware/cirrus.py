#this belongs in apps/hardware/cirrus.py - Version: 1
# X-Seti - November 22 2026 - Morosa - Morosa Cirrus GD5446 Graphics Chip.

"""
Morosa Cirrus - GD5446 style SVGA chip for RTG boards. Registers, packed pixel scanout, hardware cursor, blitter.
Register behaviour follows QEMU hw/display/cirrus_vga.c (MIT licence, Fabrice Bellard, Makoto Suzuki).
"""

##Methods list -
# Cirrus
# Cirrus.__init__
# Cirrus.active
# Cirrus.bpp
# Cirrus.frame
# Cirrus.io_read
# Cirrus.io_write
# Cirrus.params
# Cirrus.resolution
# Cirrus._blit_start
# Cirrus._cursor
# Cirrus._gr_write
# Cirrus._rop
# Cirrus._sr_write

import numpy as np

ID_5446 = 0x2E << 2
ROPS = {0x00: 0, 0x05: 1, 0x06: 2, 0x09: 3, 0x0B: 4, 0x0D: 5, 0x0E: 6, 0x50: 7, 0x59: 8, 0x6D: 9, 0x90: 10, 0x95: 11, 0xAD: 12, 0xD0: 13, 0xD6: 14, 0xDA: 15}
SR_MASK = (0x03, 0x3D, 0x0F, 0x3F, 0x0E)
GR_MASK = (0x0F, 0x0F, 0x0F, 0x1F, 0x03, 0x7B, 0x0F, 0x0F, 0xFF)
STATUS = (0x00, 0x01, 0x08, 0x09)


class Cirrus:
    """One GD5446. vram is a bytearray; io_read/io_write take VGA port numbers (0x3B4 to 0x3DA)."""

    def __init__(self, vram_kb: int = 4096):  #vers 1
        self.size = vram_kb * 1024
        self.vram = bytearray(self.size)
        self.sr, self.gr, self.cr = [0] * 256, [0] * 256, [0] * 256
        self.ar = [0] * 32
        self.pal = [0] * 768
        self.hpal = [0] * 48
        self.misc = 0
        self.sr_i = self.gr_i = self.cr_i = self.ar_i = 0
        self.ar_flip = 0
        self.dac_r = self.dac_w = self.dac_sub = 0
        self.dac_cache = [0, 0, 0]
        self.dac_state = 0
        self.hdac_lock, self.hdac = 5, 0
        self.pel_mask = 0xFF
        self.stat = 0
        self.cur_x = self.cur_y = 0
        self.sr[6] = 0x0F
        self.sr[0x1F] = 0x2D
        self.sr[0x0F] = 0x98
        self.sr[0x17] = 0x20
        self.sr[0x15] = 0x04
        self.gr[0x18] = 0x0F
        self.cr[0x27] = ID_5446
        self.sh0 = self.sh1 = 0
        self.blt = {}
        self.log = None

    # ---- ports
    def io_read(self, port: int) -> int:  #vers 1
        if port == 0x3C0:
            return self.ar_i | 0x20
        if port == 0x3C1:
            return self.ar[self.ar_i & 31]
        if port == 0x3C2:
            return 0
        if port == 0x3C4:
            return self.sr_i
        if port == 0x3C5:
            i = self.sr_i
            if i & 15 == 0 and i >= 0x10:
                return self.sr[0x10 + (i & 1)]
            return self.sr[i] if i < 0x20 else 0xFF
        if port == 0x3C6:
            if self.hdac_lock + 1 == 5:
                self.hdac_lock = 0
                return self.hdac
            self.hdac_lock += 1
            return 0xFF if self.hdac_lock != 5 else self.pel_mask
        if port == 0x3C7:
            return self.dac_state
        if port == 0x3C8:
            return self.dac_w
        if port == 0x3C9:
            if self.sr[0x12] & 2:
                v = self.hpal[(self.dac_r & 15) * 3 + self.dac_sub]
            else:
                v = self.pal[self.dac_r * 3 + self.dac_sub]
            self.dac_sub += 1
            if self.dac_sub == 3:
                self.dac_sub = 0
                self.dac_r = (self.dac_r + 1) & 255
            return v
        if port == 0x3CC:
            return self.misc
        if port == 0x3CE:
            return self.gr_i
        if port == 0x3CF:
            i = self.gr_i
            if i == 0:
                return self.sh0
            if i == 1:
                return self.sh1
            return self.gr[i] if i < 0x3A else 0xFF
        if port in (0x3B4, 0x3D4):
            return self.cr_i
        if port in (0x3B5, 0x3D5):
            i = self.cr_i
            if i == 0x24:
                return self.ar_flip << 7
            if i == 0x26:
                return self.ar_i & 0x3F
            return self.cr[i] if i < 0x28 else 0xFF
        if port in (0x3BA, 0x3DA):
            self.ar_flip = 0
            self.stat = (self.stat + 1) & 3
            return STATUS[self.stat]
        return 0xFF

    def io_write(self, port: int, v: int) -> None:  #vers 1
        v &= 0xFF
        if port == 0x3C0:
            if not self.ar_flip:
                self.ar_i = v & 0x1F
            else:
                self.ar[self.ar_i] = v
            self.ar_flip ^= 1
        elif port == 0x3C2:
            self.misc = v
        elif port == 0x3C4:
            self.sr_i = v
        elif port == 0x3C5:
            self._sr_write(v)
        elif port == 0x3C6:
            if self.hdac_lock == 4:
                self.hdac = v
            else:
                self.pel_mask = v
            self.hdac_lock = 0
        elif port == 0x3C7:
            self.dac_r, self.dac_sub, self.dac_state = v, 0, 3
        elif port == 0x3C8:
            self.dac_w, self.dac_sub, self.dac_state = v, 0, 0
        elif port == 0x3C9:
            self.dac_cache[self.dac_sub] = v
            self.dac_sub += 1
            if self.dac_sub == 3:
                tgt = self.hpal if self.sr[0x12] & 2 else self.pal
                base = (self.dac_w & 15) * 3 if tgt is self.hpal else self.dac_w * 3
                tgt[base:base + 3] = self.dac_cache
                self.dac_sub = 0
                self.dac_w = (self.dac_w + 1) & 255
        elif port == 0x3CE:
            self.gr_i = v
        elif port == 0x3CF:
            self._gr_write(self.gr_i, v)
        elif port in (0x3B4, 0x3D4):
            self.cr_i = v
        elif port in (0x3B5, 0x3D5):
            i = self.cr_i
            if i <= 0x18:
                if self.cr[0x11] & 0x80 and i <= 7:
                    if i == 7:
                        self.cr[7] = (self.cr[7] & ~0x10) | (v & 0x10)
                    return
                self.cr[i] = v
            elif i in (0x19, 0x1A, 0x1B, 0x1C, 0x1D):
                self.cr[i] = v
        if self.log:
            self.log(port, v)

    def _sr_write(self, v: int) -> None:  #vers 1
        i = self.sr_i
        if i <= 4:
            self.sr[i] = v & SR_MASK[i]
        elif i == 6:
            self.sr[6] = 0x12 if v & 0x17 == 0x12 else 0x0F
        elif i & 0x0F == 0 and i >= 0x10:
            self.sr[0x10] = v
            self.cur_x = v << 3 | i >> 5
        elif i & 0x0F == 1 and i >= 0x10:
            self.sr[0x11] = v
            self.cur_y = v << 3 | i >> 5
        elif i == 0x17:
            self.sr[0x17] = (self.sr[0x17] & 0x38) | (v & 0xC7)
        elif i in (7, 8, 9, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x12, 0x13, 0x14, 0x15, 0x16, 0x18, 0x19, 0x1A, 0x1B, 0x1C, 0x1D, 0x1E, 0x1F):
            self.sr[i] = v

    def _gr_write(self, i: int, v: int) -> None:  #vers 1
        g = self.gr
        if i == 0:
            g[0] = v & 0x0F
            self.sh0 = v
        elif i == 1:
            g[1] = v & 0x0F
            self.sh1 = v
        elif i < 9:
            g[i] = v & GR_MASK[i]
        elif i == 5:
            g[5] = v & 0x7F
        elif i in (0x09, 0x0A, 0x0B, 0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x20, 0x22, 0x24, 0x26, 0x28, 0x29, 0x2C, 0x2D, 0x2F, 0x30, 0x32, 0x33, 0x34, 0x35, 0x38, 0x39):
            g[i] = v
        elif i in (0x21, 0x23, 0x25, 0x27):
            g[i] = v & 0x1F
        elif i == 0x2A:
            g[i] = v & 0x3F
            if g[0x31] & 0x80:
                self._blit_start()
        elif i == 0x2E:
            g[i] = v & 0x3F
        elif i == 0x31:
            old, g[0x31] = g[0x31], v
            if old & 4 and not v & 4:
                g[0x31] &= ~0x13
            elif not old & 2 and v & 2:
                self._blit_start()

    # ---- display
    def bpp(self) -> int:  #vers 1
        s7 = self.sr[7]
        if not s7 & 1:
            return 0
        m = s7 & 0x0E
        if m == 0:
            return 8
        if m in (2, 6):
            return 16 if self.hdac & 0x0F == 1 else 15
        return 24 if m == 4 else 32 if m == 8 else 8

    def resolution(self) -> tuple:  #vers 1
        c = self.cr
        w = (c[1] + 1) * 8
        h = (c[0x12] | (c[7] & 2) << 7 | (c[7] & 0x40) << 3) + 1
        if c[0x1A] & 1:
            h *= 2
        return w, h

    def params(self) -> tuple:  #vers 1
        c = self.cr
        pitch = (c[0x13] | (c[0x1B] & 0x10) << 4) << 3
        start = c[0x0C] << 8 | c[0x0D] | (c[0x1B] & 1) << 16 | (c[0x1B] & 0x0C) << 15 | (c[0x1D] & 0x80) << 12
        return pitch, start

    def active(self) -> bool:  #vers 1
        return self.bpp() > 0 and not self.sr[1] & 0x20 and bool(self.ar_i is not None)

    def frame(self):  #vers 1
        """(w, h, BGRA bytes) of the current mode, or None when the chip is in VGA or blanked."""
        b = self.bpp()
        if not b or self.sr[1] & 0x20:
            return None
        w, h = self.resolution()
        pitch, start = self.params()
        start *= 4
        if w < 8 or h < 8 or pitch == 0 or w > 2048 or h > 2048:
            return None
        bytes_pp = 1 if b == 8 else 2 if b in (15, 16) else 3 if b == 24 else 4
        need = start + pitch * (h - 1) + w * bytes_pp
        if need > self.size or pitch < w * bytes_pp:
            return None
        buf = np.frombuffer(self.vram, dtype=np.uint8, count=pitch * h, offset=start).reshape(h, pitch)[:, :w * bytes_pp]
        out = np.empty((h, w, 4), dtype=np.uint8)
        out[..., 3] = 255
        if b == 8:
            p = np.array(self.pal[:768], dtype=np.uint32).reshape(256, 3) & 0x3F
            lut = ((p << 2) | (p >> 4)).astype(np.uint8)
            idx = buf
            out[..., 2], out[..., 1], out[..., 0] = lut[idx, 0], lut[idx, 1], lut[idx, 2]
        elif b in (15, 16):
            px = np.ascontiguousarray(buf).view("<u2").reshape(h, w).astype(np.uint32)
            if b == 15:
                r, g, bl = (px >> 10) & 31, (px >> 5) & 31, px & 31
                r, g, bl = (r << 3) | (r >> 2), (g << 3) | (g >> 2), (bl << 3) | (bl >> 2)
            else:
                r, g, bl = (px >> 11) & 31, (px >> 5) & 63, px & 31
                r, g, bl = (r << 3) | (r >> 2), (g << 2) | (g >> 4), (bl << 3) | (bl >> 2)
            out[..., 2], out[..., 1], out[..., 0] = r, g, bl
        elif b == 24:
            t = buf.reshape(h, w, 3)
            out[..., 0], out[..., 1], out[..., 2] = t[..., 0], t[..., 1], t[..., 2]
        else:
            t = np.ascontiguousarray(buf).reshape(h, w, 4)
            out[..., 0], out[..., 1], out[..., 2] = t[..., 0], t[..., 1], t[..., 2]
        self._cursor(out, w, h)
        return w, h, out.tobytes()

    def _cursor(self, out, w: int, h: int) -> None:  #vers 1
        if not self.sr[0x12] & 1:
            return
        large = bool(self.sr[0x12] & 4)
        n = 64 if large else 32
        base = self.size - 16384
        base += (self.sr[0x13] & 0x3C) * 256 if large else (self.sr[0x13] & 0x3F) * 256
        c0 = tuple((self.hpal[i] & 0x3F) << 2 for i in (2, 1, 0))
        c1 = tuple((self.hpal[45 + i] & 0x3F) << 2 for i in (2, 1, 0))
        for y in range(n):
            sy = self.cur_y + y
            if not 0 <= sy < h:
                continue
            if large:
                a = base + y * 16
                p0, p1 = self.vram[a:a + 8], self.vram[a + 8:a + 16]
            else:
                a = base + y * 4
                p0, p1 = self.vram[a:a + 4], self.vram[a + 128:a + 132]
            for x in range(n):
                sx = self.cur_x + x
                if not 0 <= sx < w:
                    continue
                b0 = p0[x >> 3] >> (7 - (x & 7)) & 1
                b1 = p1[x >> 3] >> (7 - (x & 7)) & 1
                if b0 and not b1:
                    out[sy, sx, :3] ^= 255
                elif b1 and not b0:
                    out[sy, sx, :3] = c0
                elif b0 and b1:
                    out[sy, sx, :3] = c1

    # ---- blitter
    @staticmethod
    def _rop(code: int, s, d):  #vers 1
        k = ROPS.get(code, 5)
        if k == 0: return d & 0
        if k == 1: return s & d
        if k == 2: return d
        if k == 3: return s & ~d
        if k == 4: return ~d
        if k == 5: return s
        if k == 6: return ~(d & 0)
        if k == 7: return ~s & d
        if k == 8: return s ^ d
        if k == 9: return s | d
        if k == 10: return ~s | ~d
        if k == 11: return ~(s ^ d)
        if k == 12: return s | ~d
        if k == 13: return ~s
        if k == 14: return ~s | d
        return ~s & ~d

    def _px(self, addr: int, n: int, bpp: int):  #vers 1
        """n pixels starting at addr as an integer array."""
        v = self.vram
        if bpp == 1:
            return np.frombuffer(v, dtype=np.uint8, count=n, offset=addr).astype(np.uint32)
        if bpp == 2:
            return np.frombuffer(bytes(v[addr:addr + 2 * n]), dtype="<u2").astype(np.uint32)
        if bpp == 4:
            return np.frombuffer(bytes(v[addr:addr + 4 * n]), dtype="<u4").astype(np.uint32)
        t = np.frombuffer(bytes(v[addr:addr + 3 * n]), dtype=np.uint8).reshape(n, 3).astype(np.uint32)
        return t[:, 0] | t[:, 1] << 8 | t[:, 2] << 16

    def _put(self, addr: int, px, bpp: int) -> None:  #vers 1
        if bpp == 1:
            self.vram[addr:addr + len(px)] = (px & 0xFF).astype(np.uint8).tobytes()
        elif bpp == 2:
            self.vram[addr:addr + 2 * len(px)] = (px & 0xFFFF).astype("<u2").tobytes()
        elif bpp == 4:
            self.vram[addr:addr + 4 * len(px)] = px.astype("<u4").tobytes()
        else:
            t = np.empty((len(px), 3), dtype=np.uint8)
            t[:, 0], t[:, 1], t[:, 2] = px & 255, (px >> 8) & 255, (px >> 16) & 255
            self.vram[addr:addr + 3 * len(px)] = t.tobytes()

    def _color(self, fg: bool, bpp: int) -> int:  #vers 1
        g = self.gr
        lo = (self.sh1 if fg else self.sh0) & 0xFF
        a = (0x11, 0x13, 0x15) if fg else (0x10, 0x12, 0x14)
        if bpp == 1:
            return lo
        if bpp == 2:
            return lo | g[a[0]] << 8
        if bpp == 3:
            return lo | g[a[0]] << 8 | g[a[1]] << 16
        return lo | g[a[0]] << 8 | g[a[1]] << 16 | g[a[2]] << 24

    def _blit_start(self) -> None:  #vers 1
        g = self.gr
        g[0x31] |= 1
        width = (g[0x20] | g[0x21] << 8) + 1
        height = (g[0x22] | g[0x23] << 8) + 1
        dpitch = g[0x24] | g[0x25] << 8
        spitch = g[0x26] | g[0x27] << 8
        daddr = (g[0x28] | g[0x29] << 8 | g[0x2A] << 16) % self.size
        saddr = (g[0x2C] | g[0x2D] << 8 | g[0x2E] << 16) % self.size
        mode, ext, rop = g[0x30], g[0x33], g[0x32]
        bpp = ((mode & 0x30) >> 4) + 1
        done = True
        try:
            if mode & 6:
                done = False
            elif ext & 4 and mode & 0xCA == 0xC0:
                self._fill(daddr, dpitch, width, height, bpp, rop)
            elif mode & 0xC0 == 0x80:
                self._expand(daddr, saddr, dpitch, width, height, bpp, rop, mode, ext, pattern=False)
            elif mode & 0x40:
                if mode & 0x80:
                    self._expand(daddr, saddr, dpitch, width, height, bpp, rop, mode, ext, pattern=True)
                else:
                    self._pattern(daddr, saddr, dpitch, width, height, bpp, rop)
            else:
                self._copy(daddr, saddr, dpitch, spitch, width, height, bpp, rop, mode)
        except (ValueError, IndexError):
            done = False
        if not done and self.log:
            self.log("blit-ignored", mode)
        g[0x31] &= ~0x13

    def _rows(self, addr: int, pitch: int, w_bytes: int, h: int, bpp: int, back: bool):  #vers 1
        """Pixel arrays for h rows at addr, pitch bytes apart."""
        n = w_bytes // bpp
        step = -pitch if back else pitch
        return [self._px(addr + r * step, n, bpp) for r in range(h)], step, n

    def _copy(self, daddr, saddr, dpitch, spitch, width, height, bpp, rop, mode) -> None:  #vers 1
        back = bool(mode & 1)
        n = width // bpp
        srcs = [self._px(saddr + r * (-spitch if back else spitch), n, bpp) for r in range(height)]
        mask = (1 << (8 * bpp)) - 1
        tc = None
        if mode & 8:
            tc = (self.gr[0x34] | self.gr[0x35] << 8) & (0xFF if bpp == 1 else 0xFFFF)
        for r in range(height):
            a = daddr + r * (-dpitch if back else dpitch)
            d = self._px(a, n, bpp)
            res = self._rop(rop, srcs[r], d) & mask
            if tc is not None:
                res = np.where(res != tc, res, d)
            self._put(a, res, bpp)

    def _fill(self, daddr, dpitch, width, height, bpp, rop) -> None:  #vers 1
        n = width // bpp
        col = np.full(n, self._color(True, bpp), dtype=np.uint32)
        mask = (1 << (8 * bpp)) - 1
        for r in range(height):
            a = daddr + r * dpitch
            d = self._px(a, n, bpp)
            self._put(a, self._rop(rop, col, d) & mask, bpp)

    def _pattern(self, daddr, saddr, dpitch, width, height, bpp, rop) -> None:  #vers 2
        size = 64 if bpp == 1 else 128 if bpp == 2 else 256
        base = saddr & ~(size - 1)
        py0 = saddr & 7
        skip = self.gr[0x2F] & 0x1F
        skip = skip // 3 if bpp == 3 else skip & 7
        n = width // bpp
        mask = (1 << (8 * bpp)) - 1
        cols = np.arange(n) & 7
        for r in range(height):
            row = self._px(base + ((py0 + r) & 7) * 8 * bpp, 8, bpp)
            a = daddr + r * dpitch
            d = self._px(a, n, bpp)
            res = self._rop(rop, row[cols], d) & mask
            res[:skip] = d[:skip]
            self._put(a, res, bpp)

    def _expand(self, daddr, saddr, dpitch, width, height, bpp, rop, mode, ext, pattern: bool) -> None:  #vers 2
        n = width // bpp
        skip = self.gr[0x2F] & 0x1F
        skip = skip // 3 if bpp == 3 else skip & 7
        mask = (1 << (8 * bpp)) - 1
        fg, bg = self._color(True, bpp), self._color(False, bpp)
        inv = bool(ext & 2)
        transp = bool(mode & 8)
        py0 = saddr & 7
        sp = (n + 7) // 8
        for r in range(height):
            if pattern:
                byte = self.vram[(saddr & ~7) + ((py0 + r) & 7)]
                bits = np.resize(np.unpackbits(np.array([byte], dtype=np.uint8)), n)
            else:
                a0 = saddr + r * sp
                bits = np.unpackbits(np.frombuffer(bytes(self.vram[a0:a0 + sp]), dtype=np.uint8))[:n]
            if inv:
                bits = bits ^ 1
            a = daddr + r * dpitch
            d = self._px(a, n, bpp)
            if transp:
                col = np.full(n, bg if inv else fg, dtype=np.uint32)
                res = np.where(bits == 1, self._rop(rop, col, d) & mask, d)
            else:
                col = np.where(bits == 1, fg, bg).astype(np.uint32)
                res = self._rop(rop, col, d) & mask
            res[:skip] = d[:skip]
            self._put(a, res, bpp)
