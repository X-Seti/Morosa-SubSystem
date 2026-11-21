#this belongs in apps/methods/config.py - Version: 6
# X-Seti - November 17 2026 - Morosa - Morosa Subsystem.

"""
Morosa Subsystem - AmiSys: folder handling and hunk executable check for the Morosa libraries.
"""

##Methods list -
# amisys_dir
# ensure_amisys
# is_exe
# set_amisys
# build_machine
# delete_profile
# profiles
# save_profile

import json
import os
from pathlib import Path

CONFIG = Path.home() / ".config" / "Morosa" / "morosa.json"
ROOT = Path(__file__).resolve().parents[2]


def _load() -> dict: #vers 1
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def amisys_dir() -> str: #vers 1
    """Host folder that AmiSys: points to; AmiSys beside the program root by default."""
    return _load().get("amisys") or str(ROOT / "AmiSys")


def set_amisys(path: str): #vers 1
    """Choose the host folder behind AmiSys:."""
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    d = _load()
    d["amisys"] = path
    CONFIG.write_text(json.dumps(d, indent=1), encoding="utf-8")


def ensure_amisys() -> str: #vers 2
    """Create the AmiSys folder with the standard drawers; returns its path."""
    base = Path(amisys_dir())
    for d in ("C", "S", "L", "Libs", "Devs", "Fonts", "T", "Prefs", "Work", "Tools", "Utilities", "System", "Storage",
              "WBStartup", "Expansion", "Locale/Help", "Classes/Datatypes"):
        (base / d).mkdir(parents=True, exist_ok=True)
    return str(base)


def is_exe(path: str) -> bool: #vers 1
    """True for an Amiga hunk executable (m68k)."""
    try:
        with open(path, "rb") as f:
            return f.read(4) == b"\x00\x00\x03\xf3" and not path.lower().endswith(".info")
    except OSError:
        return False


# ---- machine profiles ----
HD_SLOTS = 12
PROFILE_DEFAULT = {"preset": "A500", "cpu": 0, "fast_mb": 0, "pal": True, "rom": "", "bootstrap": "", "df": ["", "", "", ""],
                   "hd": [""] * HD_SLOTS, "hdf_write": False, "hf_heads": 16, "hf_spt": 63, "boards_kb": [], "audio": True}


def profiles() -> dict:  #vers 2
    """All saved machine profiles {name: settings}; old hdf lists move to hd."""
    out = {}
    for k, v in _load().get("profiles", {}).items():
        p = {**PROFILE_DEFAULT, **v}
        old = v.get("hdf")
        if old and "hd" not in v:
            p["hd"] = (list(old) + [""] * HD_SLOTS)[:HD_SLOTS]
        p["hd"] = (list(p["hd"]) + [""] * HD_SLOTS)[:HD_SLOTS]
        p.pop("hdf", None)
        out[k] = p
    return out


def save_profile(name: str, profile: dict) -> None:  #vers 1
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    d = _load()
    d.setdefault("profiles", {})[name] = {k: profile[k] for k in PROFILE_DEFAULT if k in profile}
    CONFIG.write_text(json.dumps(d, indent=1), encoding="utf-8")


def delete_profile(name: str) -> None:  #vers 1
    d = _load()
    d.get("profiles", {}).pop(name, None)
    CONFIG.write_text(json.dumps(d, indent=1), encoding="utf-8")


def build_machine(profile: dict):  #vers 6
    """Create an Amiga from a profile; raises OSError or ValueError for bad files or settings."""
    import mmap
    from apps.hardware.amiga import Amiga
    from apps.hardware.zorro import RamBoard
    p = {**PROFILE_DEFAULT, **profile}
    m = Amiga(p["preset"], p["fast_mb"] * 1024, p["pal"], p["cpu"] or None)
    for kb in p["boards_kb"]:
        m.add_board(RamBoard(int(kb), 3 if m.cpu.model >= 68030 else 2))
    if p["bootstrap"]:
        if p["preset"] != "A1000":
            raise ValueError("a boot ROM is only supported on the A1000")
        with open(p["bootstrap"], "rb") as f:
            m.load_bootstrap(f.read())
        if p["rom"] and not p["df"][0]:
            from apps.methods import kickstart_disk
            with open(p["rom"], "rb") as f:
                m.insert_disk(kickstart_disk.build_image(f.read()), 0, True)
        m.boot()
    elif p["rom"]:
        with open(p["rom"], "rb") as f:
            m.load_rom(f.read())
        m.boot()
    for unit, path in enumerate(p["df"]):
        if path:
            with open(path, "rb") as f:
                m.insert_disk(f.read(), unit, True)
    for unit, path in enumerate(p["hd"]):
        if not path:
            continue
        scsi = unit > 1
        if m.akiko is not None or m.dmac is not None:
            from apps.hardware import cdimage
            if not os.path.isdir(path) and cdimage.is_cd_image(path):
                m.insert_cd(cdimage.CDImage(path))
                continue
        if scsi and m.sdmac is None:
            raise ValueError("SCSI drives (slots 2-8) need an A3000")
        if not scsi and m.ide is None:
            raise ValueError("IDE drives (slots 0-1) need an A600, A1200 or A4000")
        from apps.hardware import cdimage
        if not os.path.isdir(path) and cdimage.is_cd_image(path):
            from apps.hardware.scsicd import SCSICD
            cd = SCSICD(cdimage.CDImage(path))
            if scsi:
                m.attach_scsi(unit - 2, cd)
            else:
                from apps.hardware.atapi import ATAPIDrive
                m.attach_drive(ATAPIDrive(cd), unit)
            continue
        if os.path.isdir(path):
            from apps.methods import folder_disk
            image = folder_disk.build_image(path, f"DH{unit}", -unit)
        else:
            f = open(path, "r+b" if p["hdf_write"] else "rb")
            image = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_WRITE if p["hdf_write"] else mmap.ACCESS_COPY)
            from apps.methods import hardfile
            if not hardfile.has_rdb(image):
                image = hardfile.HardfileImage(image, p["hf_heads"], p["hf_spt"], f"DH{unit}")
        if scsi:
            from apps.hardware.scsi import SCSIDisk
            m.attach_scsi(unit - 2, SCSIDisk(image))
        else:
            m.attach_disk(image, unit)
    return m
