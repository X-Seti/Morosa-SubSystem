#this belongs in apps/hardware/input.py - Version: 1
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

    def __init__(self):  #vers 1
        self.x = self.y = 0
        self.left = self.right = False
        self.up = self.down = self.jl = self.jr = self.fire = False

    def mouse_move(self, dx: int, dy: int) -> None:  #vers 1
        self.x = self.x + dx & 0xFF
        self.y = self.y + dy & 0xFF

    def mouse_button(self, left: bool = None, right: bool = None) -> None:  #vers 1
        if left is not None:
            self.left = left
        if right is not None:
            self.right = right

    def joy(self, up=False, down=False, left=False, right=False, fire=False) -> None:  #vers 1
        self.up, self.down, self.jl, self.jr, self.fire = up, down, left, right, fire

    def fire_bits(self) -> int:  #vers 1
        """CIA-A PRA input bits 7 and 6, active low."""
        return 0xC0 & ~(0x40 if self.left else 0) & ~(0x80 if self.fire else 0)

    def read(self, off: int):  #vers 1
        if off == 0x00A:
            return self.y << 8 | self.x
        if off == 0x00C:
            r = 1 if self.jr else 0
            l = 1 if self.jl else 0
            u = 1 if self.up else 0
            d = 1 if self.down else 0
            return (l << 9 | (l ^ u) << 8 | r << 1 | (r ^ d))
        if off == 0x016:
            return 0xFFFF & ~(0x400 if self.right else 0)
        return None

    def write(self, off: int, v: int) -> bool:  #vers 1
        if off == 0x036:
            self.x, self.y = v & 0xFF, v >> 8 & 0xFF
            return True
        return False
