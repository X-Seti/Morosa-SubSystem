#this belongs in apps/hardware/amiga.py - Version: 30
# X-Seti - November 17 2026 - Morosa - Morosa Amiga Hardware.

"""
Morosa Amiga hardware - CPU, memory map and the custom chips wired together as a machine preset.
"""

##Methods list -
# PRESETS
# Amiga
# Amiga.activity
# Amiga._custom_read
# Amiga._custom_write
# Amiga._cia_read
# Amiga._cia_write
# Amiga._fast_read
# Amiga._fast_write
# Amiga._proc_read
# Amiga._proc_write
# Amiga._slow_read
# Amiga._slow_write
# Amiga._glue_read
# Amiga._nv_read
# Amiga._nv_write
# Amiga._ide_read
# Amiga._ide_write
# Amiga._ide_irq
# Amiga.attach_disk
# Amiga.attach_drive
# Amiga.insert_cd
# Amiga.attach_scsi
# Amiga._dma_read
# Amiga._dma_write
# Amiga._glue_write
# Amiga._akiko_read
# Amiga._map_board
# Amiga.add_board
# Amiga._akiko_write
# Amiga._ciab_out
# Amiga._rtc_read
# Amiga._rtc_write
# Amiga.flush_disks
# Amiga.insert_disk
# Amiga._rom_read
# Amiga._rom_write
# Amiga.load_bootstrap
# Amiga.display_box
# Amiga.framebuffer
# Amiga.boot
# Amiga.load_rom
# Amiga.reset
# Amiga.run_frame

from apps.hardware.akiko import AKIKO_BASE, Akiko
from apps.hardware.agnus import Agnus
from apps.hardware.blitter import Blitter
from apps.hardware.cia import CIA
from apps.hardware.cdtv import DMAC, DMACBoard
from apps.hardware.copper import Copper
from apps.methods.bus import Bus
from apps.core.m68k import M68K
from apps.hardware.denise import FB_LINES, FB_WIDTH, LEFT_ABS, Denise
from apps.hardware.disk import DiskDMA
from apps.hardware.floppy import Floppy
from apps.hardware.gary import Gary, Gayle, Ramsey
from apps.hardware.ide import ATADisk, IDEChannel
from apps.hardware.input import Keyboard, Ports
from apps.hardware.lisa import Lisa
from apps.hardware.memory import SparseRAM
from apps.hardware.rtc import MSM6242B, RP5C01, RTC_BASE
from apps.hardware.zorro import AutoConfig, RamBoard, Z2_CONFIG, Z3_CONFIG
from apps.hardware.ncr710 import NCR710, NCR_BASE, NCR_SIZE
from apps.hardware.paula import Paula
from apps.hardware.sdmac import SDMAC, SDMAC_BASE

# name: (cpu model, chipset, chip RAM KB, PAL by default)
PRESETS = {
    "A1000": (68000, "ocs", 256, True),
    "A500": (68000, "ocs", 512, True),
    "A2000": (68000, "ocs", 1024, True),
    "A500+": (68000, "ecs", 1024, True),
    "A600": (68000, "ecs", 1024, True),
    "A3000": (68030, "ecs", 2048, True),
    "A1200": (68020, "aga", 2048, True),
    "A4000": (68040, "aga", 2048, True),
    "A4000D": (68040, "aga", 2048, True),
    "A4000T": (68040, "aga", 2048, True),
    "CD32": (68020, "aga", 2048, True),
    "CDTV": (68000, "ocs", 1024, True),
}
CPI = 10            # CPU clocks per instruction used to share a line between CPU and chips
FAST_BASE = 0x200000
SLOW_BASE = 0xC00000
PROC_BASE = 0x08000000
MOBO_BASE = 0x07000000    # A3000 and A4000 motherboard RAM (Ramsey)
MOBO_PRESETS = ("A3000", "A4000", "A4000D", "A4000T")
ROM_BASE = 0xF80000


class Amiga:
    """One hardware Amiga. Chipsets that are not written yet refuse to start."""

    def __init__(self, preset: str = "A500", fast_kb: int = 0, pal: bool = True, cpu: int = None, addr24: bool = False, mhz: float = 0, chipset: str = "", chip_kb: int = 0, snd: tuple = (4, 8, 44100), slow_kb: int = 0, ports: tuple = ("mouse", "joy"), proc_kb: int = 0, fpu: int = 2, clx: int = 3):  #vers 16
        model, base_chipset, preset_chip, _ = PRESETS[preset]
        chip_kb = chip_kb if chip_kb in (256, 512, 1024, 2048) else preset_chip
        chipset = chipset if chipset in ("ocs", "ecs") and base_chipset != "aga" else base_chipset
        model = cpu or model
        self.preset, self.chipset = preset, chipset
        self._de03 = 0xFF
        self.bus = Bus(chip_kb * 1024)
        self.bus.amask = 0xFFFFFF if model < 68020 or addr24 else 0xFFFFFFFF
        self.bus.open_bus = preset not in ("A3000", "A4000", "A4000D", "A4000T")
        self.bus.open_ranges = [(0x200000, 0xA00000), (0xC00000, 0xD80000), (0xF00000, 0xF80000), (0x1000000, 0x10000000), (0xDD0000, 0xDE0000)]
        self.bus.open_value = 0xFFFFFFFF if chipset != "aga" and preset not in MOBO_PRESETS else 0
        self.cpu = M68K(self.bus, model)
        self.cpu.core.set_fpu(fpu)
        if addr24 and model >= 68020:
            self.cpu.core.set_amask(0xFFFFFF)
        self.ratio = max(1, round(mhz / 7.09)) if mhz else 1 if model < 68020 else 2 if model == 68020 else 3
        self.cpu.sync(lambda done: setattr(self.agnus, "hpos", min(done // self.ratio // 2, 226)))
        self.fast = SparseRAM(fast_kb * 1024)
        slow_kb = min(slow_kb, 1792)
        self.slow = SparseRAM(slow_kb * 1024)
        self.proc = SparseRAM(proc_kb * 1024)
        self.act_hd = self.act_ram = 0
        self._act_last = (0, 0, 0)
        self.fast_base = MOBO_BASE if preset in MOBO_PRESETS else FAST_BASE
        self.rom = b""
        self.wcs, self.wcs_lock = None, False
        self.paula = Paula(irq=self._irq, nch=snd[0], bits=snd[1], rate=snd[2])
        self.ciaa = CIA(irq=lambda lv: lv and self.paula.request(0x0008), port_in=self._ciaa_in)
        self.drives = [Floppy() for _ in range(4)]
        self.ciab = CIA(irq=lambda lv: lv and self.paula.request(0x2000), port_out=self._ciab_out)
        ecs = chipset == "ecs"
        self.denise = Lisa() if chipset == "aga" else Denise(ecs)
        self.denise.clx_mask = (0, 0x7E00, 0x7FFE, 0x7FFF)[clx]
        self.blitter = Blitter(None, None, ecs=chipset != "ocs" or chip_kb > 512)
        self.copper = Copper(None, None, ecs=chipset != "ocs")
        self.agnus = Agnus(self.bus.ram, self.paula, self.denise, self.blitter, self.copper, self.ciaa, self.ciab, pal, chipset)
        self.agnus.disk = DiskDMA(self.agnus.read16, self.agnus.write16, self._spinning, self.paula.request,
                                  lambda: self.agnus.dmacon, lambda: self.paula.adkcon, self.ciaa.flag)
        self.paula.dma_read = self.agnus.read16
        self.ports = self.agnus.inp = Ports()
        self.ports.devs = list(ports)
        self.keyboard = self.agnus.kbd = Keyboard(self.ciaa)
        self.gary = Gary()
        if preset in MOBO_PRESETS:
            self.bus.berr_on = lambda: bool(self.gary.timeout)
        self.ramsey = Ramsey(preset) if preset in ("A3000", "A4000", "A4000D", "A4000T") else None
        self.gayle = Gayle(0xD1 if preset in ("A1200", "CD32") else 0xD0) if preset in ("A600", "A1200", "CD32") else None
        self.dmac = DMAC(lambda on: on and self.paula.request(0x0008), lambda a, d: self._dma_write(a, d)) if preset == "CDTV" else None
        if self.dmac:
            self.agnus.hsync = self.dmac.hsync
        self.nvram = bytearray(0x8000) if preset == "CDTV" else None
        if self.nvram is not None:
            self.bus.hook_range(0xDC8000, 0xDD0000, self._nv_read, self._nv_write)
        self.card = bytearray(0x10000) if preset == "CDTV" else None
        if self.card is not None:
            self.bus.hook_range(0xE00000, 0xE80000, self._card_read, self._card_write)
        self.sdmac = SDMAC(lambda on: on and self.paula.request(0x0008), self._dma_read, self._dma_write) if preset == "A3000" else None
        if self.sdmac:
            self.bus.hook_range(SDMAC_BASE, SDMAC_BASE + 0x10000, self.sdmac.read, self.sdmac.write)
        self.ncr = NCR710(irq=lambda on: on and self.paula.request(0x0008)) if preset == "A4000T" else None
        if self.ncr:
            self.bus.hook_range(NCR_BASE, NCR_BASE + NCR_SIZE, self.ncr.read, self.ncr.write)
        self.rtc = (RP5C01() if preset in MOBO_PRESETS else MSM6242B() if preset in ("A2000", "A500+") else None)
        if self.rtc:
            self.bus.hook_range(RTC_BASE, RTC_BASE + 0x10000, self._rtc_read, self._rtc_write)
        self.z2 = AutoConfig(2, self._map_board)
        self.z3 = AutoConfig(3, self._map_board)
        if self.dmac:
            self.z2.add(DMACBoard(self.dmac))
        self.bus.hook_range(Z2_CONFIG, Z2_CONFIG + 0x10000, lambda a, n: self.z2.read(a - Z2_CONFIG, n),
                            lambda a, n, v: self.z2.write(a - Z2_CONFIG, n, v))
        if model >= 68020:
            self.bus.hook_range(Z3_CONFIG, Z3_CONFIG + 0x10000, lambda a, n: self.z3.read(a - Z3_CONFIG, n),
                                lambda a, n, v: self.z3.write(a - Z3_CONFIG, n, v))
        self.ide = None
        if preset in ("A600", "A1200", "A4000", "A4000D", "A4000T"):
            self.ide = IDEChannel(self._ide_irq)
            if self.gayle:
                self.gayle.irq = lambda on: on and self.paula.request(0x0008)
                self.bus.hook_range(0xDA0000, 0xDB0000, self._ide_read, self._ide_write)
            else:
                self.bus.hook_range(0xDD0000, 0xDE0000, self._ide_read, self._ide_write)
        self.akiko = Akiko(lambda on: on and self.paula.request(0x0008), lambda a: self.bus.r8(a), lambda a, v: self._dma_write(a, bytes([v]))) if preset == "CD32" else None
        b = self.bus
        if self.akiko:
            self.agnus.hsync = self.akiko.cd.hsync
            b.hook_range(AKIKO_BASE, AKIKO_BASE + 0x10000, self._akiko_read, self._akiko_write)
        if self.ramsey or self.gayle:
            b.hook_range(0xDE0000, 0xDF0000, self._glue_read, self._glue_write)
        b.hook_range(0xDFF000, 0xE00000, self._custom_read, self._custom_write)
        if chipset != "aga" and preset not in MOBO_PRESETS:
            for pg in range(0xC0F000, 0xD80000, 0x10000):
                b.hook_range(pg, pg + 0x1000, self._custom_read, self._custom_write)
        if not self.akiko:
            b.hook_range(0xB80000, 0xBF0000, lambda a, n: 0, lambda a, n, v: None)
        b.hook_range(0xBFD000, 0xBFF000, self._cia_read, self._cia_write)
        if fast_kb:
            b.hook_range(self.fast_base, self.fast_base + fast_kb * 1024, self._fast_read, self._fast_write)
            self.cpu.add_ram(self.fast_base, self.fast.buf)
        if proc_kb:
            b.hook_range(PROC_BASE, PROC_BASE + proc_kb * 1024, self._proc_read, self._proc_write)
            self.cpu.add_ram(PROC_BASE, self.proc.buf)
        if slow_kb:
            b.hook_range(SLOW_BASE, SLOW_BASE + slow_kb * 1024, self._slow_read, self._slow_write)
            self.cpu.add_ram(SLOW_BASE, self.slow.buf)
        b.hook_range(ROM_BASE, 0x1000000, self._rom_read, self._rom_write)

    # ---- wiring ----
    def _irq(self, level: int) -> None:  #vers 1
        self.cpu.irq_level = level

    def _ciaa_in(self, port: int) -> int:  #vers 1
        if port:
            return 0xFF
        v = self.ports.fire_bits() | 0x03 | 0x3C
        for d in self.drives:
            v &= 0xC3 | d.status()
        return v

    def _ciab_out(self, port: int, v: int) -> None:  #vers 1
        if port == 1:
            for n, d in enumerate(self.drives):
                d.control(v, not v >> (3 + n) & 1)

    def _spinning(self):  #vers 1
        for d in self.drives:
            if d.selected and d.motor and d.image is not None:
                return d
        return None

    def insert_disk(self, data: bytes, unit: int = 0, protected: bool = True, path: str = "") -> None:  #vers 2
        self.drives[unit].insert(data, protected)
        self.drives[unit].path, self.drives[unit].saved, self.drives[unit].writes = path, 0, 0

    def flush_disks(self) -> list:  #vers 1
        """Write changed unprotected disks back to their ADF files; returns the units saved."""
        return [i for i, d in enumerate(self.drives) if d.flush()]

    def _custom_read(self, a: int, size: int) -> int:  #vers 2
        if 0x400 <= (a & 0xFFF) < 0x500 and self.paula.nch > 4:
            w = self.paula.xread(a & 0xFFE)
            return (w & 0xFF if a & 1 else w >> 8) if size == 0 else w if size == 1 else w << 16 | self.paula.xread((a + 2) & 0xFFE)
        w = self.agnus.read(a & 0x1FE)
        if size == 0:
            return w & 0xFF if a & 1 else w >> 8
        if size == 1:
            return w
        return w << 16 | self.agnus.read((a + 2) & 0x1FE)

    def _custom_write(self, a: int, size: int, v: int) -> None:  #vers 2
        if 0x400 <= (a & 0xFFF) < 0x500 and self.paula.nch > 4:
            if size == 2:
                self.paula.xwrite(a & 0xFFE, v >> 16)
                self.paula.xwrite((a + 2) & 0xFFE, v & 0xFFFF)
            else:
                self.paula.xwrite(a & 0xFFE, (v & 0xFF) * 0x101 if size == 0 else v)
            return
        if size == 0:
            v = (v & 0xFF) * 0x101
        if size == 2:
            self.agnus.write(a & 0x1FE, v >> 16)
            self.agnus.write((a + 2) & 0x1FE, v & 0xFFFF)
        else:
            self.agnus.write(a & 0x1FE, v & 0xFFFF)

    def _cia_read(self, a: int, size: int) -> int:  #vers 1
        cia = self.ciaa if a & 1 else self.ciab
        return cia.read(a >> 8 & 15) & 0xFF

    def _cia_write(self, a: int, size: int, v: int) -> None:  #vers 1
        cia = self.ciaa if a & 1 else self.ciab
        cia.write(a >> 8 & 15, v & 0xFF)

    def _nv_read(self, a: int, size: int) -> int:  #vers 1
        o = a - 0xDC8000
        return int.from_bytes(self.nvram[o:o + (1, 2, 4)[size]], "big")

    def _nv_write(self, a: int, size: int, v: int) -> None:  #vers 1
        o, n = a - 0xDC8000, (1, 2, 4)[size]
        self.nvram[o:o + n] = (v & (1 << 8 * n) - 1).to_bytes(n, "big")

    def _card_read(self, a: int, size: int) -> int:  #vers 1
        """CDTV memory card, 64K mirrored."""
        o, n = a & 0xFFFF, (1, 2, 4)[size]
        return int.from_bytes(bytes(self.card[(o + i) & 0xFFFF] for i in range(n)), "big")

    def _card_write(self, a: int, size: int, v: int) -> None:  #vers 1
        n = (1, 2, 4)[size]
        for i, x in enumerate((v & (1 << 8 * n) - 1).to_bytes(n, "big")):
            self.card[(a + i) & 0xFFFF] = x

    def _glue_read(self, a: int, size: int) -> int:  #vers 2
        o = a & 0xFFFF
        if self.gayle and o >= 0x1000:
            return self.gayle.read(o)
        if o < 3:
            return self.gary.read(o)
        if self.ramsey:
            return self.ramsey.read(o)
        return self._de03 if o == 3 else 0xFF

    def _glue_write(self, a: int, size: int, v: int) -> None:  #vers 2
        o = a & 0xFFFF
        if self.gayle and o >= 0x1000:
            self.gayle.write(o, v)
        elif o < 3:
            self.gary.write(o, v)
        elif self.ramsey:
            self.ramsey.write(o, v)
        elif o == 3:
            self._de03 = v & 0xFF

    def _akiko_read(self, a: int, size: int) -> int:  #vers 1
        o, n = a - AKIKO_BASE, (1, 2, 4)[size]
        return int.from_bytes(bytes(self.akiko.read(o + i) for i in range(n)), "big")

    def _akiko_write(self, a: int, size: int, v: int) -> None:  #vers 1
        o, n = a - AKIKO_BASE, (1, 2, 4)[size]
        for i, byte in enumerate(v.to_bytes(4, "big")[4 - n:]):
            self.akiko.write(o + i, byte)

    def _rtc_read(self, a: int, size: int) -> int:  #vers 1
        return self.rtc.read(a & 0xFFFF) if size == 0 else self.rtc.read(a & 0xFFFF) << 8 | self.rtc.read(a + 1 & 0xFFFF)

    def _rtc_write(self, a: int, size: int, v: int) -> None:  #vers 1
        self.rtc.write(a & 0xFFFF, v & 0xFF)

    def activity(self) -> dict:  #vers 2
        """Which parts were busy since the last call."""
        from apps.hardware.cdimage import CDImage
        now = (self.act_hd, self.act_ram + self.cpu.touches, CDImage.reads)
        last, self._act_last = self._act_last, now
        return {"FD": any(d.motor for d in self.drives), "HD": now[0] != last[0], "CD": now[2] != last[2],
                "RAM": now[1] != last[1], "CPU": not self.cpu.stopped}

    def add_board(self, board) -> None:  #vers 1
        (self.z2 if board.zorro == 2 else self.z3).add(board)

    def _map_board(self, board, base: int, size: int) -> None:  #vers 3
        if hasattr(board, "map"):
            board.map(self.bus, self.cpu, base, size)
            return
        self.bus.hook_range(base, base + size, board.read, board.write)
        self.cpu.add_ram(base, board.ram.buf)

    def _dma_read(self, a: int, n: int) -> bytes:  #vers 2
        self.act_hd += 1
        b = self.bus
        return bytes(b.ram[a:a + n]) if a + n <= b.size else bytes(b.r8(a + i) for i in range(n))

    def _dma_write(self, a: int, data: bytes) -> None:  #vers 2
        self.act_hd += 1
        b = self.bus
        if a + len(data) <= b.size:
            b.ram[a:a + len(data)] = data
        else:
            for i, v in enumerate(data):
                b.w8(a + i, v)

    def attach_scsi(self, tid: int, target) -> None:  #vers 1
        """Put a SCSI target on the machine's controller; raises when there is none."""
        if self.sdmac is None:
            raise ValueError("this machine has no SCSI controller implemented; use an A3000")
        self.sdmac.wd.attach(tid, target)

    def attach_disk(self, image: bytearray, unit: int = 0) -> None:  #vers 1
        self.ide.disks[unit] = ATADisk(image)

    def insert_cd(self, image) -> None:  #vers 1
        """Put a CDImage in the CD32 or CDTV drive."""
        if self.akiko is not None:
            self.akiko.cd.insert(image)
        elif self.dmac is not None:
            self.dmac.insert(image)
        else:
            raise ValueError("this machine has no CD drive; use CD32, CDTV, A3000 SCSI or IDE")

    def attach_drive(self, drive, unit: int = 0) -> None:  #vers 1
        self.ide.disks[unit] = drive

    def _ide_irq(self, on: bool) -> None:  #vers 1
        if self.gayle:
            self.gayle.ide_irq(on)
        elif on:
            self.ide_irqreg = 0x80
            self.paula.request(0x0008)

    def _ide_read(self, a: int, size: int) -> int:  #vers 3
        off = a & 0xFFFF
        g = self.gayle
        if g and off >= 0x8000:
            r = off & 0xF000
            if r == 0x8000:
                return 0x80
            if r == 0x9000:
                return g.irqreg
            if r == 0xA000:
                return g.inten
            return 0
        if not g and off == 0x3020:
            v, self.ide_irqreg = getattr(self, "ide_irqreg", 0), 0
            return v << 8 if size else v
        reg = (off & ~0x2020) >> 2
        if reg == 0:
            self.act_hd += 1
            return self.ide.read(0, 2 if size == 2 else 1)
        return self.ide.read(reg & 0x7 if reg != 0x406 else reg)

    def _ide_write(self, a: int, size: int, v: int) -> None:  #vers 3
        off = a & 0xFFFF
        g = self.gayle
        if g and off >= 0x8000:
            r = off & 0xF000
            if r == 0x9000:
                g.irqreg &= v | 0x03
            elif r == 0xA000:
                g.inten = v & 0xFF
            return
        reg = (off & ~0x2020) >> 2
        if reg == 0:
            self.act_hd += 1
            self.ide.write(0, v, 2 if size == 2 else 1)
        else:
            self.act_hd += reg == 7
            self.ide.write(reg & 0x7 if reg != 0x406 else reg, v)

    def _fast_read(self, a: int, size: int) -> int:  #vers 2
        self.act_ram += 1
        return self.fast.read(a - self.fast_base, (1, 2, 4)[size])

    def _fast_write(self, a: int, size: int, v: int) -> None:  #vers 2
        self.act_ram += 1
        n = (1, 2, 4)[size]
        self.fast.write(a - self.fast_base, n, v & (1 << 8 * n) - 1)

    def _proc_read(self, a: int, size: int) -> int:  #vers 1
        self.act_ram += 1
        return self.proc.read(a - PROC_BASE, (1, 2, 4)[size])

    def _proc_write(self, a: int, size: int, v: int) -> None:  #vers 1
        self.act_ram += 1
        n = (1, 2, 4)[size]
        self.proc.write(a - PROC_BASE, n, v & (1 << 8 * n) - 1)

    def _slow_read(self, a: int, size: int) -> int:  #vers 1
        self.act_ram += 1
        return self.slow.read(a - SLOW_BASE, (1, 2, 4)[size])

    def _slow_write(self, a: int, size: int, v: int) -> None:  #vers 1
        self.act_ram += 1
        n = (1, 2, 4)[size]
        self.slow.write(a - SLOW_BASE, n, v & (1 << 8 * n) - 1)

    def _rom_read(self, a: int, size: int) -> int:  #vers 2
        o, n = a - ROM_BASE, (1, 2, 4)[size]
        if self.wcs is not None and o >= 0x40000:
            return int.from_bytes(self.wcs[o - 0x40000:o - 0x40000 + n], "big")
        if o + n > len(self.rom):
            return 0
        return int.from_bytes(self.rom[o:o + n], "big")

    def _rom_write(self, a: int, size: int, v: int) -> None:  #vers 1
        """A1000 writable control store above 0xFC0000; a write to the boot ROM locks it."""
        if self.wcs is None:
            return
        o, n = a - ROM_BASE, (1, 2, 4)[size]
        if o < 0x40000:
            self.wcs_lock = True
        elif not self.wcs_lock:
            self.wcs[o - 0x40000:o - 0x40000 + n] = (v & (1 << 8 * n) - 1).to_bytes(n, "big")

    # ---- control ----
    def load_rom(self, data: bytes) -> None:  #vers 2
        """Map a ROM image so it ends at 0x1000000; a 256K image is mirrored at 0xF80000 and 0xFC0000; 1 MB is extended + Kickstart."""
        if len(data) == 0x100000:
            self.load_ext(data[:0x80000], 0xE00000)
            data = data[0x80000:]
        self.rom = data * 2 if len(data) == 0x40000 else data.rjust(0x80000, b"\0")

    def load_bootstrap(self, data: bytes) -> None:  #vers 1
        """A1000 8K boot ROM mirrored over 0xF80000-0xFBFFFF; empty writable store at 0xFC0000."""
        self.rom = data[:0x2000] * 32 + bytes(0x40000)
        self.wcs, self.wcs_lock = bytearray(0x40000), False

    def load_ext(self, data: bytes, base: int = 0xE00000) -> None:  #vers 1
        """Extended ROM mapped at base (CD32 0xE00000, CDTV 0xF00000)."""
        self.ext, self.ext_base = data, base
        self.bus.hook_range(base, base + len(data), self._ext_read, None)

    def _ext_read(self, a: int, size: int) -> int:  #vers 1
        o, n = a - self.ext_base, (1, 2, 4)[size]
        return int.from_bytes(self.ext[o:o + n], "big") if o + n <= len(self.ext) else 0

    def boot(self) -> None:  #vers 3
        """Hardware reset: stack and start address come from the first two longs of the ROM."""
        sp, pc = int.from_bytes(self.rom[0:4], "big"), int.from_bytes(self.rom[4:8], "big")
        if self.wcs is None:
            self.cpu.set_rom(self.rom, ROM_BASE)
        self.reset(pc, sp)

    def reset(self, pc: int, sp: int) -> None:  #vers 1
        self.cpu.reset(pc, sp)
        self.paula.intena = self.paula.intreq = 0

    def run_frame(self) -> None:  #vers 3
        self.agnus.run_frame(lambda cycles: self.cpu.execute(cycles * self.ratio))

    def display_box(self):  #vers 1
        """(x, y, w, h) of the active display window in framebuffer pixels."""
        a = self.agnus
        hs, he = a.diwstrt & 0xFF, (a.diwstop & 0xFF) | 0x100
        vs, ve = a.diwstrt >> 8, (a.diwstop >> 8) | (0 if a.diwstop >> 8 & 0x80 else 0x100)
        x0, x1 = max(0, (hs - LEFT_ABS) * 2), min(FB_WIDTH, (he - LEFT_ABS) * 2)
        y0, y1 = max(0, vs * 2), min(FB_LINES, ve * 2)
        if x1 - x0 < 64 or y1 - y0 < 64:
            return 0, 0, FB_WIDTH, FB_LINES
        return x0, y0, x1 - x0, y1 - y0

    def framebuffer(self):  #vers 2
        """(width, height, BGRA bytes) of the whole raster, or the RTG board's screen when it has a mode set."""
        for z in (self.z2, self.z3):
            for b in z.boards:
                f = b.frame() if hasattr(b, "frame") else None
                if f:
                    return f
        return FB_WIDTH, FB_LINES, bytes(self.denise.fb)
