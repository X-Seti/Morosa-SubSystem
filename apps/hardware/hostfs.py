#this belongs in apps/hardware/hostfs.py - Version: 4
# X-Seti - November 23 2026 - Morosa - Host Folder Filesystem Board.

"""
Morosa Hostfs - Zorro II autoconfig board whose boot ROM mounts a host folder as an AmigaDOS volume.
"""

##Methods list -
# _bstr
##class GuestMem: -
# __init__
# _find
# r32
# rd
# w32
# wr
##class HostFS: -
# __init__
# attach
# boot_block
# config_rom
# map
# read
# write
# _device_code
# _handler_code
# _io
# _packet
# _rom_image
# _setup
# _silent
# _time_code

import os
import struct
import time

from apps.methods.asm68k import Asm

REGS = 0x1000
R_SETUP, R_CONFIGDEV, R_SILENT, R_PACKET, R_PORT, R_ADD, R_DBG, R_IO, R_TIME = 0x00, 0x04, 0x08, 0x10, 0x14, 0x18, 0x20, 0x40, 0x50
AREA, LOCKS, DN, VN, PRIO, NODE, DEVPTR = 0x10000, 0x1000, 0x100, 0x200, 0xF0, 0xF4, 0xF8
TIMEC, DEVCODE, DEVLIB, FSSM, ENV, BS_DEV, BS_VOL, BS_HDEV, CS_HDEV = 0x600, 0x300, 0x440, 0x500, 0x520, 0x140, 0x160, 0x580, 0x5A0
MFR, PRODUCT = 0x4D52, 0x01
DIAG = 0x400
DEVNAME = "hostfs.device"


class GuestMem:
    """Read and write guest memory from the host: direct for RAM buffers, bus for everything else."""

    def __init__(self, bus, regions: list):  #vers 1
        self.bus = bus
        self.regions = regions

    def _find(self, a: int, n: int):  #vers 1
        if a + n <= self.bus.size:
            return self.bus.ram, a
        for base, buf in self.regions:
            if base <= a and a + n <= base + len(buf):
                return buf, a - base
        return None, 0

    def rd(self, a: int, n: int) -> bytes:  #vers 1
        buf, o = self._find(a, n)
        return bytes(buf[o:o + n]) if buf is not None else bytes(self.bus.r8(a + i) for i in range(n))

    def wr(self, a: int, data: bytes) -> None:  #vers 1
        buf, o = self._find(a, len(data))
        if buf is not None:
            buf[o:o + len(data)] = data
        else:
            for i, v in enumerate(data):
                self.bus.w8(a + i, v)

    def r32(self, a: int) -> int:  #vers 1
        return struct.unpack(">I", self.rd(a, 4))[0]

    def w32(self, a: int, v: int) -> None:  #vers 1
        self.wr(a, struct.pack(">I", v & 0xFFFFFFFF))


def _bstr(text: str) -> bytes:  #vers 1
    b = text.replace("/", "_").replace(":", "_").encode("latin-1", "replace")[:30]
    return bytes([len(b)]) + b


class HostFS:
    """One mounted folder. The ROM adds a small boot device and a DeviceNode; the handler process hands every DOS packet to the host."""

    zorro, kb = 2, 64

    def __init__(self, folder: str, unit: int = 0, boot_pri: int = 0, label: str = "", log=None, writable: bool = False, startup: str = "", limit: int = 0):  #vers 4
        self.folder, self.unit, self.boot_pri, self.startup = folder, unit, boot_pri, startup
        self.label = label or os.path.basename(os.path.abspath(folder)) or "Morosa"
        self.mfr, self.product, self.serial = MFR, PRODUCT, unit + 1
        self.base = None
        self.mem = None
        self.owner = None
        self.log = log
        self.writable = writable
        self.limit = limit
        self.area = 0
        self.port = 0
        self.add_vol = 0
        self.rom = bytearray(REGS)
        self.vol = None

    def attach(self, mem) -> None:  #vers 2
        self.mem = mem
        from apps.methods.hostfs_packets import Volume
        self.vol = Volume(self.folder, mem, self.label, self.log, self.writable, self.startup, self.limit)

    def config_rom(self) -> bytes:  #vers 2
        """Zorro II, 64K, diag valid; the DiagArea sits at DIAG inside the board."""
        typ = 0xC0 | 0x10 | 1
        return bytes([typ, self.product, 0x00, 0, self.mfr >> 8, self.mfr & 255]) + self.serial.to_bytes(4, "big") + DIAG.to_bytes(2, "big") + bytes(4)

    def map(self, bus, cpu, base: int, size: int) -> None:  #vers 2
        self.rom[DIAG:REGS] = self._rom_image()[:REGS - DIAG]
        bus.hook_range(base, base + size, self.read, self.write)
        cpu.add_ram(base, self.rom)

    def _rom_image(self) -> bytes:  #vers 2
        """DiagArea header plus the config-time routine: a0 board, a2 diag copy, a3 ConfigDev, a6 ExecBase."""
        a = Asm()
        a.raw(0x9000, 0, 16, 0, 0, 0, 0, 0)
        a.movem_save(0x3F3E)                       # d2-d7/a2-a6
        a.move("l", ("a", 0), ("a", 4))            # a4 = board base
        a.move("l", ("absw", 4), ("a", 6))         # a6 = exec
        a.move("l", ("a", 0), ("dis", 4, REGS + R_DBG))
        a.move("l", ("a", 2), ("dis", 4, REGS + R_DBG + 4))
        a.move("l", ("a", 3), ("dis", 4, REGS + R_DBG + 8))
        a.move("l", ("imm", AREA), ("d", 0))
        a.move("l", ("imm", 0x10001), ("d", 1))
        a.jsr(("dis", 6, -198))                    # AllocMem
        a.tst_l(("d", 0))
        a.bcc("eq", "out")
        a.move("l", ("d", 0), ("a", 2))
        a.move("l", ("a", 3), ("dis", 4, REGS + R_CONFIGDEV))
        a.move("l", ("a", 2), ("dis", 4, REGS + R_SETUP))
        a.move("l", ("dis", 2, DEVPTR), ("a", 1))
        a.jsr(("dis", 6, -432))                    # AddDevice
        a.lea(("pc", "expname"), 1)
        a.moveq(0, 0)
        a.jsr(("dis", 6, -552))                    # OpenLibrary
        a.tst_l(("d", 0))
        a.bcc("eq", "out")
        a.move("l", ("d", 0), ("a", 5))            # a5 = expansion.library
        a.move("l", ("a", 6), ("d", 7))            # d7 = exec
        a.move("l", ("a", 5), ("a", 6))
        a.move("l", ("dis", 2, PRIO), ("d", 0))
        a.moveq(1, 1)                              # ADNF_STARTPROC
        a.move("l", ("dis", 2, NODE), ("a", 0))
        a.move("l", ("a", 3), ("a", 1))
        a.jsr(("dis", 6, -36))                     # AddBootNode
        a.move("l", ("a", 5), ("a", 1))
        a.move("l", ("d", 7), ("a", 6))
        a.jsr(("dis", 6, -414))                    # CloseLibrary
        a.label("out")
        a.movem_load(0x7CFC)                       # d2-d7/a2-a6
        a.moveq(1, 0)
        a.raw(0x4E75)
        a.label("bootp")
        for r in range(4):
            a.move("l", ("a", r), ("abs", self.base + REGS + R_DBG + 0x10 + 4 * r))
        a.moveq(1, 0)
        a.raw(0x4E75)
        a.label("expname")
        a.out += b"expansion.library\0"
        if len(a.out) & 1:
            a.out += b"\0"
        code = bytearray(a.bytes())
        struct.pack_into(">H", code, 2, len(code))
        struct.pack_into(">H", code, 6, a.labels["bootp"])
        return bytes(code).ljust(REGS, b"\0")

    def _handler_code(self) -> bytes:  #vers 3
        """The DOS handler process: wait for a packet, call the host, reply."""
        a = Asm()
        a.movem_save(0x3F3E)
        a.move("l", ("absw", 4), ("a", 5))         # a5 = exec
        a.move("l", ("imm", self.base), ("a", 4))  # a4 = board base
        a.move("l", ("a", 5), ("a", 6))
        a.raw(0x93C9)                              # suba.l a1,a1
        a.jsr(("dis", 6, -294))                    # FindTask(0)
        a.move("l", ("d", 0), ("a", 3))
        a.lea(("dis", 3, 92), 3)                   # a3 = pr_MsgPort
        a.lea(("pc", "dosname"), 1)
        a.moveq(0, 0)
        a.jsr(("dis", 6, -552))                    # OpenLibrary
        a.move("l", ("d", 0), ("d", 7))            # d7 = dos
        a.jsr(("abs", self.area + TIMEC))          # set system time from host
        a.label("loop")
        a.move("l", ("a", 5), ("a", 6))
        a.move("l", ("a", 3), ("a", 0))
        a.jsr(("dis", 6, -384))                    # WaitPort
        a.move("l", ("a", 3), ("a", 0))
        a.jsr(("dis", 6, -372))                    # GetMsg
        a.move("l", ("d", 0), ("a", 1))
        a.move("l", ("dis", 1, 10), ("a", 2))      # packet
        a.move("l", ("a", 3), ("dis", 4, REGS + R_PORT))
        a.move("l", ("a", 2), ("dis", 4, REGS + R_PACKET))   # host call
        a.move("l", ("dis", 2, 4), ("a", 0))       # reply port
        a.move("l", ("a", 3), ("dis", 2, 4))       # dp_Port = our port
        a.jsr(("dis", 6, -366))                    # PutMsg
        a.move("l", ("dis", 4, REGS + R_ADD), ("d", 6))
        a.bcc("eq", "loop")
        a.move("l", ("imm", 0), ("dis", 4, REGS + R_ADD))
        a.move("l", ("d", 7), ("a", 6))
        a.moveq(10, 1)                             # LDF_VOLUMES|LDF_WRITE
        a.jsr(("dis", 6, -654))                    # LockDosList
        a.move("l", ("d", 6), ("d", 1))
        a.jsr(("dis", 6, -678))                    # AddDosEntry
        a.moveq(10, 1)
        a.jsr(("dis", 6, -660))                    # UnLockDosList
        a.bcc("ra", "loop")
        a.label("dosname")
        a.out += b"dos.library\0"
        if len(a.out) & 1:
            a.out += b"\0"
        code = a.bytes()
        if len(code) > PRIO - 8:
            raise ValueError("handler code too large")
        return code

    def _time_code(self) -> bytes:  #vers 1
        """Guest routine: timer.device TR_SETSYSTIME with the host clock."""
        a = Asm()
        a.movem_save(0x3F3E)
        a.move("l", ("absw", 4), ("a", 6))
        a.jsr(("dis", 6, -666))                    # CreateMsgPort
        a.move("l", ("d", 0), ("a", 2))
        a.tst_l(("d", 0))
        a.bcc("eq", "end")
        a.moveq(40, 0)
        a.move("l", ("imm", 0x10001), ("d", 1))
        a.jsr(("dis", 6, -198))                    # AllocMem
        a.move("l", ("d", 0), ("a", 3))
        a.tst_l(("d", 0))
        a.bcc("eq", "port")
        a.move("l", ("a", 2), ("dis", 3, 14))      # mn_ReplyPort
        a.move("w", ("imm", 11), ("dis", 3, 28))   # TR_SETSYSTIME
        a.move("l", ("abs", self.base + REGS + R_TIME), ("dis", 3, 32))
        a.lea(("pc", "timer"), 0)
        a.moveq(0, 0)
        a.move("l", ("a", 3), ("a", 1))
        a.moveq(0, 1)
        a.jsr(("dis", 6, -444))                    # OpenDevice
        a.tst_l(("d", 0))
        a.bcc("ne", "free")
        a.move("l", ("a", 3), ("a", 1))
        a.jsr(("dis", 6, -456))                    # DoIO
        a.move("l", ("a", 3), ("a", 1))
        a.jsr(("dis", 6, -450))                    # CloseDevice
        a.label("free")
        a.move("l", ("a", 3), ("a", 1))
        a.moveq(40, 0)
        a.jsr(("dis", 6, -210))                    # FreeMem
        a.label("port")
        a.move("l", ("a", 2), ("a", 0))
        a.jsr(("dis", 6, -672))                    # DeleteMsgPort
        a.label("end")
        a.movem_load(0x7CFC)
        a.raw(0x4E75)
        a.label("timer")
        a.out += b"timer.device\0"
        if len(a.out) & 1:
            a.out += b"\0"
        return a.bytes()

    def _device_code(self) -> tuple:  #vers 1
        """Boot device entry points; returns (code, label offsets)."""
        a = Asm()
        a.label("open")
        a.move("l", ("a", 6), ("dis", 1, 20))      # io_Device
        a.raw(0x4229, 31)                          # clr.b 31(a1)
        a.moveq(0, 0)
        a.raw(0x4E75)
        a.label("nul")
        a.moveq(0, 0)
        a.raw(0x4E75)
        a.label("begin")
        a.move("l", ("a", 1), ("abs", self.base + REGS + R_IO))
        a.raw(0x0829, 0, 30)                       # btst #0,30(a1)  IOF_QUICK
        a.bcc("ne", "done")
        a.move("l", ("a", 6), ("pre", 7))
        a.move("l", ("absw", 4), ("a", 6))
        a.jsr(("dis", 6, -378))                    # ReplyMsg
        a.move("l", ("post", 7), ("a", 6))
        a.label("done")
        a.raw(0x4E75)
        return a.bytes(), a.labels

    def boot_block(self) -> bytes:  #vers 2
        """Standard DOS boot block: finds dos.library and returns its init."""
        code = bytes.fromhex("42B9") + struct.pack(">I", self.base + REGS + R_SILENT) + bytes.fromhex("43FA00184EAEFFA04A80670A20402068001670004E7570FF4E75") + b"dos.library\0"
        blk = bytearray(1024)
        blk[0:4] = b"DOS\x01"
        blk[8:12] = struct.pack(">I", 880)
        blk[12:12 + len(code)] = code
        s = 0
        for i in range(0, 1024, 4):
            s += struct.unpack(">I", blk[i:i + 4])[0]
            if s > 0xFFFFFFFF:
                s = (s & 0xFFFFFFFF) + 1
        blk[4:8] = struct.pack(">I", ~s & 0xFFFFFFFF)
        return bytes(blk)

    def _setup(self, area: int) -> None:  #vers 2
        """Host side of the config-time call: segment, boot device, DeviceNode, volume node and lock pool."""
        m = self.mem
        self.area = area
        m.wr(area + TIMEC, self._time_code())
        m.wr(area + 8, self._handler_code())
        m.w32(area, PRIO)                                   # segment length
        m.wr(area + BS_DEV, _bstr(f"DH{self.unit}"))
        m.wr(area + BS_VOL, _bstr(self.label))
        m.wr(area + BS_HDEV, _bstr(DEVNAME))
        m.wr(area + CS_HDEV, DEVNAME.encode() + b"\0")
        code, lab = self._device_code()
        m.wr(area + DEVCODE, code)
        lib = area + DEVLIB
        vec = [lab["open"], lab["nul"], lab["nul"], lab["nul"], lab["begin"], lab["nul"]]
        for i, off in enumerate(vec):
            m.wr(lib - 6 * (i + 1), struct.pack(">HI", 0x4EF9, area + DEVCODE + off))
        m.wr(lib, struct.pack(">IIBBIBBHHHHIIH", 0, 0, 3, 0, area + CS_HDEV, 0, 0, 36, 34, 1, 0, 0, 0, 0))
        m.w32(area + DEVPTR, lib)
        m.wr(area + FSSM, struct.pack(">4I", self.unit, (area + BS_HDEV) >> 2, (area + ENV) >> 2, 0))
        m.wr(area + ENV, struct.pack(">20I", 19, 128, 0, 1, 1, 1, 2, 0, 0, 0, 1, 30, 0, 0xFFFFFF, 0xFFFFFFFE, self.boot_pri & 0xFFFFFFFF, 0x444F5301, 0, 0, 2))
        dn = area + DN
        m.wr(dn, struct.pack(">11I", 0, 0, 0, 0, 0, 8192, 5, (area + FSSM) >> 2, (area + 4) >> 2, 0xFFFFFFFF, (area + BS_DEV) >> 2))
        vn = area + VN
        t = time.time() - 252460800
        d, mi = int(t // 86400), int(t % 86400 // 60)
        m.wr(vn, struct.pack(">11I", 0, 2, 0, 0, d, mi, int(t % 60 * 50), 0, 0x444F5301, 0, 0))
        m.w32(vn + 40, (area + BS_VOL) >> 2)
        m.w32(area + PRIO, self.boot_pri & 0xFFFFFFFF)
        m.w32(area + NODE, dn)
        self.vol.setup(area, LOCKS, AREA - LOCKS)
        if self.log:
            self.log(f"setup area {area:08X} base {self.base:08X}")

    def _silent(self) -> None:  #vers 1
        """Set EBF_SILENTSTART: strap clears it, boot board sets it like a ROM boot device."""
        m = self.mem
        n = m.r32(m.r32(4) + 378)
        while n and m.r32(n):
            nm = m.r32(n + 10)
            if nm and m.rd(nm, 18) == b"expansion.library\0":
                m.wr(n + 0x22, bytes([m.rd(n + 0x22, 1)[0] | 0x40]))
                return
            n = m.r32(n)

    def _io(self, io: int) -> None:  #vers 2
        """Boot device request: serve the boot block, answer status commands."""
        m = self.mem
        cmd = struct.unpack(">H", m.rd(io + 28, 2))[0]
        length, data, off = m.r32(io + 36), m.r32(io + 40), m.r32(io + 44)
        err, actual = 0, 0
        if cmd in (2, 24, 0x8000 + 24):                       # CMD_READ, TD_READ64
            blk = self.boot_block() + bytes(1024)
            chunk = blk[off:off + length] if off < len(blk) else b""
            chunk = chunk.ljust(length, b"\0")
            m.wr(data, chunk)
            actual = length
        elif cmd in (14, 15, 18, 19):                         # changestate, protstatus, drivetype, numtracks
            actual = 0 if cmd in (14, 15) else 80
        elif cmd in (3, 11):                                  # writes refused
            err = -4
        elif cmd in (4, 5, 7, 8, 9, 10, 12, 13, 20, 21):
            pass
        else:
            err = -3
        if self.log:
            self.log(f"io cmd {cmd} len {length} off {off} err {err}")
        m.wr(io + 31, bytes([err & 0xFF]))
        m.w32(io + 32, actual)

    def _packet(self, pkt: int) -> None:  #vers 2
        """Run one DOS packet on the volume; the first packet starts the handler."""
        if self.owner:
            self.owner.act_hfs += 1
        if self.vol.packet(pkt, self.port, self.area + DN, self.area + VN) == "start":
            self.add_vol = self.area + VN

    def read(self, a: int, size: int) -> int:  #vers 2
        off = a - self.base - REGS
        if off == R_ADD and size == 2:
            return self.add_vol
        if off == R_TIME and size == 2:
            return int(time.time() + time.localtime().tm_gmtoff) - 252460800 & 0xFFFFFFFF
        return 0

    def write(self, a: int, size: int, v: int) -> None:  #vers 2
        off = a - self.base - REGS
        if off < 0 or size != 2:
            return
        if off == R_SETUP:
            self._setup(v)
        elif off == R_PORT:
            self.port = v
        elif off == R_SILENT:
            self._silent()
        elif off == R_PACKET:
            self._packet(v)
        elif off == R_ADD:
            self.add_vol = v
        elif off == R_IO:
            self._io(v)
        elif self.log and R_DBG <= off < R_IO:
            self.log(f"diag reg {off:02X} = {v:08X}")
