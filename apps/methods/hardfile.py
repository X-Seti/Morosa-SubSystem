#this belongs in apps/methods/hardfile.py - Version: 4
# X-Seti - November 18 2026 - Morosa - Morosa Hardfile.

"""
Morosa Hardfile - wraps an image without an RDB in a virtual RDB with one partition, UAE style.
"""

##Methods list -
# HardfileImage
# HardfileImage.__getitem__
# HardfileImage.__len__
# HardfileImage.__setitem__
# HardfileImage._rdb
# _bstr
# describe
# _geometry
# _seal
# has_rdb

import mmap
import os
import struct

ROM_FS = {0x444F5300: "OFS", 0x444F5301: "FFS", 0x444F5302: "OFS international", 0x444F5303: "FFS international",
          0x444F5304: "OFS dir cache", 0x444F5305: "FFS dir cache", 0x444F5306: "OFS long names",
          0x444F5307: "FFS long names"}
EXT_FS = {b"PFS": "PFS (needs handler in RDB)", b"SFS": "SmartFileSystem (needs handler in RDB)",
          b"DOS": "DOS", b"MUF": "MultiUser FS", b"PDS": "PFS (needs handler in RDB)"}
MAGIC = {b"PK": "zip archive, unpack first", b"LZX": "LZX archive, unpack first", b"\x1f\x8b": "gzip, unpack first",
         b"7z": "7z archive, unpack first", b"Rar": "rar archive, unpack first"}


def has_rdb(image) -> bool:  #vers 1
    """True when one of the first 16 blocks holds an RDSK block."""
    return any(bytes(image[b * 512:b * 512 + 4]) == b"RDSK" for b in range(16))


def _bstr(text: str, size: int) -> bytes:  #vers 1
    return bytes([len(text)]) + text.encode().ljust(size - 1, b"\0")[:size - 1]


def _seal(longs: list) -> bytes:  #vers 1
    """Set the checksum so all summed longs add to zero."""
    longs[2] = 0
    longs[2] = -sum(longs[:longs[1]]) & 0xFFFFFFFF
    return struct.pack(">128L", *longs)


def _geometry(blocks: int, heads: int, spt: int) -> tuple:  #vers 1
    """Heads and sectors giving whole cylinders, so the root block sits where the filesystem expects."""
    if blocks % (heads * spt) == 0:
        return heads, spt
    for h in dict.fromkeys((heads, 16, 8, 4, 2, 1)):
        for s in range(63, 7, -1):
            if blocks % (h * s) == 0:
                return h, s
    return heads, spt


class HardfileImage:
    """Slice access like a bytearray: a reserved cylinder with RDB and PART blocks, then the image."""

    def __init__(self, image, heads: int = 16, spt: int = 63, name: str = "DH0", dostype: int = 0, boot_pri: int = 0):  #vers 2
        self.image = image
        heads, spt = _geometry((len(image) + 511) // 512, heads, spt)
        self.heads, self.spt = heads, spt
        self.cylblocks = heads * spt
        data_blocks = (len(image) + 511) // 512
        self.cyls = 1 + -(-data_blocks // self.cylblocks)
        self.size = self.cyls * self.cylblocks * 512
        self.base = self.cylblocks * 512
        self.boot_pri = boot_pri
        self.head = self._rdb(name, dostype or self._guess_dostype())
        self.name = name

    def _guess_dostype(self) -> int:  #vers 1
        t = bytes(self.image[:4])
        return struct.unpack(">I", t)[0] if t[:3] == b"DOS" else 0x444F5301

    def _rdb(self, name: str, dostype: int) -> bytes:  #vers 1
        r = [0xFFFFFFFF] * 128
        r[0], r[1], r[3], r[4], r[5] = 0x5244534B, 64, 7, 512, 0x12
        r[6], r[7], r[8], r[9] = 0xFFFFFFFF, 1, 0xFFFFFFFF, 0xFFFFFFFF
        r[16], r[17], r[18], r[19], r[20] = self.cyls, self.spt, self.heads, 0, self.cyls
        r[23] = r[24] = r[25] = 0
        r[32], r[33], r[34], r[35], r[36], r[37], r[38] = 0, self.cylblocks - 1, 1, self.cyls - 1, self.cylblocks, 0, 1
        r[39] = 0
        for i in range(40, 64):
            r[i] = 0
        vend = b"MOROSA  " + b"HARDFILE".ljust(16) + b"1.0 "
        r[40:40 + len(vend) // 4] = struct.unpack(">7L", vend)
        p = [0] * 128
        p[0], p[1], p[3], p[4], p[5] = 0x50415254, 64, 7, 0xFFFFFFFF, 0 if self.boot_pri <= -128 else 1
        p[9:17] = struct.unpack(">8L", _bstr(name, 32))
        p[32:52] = [16, 128, 0, self.heads, 1, self.spt, 2, 0, 0, 1, self.cyls - 1, 30, 0,
                    0x7FFFFFFF, 0xFFFFFFFE, self.boot_pri & 0xFFFFFFFF, dostype, 0, 0, 0]
        return _seal(r) + _seal(p)

    def __len__(self) -> int:  #vers 1
        return self.size

    def __getitem__(self, key):  #vers 1
        start, stop, _ = key.indices(self.size)
        out = bytearray(max(0, stop - start))
        if start < 1024:
            n = min(stop, 1024) - start
            out[:n] = self.head[start:start + n]
        lo = max(start, self.base)
        if stop > lo:
            src = self.image[lo - self.base:min(stop - self.base, len(self.image))]
            out[lo - start:lo - start + len(src)] = src
        return bytes(out)

    def __setitem__(self, key, value) -> None:  #vers 1
        start, stop, _ = key.indices(self.size)
        lo = max(start, self.base)
        hi = min(stop - self.base, len(self.image))
        if hi > lo - self.base:
            self.image[lo - self.base:hi] = value[lo - start:lo - start + hi - (lo - self.base)]


def _fs_name(t: int) -> str:  #vers 1
    if t in ROM_FS:
        return f"{ROM_FS[t]} (in ROM)"
    b = struct.pack(">I", t)
    return f"{b[:3].decode('latin-1', 'replace')}\\{b[3]} {EXT_FS.get(b[:3], 'unknown')}"


def _sum_ok(blk: bytes, n: int = 128) -> bool:  #vers 1
    return sum(struct.unpack(f">{n}I", blk[:n * 4])) & 0xFFFFFFFF == 0


def describe(path: str) -> list:  #vers 2
    """Lines describing a hard disk image: RDB or plain hardfile, filesystem, geometry, and what is wrong."""
    out = []
    if os.path.isdir(path):
        out.append("Folder: mounted live as a host filesystem (Zorro II board).")
        s_dir = next((n for n in os.listdir(path) if n.lower() == "s"), None)
        has = s_dir and any(n.lower() == "startup-sequence" for n in os.listdir(os.path.join(path, s_dir)))
        out.append("S/Startup-Sequence found; bootable." if has else "No S/Startup-Sequence in this folder; not bootable.")
        out.append("Writes follow the hard disk write setting.")
        return out
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            head = f.read(512 * 32)
            data = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) if size else b""
    except OSError as e:
        return [f"Cannot read: {e}"]
    out.append(f"Size: {size} bytes ({size / 1048576:.2f} MB, {size // 512} blocks){'' if size % 512 == 0 else ', not a multiple of 512'}")
    for k, v in MAGIC.items():
        if head[:len(k)] == k:
            return out + [f"File is a {v}."]
    from apps.hardware import cdimage
    if cdimage.is_cd_image(path):
        return out + ["CD image: use a SCSI or ATAPI slot; no RDB needed."]
    if size == 901120 or size == 1802240:
        return out + ["Floppy disk image (ADF): put it in a DF slot, not a hard drive slot."]
    rdb = next((b for b in range(16) if head[b * 512:b * 512 + 4] == b"RDSK"), None)
    if rdb is not None:
        blk = head[rdb * 512:rdb * 512 + 512]
        r = struct.unpack(">128I", blk)
        out.append(f"RDB at block {rdb}, checksum {'ok' if _sum_ok(blk, r[1]) else 'BAD'}")
        out.append(f"Geometry: {r[16]} cylinders, {r[18]} heads, {r[17]} sectors; block size {r[4]}")
        n, nxt, seen = 0, r[7], set()
        while nxt not in (0xFFFFFFFF, 0) and nxt not in seen and (nxt + 1) * 512 <= len(data):
            seen.add(nxt)
            pb = data[nxt * 512:nxt * 512 + 512]
            p = struct.unpack(">128I", pb)
            if p[0] != 0x50415254:
                out.append(f"Block {nxt}: not a PART block")
                break
            nm = pb[37:37 + pb[36]].decode("latin-1", "replace")
            env = p[32:52]
            out.append(f"Partition {n} {nm}: cyl {env[9]}-{env[10]}, {'bootable' if p[5] & 1 else 'not bootable'}, "
                       f"{'no automount, ' if p[5] & 2 else ''}pri {struct.unpack('>i', struct.pack('>I', env[15]))[0]}, {_fs_name(env[16])}")
            if env[16] not in ROM_FS and not r[8] + 1:
                out.append("  needs a filesystem handler, but the RDB has no FSHD block")
            n, nxt = n + 1, p[4]
        if r[8] not in (0xFFFFFFFF, 0):
            out.append("RDB holds filesystem handler(s) (FSHD): loaded by scsi.device.")
        if n == 0:
            out.append("No partitions found.")
        return out
    if size < 1024:
        return out + ["Too small to be a disk."]
    t = head[:4]
    dt = struct.unpack(">I", t)[0]
    out.append("No RDB: loaded as a hardfile with a virtual RDB.")
    out.append(f"Boot block type: {_fs_name(dt) if t[:3] == b'DOS' else 'none (' + t.hex() + ')'}")
    blocks = size // 512
    h, sp = _geometry(blocks, 16, 63)
    out.append(f"Geometry used: {h} heads, {sp} sectors per track ({blocks // (h * sp)} cylinders)")
    roots = []
    cand = range(blocks) if size <= 64 << 20 else (blocks // 2,)
    for b in cand:
        o = b * 512
        if data[o:o + 4] == b"\x00\x00\x00\x02" and data[o + 508:o + 512] == b"\x00\x00\x00\x01" and _sum_ok(data[o:o + 512]):
            roots.append(b)
            if len(roots) > 3:
                break
    if not roots:
        out.append("No filesystem root block found: not an Amiga disk, or it uses a filesystem other than OFS/FFS (PFS, SFS).")
    else:
        out.append(f"Root block at {roots[0]}; expected at {blocks // 2}" + (" (matches)" if roots[0] == blocks // 2 else ""))
        if roots[0] != blocks // 2:
            out.append(f"Partition seems to span {roots[0] * 2} blocks of the {blocks}: file may have extra data or an offset.")
    return out
