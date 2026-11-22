#this belongs in apps/hardware/paula.py - Version: 2
# X-Seti - November 17 2026 - Morosa - Morosa Paula.

"""
Morosa Paula - interrupt controller and DMA audio mixed to stereo PCM. Paula Plus: 8 or 16 channels, 8 to 32 bit samples.
"""

##Methods list -
# Channel
# Channel.enable
# Channel.reload
# Channel.step
# Paula
# Paula.irq_level
# Paula._chan_write
# Paula.read
# Paula.tick
# Paula.xread
# Paula.xwrite
# Paula.request
# Paula.write

import math
from apps.core import video_ext

COLOR_CLOCK_PAL = 3546895
INTEN = 0x4000
LEVEL = {0: 1, 1: 1, 2: 1, 3: 2, 4: 3, 5: 3, 6: 3, 7: 4, 8: 4, 9: 4, 10: 4, 11: 5, 12: 5, 13: 6}
DMAEN = 0x200
AUD_BASE = 0x0A0


class Channel:
    """One audio channel; state lives in a list so video_ext.paula_tick can run it."""

    FIELDS = ("on", "per", "counter", "ptr", "left", "word", "byte_no", "out", "vol", "lc", "len", "fmt")

    def __init__(self, paula, index: int):  #vers 2
        self.paula, self.index = paula, index
        self.s = [0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0]
        self.dat = 0

    def enable(self, on: bool) -> None:  #vers 2
        if on and not self.on:
            self.reload(irq=True)
            self.byte_no = 2
            self.counter = 0
        self.on = on
        if not on:
            self.out = 0

    def reload(self, irq: bool) -> None:  #vers 2
        self.ptr, self.left = self.lc, (self.len or 0x10000) * 2
        if irq and self.index < 4:
            self.paula.request(1 << (7 + self.index))


for _i, _n in enumerate(Channel.FIELDS):
    setattr(Channel, _n, property(lambda self, i=_i: self.s[i], lambda self, v, i=_i: self.s.__setitem__(i, v)))


class Paula:
    """Registers: interrupts, ADKCON, audio. dma_read(addr) reads chip RAM words; dmacon() gives DMACON."""

    def __init__(self, dma_read=None, dmacon=None, irq=None, nch: int = 4, bits: int = 8, rate: int = 44100):  #vers 2
        self.dma_read = dma_read or (lambda addr: 0)
        self.dmacon = dmacon or (lambda: 0)
        self.irq_cb = irq or (lambda level: None)
        self.intena = self.intreq = self.adkcon = 0
        self.nch, self.maxfmt, self.rate = nch, {8: 0, 16: 1, 24: 2, 32: 3}[bits], rate
        self.channels = [Channel(self, i) for i in range(nch)]
        self.xdma = 0
        self.chip, self.mask = bytearray(8), 0
        self.level = 0
        self.due = 0.0
        self.samples = []
        self.sep, self.filter_mode, self.led = 100, 0, None
        self.gshift = {4: 0, 8: 1, 16: 2}.get(nch, 0)

    def request(self, bits: int) -> None:  #vers 1
        self.intreq |= bits
        self._notify()

    def irq_level(self) -> int:  #vers 1
        """Highest pending enabled interrupt level, 0 when none."""
        if not self.intena & INTEN:
            return 0
        act = self.intena & self.intreq & 0x3FFF
        return max((lv for bit, lv in LEVEL.items() if act >> bit & 1), default=0)

    def _notify(self) -> None:  #vers 1
        lv = self.irq_level()
        if lv != self.level:
            self.level = lv
            self.irq_cb(lv)

    def sync_dma(self) -> None:  #vers 1
        d = self.dmacon()
        for ch in self.channels[:4]:
            ch.enable(bool(d & DMAEN and d >> ch.index & 1))

    def read(self, off: int):  #vers 1
        """Register read; None when the offset is not a Paula register."""
        if off == 0x01C:
            return self.intena
        if off == 0x01E:
            return self.intreq
        if off == 0x010:
            return self.adkcon
        if off in (0x012, 0x014, 0x016):
            return 0
        if off == 0x018:
            return 0x3000
        if off == 0x01A:
            return 0
        return None

    def _chan_write(self, ch, reg: int, v: int) -> None:  #vers 1
        if reg == 0:
            ch.lc = ch.lc & 0xFFFF | (v & 7) << 16
        elif reg == 2:
            ch.lc = ch.lc & 0x1F0000 | v & 0xFFFE
        elif reg == 4:
            ch.len = v
        elif reg == 6:
            ch.per = v
        elif reg == 8:
            ch.vol = 64 if v & 0x40 else v & 0x3F
        elif reg == 0xA:
            ch.dat = v
        elif reg == 0xC:
            ch.fmt = min(v & 3, self.maxfmt)

    def write(self, off: int, v: int) -> bool:  #vers 1
        v &= 0xFFFF
        if off == 0x09A:
            self.intena = (self.intena | v & 0x7FFF) if v & 0x8000 else self.intena & ~v
            self._notify()
        elif off == 0x09C:
            self.intreq = (self.intreq | v & 0x7FFF) if v & 0x8000 else self.intreq & ~v
            self._notify()
        elif off == 0x09E:
            self.adkcon = (self.adkcon | v & 0x7FFF) if v & 0x8000 else self.adkcon & ~v
        elif AUD_BASE <= off < AUD_BASE + 0x40 and off & 0xF <= 0xC:
            self._chan_write(self.channels[(off - AUD_BASE) >> 4], off & 0xF, v)
        elif off in (0x030, 0x032, 0x034):
            pass
        else:
            return False
        return True

    def tick(self, clocks: int) -> None:  #vers 2
        """Run the channels for clocks colour clocks; frames collect in self.samples."""
        self.due, irq = video_ext.paula_tick(self.chip, self.mask, [c.s for c in self.channels], clocks, self.due,
                                             COLOR_CLOCK_PAL / self.rate, self.samples, 200000, self.gshift)
        if irq:
            self.request(irq)

    def xread(self, off: int) -> int:  #vers 1
        """Paula Plus register read at 0x400 and up."""
        if off == 0x4F0:
            return self.xdma
        if off == 0x4F2:
            return 0x5000 | self.nch
        if off == 0x4F4:
            return self.rate // 10
        return 0

    def xwrite(self, off: int, v: int) -> None:  #vers 1
        """Paula Plus registers: channel 4 and up at 0x400 + 0x10 per channel, XDMACON at 0x4F0."""
        v &= 0xFFFF
        if off == 0x4F0:
            self.xdma = (self.xdma | v & 0x7FFF) if v & 0x8000 else self.xdma & ~v
            for ch in self.channels[4:]:
                ch.enable(bool(self.xdma >> (ch.index - 4) & 1))
        elif 0x400 <= off < 0x400 + 0x10 * (self.nch - 4):
            self._chan_write(self.channels[4 + ((off - 0x400) >> 4)], off & 0xF, v)

    def take_samples(self) -> list:  #vers 2
        """Collected frames with filter and stereo separation applied."""
        out, self.samples = self.samples, []
        sep = getattr(self, "sep", 100)
        mode = getattr(self, "filter_mode", 0)
        if sep >= 100 and not mode:
            return out
        k = (1 + sep / 100) / 2
        led = bool(self.led and self.led()) if mode else False
        fa = 1 - math.exp(-6.2832 * 4900 / self.rate) if mode == 1 else 0
        fl = 1 - math.exp(-6.2832 * 3300 / self.rate) if led else 0
        st = self._fst = getattr(self, "_fst", [0.0] * 4)
        res = []
        for l, r in out:
            if sep < 100:
                l, r = l * k + r * (1 - k), r * k + l * (1 - k)
            if fa:
                st[0] += fa * (l - st[0]); st[1] += fa * (r - st[1]); l, r = st[0], st[1]
            if fl:
                st[2] += fl * (l - st[2]); st[3] += fl * (r - st[3]); l, r = st[2], st[3]
            res.append((int(l), int(r)))
        return res
