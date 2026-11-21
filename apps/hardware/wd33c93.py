#this belongs in apps/hardware/wd33c93.py - Version: 3
# X-Seti - November 18 2026 - Morosa - Morosa WD33C93.

"""
Morosa WD33C93 - SCSI bus controller registers and command state; targets answer CDBs, data moves by a DMA object.
"""

##Methods list -
# WD33C93
# WD33C93.attach
# WD33C93.aux
# WD33C93.read_reg
# WD33C93.write_reg
# WD33C93._command
# WD33C93._finish
# WD33C93._select
# WD33C93._select_transfer
# WD33C93._transfer_info
# WD33C93._cdb_length
# WD33C93._pio_done
# WD33C93._pio_start
# WD33C93._raise

OWN_ID, CONTROL, TIMEOUT, CDB1 = 0x00, 0x01, 0x02, 0x03
TARGET_LUN, COMMAND_PHASE, SYNCH, COUNT_HI, COUNT_MID, COUNT_LO = 0x0F, 0x10, 0x11, 0x12, 0x13, 0x14
DEST_ID, SOURCE_ID, STATUS, COMMAND, DATA = 0x15, 0x16, 0x17, 0x18, 0x19
CSR_RESET, CSR_RESET_AF, CSR_SELECT, CSR_SEL_XFER_DONE, CSR_XFER_DONE = 0x00, 0x01, 0x11, 0x16, 0x18
CSR_MSGIN, CSR_TIMEOUT, CSR_UNEXP, CSR_DISC = 0x20, 0x42, 0x48, 0x85
PH_DATA_OUT, PH_DATA_IN, PH_COMMAND, PH_STATUS, PH_MSG_OUT, PH_MSG_IN = 0, 1, 2, 3, 6, 7
DATA_OUT_OPS = (0x0A, 0x2A, 0x15, 0x55, 0x2E, 0x3B, 0x04)


class WD33C93:
    """DMA object needs pull(n) -> bytes (memory to device) and push(data) (device to memory)."""

    def __init__(self, irq=None, dma=None):  #vers 2
        self.irq = irq or (lambda on: None)
        self.dma = dma
        self.regs = [0] * 32
        self.sasr = 0
        self.status = 0
        self.pending = False
        self.targets = {}
        self.phase = None
        self.queue = []
        self.target = None
        self.out_data = b""
        self.in_data = b""
        self.tstatus = 0
        self.follow = 0
        self.pio = None

    def attach(self, tid: int, target) -> None:  #vers 1
        self.targets[tid & 7] = target

    def aux(self) -> int:  #vers 2
        dbr = 0
        if self.pio:
            dbr = 1 if self.pio[3] == "in" or len(self.pio[2]) < self.pio[1] else 0
        return (0x80 if self.pending else 0) | (0x10 if self.target is not None else 0) | dbr

    def _raise(self, status: int) -> None:  #vers 1
        self.status = status
        self.pending = True
        self.irq(True)

    def _cdb_length(self, op: int) -> int:  #vers 1
        return (6, 10, 10, 12, 16, 12, 6, 6)[op >> 5]

    def _count(self) -> int:  #vers 1
        return self.regs[COUNT_HI] << 16 | self.regs[COUNT_MID] << 8 | self.regs[COUNT_LO]

    def _set_count(self, n: int) -> None:  #vers 1
        self.regs[COUNT_HI], self.regs[COUNT_MID], self.regs[COUNT_LO] = n >> 16 & 255, n >> 8 & 255, n & 255

    def _run(self, cdb: bytes) -> None:  #vers 1
        """Execute the CDB on the selected target and queue the remaining bus phases."""
        n = self._count()
        out = b""
        if cdb[0] in DATA_OUT_OPS and self.dma and n:
            out = self.dma.pull(n)
        self.tstatus, data = self.target.execute(cdb, out)
        self.in_data = data
        self.queue = []
        if data and cdb[0] not in DATA_OUT_OPS:
            self.queue.append(PH_DATA_IN)
        elif out:
            self.queue.append(PH_DATA_OUT)
        self.queue += [PH_STATUS, PH_MSG_IN]

    def _select(self, atn: bool) -> None:  #vers 2
        t = self.targets.get(self.regs[DEST_ID] & 7)
        if t is None:
            self.target = None
            return self._raise(CSR_TIMEOUT)
        self.target = t
        self.queue = ([PH_MSG_OUT] if atn else []) + [PH_COMMAND]
        self._raise(CSR_SELECT)
        self.follow = 0x88 | self.queue[0]

    def _select_transfer(self, atn: bool) -> None:  #vers 3
        t = self.targets.get(self.regs[DEST_ID] & 7)
        if t is None:
            self.target = None
            return self._raise(CSR_TIMEOUT)
        if self.target is t and self.regs[COMMAND_PHASE] >= 0x10:
            self.regs[TARGET_LUN] = self.tstatus
            self.target, self.queue = None, []
            self._raise(CSR_SEL_XFER_DONE)
            self.follow = CSR_DISC
            return
        self.target = t
        cdb = bytes(self.regs[CDB1:CDB1 + self._cdb_length(self.regs[CDB1])])
        self._run(cdb)
        n = self._count()
        if self.in_data and self.dma:
            self.dma.push(self.in_data[:n])
        self.regs[TARGET_LUN] = self.tstatus
        self._set_count(max(0, n - len(self.in_data)) if self.in_data else 0)
        self.queue = []
        self.target = None
        self._raise(CSR_SEL_XFER_DONE)

    def _pio_start(self, ph: int, n: int) -> None:  #vers 1
        """Byte transfers through the data register, polled by the driver."""
        if ph in (PH_MSG_OUT, PH_COMMAND, PH_DATA_OUT):
            self.pio = [ph, n, bytearray(), "out"]
            return
        if ph == PH_DATA_IN:
            buf = bytearray(self.in_data[:n])
            self.in_data = self.in_data[n:]
        else:
            buf = bytearray([self.tstatus if ph == PH_STATUS else 0])
        self.pio = [ph, len(buf), buf, "in"]

    def _pio_done(self) -> None:  #vers 1
        ph, n, buf, _ = self.pio
        self.pio = None
        if ph == PH_COMMAND:
            self._run(bytes(buf))
        if ph == PH_MSG_IN:
            self.queue = []
            return self._raise(CSR_MSGIN)
        self._set_count(0)
        self._raise(CSR_XFER_DONE | (self.queue[0] if self.queue else PH_MSG_IN))

    def _transfer_info(self, single: bool) -> None:  #vers 2
        if self.target is None:
            return self._raise(CSR_UNEXP)
        ph = self.queue.pop(0)
        n = 1 if single else self._count()
        if not self.regs[CONTROL] & 0xE0:
            return self._pio_start(ph, n)
        if ph == PH_MSG_OUT:
            self.out_data = bytes([self.regs[DATA]]) if single else (self.dma.pull(n) if self.dma else b"")
        elif ph == PH_COMMAND:
            cdb = bytes([self.regs[DATA]]) if single else (self.dma.pull(n) if self.dma else b"")
            self._run(cdb)
        elif ph == PH_DATA_IN:
            if self.dma:
                self.dma.push(self.in_data[:n])
            self.in_data = self.in_data[n:]
        elif ph == PH_DATA_OUT:
            pass
        elif ph == PH_STATUS:
            self.regs[DATA] = self.tstatus
        elif ph == PH_MSG_IN:
            self.regs[DATA] = 0
            self.queue = []
            return self._raise(CSR_MSGIN)
        self._set_count(0)
        self._raise(CSR_XFER_DONE | (self.queue[0] if self.queue else PH_MSG_IN))

    def _finish(self) -> None:  #vers 1
        self.target = None
        self.queue = []
        self._raise(CSR_DISC)

    def _command(self, cmd: int) -> None:  #vers 1
        c = cmd & 0x7F
        if c == 0x00:
            adv = bool(self.regs[OWN_ID] & 8)
            self.regs = [0] * 32
            self.target, self.queue = None, []
            self._raise(CSR_RESET_AF if adv else CSR_RESET)
        elif c == 0x01:
            self._finish()
        elif c == 0x03:
            self._finish()
        elif c == 0x04:
            self._finish()
        elif c in (0x06, 0x07):
            self._select(c == 0x06)
        elif c in (0x08, 0x09):
            self._select_transfer(c == 0x08)
        elif c == 0x20:
            self._transfer_info(bool(cmd & 0x80))
        else:
            self._raise(0x40)

    def read_reg(self, n: int) -> int:  #vers 3
        n &= 31
        if n == STATUS:
            v = self.status
            self.pending = False
            self.irq(False)
            if self.follow:
                f, self.follow = self.follow, 0
                self._raise(f)
            return v
        if n == DATA and self.pio and self.pio[3] == "in":
            v = self.pio[2].pop(0)
            if not self.pio[2]:
                self._pio_done()
            return v
        return self.regs[n]

    def write_reg(self, n: int, v: int) -> None:  #vers 2
        n &= 31
        self.regs[n] = v & 0xFF
        if n == DATA and self.pio and self.pio[3] == "out":
            self.pio[2].append(v & 0xFF)
            if len(self.pio[2]) >= self.pio[1]:
                self._pio_done()
        elif n == COMMAND:
            self._command(v & 0xFF)
