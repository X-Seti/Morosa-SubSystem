#this belongs in apps/hardware/cdimage.py - Version: 2
# X-Seti - November 18 2026 - Morosa - Morosa CD Image.

"""
Morosa CD Image - ISO (2048), IMG/BIN (2352) and CUE/BIN disc images read as 2048 byte data sectors.
"""

##Methods list -
# CDImage
# CDImage.close
# CDImage.read
# CDImage.read_raw
# CDImage.track_at
# CDImage._add
# CDImage._load_cue
# CDImage._load_raw
# is_cd_image

import mmap
import os
import re

CD_EXT = (".iso", ".cue", ".bin")
FRAME = 2352


def is_cd_image(path: str) -> bool:  #vers 1
    """True for .iso/.cue/.bin files, and .img files holding an ISO9660 volume."""
    ext = os.path.splitext(path)[1].lower()
    if ext in CD_EXT:
        return True
    if ext != ".img":
        return False
    with open(path, "rb") as f:
        for off in (0x8001, 0x9311, 0x9319):
            f.seek(off)
            if f.read(5) == b"CD001":
                return True
    return False


class CDImage:
    """tracks: dicts with num, audio, size, skip, map, foff, start, blocks. Disc LBAs run across tracks."""

    def __init__(self, path: str):  #vers 1
        self.tracks = []
        self.files = []
        self.blocks = 0
        if path.lower().endswith(".cue"):
            self._load_cue(path)
        else:
            self._load_raw(path)
        if not self.tracks:
            raise ValueError("no tracks in " + path)

    def _open(self, path: str):  #vers 1
        f = open(path, "rb")
        m = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        self.files.append((f, m))
        return m

    def _add(self, m, audio: bool, size: int, skip: int, foff: int, end: int) -> None:  #vers 1
        n = max(0, (end - foff) // size)
        self.tracks.append({"num": len(self.tracks) + 1, "audio": audio, "size": size, "skip": skip,
                            "map": m, "foff": foff, "start": self.blocks, "blocks": n})
        self.blocks += n

    def _load_raw(self, path: str) -> None:  #vers 1
        m = self._open(path)
        size, skip = 2048, 0
        if len(m) > 0x9319 + 5:
            if m[0x8001:0x8006] == b"CD001":
                size = 2048
            elif m[0x9311:0x9316] == b"CD001":
                size, skip = FRAME, 16
            elif m[0x9319:0x931E] == b"CD001":
                size, skip = FRAME, 24
            elif len(m) % FRAME == 0:
                size, skip = FRAME, 16
        elif path.lower().endswith((".bin", ".img")) and len(m) % FRAME == 0:
            size, skip = FRAME, 16
        self._add(m, False, size, skip, 0, len(m))

    def _load_cue(self, path: str) -> None:  #vers 1
        base = os.path.dirname(path)
        cur, trk, lines = None, None, []
        for ln in open(path, "r", errors="replace"):
            t = ln.strip()
            m = re.match(r'FILE\s+"?(.*?)"?\s+\w+\s*$', t, re.I)
            if m:
                cur = self._open(os.path.join(base, m.group(1)))
                continue
            m = re.match(r"TRACK\s+(\d+)\s+(\S+)", t, re.I)
            if m:
                trk = {"mode": m.group(2).upper(), "map": cur, "idx": None}
                lines.append(trk)
                continue
            m = re.match(r"INDEX\s+0?1\s+(\d+):(\d+):(\d+)", t, re.I)
            if m and trk is not None:
                mm, ss, ff = (int(x) for x in m.groups())
                trk["idx"] = (mm * 60 + ss) * 75 + ff
        for i, t in enumerate(lines):
            mode = t["mode"]
            audio = mode == "AUDIO"
            size = 2048 if mode.endswith("/2048") else FRAME
            skip = 0 if size == 2048 else (24 if mode.startswith("MODE2") else 16)
            foff = (t["idx"] or 0) * size
            nxt = lines[i + 1] if i + 1 < len(lines) else None
            end = nxt["idx"] * size if nxt and nxt["map"] is t["map"] and nxt["idx"] is not None else len(t["map"])
            self._add(t["map"], audio, size, skip, foff, end)

    def track_at(self, lba: int):  #vers 1
        for t in self.tracks:
            if t["start"] <= lba < t["start"] + t["blocks"]:
                return t
        return None

    def read(self, lba: int) -> bytes:  #vers 1
        """One 2048 byte data sector, or None if the sector is outside a data track."""
        t = self.track_at(lba)
        if t is None or t["audio"]:
            return None
        o = t["foff"] + (lba - t["start"]) * t["size"] + t["skip"]
        return bytes(t["map"][o:o + 2048])

    def read_raw(self, lba: int) -> bytes:  #vers 1
        """One 2352 byte mode 1 sector; 2048 byte images get sync, header and zero EDC."""
        t = self.track_at(lba)
        if t is None or t["audio"]:
            return None
        if t["size"] == FRAME:
            o = t["foff"] + (lba - t["start"]) * FRAME
            return bytes(t["map"][o:o + FRAME])
        f = lba + 150
        bcd = lambda v: v // 10 << 4 | v % 10
        head = b"\0" + b"\xff" * 10 + b"\0" + bytes([bcd(f // 4500), bcd(f // 75 % 60), bcd(f % 75), 1])
        return head + self.read(lba) + bytes(288)

    def close(self) -> None:  #vers 1
        for f, m in self.files:
            m.close()
            f.close()
        self.files = []
