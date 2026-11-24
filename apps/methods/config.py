#this belongs in apps/methods/config.py - Version: 28
# X-Seti - November 17 2026 - Morosa - Morosa Subsystem.

"""
Morosa Subsystem - AmiSys: folder handling and hunk executable check for the Morosa libraries.
"""

##Methods list -
# amisys_dir
# roms_dir
# configs_dir
# ensure_amisys
# is_exe
# last_dir
# set_amisys
# set_roms_dir
# set_last_dir
# build_machine
# delete_profile
# export_profile
# import_profile
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


def roms_dir() -> str: #vers 1
    """Host folder scanned for Kickstart ROMs; ~/Roms/Amiga by default."""
    return _load().get("roms") or str(Path.home() / "Roms" / "Amiga")


def set_roms_dir(path: str): #vers 1
    """Choose the folder scanned for Kickstart ROMs."""
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    d = _load()
    d["roms"] = path
    CONFIG.write_text(json.dumps(d, indent=1), encoding="utf-8")


def crash_log() -> bool:  #vers 1
    """True when crash.log writing is on; on by default."""
    return bool(_load().get("crash_log", True))


def set_crash_log(on: bool) -> None:  #vers 1
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    d = _load()
    d["crash_log"] = bool(on)
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
PROFILE_DEFAULT = {"preset": "A500", "cpu": 0, "cpu_name": "", "fast_mb": 0, "pal": True, "rom": "", "ext_rom": "", "xfer": "", "cart": "None", "rtc": False, "bootstrap": "", "df": ["", "", "", ""],
                   "hd": [""] * HD_SLOTS, "hd_pri": [-i for i in range(HD_SLOTS)], "hd_ss": [""] * HD_SLOTS, "hdf_write": False, "addr24": False, "fpu": 3, "clx": 3, "rtg": False, "rtg_mb": 4, "rctrl": False, "blit": 0, "snd_filter": 0, "snd_sep": 100, "mhz": 0, "chipset": "", "c2p": True, "chip_kb": 0, "snd_ch": 4, "snd_bits": 8, "snd_rate": 44100, "snd_out": "qt", "slow_kb": 0, "pause_unfocus": False, "df_write": [False] * 4, "vkeyboard": False, "z2_kb": 0, "z3_kb": 0, "proc_kb": 0, "port0": "mouse", "port1": "joy", "disp_line": 0, "disp_filter": 0, "disp_aspect": 0, "disp_scale": 0, "swapper": [], "hf_heads": 16, "hf_spt": 63, "boards_kb": [], "audio": True, "status": True, "trim": False,
                   "joykeys": {"up": 16777235, "down": 16777237, "left": 16777234, "right": 16777236, "fire": 16777249, "fire2": 16777251}}


def configs_dir() -> Path:  #vers 1
    """Folder inside Morosa that holds exported configs."""
    d = ROOT / "configs"
    d.mkdir(exist_ok=True)
    return d


def export_profile(name: str) -> Path:  #vers 1
    """Write one saved profile to configs/<name>.json."""
    p = profiles()[name]
    path = configs_dir() / (name.replace("/", "_") + ".json")
    path.write_text(json.dumps({"name": name, "profile": {k: p[k] for k in PROFILE_DEFAULT if k in p}}, indent=1), encoding="utf-8")
    return path


def import_profile(path: str) -> str:  #vers 1
    """Load an exported config as a new profile; a taken name gets a number. Returns the name."""
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    prof = d.get("profile") if isinstance(d, dict) and "profile" in d else d
    if not isinstance(prof, dict):
        raise ValueError("Not a Morosa config file")
    name = str(d.get("name") or Path(path).stem) if isinstance(d, dict) else Path(path).stem
    have = profiles()
    new, n = name, 2
    while new in have:
        new, n = f"{name} ({n})", n + 1
    save_profile(new, {**PROFILE_DEFAULT, **prof})
    return new


def last_dir(kind: str) -> str:  #vers 1
    """Folder last used to browse for kind (rom, adf, hdf, ...)."""
    d = _load().get("dirs", {}).get(kind, "")
    return d if os.path.isdir(d) else ""


def set_last_dir(kind: str, path: str) -> None:  #vers 1
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    d = _load()
    d.setdefault("dirs", {})[kind] = path
    CONFIG.write_text(json.dumps(d, indent=1), encoding="utf-8")


def profiles() -> dict:  #vers 3
    """All saved machine profiles {name: settings}; old hdf lists move to hd."""
    out = {}
    for k, v in _load().get("profiles", {}).items():
        p = {**PROFILE_DEFAULT, **v}
        old = v.get("hdf")
        if old and "hd" not in v:
            p["hd"] = (list(old) + [""] * HD_SLOTS)[:HD_SLOTS]
        p["hd"] = (list(p["hd"]) + [""] * HD_SLOTS)[:HD_SLOTS]
        if "hd_pri" not in v:
            old = list(v.get("hd_boot", [])) + [False] * HD_SLOTS
            p["hd_pri"] = [0 if old[i] else -i for i in range(HD_SLOTS)]
        p["hd_pri"] = ([int(x) for x in p["hd_pri"]] + [-i for i in range(HD_SLOTS)])[:HD_SLOTS]
        p["hd_ss"] = (list(p.get("hd_ss", [])) + [""] * HD_SLOTS)[:HD_SLOTS]
        p.pop("hd_boot", None)
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


def build_machine(profile: dict):  #vers 24
    """Create an Amiga from a profile; raises OSError or ValueError for bad files or settings."""
    import mmap
    from apps.hardware.amiga import Amiga
    from apps.hardware.zorro import RamBoard
    p = {**PROFILE_DEFAULT, **profile}
    fast_kb = p["fast_mb"] * 1024
    if p["preset"] == "CD32" and p["cart"] not in ("SX-1", "SX-32", "TF328/TF330/TF360"):
        fast_kb = 0
    chip_kb = 0 if p["preset"] in ("A3000", "A1200", "A4000", "A4000D", "A4000T", "CD32") else p.get("chip_kb", 0)
    board_fast = p["preset"] in ("A1200", "CD32") and fast_kb > 0
    m = Amiga(p["preset"], 0 if board_fast else fast_kb, p["pal"], p["cpu"] or None, p.get("addr24", False) or (not p["cpu"] and p["preset"] in ("A1200", "CD32")), p.get("mhz", 0), p.get("chipset", ""), chip_kb, (p["snd_ch"], p["snd_bits"], p["snd_rate"]), p["slow_kb"], (p["port0"], p["port1"]), p["proc_kb"], (0, 1, 1, 2)[p.get("fpu", 3)], p.get("clx", 3))
    if m.akiko:
        m.akiko.c2p_on = p["c2p"]
    m.blitter.mode = p.get("blit", 0)
    m.paula.filter_mode, m.paula.sep = p.get("snd_filter", 0), p.get("snd_sep", 100)
    m.paula.led = lambda: bool(m.ciaa.ddra & 2) and not m.ciaa.pra & 2
    if board_fast:
        z3 = fast_kb > 8192 and m.cpu.model >= 68030
        kb = fast_kb if z3 else max(k for k in (64, 128, 256, 512, 1024, 2048, 4096, 8192) if k <= min(fast_kb, 8192))
        m.add_board(RamBoard(kb, 3 if z3 else 2))
    if p["z2_kb"]:
        m.add_board(RamBoard(int(p["z2_kb"]), 2))
    if p["z3_kb"]:
        if m.cpu.model < 68030:
            raise ValueError("Zorro III RAM needs a 68030 or better")
        m.add_board(RamBoard(int(p["z3_kb"]), 3))
    for kb in p["boards_kb"]:
        m.add_board(RamBoard(int(kb), 3 if m.cpu.model >= 68030 else 2))
    if p.get("rtg"):
        if m.cpu.model < 68030:
            raise ValueError("Picasso IV is Zorro III and needs a 68030 or better")
        from apps.hardware.picasso import PicassoIV
        m.add_board(PicassoIV(p.get("rtg_mb", 4), (lambda s: open("morosa_rtglog.txt", "a").write(s + "\n")) if os.environ.get("MOROSA_RTGLOG") else None))
    if p.get("rtc") and p["preset"] == "A1200" and m.rtc is None:
        m.add_rtc()
    if p["ext_rom"]:
        with open(p["ext_rom"], "rb") as f:
            m.load_ext(f.read(), 0xF00000 if p["preset"] == "CDTV" else 0xE00000)
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
                m.insert_disk(f.read(), unit, not p["df_write"][unit], path)
    if p["xfer"]:
        if not os.path.isdir(p["xfer"]):
            raise ValueError("Transfer folder not found: " + p["xfer"])
        from apps.hardware.hostfs import HostFS
        m.add_board(HostFS(p["xfer"], HD_SLOTS, -128, "Transfer", None, True, ""))
    for unit, path in enumerate(p["hd"]):
        if not path:
            continue
        scsi = unit > 1
        if os.path.isdir(path):
            from apps.hardware.hostfs import HostFS
            pri = p["hd_pri"][unit]
            m.add_board(HostFS(path, unit, pri if pri >= 0 else -128, "", None, bool(p["hdf_write"]), p["hd_ss"][unit]))
            continue
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
        f = open(path, "r+b" if p["hdf_write"] else "rb")
        image = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_WRITE if p["hdf_write"] else mmap.ACCESS_COPY)
        from apps.methods import hardfile
        if not hardfile.has_rdb(image):
            image = hardfile.HardfileImage(image, p["hf_heads"], p["hf_spt"], f"DH{unit}", 0, p["hd_pri"][unit])
        if scsi:
            from apps.hardware.scsi import SCSIDisk
            m.attach_scsi(unit - 2, SCSIDisk(image))
        else:
            m.attach_disk(image, unit)
    return m
