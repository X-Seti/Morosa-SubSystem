#this belongs in apps/methods/amiga_disk.py - Version: 2
# X-Seti - November 17 2026 - Morosa - Amiga ADF and HDF disk images.

"""
Amiga Disk - extracts OFS / FFS volumes from ADF floppy and HDF hard disk images (RDB or single volume).
"""

##Methods list -
# extract
# info
# is_disk
# main
# _entries
# _boot_sum_ok
# _dostype
# _find_root
# _free_blocks
# _partitions
# _read_file
# _vol_info
# _volume

import os
import struct
import sys

AMIGA_EPOCH = 252460800          # 1978-01-01 in unix seconds
_T_HEADER, _ST_ROOT, _ST_DIR, _ST_FILE = 2, 1, 2, -3


class DiskError(Exception):
    pass


def is_disk(path: str) -> bool: #vers 1
    """True for .adf and .hdf names."""
    return path.lower().endswith(('.adf', '.hdf'))


def _long(blk: bytes, i: int) -> int: #vers 1
    return struct.unpack_from('>I', blk, i * 4)[0]


def _slong(blk: bytes, i: int) -> int: #vers 1
    return struct.unpack_from('>i', blk, i * 4)[0]


def _sum_ok(blk: bytes) -> bool: #vers 1
    return sum(struct.unpack('>%dI' % (len(blk) // 4), blk)) & 0xFFFFFFFF == 0


class _Vol:
    def __init__(self, f, start: int, nblocks: int, bsize: int, ffs: bool):
        self.f, self.start, self.n, self.bs, self.ffs = f, start, nblocks, bsize, ffs

    def block(self, n: int) -> bytes:
        if not 0 <= n < self.n:
            raise DiskError(f"bad block {n}")
        self.f.seek((self.start + n) * self.bs)
        b = self.f.read(self.bs)
        if len(b) != self.bs:
            raise DiskError("short read")
        return b


def _find_root(vol: _Vol): #vers 1
    """Root block number: scan around the middle for a valid root block."""
    mid = vol.n // 2
    for d in range(0, 2000):
        for n in (mid + d, mid - d):
            if 2 <= n < vol.n:
                b = vol.block(n)
                if _long(b, 0) == _T_HEADER and _slong(b, vol.bs // 4 - 1) == _ST_ROOT and _sum_ok(b):
                    return n
    raise DiskError("no root block (not OFS / FFS?)")


def _name(blk: bytes, bs: int) -> str: #vers 1
    off = bs - 80
    ln = min(blk[off], 30)
    return blk[off + 1:off + 1 + ln].decode('latin-1').replace('/', '_').replace('\0', '') or '_'


def _mtime(blk: bytes, bs: int) -> int: #vers 1
    i = bs // 4 - 23                       # days, mins, ticks
    return AMIGA_EPOCH + _long(blk, i) * 86400 + _long(blk, i + 1) * 60 + _long(blk, i + 2) // 50


def _read_file(vol: _Vol, hdr: bytes, out) -> None: #vers 1
    """Write the data blocks of a file header chain to out."""
    size = _long(hdr, vol.bs // 4 - 47)
    ptrs, blk, seen = [], hdr, set()
    while True:
        cnt = _long(blk, 2)
        ptrs += [_long(blk, vol.bs // 4 - 51 - i) for i in range(cnt)]
        nxt = _long(blk, vol.bs // 4 - 2)
        if not nxt or nxt in seen:
            break
        seen.add(nxt)
        blk = vol.block(nxt)
    left = size
    for p in ptrs:
        if left <= 0:
            break
        b = vol.block(p)
        data = b[:vol.bs] if vol.ffs else b[24:24 + _long(b, 3)]
        out.write(data[:left])
        left -= len(data[:left])


def _entries(vol: _Vol, dirblk: bytes):  #vers 1
    """(header block number, header) of each entry in a directory's hash table."""
    seen = set()
    for i in range(6, 6 + (vol.bs // 4 - 56)):
        n = _long(dirblk, i)
        while n and n not in seen:
            seen.add(n)
            b = vol.block(n)
            yield n, b
            n = _long(b, vol.bs // 4 - 4)


def _volume(vol: _Vol, dest: str, count: list) -> None: #vers 1
    """Extract a whole volume into dest."""
    root = vol.block(_find_root(vol))

    def walk(dirblk: bytes, path: str):
        os.makedirs(path, exist_ok=True)
        for _n, b in _entries(vol, dirblk):
            st = _slong(b, vol.bs // 4 - 1)
            tgt = os.path.join(path, _name(b, vol.bs))
            if st == _ST_DIR:
                walk(b, tgt)
            elif st == _ST_FILE:
                with open(tgt, 'wb') as out:
                    _read_file(vol, b, out)
                try:
                    os.utime(tgt, (_mtime(b, vol.bs),) * 2)
                except OSError:
                    pass
                count[0] += 1
    walk(root, dest)


def _partitions(f, size: int):  #vers 1
    """[(name, start block, blocks, bsize, dostype)] from an RDB, or []."""
    for n in range(16):
        f.seek(n * 512)
        b = f.read(512)
        if b[:4] == b'RDSK':
            part = struct.unpack_from('>I', b, 28)[0]
            out, seen = [], set()
            while part != 0xFFFFFFFF and part not in seen:
                seen.add(part)
                f.seek(part * 512)
                p = f.read(512)
                if p[:4] != b'PART':
                    break
                nlen = p[36]
                name = p[37:37 + min(nlen, 30)].decode('latin-1')
                env = struct.unpack_from('>17I', p, 128)
                bs, surf, bpt = env[1] * 4, env[3], env[5]
                low, high, dos = env[9], env[10], env[16]
                out.append((name or f"DH{len(out)}", low * surf * bpt, (high - low + 1) * surf * bpt, bs, dos))
                part = struct.unpack_from('>I', p, 16)[0]
            return out
    return []


def extract(path: str, dest: str) -> int: #vers 2
    """Extract an ADF or HDF into dest; returns the number of files. Raises DiskError."""
    size = os.path.getsize(path)
    count = [0]
    os.makedirs(dest, exist_ok=True)
    with open(path, 'rb') as f:
        parts = _partitions(f, size) if path.lower().endswith('.hdf') else []
        if parts:
            if not any(p[4] >> 8 == 0x444F53 for p in parts):
                raise DiskError("Not OFS / FFS (" + ", ".join(f"{p[0]} 0x{p[4]:08X}" for p in parts) + "). Needs live mount.")
            for name, start, n, bs, dos in parts:
                if dos >> 8 != 0x444F53:                      # 'DOS'
                    with open(os.path.join(dest, name + '.unsupported.txt'), 'w') as note:
                        note.write(f"{name}: filesystem 0x{dos:08X} not supported (OFS/FFS only)\n")
                    continue
                _volume(_Vol(f, start, n, bs, bool(dos & 1)), os.path.join(dest, name), count)
        else:
            f.seek(0)
            boot = f.read(4)
            if boot[:3] != b'DOS':
                raise DiskError("not a DOS disk (needs OFS / FFS)")
            _volume(_Vol(f, 0, size // 512, 512, bool(boot[3] & 1)), dest, count)
    return count[0]


def _free_blocks(vol: _Vol, root: bytes) -> int: #vers 1
    """Free blocks counted from the bitmap blocks."""
    free, total = 0, vol.n - 2
    lo = vol.bs // 4 - 49
    for k in range(25):
        n = _long(root, lo + k)
        if not n:
            break
        b = vol.block(n)
        base = k * (vol.bs // 4 - 1) * 32
        for w in range(1, vol.bs // 4):
            word = _long(b, w)
            first = base + (w - 1) * 32
            if first >= total:
                break
            if first + 32 > total:
                word &= (1 << (total - first)) - 1
            free += bin(word).count("1")
    return free


def _dostype(dos: int) -> str: #vers 1
    name = {0: "OFS", 1: "FFS", 2: "OFS intl", 3: "FFS intl", 4: "OFS dircache", 5: "FFS dircache"}.get(dos & 0xFF, "?")
    return f"DOS\\{dos & 0xFF}  ({name})"


def _vol_info(f, start: int, n: int, bs: int, dos: int, label: str) -> dict: #vers 1
    vol = _Vol(f, start, n, bs, bool(dos & 1))
    out = {"label": label, "type": _dostype(dos), "blocks": n, "bsize": bs, "size": n * bs}
    try:
        root = vol.block(_find_root(vol))
        out["name"] = _name(root, bs)
        out["free"] = _free_blocks(vol, root)
        out["modified"] = _mtime(root, bs)
    except DiskError as e:
        out["error"] = str(e)
    return out


def info(path: str) -> list: #vers 1
    """[dict] one per volume: name, type, size, free blocks, modified; boot block data for floppies."""
    size = os.path.getsize(path)
    res = []
    with open(path, 'rb') as f:
        parts = _partitions(f, size) if path.lower().endswith('.hdf') else []
        if parts:
            for name, start, n, bs, dos in parts:
                if dos >> 8 == 0x444F53:
                    res.append(_vol_info(f, start, n, bs, dos, name))
                else:
                    res.append({"label": name, "type": f"0x{dos:08X} (not OFS/FFS)", "blocks": n, "bsize": bs,
                                "size": n * bs, "error": "filesystem not supported"})
        else:
            f.seek(0)
            boot = f.read(1024)
            if boot[:3] != b'DOS':
                raise DiskError("not a DOS disk")
            v = _vol_info(f, 0, size // 512, 512, boot[3], "")
            v["bootable"] = len(boot) == 1024 and _boot_sum_ok(boot) and any(boot[12:])
            res.append(v)
    return res


def _boot_sum_ok(boot: bytes) -> bool: #vers 1
    """Boot block checksum (carry wrapped sum of the 256 longs)."""
    tot = 0
    for i in range(256):
        tot += _long(boot, i)
        if tot > 0xFFFFFFFF:
            tot = (tot & 0xFFFFFFFF) + 1
    return tot == 0xFFFFFFFF


def main(argv: list) -> int: #vers 1
    """Command line: amiga_disk.py image folder."""
    try:
        n = extract(argv[1], argv[2])
    except (DiskError, OSError, struct.error) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    print(f"{n} files")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
