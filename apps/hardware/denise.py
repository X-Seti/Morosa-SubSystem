#this belongs in apps/hardware/denise.py - Version: 1
# X-Seti - November 17 2026 - Morosa - Morosa Denise.

"""
Morosa Denise - OCS/ECS video: bitplane lines to pixels with dual playfield, HAM, EHB and eight sprites.
"""

##Methods list -
# Denise
# Denise._compose
# Denise._sprite_pixels
# Denise.expand
# Denise.fetch_mult
# Denise.map_pens
# Denise.nplanes
# Denise.read
# Denise.render_line
# Denise.rgb
# Denise.write

LEFT_ABS = 0x70          # lowres x of framebuffer column 0
FB_WIDTH = 704           # hires pixels
FB_LINES = 313
HIRES, HAM, DBLPF, LACE = 0x8000, 0x0800, 0x0400, 0x0004


class Denise:
    """Register file and line renderer; Agnus feeds plane words and sprite data."""

    def __init__(self, ecs: bool = False):  #vers 1
        self.ecs = ecs
        self.bplcon0 = self.bplcon1 = self.bplcon2 = self.bplcon3 = 0
        self.color = [0] * 32
        self.spr = [dict(pos=0, ctl=0, a=0, b=0, armed=False) for _ in range(8)]
        self.fb = bytearray(FB_WIDTH * FB_LINES * 4)
        self.bpldat = [0] * 6
        self.joy = [0, 0]
        self.clxcon = self.clxdat = 0
        self.diw = (0x2C81, 0x2CC1)

    # ---- registers ----
    def write(self, off: int, v: int) -> bool:  #vers 1
        v &= 0xFFFF
        if off == 0x100:
            self.bplcon0 = v
        elif off == 0x102:
            self.bplcon1 = v
        elif off == 0x104:
            self.bplcon2 = v
        elif off == 0x106 and self.ecs:
            self.bplcon3 = v
        elif 0x180 <= off < 0x1C0:
            self.color[(off - 0x180) >> 1] = v & 0xFFF
        elif 0x110 <= off <= 0x11A:
            self.bpldat[(off - 0x110) >> 1] = v
        elif 0x140 <= off < 0x180:
            n, reg = (off - 0x140) >> 3, (off >> 1) & 3
            s = self.spr[n]
            if reg == 0:
                s["pos"] = v
            elif reg == 1:
                s["ctl"] = v
                s["armed"] = False
            elif reg == 2:
                s["a"] = v
                s["armed"] = True
            else:
                s["b"] = v
        elif off == 0x098:
            self.clxcon = v
        elif off in (0x02A, 0x02C, 0x036):
            pass
        else:
            return False
        return True

    def read(self, off: int):  #vers 1
        if off in (0x00A, 0x00C):
            return self.joy[(off - 0x00A) >> 1]
        if off == 0x00E:
            v, self.clxdat = self.clxdat, 0
            return v
        if off == 0x07C:
            return 0xFC if self.ecs else 0xFF
        return None

    def nplanes(self) -> int:  #vers 1
        return self.bplcon0 >> 12 & 7

    def fetch_mult(self) -> int:  #vers 1
        return 1

    def map_pens(self, pens: list) -> list:  #vers 1
        return pens

    def rgb(self, c: int) -> bytes:  #vers 1
        return bytes(((c & 15) * 17, (c >> 4 & 15) * 17, (c >> 8 & 15) * 17, 255))

    # ---- rendering ----
    def expand(self, words: list, hires: bool, scroll: int) -> list:  #vers 1
        """One plane's words to a list of 0/1 pixels, delayed by scroll pixels."""
        px = []
        for w in words:
            px.extend(w >> (15 - i) & 1 for i in range(16))
        if scroll:
            px = [0] * scroll + px[:-scroll]
        return px

    def _sprite_pixels(self, vpos: int, width: int) -> list:  #vers 1
        """Per hires pixel: (sprite group, colour index) or None."""
        out = [None] * width
        lace = 0
        for n in range(7, -1, -1):
            s = self.spr[n]
            if not s["armed"]:
                continue
            hstart = (s["pos"] & 0xFF) << 1 | (s["ctl"] & 1)
            x0 = (hstart - LEFT_ABS) * 2
            a, b = s["a"], s["b"]
            attached = n & 1 and s["ctl"] & 0x80
            for i in range(16):
                v = (a >> (15 - i) & 1) | (b >> (15 - i) & 1) << 1
                if not v:
                    continue
                for k in range(2):
                    x = x0 + i * 2 + k
                    if 0 <= x < width:
                        if attached:
                            other = self.spr[n - 1]
                            ov = (other["a"] >> (15 - i) & 1) | (other["b"] >> (15 - i) & 1) << 1
                            out[x] = (n >> 1, 16 + (ov | v << 2))
                        else:
                            out[x] = (n >> 1, 16 + 4 * (n >> 1) + v)
        return out

    def _compose(self, pens: list, vpos: int, bpu: int, ham: bool, dbl: bool) -> list:  #vers 1
        """Planes to colour values (12-bit) per pixel before sprites."""
        res = []
        pf2pri = bool(self.bplcon2 & 0x40)
        prev = self.color[0]
        for p in pens:
            if ham and bpu >= 5:
                ctl, d = p >> 4 & 3, p & 15
                r, g, b = prev >> 8 & 15, prev >> 4 & 15, prev & 15
                if ctl == 0:
                    prev = self.color[d]
                    res.append((prev, 1))
                    continue
                if ctl == 1:
                    b = d
                elif ctl == 2:
                    r = d
                else:
                    g = d
                prev = r << 8 | g << 4 | b
                res.append((prev, 1))
            elif dbl:
                p1 = (p & 1) | (p >> 2 & 1) << 1 | (p >> 4 & 1) << 2
                p2 = (p >> 1 & 1) | (p >> 3 & 1) << 1 | (p >> 5 & 1) << 2
                if pf2pri:
                    res.append((self.color[8 + p2], 2) if p2 else (self.color[p1], 1) if p1 else (self.color[0], 0))
                else:
                    res.append((self.color[p1], 1) if p1 else (self.color[8 + p2], 2) if p2 else (self.color[0], 0))
            elif bpu == 6:
                c = self.color[p & 31]
                res.append(((c >> 1 & 0x777) if p & 32 else c, 1 if p else 0))
            else:
                res.append((self.color[p], 1 if p else 0))
        return res

    def render_line(self, vpos: int, planes: list, x_abs: int, diw_h: tuple, diw_v: tuple) -> None:  #vers 1
        """planes: per-plane word lists for the fetched region starting at lowres x_abs; clipped to the display window."""
        if not 0 <= vpos < FB_LINES:
            return
        bc = self.bplcon0
        bpu = self.nplanes()
        hires = bool(bc & HIRES)
        ham, dbl = bool(bc & HAM), bool(bc & DBLPF)
        base = vpos * FB_WIDTH * 4
        bg = self.rgb(self.color[0])
        self.fb[base:base + FB_WIDTH * 4] = bg * FB_WIDTH
        inside_v = diw_v[0] <= vpos < diw_v[1]
        if not inside_v or not planes or not bpu:
            return
        sc1, sc2 = self.bplcon1 & 15, self.bplcon1 >> 4 & 15
        px = [self.expand(planes[i], hires, (sc1 if i % 2 == 0 else sc2) * (2 if hires else 1) // (1 if hires else 1)) if i < len(planes) else [] for i in range(bpu)]
        n = len(px[0]) if px and px[0] else 0
        pens = [sum(px[i][x] << i for i in range(bpu) if x < len(px[i])) for x in range(n)]
        pens = self.map_pens(pens)
        comp = self._compose(pens, vpos, bpu, ham, dbl)
        width = FB_WIDTH
        sprites = self._sprite_pixels(vpos, width)
        scale = 1 if hires else 2
        start = (x_abs - LEFT_ABS) * 2
        win_l, win_r = (diw_h[0] - LEFT_ABS) * 2, (diw_h[1] - LEFT_ABS) * 2
        pf1p, pf2p = self.bplcon2 & 7, self.bplcon2 >> 3 & 7
        fb = self.fb
        for i, (color, pf) in enumerate(comp):
            for k in range(scale):
                x = start + i * scale + k
                if not (win_l <= x < win_r and 0 <= x < width):
                    continue
                sp = sprites[x]
                c = color
                if sp is not None:
                    grp, idx = sp
                    lim = pf2p if pf == 2 else pf1p
                    if pf == 0 or grp < lim:
                        c = self.color[idx]
                o = base + x * 4
                fb[o:o + 4] = self.rgb(c)
