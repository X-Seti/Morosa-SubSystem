#this belongs in apps/core/doslist.py - Version: 1
# X-Seti - November 17 2026 - Morosa - Morosa dos.library Device List.

"""
Morosa dos.library device list - DosList entries for devices, volumes and assigns, and assign calls.
"""

##Methods list -
# DosList
# DosList._assign
# DosList._bstr
# DosList._name
# DosList._next
# DosList.build_list
# DosList.make_ports
# DosList.port_for
# DosList.f_AssignAdd
# DosList.f_AssignLate
# DosList.f_AssignLock
# DosList.f_AssignPath
# DosList.f_AttemptLockDosList
# DosList._action
# DosList.f_DoPkt
# DosList.f_FindCliProc
# DosList.f_FindDosEntry
# DosList.f_LockDosList
# DosList.f_NextDosEntry
# DosList.f_RemAssignList
# DosList.f_SendPkt
# DosList.f_UnLockDosList
# DosList.f_WaitPkt

from apps.core.exec import Unimplemented

TRUE = 0xFFFFFFFF
LDF_DEVICES, LDF_VOLUMES, LDF_ASSIGNS = 4, 8, 16
DLT_DEVICE, DLT_DIRECTORY, DLT_VOLUME = 0, 1, 2
WANT = {DLT_DEVICE: LDF_DEVICES, DLT_VOLUME: LDF_VOLUMES, DLT_DIRECTORY: LDF_ASSIGNS}
VOLUME_NAMES = {"sys": "Workbench", "ram": "Ram Disk"}
DEVICES = ("DF0", "RAM", "CON", "NIL")


class DosList:
    """Mixed into Dos: DosList walking over the Shell's volumes and assigns."""

    def _bstr(self, text: str) -> int:  #vers 1
        a = self.ex.alloc(len(text) + 8)
        self.bus.w8(a, len(text))
        for i, c in enumerate(text.encode("latin-1", "replace")):
            self.bus.w8(a + 1 + i, c)
        return a >> 2

    def make_ports(self) -> None:  #vers 1
        if not self.ports:
            self.ports = {n: self.ex.alloc(40) for n in DEVICES}
            self.devport = self.ports["RAM"]

    def port_for(self, apath: str) -> int:  #vers 1
        """Device port for an Amiga path: RAM for ram: and t:, else DF0."""
        self.make_ports()
        vol = apath.split(":", 1)[0].lower() if ":" in apath else ""
        return self.ports["RAM" if vol in ("ram", "t") else "DF0"]

    def build_list(self) -> None:  #vers 1
        """Entries for devices, volumes and assigns; rebuilt on every lock."""
        for a in self.dlist:
            self.ex.free(a, 48)
        self.dlist, self.dltype = [], {}
        self.make_ports()
        b = self.bus

        def entry(kind, name, lock=0, task=0):
            a = self.ex.alloc(48)
            b.w32(a + 4, kind)
            b.w32(a + 8, task)
            b.w32(a + 12, lock)
            b.w32(a + 40, self._bstr(name))
            self.dlist.append(a)
            self.dltype[a] = kind

        volent = {}
        for d in DEVICES:
            entry(DLT_DEVICE, d, 0, self.ports[d])
        for vol in self.shell.vols:
            if vol == "amisys" or vol.startswith("_a_"):
                continue
            entry(DLT_VOLUME, VOLUME_NAMES.get(vol, vol.capitalize()), 0, self.devport)
            volent[vol] = self.dlist[-1]
        for name, targets in self.shell.assigns.items():
            vol, comps = targets[0]
            path = (vol[3:] if vol.startswith("_a_") else vol) + ":" + "/".join(comps)
            lk = self.new_lock(path)
            b.w32((lk << 2) + 12, self.devport)
            b.w32((lk << 2) + 16, volent.get(vol if not vol.startswith("_a_") else "sys", 0) >> 2)
            entry(DLT_DIRECTORY, name.upper(), lk)
        for i, a in enumerate(self.dlist):
            b.w32(a, self.dlist[i + 1] >> 2 if i + 1 < len(self.dlist) else 0)

    def f_LockDosList(self):  #vers 1
        self.build_list()
        if not self.dlhead:
            self.dlhead = self.ex.alloc(48)
        self.bus.w32(self.dlhead, self.dlist[0] >> 2 if self.dlist else 0)
        self.cpu.d[0] = self.dlhead

    def f_AttemptLockDosList(self):  #vers 1
        self.f_LockDosList()

    def f_UnLockDosList(self):  #vers 1
        pass

    def _name(self, e: int) -> str:  #vers 1
        p = self.bus.r32(e + 40) << 2
        return bytes(self.bus.r8(p + 1 + i) for i in range(self.bus.r8(p))).decode("latin-1")

    def _next(self, cur: int, flags: int, name: str = None) -> int:  #vers 1
        nxt = self.bus.r32(cur) << 2
        while nxt:
            if WANT.get(self.dltype.get(nxt), 0) & flags:
                if name is None:
                    return nxt
                if self._name(nxt).lower() == name:
                    return nxt
            nxt = self.bus.r32(nxt) << 2
        return 0

    def f_NextDosEntry(self):  #vers 1
        self.cpu.d[0] = self._next(self.cpu.d[1], self.cpu.d[2])

    def f_FindDosEntry(self):  #vers 1
        cpu = self.cpu
        cpu.d[0] = self._next(cpu.d[1], cpu.d[3], self._cstr(cpu.d[2]).lower())

    def _action(self, port: int, act: int, args: list):  #vers 1
        """Run one packet action; returns (res1, res2)."""
        b = self.bus
        if act == 1027:
            return (TRUE if port in (self.ports.get("DF0"), self.ports.get("RAM")) else 0), 0
        if act == 25 and args[0]:
            ib = args[0] << 2
            for i, v in enumerate((0, 0, 82, 1000000, 400000, 512, 0x444F5303)):
                b.w32(ib + i * 4, v)
            want = "Ram Disk" if port == self.ports.get("RAM") else "Workbench"
            vols = [a for a in self.dlist if self.dltype[a] == DLT_VOLUME and self._name(a) == want]
            b.w32(ib + 28, vols[0] >> 2 if vols else 0)
            return TRUE, 0
        h = self._h(args[0]) if act in (82, 87, 1008) else None
        if h is not None and act == 82:
            data = self._read(h, args[2])
            for i, c in enumerate(data):
                b.w8(args[1] + i, c)
            return len(data), 0
        if h is not None and act == 87:
            return self._write(h, bytes(b.r8(args[1] + i) for i in range(args[2]))), 0
        if h is not None and act == 1008 and h.kind == "file":
            old = h.f.tell() - len(h.unget)
            h.unget = []
            pos = args[1] - (1 << 32) if args[1] >> 31 else args[1]
            mode = args[2] - (1 << 32) if args[2] >> 31 else args[2]
            h.f.seek(pos, {-1: 0, 0: 1, 1: 2}.get(mode, 0))
            return old, 0
        return 0, 209

    def f_DoPkt(self):  #vers 2
        cpu = self.cpu
        r1, r2 = self._action(cpu.d[1], cpu.d[2], [cpu.d[3], cpu.d[4], cpu.d[5], cpu.d[6], cpu.d[7]])
        cpu.d[0] = r1
        self.set_err(r2)

    def f_SendPkt(self):  #vers 1
        cpu = self.cpu
        dp, port, reply = cpu.d[1], cpu.d[2], cpu.d[3]
        b = self.bus
        r1, r2 = self._action(port, b.r32(dp + 8), [b.r32(dp + 20 + 4 * i) for i in range(5)])
        b.w32(dp + 12, r1)
        b.w32(dp + 16, r2)
        b.w32(dp + 4, port)
        msg = b.r32(dp)
        b.w8(msg + 8, 7)
        cpu.a[0], cpu.a[1] = reply + 20, msg
        self.ex.f_AddTail()

    def f_WaitPkt(self):  #vers 1
        cpu = self.cpu
        port = self.m.process + 92
        if self.bus.r32(port + 20) == port + 24:
            raise Unimplemented("WaitPkt with no reply packet")
        cpu.a[0] = port + 20
        self.ex.f_RemHead()
        cpu.d[0] = self.bus.r32(cpu.d[0] + 10)

    def _assign(self, name: str, path: str, add: bool = False) -> int:  #vers 1
        self.shell.cmd_assign([name.rstrip(":"), path] + (["add"] if add else []))
        return TRUE

    def f_AssignLock(self):  #vers 1
        cpu = self.cpu
        name = self._cstr(cpu.d[1])
        if not cpu.d[2]:
            self.shell.cmd_assign([name.rstrip(":"), "remove"])
            cpu.d[0] = TRUE
            return
        p = self.locks.get(cpu.d[2])
        cpu.d[0] = self._assign(name, p) if p else 0

    def f_AssignAdd(self):  #vers 1
        cpu = self.cpu
        p = self.locks.get(cpu.d[2])
        cpu.d[0] = self._assign(self._cstr(cpu.d[1]), p, True) if p else 0

    def f_AssignLate(self):  #vers 1
        cpu = self.cpu
        cpu.d[0] = self._assign(self._cstr(cpu.d[1]), self._cstr(cpu.d[2]))

    f_AssignPath = f_AssignLate

    def f_RemAssignList(self):  #vers 1
        self.cpu.d[0] = TRUE

    def f_FindCliProc(self):  #vers 1
        self.cpu.d[0] = self.m.process if self.cpu.d[1] == 1 else 0
