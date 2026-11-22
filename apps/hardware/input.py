#this belongs in apps/hardware/input.py - Version: 3
# X-Seti - November 17 2026 - Morosa - Morosa Keyboard, Mouse and Joystick.

"""
Morosa Input - Amiga keyboard serial protocol on CIA-A, mouse counters and joystick lines.
"""

##Methods list -
# Keyboard
# Keyboard.line
# Keyboard.press
# Keyboard.release
# Ports
# Ports._dat
# Ports._press
# Ports.fire_bits
# Ports.joy
# Ports.mouse_button
# Ports.mouse_move
# Ports.read
# Ports.write

from collections import deque


class Keyboard:
    """Sends raw key codes to CIA-A SDR and waits for the software handshake (CRA bit 6 pulse)."""

    def __init__(self, ciaa):  #vers 1
        self.cia = ciaa
        self.queue = deque()
        self.waiting = False
        self.seen_out = False

    def press(self, code: int) -> None:  #vers 1
        self.queue.append(code & 0x7F)

    def release(self, code: int) -> None:  #vers 1
        self.queue.append(code & 0x7F | 0x80)

    def line(self) -> None:  #vers 1
        out = bool(self.cia.cra & 0x40)
        if self.waiting:
            if out:
                self.seen_out = True
            elif self.seen_out:
                self.waiting = False
            return
        if self.queue and not out:
            c = self.queue.popleft()
            self.cia.sp_in(~(c << 1 | c >> 7) & 0xFF)
            self.waiting, self.seen_out = True, False


class Ports:
    """Game port 1 mouse (JOY0DAT), game port 2 joystick (JOY1DAT); buttons reach CIA-A PRA and POTGOR."""

    def __init__(self):  #vers 2
        self.devs = ["mouse", "joy"]
        self.x = self.y = 0
        self.left = self.right = False
        self.up = self.down = self.jl = self.jr = self.fire = self.fire2 = False

    def mouse_move(self, dx: int, dy: int) -> None:  #vers 1
        self.x = self.x + dx & 0xFF
        self.y = self.y + dy & 0xFF

    def mouse_button(self, left: bool = None, right: bool = None) -> None:  #vers 1
        if left is not None:
            self.left = left
        if right is not None:
            self.right = right

    def joy(self, up=False, down=False, left=False, right=False, fire=False, fire2=False) -> None:  #vers 2
        self.up, self.down, self.jl, self.jr, self.fire, self.fire2 = up, down, left, right, fire, fire2

    def _dat(self, dev: str) -> int:  #vers 1
        """JOYxDAT value for what is plugged in: mouse, joy or none."""
        if dev == "mouse":
            return self.y << 8 | self.x
        if dev == "joy":
            r, l, u, d = (1 if x else 0 for x in (self.jr, self.jl, self.up, self.down))
            return l << 9 | (l ^ u) << 8 | r << 1 | (r ^ d)
        return 0

    def _press(self, dev: str, second: bool) -> bool:  #vers 1
        """Button state on a port: first or second button of the plugged device."""
        if dev == "mouse":
            return self.right if second else self.left
        if dev == "joy":
            return self.fire2 if second else self.fire
        return False

    def fire_bits(self) -> int:  #vers 2
        """CIA-A PRA input bits 6 (port 1) and 7 (port 2), active low."""
        return 0xC0 & ~(0x40 if self._press(self.devs[0], False) else 0) & ~(0x80 if self._press(self.devs[1], False) else 0)

    def read(self, off: int):  #vers 3
        if off == 0x00A:
            return self._dat(self.devs[0])
        if off == 0x00C:
            return self._dat(self.devs[1])
        if off == 0x016:
            return 0xFFFF & ~(0x400 if self._press(self.devs[0], True) else 0) & ~(0x4000 if self._press(self.devs[1], True) else 0)
        return None

    def write(self, off: int, v: int) -> bool:  #vers 1
        if off == 0x036:
            self.x, self.y = v & 0xFF, v >> 8 & 0xFF
            return True
        return False
