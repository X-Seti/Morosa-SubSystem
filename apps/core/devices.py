#this belongs in apps/core/devices.py - Version: 1
# X-Seti - November 17 2026 - Morosa - Morosa Devices.

"""
Morosa devices - exec device calls and timer.device; other devices fail to open.
"""

##Methods list -
# Devices
# Devices.f_AbortIO
# Devices.f_CheckIO
# Devices.f_CloseDevice
# Devices.f_CreateIORequest
# Devices.f_DeleteIORequest
# Devices.f_DoIO
# Devices.f_OpenDevice
# Devices.f_SendIO
# Devices.f_WaitIO
# Timer
# Timer.f_AddTime
# Timer.f_CmpTime
# Timer.f_GetSysTime
# Timer.f_ReadEClock
# Timer.f_SubTime
# Timer._now

import time

AMIGA_EPOCH = 252460800
IOERR_OPENFAIL = 0xFFFFFFFF
TR_ADDREQUEST, TR_GETSYSTIME, TR_SETSYSTIME = 9, 10, 11
CMD_FLUSH = 8


class Devices:
    """Mixed into Exec: IORequest handling; timer.device is the only device."""

    def f_CreateIORequest(self):  #vers 1
        cpu = self.cpu
        size = max(cpu.d[0], 48)
        io = self.alloc(size)
        self.bus.w8(io + 8, 5)
        self.bus.w16(io + 18, size)
        self.bus.w32(io + 14, cpu.a[0])
        cpu.d[0] = io

    def f_DeleteIORequest(self):  #vers 1
        io = self.cpu.a[0]
        if io:
            self.free(io, self.bus.r16(io + 18))

    def f_OpenDevice(self):  #vers 1
        cpu = self.cpu
        name = self.cstr(cpu.a[0]).lower()
        io = cpu.a[1]
        if name == "timer.device":
            base = self.m.libs.get("timer") or self.m.add_library("timer", 47)
            self.bus.w32(io + 20, base)
            self.bus.w32(io + 24, cpu.d[0])
            self.bus.w8(io + 31, 0)
            cpu.d[0] = 0
        else:
            self.bus.w32(io + 20, 0)
            self.bus.w8(io + 31, 0xFF)
            cpu.d[0] = IOERR_OPENFAIL

    def f_CloseDevice(self):  #vers 1
        self.bus.w32(self.cpu.a[1] + 20, 0)

    def _io(self, io: int) -> None:  #vers 1
        b = self.bus
        cmd = b.r16(io + 28)
        b.w8(io + 31, 0)
        if cmd == TR_ADDREQUEST:
            end = time.time() + b.r32(io + 32) + b.r32(io + 36) / 1e6
            while time.time() < end:
                if self.m.abort:
                    break
                time.sleep(min(0.05, max(0, end - time.time())))
        elif cmd == TR_GETSYSTIME:
            t = time.time()
            b.w32(io + 32, int(t) - AMIGA_EPOCH)
            b.w32(io + 36, int(t % 1 * 1e6))
        elif cmd not in (TR_SETSYSTIME, CMD_FLUSH, 1, 2):
            b.w8(io + 31, 0xFD)
        b.w8(io + 8, 7)

    def f_DoIO(self):  #vers 1
        io = self.cpu.a[1]
        self._io(io)
        self.cpu.d[0] = self.bus.r8(io + 31)

    def f_SendIO(self):  #vers 1
        self._io(self.cpu.a[1])

    def f_WaitIO(self):  #vers 1
        io = self.cpu.a[1]
        self.cpu.d[0] = self.bus.r8(io + 31)

    def f_CheckIO(self):  #vers 1
        self.cpu.d[0] = self.cpu.a[1]

    def f_AbortIO(self):  #vers 1
        self.cpu.d[0] = 0


class Timer:
    """timer.device library functions."""

    def __init__(self, machine):  #vers 1
        self.cpu = machine.cpu
        self.bus = machine.bus

    def _now(self) -> float:  #vers 1
        return time.time()

    def _tv(self, a: int) -> int:  #vers 1
        return self.bus.r32(a) * 1000000 + self.bus.r32(a + 4)

    def _put(self, a: int, us: int) -> None:  #vers 1
        self.bus.w32(a, (us // 1000000) & 0xFFFFFFFF)
        self.bus.w32(a + 4, us % 1000000)

    def f_AddTime(self):  #vers 1
        a, b = self.cpu.a[0], self.cpu.a[1]
        self._put(a, self._tv(a) + self._tv(b))

    def f_SubTime(self):  #vers 1
        a, b = self.cpu.a[0], self.cpu.a[1]
        self._put(a, self._tv(a) - self._tv(b))

    def f_CmpTime(self):  #vers 1
        a, b = self._tv(self.cpu.a[0]), self._tv(self.cpu.a[1])
        self.cpu.d[0] = 0 if a == b else 1 if a < b else 0xFFFFFFFF

    def f_GetSysTime(self):  #vers 1
        t = self._now()
        self.bus.w32(self.cpu.a[0], int(t) - AMIGA_EPOCH)
        self.bus.w32(self.cpu.a[0] + 4, int(t % 1 * 1e6))

    def f_ReadEClock(self):  #vers 1
        t = int(self._now() * 709379)
        a = self.cpu.a[0]
        self.bus.w32(a, 0)
        self.bus.w32(a + 4, t & 0xFFFFFFFF)
        self.cpu.d[0] = 50
