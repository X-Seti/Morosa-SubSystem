#this belongs in apps/methods/hostfs_packets.py - Version: 4
# X-Seti - November 23 2026 - Morosa - Host Folder DOS Packets.

"""
Host Packets - turns AmigaDOS packets for a mounted host folder into file operations.
"""

##Methods list -
##class Volume: -
# __init__
# packet
# setup
# _alloc_lock
# _bstr
# _create_dir
# _delete
# _disk_info
# _examine
# _examine_next
# _fib_fill
# _find
# _free_lock
# _make_lock
# _open
# _parent
# _read
# _rename
# _resolve
# _seek
# _set_size
# _stamp
# _used_bytes
# _write
# _from_stamp

import os
import shutil
import struct
import time

ERR_IN_USE, ERR_EXISTS, ERR_DIR_NOT_FOUND, ERR_NOT_FOUND = 202, 203, 204, 205
ERR_BAD_NAME, ERR_INVALID_LOCK, ERR_WRONG_TYPE, ERR_UNKNOWN = 210, 211, 212, 209
ERR_NOT_EMPTY, ERR_SEEK, ERR_DISK_FULL, ERR_DELETE_PROT = 216, 219, 221, 222
ERR_WRITE_PROT, ERR_NO_MORE = 214, 232
DOSTRUE = 0xFFFFFFFF
ST_ROOT, ST_DIR, ST_FILE = 1, 2, 0xFFFFFFFD
AMIGA_EPOCH = 252460800

NAMES = {0: "STARTUP", 7: "CURRENT_VOLUME", 8: "LOCATE_OBJECT", 15: "FREE_LOCK", 16: "DELETE_OBJECT", 17: "RENAME_OBJECT",
         18: "MORE_CACHE", 19: "COPY_DIR", 21: "SET_PROTECT", 22: "CREATE_DIR", 23: "EXAMINE_OBJECT", 24: "EXAMINE_NEXT",
         25: "DISK_INFO", 26: "INFO", 27: "FLUSH", 28: "SET_COMMENT", 29: "PARENT", 30: "TIMER", 31: "INHIBIT", 34: "SET_DATE",
         40: "SAME_LOCK", 82: "READ", 87: "WRITE", 1004: "FINDUPDATE", 1005: "FINDINPUT", 1006: "FINDOUTPUT", 1007: "END",
         1008: "SEEK", 1022: "SET_FILE_SIZE", 1026: "FH_FROM_LOCK", 1027: "IS_FILESYSTEM", 1028: "CHANGE_MODE",
         1030: "COPY_DIR_FH", 1031: "PARENT_FH", 1034: "EXAMINE_FH"}


class Volume:
    """State of one mounted folder: lock pool, open files, examine listings, metadata database."""

    def __init__(self, folder: str, mem, label: str, log=None, writable: bool = False, startup: str = "", limit: int = 0):  #vers 4
        self.folder = os.path.abspath(folder)
        self.mem, self.label, self.log, self.writable = mem, label, log, writable
        self.startup = os.path.join(self.folder, startup) if startup else ""
        self.locks = {}
        self.free = []
        self.files = {}
        self.lists = {}
        self.next_file = 1
        self.pool = 0
        self.port = 0
        self.vn = 0
        self.db = None
        self.limit, self.used = limit, None

    def _used_bytes(self) -> int:  #vers 1
        """Folder bytes; counted once, then tracked."""
        if self.used is None:
            self.used = sum(os.lstat(os.path.join(d, n)).st_size for d, _, ns in os.walk(self.folder) for n in ns)
        return self.used

    def setup(self, area: int, pool: int, size: int) -> None:  #vers 2
        """Lock pool: 32-byte FileLock structures carved from the area."""
        self.pool = area + pool
        self.free = list(range(size // 32 - 1, -1, -1))
        from apps.methods.fsdatabase import FsDatabase
        self.db = FsDatabase(self.folder)

    def _stamp(self, t: float) -> tuple:  #vers 1
        t = max(0, t + time.localtime(t).tm_gmtoff - AMIGA_EPOCH)
        return int(t // 86400), int(t % 86400 // 60), int(t % 60 * 50)

    def _from_stamp(self, days: int, mins: int, ticks: int) -> float:  #vers 1
        t = days * 86400 + mins * 60 + ticks / 50 + AMIGA_EPOCH
        return t - time.localtime(t).tm_gmtoff

    def _bstr(self, bptr: int) -> str:  #vers 1
        a = bptr << 2
        n = self.mem.rd(a, 1)[0]
        return self.mem.rd(a + 1, n).decode("latin-1")

    def _alloc_lock(self, host: str, rel: tuple, is_dir: bool, access: int) -> int:  #vers 1
        if not self.free:
            return 0
        i = self.free.pop()
        addr = self.pool + 32 * i
        self.locks[i] = {"host": host, "rel": rel, "dir": is_dir}
        self.mem.wr(addr, struct.pack(">IIIII", 0, i + 1, access & 0xFFFFFFFF, self.port, self.vn >> 2) + bytes(12))
        return addr >> 2

    def _free_lock(self, bptr: int) -> None:  #vers 1
        i = ((bptr << 2) - self.pool) // 32
        if i in self.locks:
            del self.locks[i]
            self.free.append(i)

    def _lock_info(self, bptr: int):  #vers 1
        """(host path, rel tuple, is_dir) for a lock BPTR; 0 is the volume root."""
        if not bptr:
            return self.folder, (), True
        i = ((bptr << 2) - self.pool) // 32
        e = self.locks.get(i)
        return (e["host"], e["rel"], e["dir"]) if e else None

    def _find(self, d: str, name: str):  #vers 1
        """Actual host name for an Amiga name inside d, case-insensitive."""
        if os.path.lexists(os.path.join(d, name)):
            return name
        low = name.lower()
        try:
            for n in os.listdir(d):
                if n.lower() == low:
                    return n
        except OSError:
            pass
        return None

    def _resolve(self, lock: int, name: str, leaf_may_miss: bool = False):  #vers 4
        """Walk name from lock. Returns (error, host, rel, leaf_name); leaf_may_miss tolerates a missing last component."""
        info = self._lock_info(lock)
        if info is None:
            return ERR_INVALID_LOCK, None, None, None
        host, rel, _ = info
        rel = list(rel)
        if ":" in name:
            pre, name = name.split(":", 1)
            if not lock or pre.lower() == self.label.lower():
                host, rel = self.folder, []
        parts = name.split("/")
        for k, part in enumerate(parts):
            last = k == len(parts) - 1
            if part == "":
                if name == "" or (last and k > 0):
                    break
                if not rel:
                    return ERR_NOT_FOUND, None, None, None
                rel.pop()
                host = os.path.dirname(host)
                continue
            if not os.path.isdir(host):
                return ERR_WRONG_TYPE, None, None, None
            real = self._find(host, part)
            if real is None:
                if last and leaf_may_miss:
                    return 0, host, tuple(rel), part
                return ERR_NOT_FOUND, None, None, None
            host = os.path.join(host, real)
            rel.append(real)
        if self.startup and tuple(x.lower() for x in rel) == ("s", "startup-sequence") and os.path.isfile(self.startup):
            host = self.startup
        return 0, host, tuple(rel), None

    def _make_lock(self, host: str, rel: tuple, access: int) -> tuple:  #vers 1
        lk = self._alloc_lock(host, rel, os.path.isdir(host), access)
        return (lk, 0) if lk else (0, ERR_DISK_FULL)

    def _fib_fill(self, fib: int, host: str, rel: tuple, key: int) -> None:  #vers 2
        """Write a FileInfoBlock for a host object."""
        st = os.stat(host)
        is_dir = os.path.isdir(host)
        root = not rel
        name = self.label if root else rel[-1]
        nm = name.encode("latin-1", "replace")[:107]
        d, mi, tk = self._stamp(st.st_mtime)
        if self.db and rel:
            self.db.adopt(os.path.dirname(host), rel[:-1])
        com = self.db.comment(rel).encode("latin-1", "replace")[:79] if self.db else b""
        prot = self.db.protection(rel) if self.db else 0
        blk = bytearray(260)
        entry = ST_ROOT if root else ST_DIR if is_dir else ST_FILE
        struct.pack_into(">II", blk, 0, key, entry)
        blk[8] = len(nm)
        blk[9:9 + len(nm)] = nm
        size = 0 if is_dir else st.st_size
        struct.pack_into(">IIIIIII", blk, 116, prot, entry, min(size, 0xFFFFFFFF), (size + 511) // 512, d, mi, tk)
        blk[144] = len(com)
        blk[145:145 + len(com)] = com
        self.mem.wr(fib, bytes(blk))

    def _examine(self, lock_or_fh: int, fib: int, is_fh: bool = False) -> int:  #vers 2
        if is_fh:
            f = self.files.get(lock_or_fh)
            if not f:
                return ERR_INVALID_LOCK
            host, rel = f["host"], f["rel"]
        else:
            info = self._lock_info(lock_or_fh)
            if info is None:
                return ERR_INVALID_LOCK
            host, rel, _ = info
        try:
            self._fib_fill(fib, host, rel, 0)
        except OSError:
            return ERR_NOT_FOUND
        return 0

    def _examine_next(self, lock: int, fib: int) -> int:  #vers 2
        info = self._lock_info(lock)
        if info is None:
            return ERR_INVALID_LOCK
        host, rel, _ = info
        key = self.mem.r32(fib)
        if key == 0 or host not in self.lists:
            self.lists[host] = sorted((n for n in os.listdir(host) if n != "_UAEFSDB.___"), key=str.lower)
        names = self.lists[host]
        while key < len(names):
            n = names[key]
            key += 1
            p = os.path.join(host, n)
            if os.path.isdir(p) or os.path.isfile(p):
                self._fib_fill(fib, p, rel + (n,), key)
                return 0
        self.lists.pop(host, None)
        return ERR_NO_MORE

    def _parent(self, lock: int):  #vers 1
        info = self._lock_info(lock)
        if info is None:
            return 0, ERR_INVALID_LOCK
        host, rel, _ = info
        if not rel:
            return 0, 0
        return self._make_lock(os.path.dirname(host), rel[:-1], 0xFFFFFFFE)

    def _open(self, typ: int, fh: int, lock: int, name: str):  #vers 2
        err, host, rel, leaf = self._resolve(lock, name, leaf_may_miss=typ != 1005)
        if err:
            return err
        if typ == 1005:
            if os.path.isdir(host):
                return ERR_WRONG_TYPE
            mode = "rb"
        else:
            if not self.writable:
                return ERR_WRITE_PROT
            if leaf is not None:
                host, rel = os.path.join(host, leaf), rel + (leaf,)
                mode = "w+b"
            elif os.path.isdir(host):
                return ERR_WRONG_TYPE
            else:
                mode = "w+b" if typ == 1006 else "r+b"
        if self.limit:
            self._used_bytes()
            if mode == "w+b" and os.path.isfile(host):
                self.used -= os.path.getsize(host)
        try:
            f = open(host, mode)
        except OSError:
            return ERR_NOT_FOUND
        fid = self.next_file
        self.next_file += 1
        self.files[fid] = {"f": f, "host": host, "rel": rel, "size": os.path.getsize(host)}
        self.mem.w32((fh << 2) + 36, fid)
        self.mem.w32((fh << 2) + 8, self.port)
        return 0

    def _read(self, fid: int, addr: int, n: int):  #vers 1
        f = self.files.get(fid)
        if not f:
            return DOSTRUE, ERR_INVALID_LOCK
        data = f["f"].read(n)
        self.mem.wr(addr, data)
        return len(data), 0

    def _write(self, fid: int, addr: int, n: int):  #vers 2
        f = self.files.get(fid)
        if not f:
            return DOSTRUE, ERR_INVALID_LOCK
        if not self.writable:
            return DOSTRUE, ERR_WRITE_PROT
        grow = max(0, f["f"].tell() + n - f["size"])
        if self.limit and self._used_bytes() + grow > self.limit:
            return DOSTRUE, ERR_DISK_FULL
        try:
            f["f"].write(self.mem.rd(addr, n))
        except OSError:
            return DOSTRUE, ERR_DISK_FULL
        f["size"] += grow
        if self.limit:
            self.used += grow
        return n, 0

    def _seek(self, fid: int, pos: int, mode: int):  #vers 1
        f = self.files.get(fid)
        if not f:
            return DOSTRUE, ERR_INVALID_LOCK
        fh = f["f"]
        old = fh.tell()
        pos = pos - (1 << 32) if pos & 0x80000000 else pos
        mode = mode - (1 << 32) if mode & 0x80000000 else mode
        fh.seek(0, 2)
        end = fh.tell()
        new = pos if mode == -1 else old + pos if mode == 0 else end + pos
        if new < 0 or new > end:
            fh.seek(old)
            return DOSTRUE, ERR_SEEK
        fh.seek(new)
        return old, 0

    def _set_size(self, fid: int, pos: int, mode: int):  #vers 2
        f = self.files.get(fid)
        if not f or not self.writable:
            return DOSTRUE, ERR_WRITE_PROT if f else ERR_INVALID_LOCK
        fh = f["f"]
        cur = fh.tell()
        pos = pos - (1 << 32) if pos & 0x80000000 else pos
        mode = mode - (1 << 32) if mode & 0x80000000 else mode
        fh.seek(0, 2)
        end = fh.tell()
        new = max(0, pos if mode == -1 else cur + pos if mode == 0 else end + pos)
        if self.limit:
            self.used = self._used_bytes() + new - f["size"]
        f["size"] = new
        fh.truncate(new)
        fh.seek(min(cur, new))
        return new, 0

    def _create_dir(self, lock: int, name: str):  #vers 1
        if not self.writable:
            return 0, ERR_WRITE_PROT
        err, host, rel, leaf = self._resolve(lock, name, leaf_may_miss=True)
        if err:
            return 0, err
        if leaf is None:
            return 0, ERR_EXISTS
        p = os.path.join(host, leaf)
        try:
            os.mkdir(p)
        except OSError:
            return 0, ERR_DISK_FULL
        return self._make_lock(p, rel + (leaf,), 0xFFFFFFFF)

    def _delete(self, lock: int, name: str) -> int:  #vers 2
        if not self.writable:
            return ERR_WRITE_PROT
        err, host, rel, leaf = self._resolve(lock, name)
        if err:
            return err
        if not rel:
            return ERR_DELETE_PROT
        if any(f["host"] == host for f in self.files.values()):
            return ERR_IN_USE
        size = os.path.getsize(host) if self.limit and os.path.isfile(host) else 0
        if self.limit:
            self._used_bytes()
        try:
            if os.path.isdir(host):
                os.rmdir(host)
            else:
                os.remove(host)
        except OSError:
            return ERR_NOT_EMPTY if os.path.isdir(host) else ERR_DELETE_PROT
        self.used = self.used - size if self.limit else self.used
        self.db.delete(rel)
        return 0

    def _rename(self, lock: int, name: str, lock2: int, name2: str) -> int:  #vers 1
        if not self.writable:
            return ERR_WRITE_PROT
        err, src, rel, _ = self._resolve(lock, name)
        if err:
            return err
        err, dd, drel, leaf = self._resolve(lock2, name2, leaf_may_miss=True)
        if err:
            return err
        if leaf is None:
            return ERR_EXISTS
        dst = os.path.join(dd, leaf)
        try:
            os.rename(src, dst)
        except OSError:
            return ERR_IN_USE
        self.db.rename(rel, drel + (leaf,))
        return 0

    def _disk_info(self, addr: int) -> None:  #vers 2
        """Fill InfoData; block size grows so counts fit 31 bits."""
        try:
            u = shutil.disk_usage(self.folder)
            total, used = u.total, u.used
        except OSError:
            total = used = 0
        if self.limit:
            total, used = self.limit, min(self._used_bytes(), self.limit)
        bs = 512
        while total // bs > 0x7FFFFFFF:
            bs *= 2
        state = 82 if self.writable else 80
        self.mem.wr(addr, struct.pack(">IIIIIIIII", 0, 0, state, total // bs, used // bs, bs, 0x444F5301, self.vn >> 2, 0))

    def packet(self, pkt: int, port: int, dn: int, vn: int):  #vers 3
        """Run one packet and write dp_Res1/dp_Res2; returns "start" for the startup packet."""
        m = self.mem
        typ = m.r32(pkt + 8)
        a = [m.r32(pkt + 20 + 4 * i) for i in range(7)]
        self.port, self.vn = port, vn
        res1, res2 = 0, 0
        try:
            if typ == 0:
                m.w32(dn + 8, port)
                m.w32(vn + 8, port)
                m.w32(pkt + 12, DOSTRUE)
                m.w32(pkt + 16, 0)
                return "start"
            res1, res2 = self._dispatch(typ, a)
        except OSError as e:
            res1, res2 = 0, ERR_NOT_FOUND
            if self.log:
                self.log(f"os error {e}")
        if self.log:
            nm = self._bstr(a[1]) if typ in (8, 16, 17, 22) else self._bstr(a[2]) if typ in (1004, 1005, 1006) else ""
            self.log(f"packet {NAMES.get(typ, typ)} {nm!r} {[hex(x) for x in a[:3]]} -> {res1:X} {res2}")
        m.w32(pkt + 12, res1 & 0xFFFFFFFF)
        m.w32(pkt + 16, res2 & 0xFFFFFFFF)

    def _dispatch(self, typ: int, a: list) -> tuple:  #vers 2
        """Map one action to (res1, res2)."""
        def fail(err):
            return 0, err

        if typ == 8:                                              # LOCATE_OBJECT
            err, host, rel, leaf = self._resolve(a[0], self._bstr(a[1]))
            if err:
                return fail(err)
            lk, e = self._make_lock(host, rel, a[2])
            return (lk, 0) if lk else fail(e)
        if typ == 15:                                             # FREE_LOCK
            self._free_lock(a[0])
            return DOSTRUE, 0
        if typ == 19:                                             # COPY_DIR
            info = self._lock_info(a[0])
            if info is None:
                return fail(ERR_INVALID_LOCK)
            lk, e = self._make_lock(info[0], info[1], 0xFFFFFFFE)
            return (lk, 0) if lk else fail(e)
        if typ == 29:                                             # PARENT
            lk, e = self._parent(a[0])
            return lk, e
        if typ == 1031:                                           # PARENT_FH
            f = self.files.get(a[0])
            if not f:
                return fail(ERR_INVALID_LOCK)
            if len(f["rel"]) < 1:
                return 0, 0
            lk, e = self._make_lock(os.path.dirname(f["host"]), f["rel"][:-1], 0xFFFFFFFE)
            return lk, e
        if typ == 1030:                                           # COPY_DIR_FH
            f = self.files.get(a[0])
            if not f:
                return fail(ERR_INVALID_LOCK)
            lk, e = self._make_lock(f["host"], f["rel"], 0xFFFFFFFE)
            return (lk, 0) if lk else fail(e)
        if typ == 40:                                             # SAME_LOCK
            x, y = self._lock_info(a[0]), self._lock_info(a[1])
            return (DOSTRUE if x and y and x[0] == y[0] else 0), 0
        if typ == 23:                                             # EXAMINE_OBJECT
            e = self._examine(a[0], a[1] << 2)
            return (DOSTRUE, 0) if not e else fail(e)
        if typ == 1034:                                           # EXAMINE_FH
            e = self._examine(a[0], a[1] << 2, True)
            return (DOSTRUE, 0) if not e else fail(e)
        if typ == 24:                                             # EXAMINE_NEXT
            e = self._examine_next(a[0], a[1] << 2)
            return (DOSTRUE, 0) if not e else fail(e)
        if typ in (1004, 1005, 1006):                             # FINDUPDATE / FINDINPUT / FINDOUTPUT
            e = self._open(typ, a[0], a[1], self._bstr(a[2]))
            return (DOSTRUE, 0) if not e else fail(e)
        if typ == 1026:                                           # FH_FROM_LOCK
            info = self._lock_info(a[1])
            if info is None or info[2]:
                return fail(ERR_WRONG_TYPE)
            try:
                f = open(info[0], "r+b" if self.writable else "rb")
            except OSError:
                return fail(ERR_NOT_FOUND)
            fid = self.next_file
            self.next_file += 1
            self.files[fid] = {"f": f, "host": info[0], "rel": info[1]}
            self.mem.w32((a[0] << 2) + 36, fid)
            self.mem.w32((a[0] << 2) + 8, self.port)
            self._free_lock(a[1])
            return DOSTRUE, 0
        if typ == 82:                                             # READ
            return self._read(a[0], a[1], a[2])
        if typ == 87:                                             # WRITE
            return self._write(a[0], a[1], a[2])
        if typ == 1008:                                           # SEEK
            return self._seek(a[0], a[1], a[2])
        if typ == 1022:                                           # SET_FILE_SIZE
            return self._set_size(a[0], a[1], a[2])
        if typ == 1007:                                           # END
            f = self.files.pop(a[0], None)
            if f:
                f["f"].close()
            return DOSTRUE, 0
        if typ == 22:                                             # CREATE_DIR
            return self._create_dir(a[0], self._bstr(a[1]))
        if typ == 16:                                             # DELETE_OBJECT
            e = self._delete(a[0], self._bstr(a[1]))
            return (DOSTRUE, 0) if not e else fail(e)
        if typ == 17:                                             # RENAME_OBJECT
            e = self._rename(a[0], self._bstr(a[1]), a[2], self._bstr(a[3]))
            return (DOSTRUE, 0) if not e else fail(e)
        if typ in (21, 28, 34):                                   # SET_PROTECT / SET_COMMENT / SET_DATE
            if not self.writable:
                return fail(ERR_WRITE_PROT)
            err, host, rel, _ = self._resolve(a[1], self._bstr(a[2]))
            if err:
                return fail(err)
            if typ == 21:
                self.db.set(rel, prot=a[3] & 0xFF)
            elif typ == 28:
                self.db.set(rel, comment=self._bstr(a[3]))
            else:
                d, mi, tk = struct.unpack(">III", self.mem.rd(a[3], 12))
                t = self._from_stamp(d, mi, tk)
                os.utime(host, (t, t))
            return DOSTRUE, 0
        if typ == 25:                                             # DISK_INFO
            self._disk_info(a[0] << 2)
            return DOSTRUE, 0
        if typ == 26:                                             # INFO
            self._disk_info(a[1] << 2)
            return DOSTRUE, 0
        if typ == 7:                                              # CURRENT_VOLUME
            return self.vn >> 2, 0
        if typ in (18, 27, 30, 31, 1027, 1028):                   # MORE_CACHE FLUSH TIMER INHIBIT IS_FILESYSTEM CHANGE_MODE
            return DOSTRUE, 0
        return fail(ERR_UNKNOWN)
