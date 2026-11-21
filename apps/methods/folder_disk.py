#this belongs in apps/methods/folder_disk.py - Version: 1
# X-Seti - November 17 2026 - Morosa - Folder To Hard Disk.

"""
Folder Disk - builds a bootable RDB + FFS hard disk image from a host folder; guest writes stay in memory.
"""

##Methods list -
# build_file
# build_image
# _alloc
# _bitmap_blocks
# _checksum
# _hash
# _name_bytes
# _rdb_blocks
# _scan
# _stamp
# _unique

import mmap
import os
import struct
import tempfile

from apps.hardware.ide import HEADS, SPT
from apps.methods.amiga_disk import AMIGA_EPOCH

BS = 512
HT = 72
CYL = HEADS * SPT
_BM_PER = 127 * 32


def _name_bytes(name: str) -> bytes:  #vers 1
    """Amiga name: Latin-1, at most 30 bytes, no slash or colon."""
    b = name.replace("/", "_").replace(":", "_").encode("latin-1", "replace")[:30]
    return b or b"_"


def _unique(raw: bytes, used: set) -> bytes:  #vers 1
    """Make a name unique (case-insensitive) inside one directory."""
    n, cand = 1, raw
    while cand.upper() in used:
        n += 1
        tail = b"~%d" % n
        cand = raw[:30 - len(tail)] + tail
    used.add(cand.upper())
    return cand


def _hash(name: bytes) -> int:  #vers 1
    h = len(name)
    for c in name:
        h = (h * 13 + (c - 32 if 97 <= c <= 122 else c)) & 0x7FF
    return h % HT


def _checksum(w: list, idx: int) -> None:  #vers 1
    w[idx] = 0
    w[idx] = -sum(w) & 0xFFFFFFFF


def _stamp(t: float) -> tuple:  #vers 1
    s = max(0, int(t) - AMIGA_EPOCH)
    return s // 86400, s % 86400 // 60, s % 60 * 50


def _scan(path: str) -> dict:  #vers 1
    """Tree of {name, path, dir, size, mtime, kids} for a host folder."""
    node = {"path": path, "dir": True, "size": 0, "mtime": os.path.getmtime(path), "kids": []}
    used = set()
    try:
        names = sorted(os.listdir(path), key=str.lower)
    except OSError:
        return node
    for n in names:
        p = os.path.join(path, n)
        try:
            st = os.stat(p)
        except OSError:
            continue
        nm = _unique(_name_bytes(n), used)
        if os.path.isdir(p):
            kid = _scan(p)
        elif os.path.isfile(p):
            kid = {"path": p, "dir": False, "size": st.st_size, "mtime": st.st_mtime, "kids": []}
        else:
            continue
        kid["name"] = nm
        node["kids"].append(kid)
    return node


def _count(node: dict) -> int:  #vers 1
    """Blocks used by a node and everything below it."""
    if not node["dir"]:
        n = -(-node["size"] // BS)
        return n + 1 + ((n - 1) // HT if n else 0)
    return 1 + sum(_count(k) for k in node["kids"])


class _Alloc:
    def __init__(self, nblocks: int, skip: range):  #vers 1
        self.n, self.skip, self.next = nblocks, skip, 2
        self.used = bytearray(nblocks)

    def take(self, count: int = 1) -> list:  #vers 1
        out = []
        while len(out) < count:
            if self.next in self.skip:
                self.next = self.skip.stop
            if self.next >= self.n:
                raise ValueError("folder does not fit the disk image")
            self.used[self.next] = 1
            out.append(self.next)
            self.next += 1
        return out


def _alloc(nblocks: int, skip: range) -> _Alloc:  #vers 1
    return _Alloc(nblocks, skip)


def _bitmap_blocks(alloc: _Alloc, bm_blocks: list) -> list:  #vers 1
    """Bitmap block images: bit set means the block is free."""
    out = []
    for k, _ in enumerate(bm_blocks):
        w = [0] * 128
        for i in range(_BM_PER):
            blk = 2 + k * _BM_PER + i
            if blk >= alloc.n:
                break
            if not alloc.used[blk] and blk not in alloc.skip:
                w[1 + i // 32] |= 1 << (i % 32)
        w[0] = -sum(w[1:]) & 0xFFFFFFFF
        out.append(w)
    return out


def _rdb_blocks(cyls: int, nblocks: int, label: str, dev: str, boot_pri: int) -> tuple:  #vers 1
    r = [0] * 128
    r[0], r[1], r[3], r[4], r[5] = 0x5244534B, 64, 7, BS, 0x12
    r[6] = r[8] = r[9] = 0xFFFFFFFF
    r[7] = 1
    r[16], r[17], r[18] = cyls, SPT, HEADS
    r[33], r[34], r[35], r[36], r[38] = CYL - 1, 1, cyls - 1, CYL, 1
    raw = b"MOROSA".ljust(8) + b"FOLDER DISK".ljust(16) + b"1.0 "
    r_pack = bytearray(512)
    struct.pack_into(">128I", r_pack, 0, *r)
    r_pack[160:160 + len(raw)] = raw
    w = list(struct.unpack(">128I", bytes(r_pack)))
    w[2] = 0
    w[2] = -sum(w[:64]) & 0xFFFFFFFF
    p = [0] * 128
    p[0], p[1], p[3], p[4], p[5] = 0x50415254, 64, 7, 0xFFFFFFFF, 1
    pb = bytearray(512)
    struct.pack_into(">128I", pb, 0, *p)
    d = _name_bytes(dev)
    pb[36] = len(d)
    pb[37:37 + len(d)] = d
    env = [16, BS // 4, 0, HEADS, 1, SPT, 2, 0, 0, 1, cyls - 1, 30, 0, 0xFFFFFF, 0xFFFFFFFE, boot_pri & 0xFFFFFFFF, 0x444F5301]
    struct.pack_into(">17I", pb, 128, *env)
    q = list(struct.unpack(">128I", bytes(pb)))
    q[2] = 0
    q[2] = -sum(q[:64]) & 0xFFFFFFFF
    return struct.pack(">128I", *w), struct.pack(">128I", *q)


def build_file(folder: str, out, dev: str = "DH0", boot_pri: int = 0, label: str = "") -> int:  #vers 1
    """Write an RDB + FFS image of folder to the open binary file out; returns its size in bytes."""
    tree = _scan(folder)
    label = label or os.path.basename(os.path.abspath(folder)) or "Morosa"
    need = _count(tree) + 3
    nbm = 1
    while True:
        ext = max(0, -(-(nbm - 25) // 127))
        total = need + nbm + ext
        total += max(1024, total // 20)
        part = -(-total // CYL) * CYL
        if -(-(part - 2) // _BM_PER) <= nbm:
            break
        nbm += 1
    cyls = part // CYL + 1
    root = (part + 1) // 2
    bm_blocks = list(range(root + 1, root + 1 + nbm))
    ext_blocks = list(range(root + 1 + nbm, root + 1 + nbm + ext))
    skip = range(root, root + 1 + nbm + ext)
    alloc = _alloc(part, skip)
    base = CYL
    out.truncate(cyls * CYL * BS)

    def put(n: int, data: bytes) -> None:
        out.seek((base + n) * BS)
        out.write(data)

    def put_words(n: int, w: list) -> None:
        put(n, struct.pack(">128I", *w))

    def set_name(w: list, name: bytes, byte_off: int) -> None:
        raw = bytearray(512)
        struct.pack_into(">128I", raw, 0, *w)
        raw[byte_off] = len(name)
        raw[byte_off + 1:byte_off + 1 + len(name)] = name
        w[:] = struct.unpack(">128I", bytes(raw))

    def write_file(node: dict, name: bytes, parent: int, nxt: int) -> int:
        size = node["size"]
        n = -(-size // BS)
        hdr = alloc.take(1)[0]
        data = alloc.take(n) if n else []
        exts = alloc.take((n - 1) // HT if n else 0)
        if n:
            with open(node["path"], "rb") as f:
                i = 0
                while i < n:
                    j = i
                    while j + 1 < n and data[j + 1] == data[j] + 1 and j - i < 2047:
                        j += 1
                    chunk = f.read((j - i + 1) * BS)
                    out.seek((base + data[i]) * BS)
                    out.write(chunk.ljust((j - i + 1) * BS, b"\0"))
                    i = j + 1
        d, m, t = _stamp(node["mtime"])

        def fill(w: list, first: int, count: int) -> None:
            for k in range(count):
                w[77 - k] = data[first + k]

        w = [0] * 128
        w[0], w[1], w[2], w[4] = 2, hdr, min(n, HT), data[0] if n else 0
        fill(w, 0, min(n, HT))
        w[81] = size & 0xFFFFFFFF
        w[105], w[106], w[107] = d, m, t
        w[124], w[125] = nxt, parent
        w[126] = exts[0] if exts else 0
        w[127] = 0xFFFFFFFD
        set_name(w, name, 432)
        _checksum(w, 5)
        put_words(hdr, w)
        for k, e in enumerate(exts):
            x = [0] * 128
            first = HT * (k + 1)
            cnt = min(HT, n - first)
            x[0], x[1], x[2] = 16, e, cnt
            fill(x, first, cnt)
            x[125] = hdr
            x[126] = exts[k + 1] if k + 1 < len(exts) else 0
            x[127] = 0xFFFFFFFD
            _checksum(x, 5)
            put_words(e, x)
        return hdr

    def write_dir(node: dict, name: bytes, parent: int, nxt: int, blk: int = 0) -> int:
        blk = blk or alloc.take(1)[0]
        ht = [0] * HT
        for kid in node["kids"]:
            h = _hash(kid["name"])
            if kid["dir"]:
                kb = write_dir(kid, kid["name"], blk, ht[h])
            else:
                kb = write_file(kid, kid["name"], blk, ht[h])
            ht[h] = kb
        d, m, t = _stamp(node["mtime"])
        w = [0] * 128
        w[0], w[1] = 2, blk
        w[6:6 + HT] = ht
        w[105], w[106], w[107] = d, m, t
        w[124], w[125] = nxt, parent
        w[127] = 2
        if parent == 0:
            w[0], w[3], w[78] = 2, HT, 0xFFFFFFFF
            w[1] = 0
            w[118], w[119], w[120], w[121], w[122], w[123] = d, m, t, d, m, t
            for i, b in enumerate(bm_blocks[:25]):
                w[79 + i] = b
            w[104] = ext_blocks[0] if ext_blocks else 0
            w[124] = w[125] = w[126] = 0
            w[127] = 1
        set_name(w, name, 432)
        _checksum(w, 5)
        put_words(blk, w)
        return blk

    put(0, b"DOS\x01" + bytes(1020))
    write_dir(tree, _name_bytes(label), 0, 0, root)
    for k, w in enumerate(_bitmap_blocks(alloc, bm_blocks)):
        put_words(bm_blocks[k], w)
    rest = bm_blocks[25:]
    for k, e in enumerate(ext_blocks):
        chunk = rest[k * 127:(k + 1) * 127]
        x = chunk + [0] * (127 - len(chunk)) + [ext_blocks[k + 1] if k + 1 < len(ext_blocks) else 0]
        put_words(e, x)
    r, p = _rdb_blocks(cyls, part, label, dev, boot_pri)
    out.seek(0)
    out.write(r + p)
    return cyls * CYL * BS


def build_image(folder: str, dev: str = "DH0", boot_pri: int = 0):  #vers 1
    """Memory-mapped bootable disk image of folder; changes made by the guest are not saved."""
    tmp = tempfile.TemporaryFile()
    size = build_file(folder, tmp, dev, boot_pri)
    return mmap.mmap(tmp.fileno(), size, access=mmap.ACCESS_COPY)
