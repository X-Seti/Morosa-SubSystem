#this belongs in apps/methods/formats.py - Version: 1
# X-Seti - November 17 2026 - Morosa - Morosa Package Formats.

"""
Morosa Package Formats - recognises Amiga programs, scripts, installers, archives and disk images by content.
"""

##Methods list -
# classify
# describe
# read_text

import os

from apps.methods import amiga_disk, dos as morosa_dos, installer as morosa_installer


def read_text(path: str, limit: int = 1 << 20) -> str: #vers 1
    """File as text; Amiga files are latin-1."""
    with open(path, "rb") as f:
        return f.read(limit).decode("latin-1")


def classify(path: str) -> str: #vers 1
    """installer, dos-script, program, whdload-slave, icon, lha, lzx, zip, dms, adf or ''."""
    if not os.path.isfile(path):
        return ""
    try:
        with open(path, "rb") as f:
            head = f.read(4096)
    except OSError:
        return ""
    if head[:4] == b"\x00\x00\x03\xf3":
        return "whdload-slave" if b"WHDLOADS" in head or path.lower().endswith(".slave") else "program"
    if head[:2] == b"\xe3\x10":
        return "icon"
    if head[2:5] == b"-lh" or head[2:5] == b"-lz":
        return "lha"
    if head[:3] == b"LZX":
        return "lzx"
    if head[:2] == b"PK":
        return "zip"
    if head[:4] == b"DMS!":
        return "dms"
    if amiga_disk.is_disk(path):
        return "adf"
    if b"\x00" in head:
        return ""
    text = head.decode("latin-1")
    if morosa_installer.is_installer(text):
        return "installer"
    if morosa_dos.is_dos_script(text):
        return "dos-script"
    return ""


def describe(path: str) -> str: #vers 1
    """Step list for installer and DOS scripts, a one line note for other kinds."""
    kind = classify(path)
    if kind == "installer":
        return morosa_installer.render(read_text(path))
    if kind == "dos-script":
        return morosa_dos.render(read_text(path))
    return {"program": "Amiga program (m68k hunk executable).", "whdload-slave": "WHDLoad slave.",
            "icon": "Amiga icon (.info).", "lha": "LHA archive.", "lzx": "LZX archive.", "zip": "ZIP archive.",
            "dms": "DMS disk image.", "adf": "Amiga disk image."}.get(kind, "Not an Amiga package.")
