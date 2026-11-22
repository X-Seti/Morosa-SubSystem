#this belongs in apps/methods/rom_scan.py - Version: 1
# X-Seti - November 22 2026 - Morosa - Kickstart ROM Scanner.

"""
Morosa ROM Scanner - finds Kickstart images in a folder and reads their version from the header.
"""

##Methods list -
# kickstart_label
# scan_roms

import os

SIZES = (262144, 524288, 1048576)
MAX_FILES = 600


def kickstart_label(path: str) -> str:  #vers 1
    """Kickstart version from the ROM header, or empty when not a Kickstart image."""
    try:
        with open(path, "rb") as f:
            h = f.read(16)
    except OSError:
        return ""
    if len(h) < 16 or h[0:2] not in (b"\x11\x11", b"\x11\x14"):
        return ""
    ver, rev = int.from_bytes(h[12:14], "big"), int.from_bytes(h[14:16], "big")
    return f"Kickstart {ver}.{rev}" if 30 <= ver <= 60 else ""


def scan_roms(folder: str, depth: int = 2) -> list:  #vers 1
    """List (path, label, size KB) of Kickstart ROMs under folder, sorted by label then name."""
    out = []
    base = os.path.expanduser(folder)
    for root, dirs, files in os.walk(base):
        if root[len(base):].count(os.sep) >= depth:
            dirs[:] = []
        for n in files:
            p = os.path.join(root, n)
            try:
                size = os.path.getsize(p)
            except OSError:
                continue
            if size in SIZES:
                lab = kickstart_label(p)
                if lab:
                    out.append((p, lab, size // 1024))
            if len(out) >= MAX_FILES:
                return sorted(out, key=lambda r: (r[1], r[0]))
    return sorted(out, key=lambda r: (r[1], r[0]))
