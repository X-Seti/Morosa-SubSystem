#this belongs in apps/hardware/paula.py - Version: 1
# X-Seti - November 17 2026 - Morosa - Morosa Paula.

"""
Morosa Paula - interrupt controller and four DMA audio channels mixed to stereo PCM.
"""

##Methods list -
# Channel
# Channel.enable
# Channel.reload
# Channel.step
# Paula
# Paula.irq_level
# Paula.read
# Paula.render
# Paula.request
# Paula.write

COLOR_CLOCK_PAL = 3546895
INTEN = 0x4000
LEVEL = {0: 1, 1: 1, 2: 1, 3: 2, 4: 3, 5: 3, 6: 3, 7: 4, 8: 4, 9: 4, 10: 4, 11: 5, 12: 5, 13: 6}
DMAEN = 0x200
AUD_BASE = 0x0A0


class Channel:
    """One audio channel in DMA mode: fetches words, outputs a signed byte every period."""

    def __init__(self, paula, index: int):  #vers 1
        self.paula, self.index = paula, index
        self.lc = self.len = self.per = self.vol = self.dat = 0
        self.ptr = self.left = 0
        self.word = 0
        self.byte_no = 2
        self.counter = 0
        self.out = 0
        self.on = False

    def enable(self, on: bool) -> None:  #vers 1
        if on and not self.on:
            self.reload(irq=True)
            self.byte_no = 2
            self.counter = 0
        self.on = on
        if not on:
            self.out = 0

    def reload(self, irq: bool) -> None:  #vers 1
        self.ptr, self.left = self.lc, self.len or 0x10000
        if irq:
            self.paula.request(1 << (7 + self.index))

    def step(self, cycles: int) -> None:  #vers 1
        """Advance colour clocks; the period counts clocks per output byte."""
        if not self.on:
            return
        per = self.per or 0x10000
        self.counter += cycles
        while self.counter >= per:
            self.counter -= per
            if self.byte_no >= 2:
                self.word = self.paula.dma_read(self.ptr) & 0xFFFF
                self.ptr = (self.ptr + 2) & 0xFFFFFFFF
                self.left -= 1
                self.byte_no = 0
                if self.left == 0:
                    self.reload(irq=True)
            b = self.word >> (8 - 8 * self.byte_no) & 0xFF
            self.out = b - 256 if b & 0x80 else b
            self.byte_no += 1


class Paula:
    """Registers: interrupts, ADKCON, audio. dma_read(addr) reads chip RAM words; dmacon() gives DMACON."""

    def __init__(self, dma_read=None, dmacon=None, irq=None):  #vers 1
        self.dma_read = dma_read or (lambda addr: 0)
        self.dmacon = dmacon or (lambda: 0)
        self.irq_cb = irq or (lambda level: None)
        self.intena = self.intreq = self.adkcon = 0
        self.channels = [Channel(self, i) for i in range(4)]
        self.level = 0
        self.due = 0.0
        self.samples = []

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
        for ch in self.channels:
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
        elif AUD_BASE <= off < AUD_BASE + 0x40 and off & 0xF < 0xC:
            ch, reg = self.channels[(off - AUD_BASE) >> 4], off & 0xF
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
        elif off in (0x030, 0x032, 0x034):
            pass
        else:
            return False
        return True

    def tick(self, clocks: int, rate: int = 44100) -> None:  #vers 1
        """Run the channels for clocks colour clocks and collect output frames into self.samples."""
        per_sample = COLOR_CLOCK_PAL / rate
        while clocks > 0:
            t = min(clocks, max(1, int(self.due)))
            for ch in self.channels:
                ch.step(t)
            clocks -= t
            self.due -= t
            if self.due < 1:
                self.due += per_sample
                v = [ch.out * ch.vol for ch in self.channels]
                if len(self.samples) < 200000:
                    self.samples.append((v[0] + v[3], v[1] + v[2]))

    def take_samples(self) -> list:  #vers 1
        out, self.samples = self.samples, []
        return out

    def render(self, samples: int, rate: int = 44100) -> list:  #vers 1
        """Stereo frames (left, right) in -128*64..127*64 per channel; channels 0 and 3 left, 1 and 2 right."""
        per_sample = COLOR_CLOCK_PAL / rate
        out, acc = [], 0.0
        for _ in range(samples):
            acc += per_sample
            n = int(acc)
            acc -= n
            for ch in self.channels:
                ch.step(n)
            val = [ch.out * ch.vol for ch in self.channels]
            out.append((val[0] + val[3], val[1] + val[2]))
        return out
