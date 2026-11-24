#this belongs in apps/hardware/cia.py - Version: 1
# X-Seti - November 17 2026 - Morosa - Morosa CIA 8520.

"""
Morosa CIA - MOS 8520 complex interface adapter: two timers, TOD clock, serial register, ports and interrupts.
"""

##Methods list -
# CIA
# CIA._ack
# CIA._flag
# CIA._shift_done
# CIA._tb_input
# CIA._underflow_a
# CIA._underflow_b
# CIA.cnt
# CIA.flag
# CIA.read
# CIA.sp_in
# CIA.tick
# CIA.tod_tick
# CIA.write

(PRA, PRB, DDRA, DDRB, TALO, TAHI, TBLO, TBHI, TOD0, TOD1, TOD2, TOD3, SDR, ICR, CRA, CRB) = range(16)
ICR_TA, ICR_TB, ICR_ALARM, ICR_SP, ICR_FLG = 1, 2, 4, 8, 16


class CIA:
    """One 8520. Callbacks: irq(level), port_in(port) -> pins, port_out(port, value), sp_out(bit)."""

    def __init__(self, irq=None, port_in=None, port_out=None, sp_out=None):  #vers 1
        self.irq_cb = irq or (lambda level: None)
        self.port_in = port_in or (lambda port: 0xFF)
        self.port_out = port_out or (lambda port, value: None)
        self.sp_out = sp_out or (lambda bit: None)
        self.cra_cb = None
        self.pra = self.prb = self.ddra = self.ddrb = 0
        self.latch_a = self.latch_b = 0xFFFF
        self.cnt_a = self.cnt_b = 0xFFFF
        self.cra = self.crb = 0
        self.icr_data = self.icr_mask = 0
        self.irq = False
        self.tod = 0
        self.tod_alarm = 0
        self.tod_latch = None
        self.tod_stopped = False
        self.sdr = 0
        self.shift_bits = 0
        self.shift_underflows = 0
        self.tog_a = self.tog_b = 0

    # ---- interrupt lines ----
    def _flag(self, bit: int) -> None:  #vers 1
        self.icr_data |= bit
        irq = bool(self.icr_data & self.icr_mask)
        if irq and not self.irq:
            self.icr_data |= 0x80
        if irq != self.irq:
            self.irq = irq
            self.irq_cb(irq)

    def _ack(self) -> int:  #vers 1
        v = self.icr_data & 0x1F | (0x80 if self.irq else 0)
        self.icr_data = 0
        if self.irq:
            self.irq = False
            self.irq_cb(False)
        return v

    def flag(self) -> None:  #vers 1
        """FLAG pin falling edge."""
        self._flag(ICR_FLG)

    # ---- timers ----
    def _underflow_a(self) -> None:  #vers 1
        self.cnt_a = self.latch_a
        self._flag(ICR_TA)
        self.tog_a ^= 1
        if self.cra & 8:
            self.cra &= ~1
        if self.cra & 0x40 and self.shift_bits:
            self.shift_underflows += 1
            if self.shift_underflows % 2 == 0:
                self.shift_bits -= 1
                self.sp_out(self.sdr >> self.shift_bits & 1)
                if self.shift_bits == 0:
                    self._flag(ICR_SP)
        if self.crb & 0x60 in (0x40, 0x60) and self.crb & 1:
            self._tb_input()

    def _underflow_b(self) -> None:  #vers 1
        self.cnt_b = self.latch_b
        self._flag(ICR_TB)
        self.tog_b ^= 1
        if self.crb & 8:
            self.crb &= ~1

    def _tb_input(self) -> None:  #vers 1
        if self.cnt_b == 0:
            self._underflow_b()
        else:
            self.cnt_b -= 1

    def tick(self, n: int) -> None:  #vers 1
        """Advance n phi2 cycles."""
        while n > 0:
            a_run = self.cra & 1 and not self.cra & 0x20
            b_run = self.crb & 1 and not self.crb & 0x60
            step = n
            if a_run:
                step = min(step, self.cnt_a + 1)
            if b_run:
                step = min(step, self.cnt_b + 1)
            if step <= 0:
                step = 1
            if a_run:
                if step == self.cnt_a + 1:
                    self.cnt_a = 0
                    self._underflow_a()
                else:
                    self.cnt_a -= step
            if b_run:
                if step == self.cnt_b + 1:
                    self.cnt_b = 0
                    self._underflow_b()
                else:
                    self.cnt_b -= step
            n -= step

    def sp_in(self, byte: int) -> None:  #vers 1
        """A byte arrives on the serial pin in input mode."""
        self.sdr = byte & 0xFF
        self._flag(ICR_SP)

    def cnt(self) -> None:  #vers 1
        """One pulse on the CNT pin."""
        if self.cra & 1 and self.cra & 0x20:
            if self.cnt_a == 0:
                self._underflow_a()
            else:
                self.cnt_a -= 1
        if self.crb & 1 and self.crb & 0x60 == 0x20:
            self._tb_input()

    def tod_tick(self) -> None:  #vers 1
        if self.tod_stopped:
            return
        self.tod = (self.tod + 1) & 0xFFFFFF
        if self.tod == self.tod_alarm:
            self._flag(ICR_ALARM)

    # ---- registers ----
    def read(self, reg: int) -> int:  #vers 1
        reg &= 15
        if reg == PRA:
            return (self.pra & self.ddra) | (self.port_in(0) & ~self.ddra & 0xFF)
        if reg == PRB:
            v = (self.prb & self.ddrb) | (self.port_in(1) & ~self.ddrb & 0xFF)
            for bit, on, mode, tog, run in ((6, self.cra & 2, self.cra & 4, self.tog_a, self.cra & 1),
                                            (7, self.crb & 2, self.crb & 4, self.tog_b, self.crb & 1)):
                if on:
                    v = v & ~(1 << bit) | ((tog if mode else int(self.cnt_a == 0 if bit == 6 else self.cnt_b == 0)) << bit)
            return v
        if reg == DDRA:
            return self.ddra
        if reg == DDRB:
            return self.ddrb
        if reg == TALO:
            return self.cnt_a & 0xFF
        if reg == TAHI:
            return self.cnt_a >> 8
        if reg == TBLO:
            return self.cnt_b & 0xFF
        if reg == TBHI:
            return self.cnt_b >> 8
        if reg in (TOD0, TOD1, TOD2):
            src = self.tod_latch if self.tod_latch is not None else self.tod
            if reg == TOD2:
                self.tod_latch = self.tod
            if reg == TOD0:
                self.tod_latch = None
                return self.tod & 0xFF
            return src >> (8 * (reg - TOD0)) & 0xFF
        if reg == TOD3:
            return 0
        if reg == SDR:
            return self.sdr
        if reg == ICR:
            return self._ack()
        if reg == CRA:
            return self.cra & ~0x10
        return self.crb & ~0x10

    def write(self, reg: int, v: int) -> None:  #vers 1
        reg &= 15
        v &= 0xFF
        if reg == PRA:
            self.pra = v
            self.port_out(0, v & self.ddra)
        elif reg == PRB:
            self.prb = v
            self.port_out(1, v & self.ddrb)
        elif reg == DDRA:
            self.ddra = v
        elif reg == DDRB:
            self.ddrb = v
        elif reg in (TALO, TAHI):
            self.latch_a = self.latch_a & 0xFF00 | v if reg == TALO else self.latch_a & 0xFF | v << 8
            if reg == TAHI and not self.cra & 1:
                self.cnt_a = self.latch_a
                if self.cra & 8:
                    self.cra |= 1
        elif reg in (TBLO, TBHI):
            self.latch_b = self.latch_b & 0xFF00 | v if reg == TBLO else self.latch_b & 0xFF | v << 8
            if reg == TBHI and not self.crb & 1:
                self.cnt_b = self.latch_b
                if self.crb & 8:
                    self.crb |= 1
        elif reg in (TOD0, TOD1, TOD2):
            shift = 8 * (reg - TOD0)
            if self.crb & 0x80:
                self.tod_alarm = self.tod_alarm & ~(0xFF << shift) | v << shift
            else:
                self.tod = self.tod & ~(0xFF << shift) | v << shift
                if reg == TOD2:
                    self.tod_stopped = True
                elif reg == TOD0:
                    self.tod_stopped = False
                if self.tod == self.tod_alarm:
                    self._flag(ICR_ALARM)
        elif reg == SDR:
            self.sdr = v
            if self.cra & 0x40:
                self.shift_bits = 8
                self.shift_underflows = 0
        elif reg == ICR:
            if v & 0x80:
                self.icr_mask |= v & 0x1F
            else:
                self.icr_mask &= ~v & 0x1F
            self._flag(0)
        elif reg == CRA:
            if v & 0x10:
                self.cnt_a = self.latch_a
            if v & 1 and not self.cra & 1:
                self.tog_a = 1
            self.cra = v & ~0x10
            if self.cra_cb:
                self.cra_cb(v)
        elif reg == CRB:
            if v & 0x10:
                self.cnt_b = self.latch_b
            if v & 1 and not self.crb & 1:
                self.tog_b = 1
            self.crb = v & ~0x10
