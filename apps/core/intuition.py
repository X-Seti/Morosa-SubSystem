#this belongs in apps/core/intuition.py - Version: 1
# X-Seti - November 17 2026 - Morosa - Morosa intuition.library.

"""
Morosa intuition.library - screens, windows and IDCMP messages; each window owns a bitmap shown by the display.
"""

##Methods list -
# Intuition
# Intuition._alloc_port
# Intuition._screen
# Intuition._tags
# Intuition._window
# Intuition._wb_screen
# Intuition.f_ActivateWindow
# Intuition.f_ClearPointer
# Intuition.f_CloseScreen
# Intuition.f_CloseWindow
# Intuition.f_DisplayBeep
# Intuition.f_EasyRequestArgs
# Intuition.f_GetDefaultPubScreen
# Intuition.f_LockIBase
# Intuition.f_LockPubScreen
# Intuition.f_ModifyIDCMP
# Intuition.f_MoveWindow
# Intuition.f_OpenScreen
# Intuition.f_OpenScreenTagList
# Intuition.f_OpenWindow
# Intuition.f_OpenWindowTagList
# Intuition.f_RefreshWindowFrame
# Intuition.f_ScreenToBack
# Intuition.f_ScreenToFront
# Intuition.f_SetPointer
# Intuition.f_SetWindowTitles
# Intuition.f_ShowTitle
# Intuition.f_SizeWindow
# Intuition.f_UnlockIBase
# Intuition.f_UnlockPubScreen
# Intuition.f_ViewPortAddress
# Intuition.f_WindowLimits
# Intuition.f_WindowToBack
# Intuition.f_WindowToFront
# Intuition.post

from apps.core.exec import Unimplemented

TAG_USER = 0x80000000
SA, WA = TAG_USER + 0x20, TAG_USER + 0x63
SCREEN_SIZE, WINDOW_SIZE, MSG_SIZE = 400, 160, 52
WB_PALETTE = {0: (170, 170, 170), 1: (0, 0, 0), 2: (255, 255, 255), 3: (102, 136, 187),
              4: (238, 68, 68), 5: (85, 221, 85), 6: (0, 68, 221), 7: (238, 153, 0)}
IDCMP_CLOSEWINDOW = 0x200


class Intuition:
    """intuition.library functions; f_<Name> reads registers from the CPU."""

    def __init__(self, machine):  #vers 1
        self.m = machine
        self.cpu = machine.cpu
        self.bus = machine.bus
        self.ex = machine.exec
        self.screens = []
        self.windows = []
        self.wb = 0
        self.front = 0

    # ---- helpers ----
    def _tags(self, a: int) -> dict:  #vers 1
        out, b = {}, self.bus
        while a:
            t = b.r32(a)
            if t == 0:
                break
            if t == 1:
                break
            if t == 2:
                a = b.r32(a + 4)
                continue
            if t == 3:
                a += 8 + 8 * 0
                continue
            out[t] = b.r32(a + 4)
            a += 8
        return out

    def _alloc_port(self) -> int:  #vers 1
        cpu = self.cpu
        saved = cpu.d[0]
        cpu.d[0] = 0xFFFFFFFF
        self.ex.f_AllocSignal()
        sb = cpu.d[0] & 0xFF
        cpu.d[0] = saved
        p = self.ex.alloc(34)
        b = self.bus
        b.w8(p + 8, 4)
        b.w8(p + 14, 0)
        b.w8(p + 15, sb)
        b.w32(p + 16, self.m.process)
        self.ex.new_list(p + 20)
        return p

    def _screen(self, w: int, h: int, depth: int, title: str, left: int = 0, top: int = 0) -> int:  #vers 1
        b, ex = self.bus, self.ex
        gfx = self.m.owners["graphics"]
        s = ex.alloc(SCREEN_SIZE)
        b.w16(s + 8, left)
        b.w16(s + 10, top)
        b.w16(s + 12, w)
        b.w16(s + 14, h)
        b.w8(s + 30, 10)
        b.w8(s + 35, 11)
        b.w8(s + 36, 4)
        b.w8(s + 37, 4)
        b.w8(s + 38, 4)
        t = ex.alloc(len(title) + 4)
        ex.put_cstr(t, title)
        b.w32(s + 22, t)
        b.w32(s + 26, t)
        b.w32(s + 40, gfx._font(8))
        bm = s + 184
        bpr = ((w + 15) >> 4) << 1
        b.w16(bm, bpr)
        b.w16(bm + 2, h)
        b.w8(bm + 5, depth)
        for i in range(min(depth, 8)):
            b.w32(bm + 8 + 4 * i, ex.alloc(bpr * h + 8))
        rp = s + 84
        self.cpu.a[1] = rp
        gfx.f_InitRastPort()
        b.w32(rp + 4, bm)
        vp = s + 44
        b.w32(vp + 16, rp)
        for i, c in WB_PALETTE.items():
            if i < (1 << depth):
                gfx._pal(vp)[i] = c
        b.w16(vp + 24, w)
        b.w16(vp + 26, h)
        self.screens.append(s)
        self.front = s
        return s

    def _wb_screen(self) -> int:  #vers 1
        if not self.wb:
            self.wb = self._screen(640, 256, 2, "Workbench Screen")
        return self.wb

    def _window(self, x, y, w, h, title, scr, idcmp, flags, pens=(0, 1), minmax=(0, 0, 0, 0)) -> int:  #vers 1
        b, ex = self.bus, self.ex
        gfx = self.m.owners["graphics"]
        win = ex.alloc(WINDOW_SIZE)
        sb = scr
        depth = b.r8(sb + 184 + 5)
        top = 11 if not flags & 0x800 else 0
        for off, v in ((4, x), (6, y), (8, w), (10, h), (16, minmax[0] or w), (18, minmax[1] or h),
                       (20, minmax[2] or 0xFFFF), (22, minmax[3] or 0xFFFF)):
            b.w16(win + off, v)
        b.w32(win + 24, flags)
        b.w32(win + 46, scr)
        b.w8(win + 54, 4 if not flags & 0x800 else 0)
        b.w8(win + 55, top)
        b.w8(win + 56, 4 if not flags & 0x800 else 0)
        b.w8(win + 57, 4 if not flags & 0x800 else 0)
        b.w8(win + 98, pens[0])
        b.w8(win + 99, pens[1])
        self._title(win, title)
        bm = ex.alloc(40)
        bpr = ((w + 15) >> 4) << 1
        b.w16(bm, bpr)
        b.w16(bm + 2, h)
        b.w8(bm + 5, depth)
        for i in range(min(depth, 8)):
            b.w32(bm + 8 + 4 * i, ex.alloc(bpr * h + 8))
        rp = ex.alloc(100)
        self.cpu.a[1] = rp
        gfx.f_InitRastPort()
        b.w32(rp + 4, bm)
        b.w32(win + 50, rp)
        if idcmp:
            b.w32(win + 82, idcmp)
            port = self._alloc_port()
            b.w32(win + 86, port)
            b.w32(win + 90, port)
        self._frame(win)
        b.w32(win, b.r32(scr + 4))
        b.w32(scr + 4, win)
        self.windows.append(win)
        return win

    def _title(self, win: int, title: str) -> None:  #vers 1
        old = self.bus.r32(win + 32)
        t = self.ex.alloc(len(title) + 4)
        self.ex.put_cstr(t, title)
        self.bus.w32(win + 32, t)
        if old:
            self.ex.free(old, len(self.ex.cstr(old)) + 4)

    def _frame(self, win: int) -> None:  #vers 1
        """Paint the border and title bar into the window bitmap."""
        b, g = self.bus, self.m.owners["graphics"]
        rp, w, h = b.r32(win + 50), b.r16(win + 8), b.r16(win + 10)
        if b.r32(win + 24) & 0x800:
            return
        cpu = self.cpu
        top = b.r8(win + 55)
        depth = b.r8(b.r32(rp + 4) + 5)
        light, dark = (2, 1) if depth > 1 else (1, 1)
        cpu.a[1] = rp
        for pen, args in ((0, (0, 0, w - 1, h - 1)), (light, (0, 0, w - 1, top - 1))):
            cpu.d[0] = pen
            g.f_SetAPen()
            cpu.d[0], cpu.d[1], cpu.d[2], cpu.d[3] = args
            g.f_RectFill()
        cpu.d[0] = dark
        g.f_SetAPen()
        for x0, y0, x1, y1 in ((0, 0, w - 1, 0), (0, 0, 0, h - 1), (w - 1, 0, w - 1, h - 1), (0, h - 1, w - 1, h - 1), (0, top - 1, w - 1, top - 1)):
            cpu.d[0], cpu.d[1] = x0, y0
            g.f_Move()
            cpu.d[0], cpu.d[1] = x1, y1
            g.f_Draw()
        t = b.r32(win + 32)
        if t:
            cpu.d[0] = dark
            g.f_SetAPen()
            cpu.d[0] = 3 if depth > 1 else 0
            g.f_SetBPen()
            cpu.d[0] = 1
            g.f_SetDrMd()
            cpu.d[0], cpu.d[1] = 20, 8
            g.f_Move()
            cpu.a[0], cpu.d[0] = t, min(len(self.ex.cstr(t)), max(0, (w - 40) // 8))
            g.f_Text()
        cpu.d[0] = 1
        g.f_SetAPen()
        cpu.d[0] = 0
        g.f_SetBPen()
        cpu.d[0], cpu.d[1] = 0, 0
        g.f_Move()

    # ---- screens ----
    def f_OpenScreen(self):  #vers 1
        cpu, b = self.cpu, self.bus
        ns = cpu.a[0]
        title = self.ex.cstr(b.r32(ns + 20)) if b.r32(ns + 20) else ""
        cpu.d[0] = self._screen(b.r16(ns + 4), b.r16(ns + 6), b.r16(ns + 8), title, b.r16(ns), b.r16(ns + 2))

    def f_OpenScreenTagList(self):  #vers 1
        cpu, b = self.cpu, self.bus
        ns, tags = cpu.a[0], self._tags(cpu.a[1])
        w = tags.get(SA + 3, b.r16(ns + 4) if ns else 640)
        h = tags.get(SA + 4, b.r16(ns + 6) if ns else 256)
        dp = tags.get(SA + 5, b.r16(ns + 8) if ns else 2)
        tt = tags.get(SA + 8, b.r32(ns + 20) if ns else 0)
        w = 640 if w >> 31 or w in (0xFFFF, 0xFFFFFFFF) else w
        h = 256 if h >> 31 or h in (0xFFFF, 0xFFFFFFFF) else h
        cpu.d[0] = self._screen(w, h, dp or 2, self.ex.cstr(tt) if tt else "")

    def f_CloseScreen(self):  #vers 1
        s = self.cpu.a[0]
        if s in self.screens:
            self.screens.remove(s)
        self.cpu.d[0] = 0xFFFFFFFF

    def f_ScreenToFront(self):  #vers 1
        self.front = self.cpu.a[0]

    def f_ScreenToBack(self):  #vers 1
        pass

    def f_ViewPortAddress(self):  #vers 1
        self.cpu.d[0] = self.bus.r32(self.cpu.a[0] + 46) + 44

    def f_LockPubScreen(self):  #vers 1
        self.cpu.d[0] = self._wb_screen()

    def f_GetDefaultPubScreen(self):  #vers 1
        self.cpu.d[0] = 0

    def f_UnlockPubScreen(self):  #vers 1
        pass

    def f_LockIBase(self):  #vers 1
        self.cpu.d[0] = 1

    def f_UnlockIBase(self):  #vers 1
        pass

    def f_ShowTitle(self):  #vers 1
        pass

    def f_DisplayBeep(self):  #vers 1
        pass

    # ---- windows ----
    def f_OpenWindow(self):  #vers 1
        cpu, b = self.cpu, self.bus
        nw = cpu.a[0]
        scr = b.r32(nw + 30) or self._wb_screen()
        title = self.ex.cstr(b.r32(nw + 26)) if b.r32(nw + 26) else ""
        cpu.d[0] = self._window(b.r16(nw), b.r16(nw + 2), b.r16(nw + 4), b.r16(nw + 6), title, scr,
                                b.r32(nw + 10), b.r32(nw + 14), (b.r8(nw + 8), b.r8(nw + 9)),
                                (b.r16(nw + 38), b.r16(nw + 40), b.r16(nw + 42), b.r16(nw + 44)))

    def f_OpenWindowTagList(self):  #vers 1
        cpu, b = self.cpu, self.bus
        nw, t = cpu.a[0], self._tags(cpu.a[1])
        g = lambda i, d: t.get(WA + i, d)
        if nw:
            d = dict(x=b.r16(nw), y=b.r16(nw + 2), w=b.r16(nw + 4), h=b.r16(nw + 6), idcmp=b.r32(nw + 10),
                     flags=b.r32(nw + 14), title=b.r32(nw + 26), scr=b.r32(nw + 30))
        else:
            d = dict(x=0, y=0, w=200, h=100, idcmp=0, flags=0, title=0, scr=0)
        scr = g(13, d["scr"]) or self._wb_screen()
        sw, sh = b.r16(scr + 12), b.r16(scr + 14)
        w, h = g(3, d["w"]), g(4, d["h"])
        bl, bt, br, bb = 4, 11, 4, 4
        if (WA + 19) in t:
            w = t[WA + 19] + bl + br
        if (WA + 20) in t:
            h = t[WA + 20] + bt + bb
        w = sw if w >> 15 else w
        h = sh if h >> 15 else h
        flags = d["flags"]
        for tag, fl in ((30, 0x1), (31, 0x2), (32, 0x4), (33, 0x8), (34, 0x100), (37, 0x800), (38, 0x1000),
                        (35, 0x200), (46, 0x400)):
            if g(tag, 0):
                flags |= fl
        tt = g(11, d["title"])
        cpu.d[0] = self._window(g(1, d["x"]), g(2, d["y"]), w, h, self.ex.cstr(tt) if tt else "", scr,
                                g(7, d["idcmp"]), flags)

    def f_CloseWindow(self):  #vers 1
        win = self.cpu.a[0]
        b = self.bus
        if win in self.windows:
            self.windows.remove(win)
        scr = b.r32(win + 46)
        prev = scr + 4
        while b.r32(prev) not in (0, win):
            prev = b.r32(prev)
        if b.r32(prev) == win:
            b.w32(prev, b.r32(win))

    def f_SetWindowTitles(self):  #vers 1
        cpu, b = self.cpu, self.bus
        win, t = cpu.a[0], cpu.a[1]
        if t != 0xFFFFFFFF and t:
            self._title(win, self.ex.cstr(t))
            self._frame(win)

    def f_ModifyIDCMP(self):  #vers 1
        cpu, b = self.cpu, self.bus
        win = cpu.a[0]
        b.w32(win + 82, cpu.d[0])
        if cpu.d[0] and not b.r32(win + 86):
            port = self._alloc_port()
            b.w32(win + 86, port)
            b.w32(win + 90, port)
        cpu.d[0] = 0xFFFFFFFF

    def f_RefreshWindowFrame(self):  #vers 1
        self._frame(self.cpu.a[0])

    def f_ActivateWindow(self):  #vers 1
        pass

    def f_WindowToFront(self):  #vers 1
        pass

    def f_WindowToBack(self):  #vers 1
        pass

    def f_MoveWindow(self):  #vers 1
        cpu, b = self.cpu, self.bus
        s = lambda v: v - (1 << 32) if v >> 31 else v
        win = cpu.a[0]
        b.w16(win + 4, (b.r16(win + 4) + s(cpu.d[0])) & 0xFFFF)
        b.w16(win + 6, (b.r16(win + 6) + s(cpu.d[1])) & 0xFFFF)

    def f_SizeWindow(self):  #vers 1
        pass

    def f_WindowLimits(self):  #vers 1
        cpu, b = self.cpu, self.bus
        win = cpu.a[0]
        for off, v in ((16, cpu.d[0]), (18, cpu.d[1]), (20, cpu.d[2]), (22, cpu.d[3])):
            if v:
                b.w16(win + off, v & 0xFFFF)
        cpu.d[0] = 0xFFFFFFFF

    def f_SetPointer(self):  #vers 1
        pass

    def f_ClearPointer(self):  #vers 1
        pass

    # ---- requesters ----
    def f_EasyRequestArgs(self):  #vers 1
        cpu, b = self.cpu, self.bus
        es, args = cpu.a[1], cpu.a[3]
        ui = getattr(self.m, "ui", None)
        if ui is None:
            raise Unimplemented("intuition.library EasyRequestArgs: no display attached")
        title = self.ex.cstr(b.r32(es + 8)) if b.r32(es + 8) else ""
        text, args = self.ex.format(b.r32(es + 12), args)
        gad, _ = self.ex.format(b.r32(es + 16), args)
        buttons = bytes(gad[:-1]).decode("latin-1").split("|")
        pick = ui.request(title, bytes(text[:-1]).decode("latin-1"), buttons)
        cpu.d[0] = 0 if pick == len(buttons) - 1 else pick + 1

    # ---- events ----
    def post(self, win: int, cls: int, code: int = 0, qual: int = 0, addr: int = 0, x: int = 0, y: int = 0) -> bool:  #vers 1
        """Queue an IntuiMessage on the window's port when its IDCMP mask wants the class."""
        b = self.bus
        if win not in self.windows or not b.r32(win + 82) & cls:
            return False
        port = b.r32(win + 86)
        msg = self.ex.alloc(MSG_SIZE)
        b.w8(msg + 8, 5)
        b.w16(msg + 18, MSG_SIZE)
        b.w32(msg + 20, cls)
        b.w16(msg + 24, code)
        b.w16(msg + 26, qual)
        b.w32(msg + 28, addr)
        b.w16(msg + 32, x & 0xFFFF)
        b.w16(msg + 34, y & 0xFFFF)
        b.w32(msg + 44, win)
        b.w32(msg + 14, 0)
        cpu = self.cpu
        saved = (cpu.a[0], cpu.a[1])
        cpu.a[0], cpu.a[1] = port, msg
        self.ex.f_PutMsg()
        cpu.a[0], cpu.a[1] = saved
        return True
