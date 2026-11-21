#this belongs in apps/hardware/rtc.py - Version: 1
# X-Seti - November 17 2026 - Morosa - Morosa Real Time Clock.

"""
Morosa RTC - RP5C01 (A3000, A4000) and MSM6242B (A2000, A500+) battery clocks, years counted from 1978.
"""

##Methods list -
# RP5C01
# RP5C01.read
# RP5C01.write
# MSM6242B
# MSM6242B.read
# MSM6242B.write
# _Clock
# _Clock.digits
# _Clock.now
# _Clock.set_digit

import time
from datetime import datetime, timedelta

RTC_BASE = 0xDC0000
EPOCH_YEAR = 1978


class _Clock:
    """Host time plus an offset set by writes."""

    def __init__(self):  #vers 1
        self.offset = timedelta(0)

    def now(self) -> datetime:  #vers 1
        return datetime.fromtimestamp(time.time()) + self.offset

    def digits(self) -> list:  #vers 1
        """Thirteen nibbles: s1 s10 m1 m10 h1 h10 weekday d1 d10 mo1 mo10 y1 y10."""
        n = self.now()
        y = (n.year - EPOCH_YEAR) % 100
        return [n.second % 10, n.second // 10, n.minute % 10, n.minute // 10, n.hour % 10, n.hour // 10,
                (n.weekday() + 1) % 7, n.day % 10, n.day // 10, n.month % 10, n.month // 10, y % 10, y // 10]

    def set_digit(self, idx: int, v: int) -> None:  #vers 1
        d = self.digits()
        d[idx] = v & 15
        try:
            new = datetime(EPOCH_YEAR + d[11] + 10 * d[12] + (self.now().year - EPOCH_YEAR) // 100 * 100, d[9] + 10 * d[10],
                           d[7] + 10 * d[8], d[4] + 10 * d[5], d[2] + 10 * d[3], d[0] + 10 * d[1])
        except ValueError:
            return
        self.offset += new - self.now()


class RP5C01(_Clock):
    """Registers at 0xDC0003 + 4*n; MODE (0xD) bits 1..0 select the bank; bank 1 reg 0xA bit 0 = 24 hour."""

    def __init__(self):  #vers 1
        super().__init__()
        self.mode = 8
        self.ram = [[0] * 13 for _ in range(2)]
        self.alarm = [0] * 13
        self.h24 = 1
        self.leap = 0

    def read(self, off: int) -> int:  #vers 1
        if off & 3 != 3:
            return 0
        r = off >> 2 & 15
        bank = self.mode & 3
        if r == 0xD:
            return self.mode
        if r in (0xE, 0xF):
            return 0
        if bank == 0:
            return self.digits()[r] | 0xF0
        if bank == 1:
            return (self.alarm[r] if r < 10 else self.h24 if r == 0xA else self.leap if r == 0xB else 0) | 0xF0
        return self.ram[bank - 2][r] | 0xF0

    def write(self, off: int, v: int) -> None:  #vers 1
        if off & 3 != 3:
            return
        r, v = off >> 2 & 15, v & 15
        bank = self.mode & 3
        if r == 0xD:
            self.mode = v
        elif bank == 0 and r < 13:
            self.set_digit(r, v)
        elif bank == 1:
            if r == 0xA:
                self.h24 = v & 1
            elif r == 0xB:
                self.leap = v & 3
            elif r < 10:
                self.alarm[r] = v
        elif bank >= 2 and r < 13:
            self.ram[bank - 2][r] = v


class MSM6242B(_Clock):
    """Registers at 0xDC0001 + 2*n; D/E/F control."""

    def __init__(self):  #vers 1
        super().__init__()
        self.ctl = [0, 0, 4]

    def read(self, off: int) -> int:  #vers 1
        if not off & 1:
            return 0
        r = off >> 1 & 15
        if r < 13:
            return self.digits()[r] | 0xF0
        return self.ctl[r - 13] | 0xF0

    def write(self, off: int, v: int) -> None:  #vers 1
        if not off & 1:
            return
        r, v = off >> 1 & 15, v & 15
        if r < 13:
            self.set_digit(r, v)
        else:
            self.ctl[r - 13] = v
