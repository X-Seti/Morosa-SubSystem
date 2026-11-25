#this belongs in apps/gui/settings.py - Version: 39
# X-Seti - November 17 2026 - Morosa - Settings Editor.

"""
Morosa Emulation - standalone editor for machine profiles and the AmiSys folder; runs a profile in a screen window.
"""

##Methods list -
# KeyButton
# KeyButton.keyPressEvent
# KeyButton.mousePressEvent
# main
# SettingsWindow
# SettingsWindow._browse
# SettingsWindow._clone
# SettingsWindow._collect
# SettingsWindow._create_hdf
# SettingsWindow._delete
# SettingsWindow._export
# SettingsWindow._fill
# SettingsWindow._icon
# SettingsWindow._import
# SettingsWindow._info
# SettingsWindow._live
# SettingsWindow._new
# SettingsWindow._page_chipset
# SettingsWindow._page_cpu
# SettingsWindow._page_display
# SettingsWindow._hw_refresh
# SettingsWindow._page_hwinfo
# SettingsWindow._page_misc
# SettingsWindow._page_vkbd
# SettingsWindow._page_ports
# SettingsWindow._page_ram
# SettingsWindow._page_sound
# SettingsWindow._pause
# SettingsWindow._swap_add
# SettingsWindow._swap_insert
# SettingsWindow._swap_remove
# SettingsWindow._quick_apply
# SettingsWindow._quick_models
# SettingsWindow._pick
# SettingsWindow._reload
# SettingsWindow._responsive
# SettingsWindow._rom_info
# SettingsWindow._rom_pick
# SettingsWindow._rom_scan
# SettingsWindow._run
# SettingsWindow._save
# SettingsWindow._stop
# SettingsWindow.resizeEvent
# SettingsWindow._tab_drives
# SettingsWindow._tab_floppy
# SettingsWindow._tab_keys
# SettingsWindow._tab_machine
# SettingsWindow._tab_rom
# SettingsWindow._tb_cog
# SettingsWindow._tb_menu
# SettingsWindow._tb_settings

import os
import sys

from PyQt6.QtCore import QByteArray, QSize, Qt
from PyQt6.QtGui import QIcon, QKeySequence, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QInputDialog,
                             QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QRadioButton, QSlider, QSizeGrip, QSpinBox, QStackedWidget, QTabWidget, QToolButton,
                             QVBoxLayout, QWidget)

from apps.gui.settings_dialog import MorosaSettingsDialog
from apps.gui.settings_pages import page_icon, quick_configs, stub_group, stub_page
from apps.gui.titlebar import TitleBar
from apps.hardware.amiga import PRESETS
from apps.methods import config
from apps.methods.rom_scan import kickstart_label, scan_roms

CPUS = ["Preset", "68000", "68010", "68EC020", "68020", "68EC030", "68030", "68EC040", "68LC040", "68040", "68EC060", "68LC060", "68060"]
A1000_PORTS = ("<b>A1000 connectors</b><br>Video: RGB (DB23), composite (RCA), TV modulator<br>Audio: left and right (RCA)<br>"
               "Serial: RS-232 (DB25)<br>Parallel: Centronics (DB25)<br>External floppy: DB23<br>"
               "Keyboard: RJ10 (4 pin)<br>Expansion: 86-pin side port<br>No internal hard disk or clock.")
A500_PORTS = ("<b>A500 connectors</b><br>Video: RGB (DB23), monochrome (RCA)<br>Audio: left and right (RCA)<br>"
              "Serial: RS-232 (DB25)<br>Parallel: Centronics (DB25)<br>External floppy: DB23<br>"
              "Keyboard: built in<br>Expansion: 86-pin side port<br>Trapdoor: A501 RAM and clock")
A500P_PORTS = ("<b>A500+ connectors</b><br>Video: RGB (DB23), monochrome (RCA)<br>Audio: left and right (RCA)<br>"
               "Serial: RS-232 (DB25)<br>Parallel: Centronics (DB25)<br>External floppy: DB23<br>"
               "Keyboard: built in<br>Expansion: 86-pin side port<br>Trapdoor: RAM expansion<br>Built-in battery clock")
CDTV_PORTS = ("<b>CDTV connectors</b><br>Keyboard: 5-pin mini-DIN<br>Mouse: 4-pin mini-DIN<br>Serial: RS-232 (DB25)<br>"
              "Parallel: Centronics (DB25)<br>External floppy: DB23<br>MIDI in and out<br>Video slot<br>"
              "Expansion: 30-pin DMA slot, 80-pin diagnostic slot<br>Memory card slot (8 KB to 1 MB)<br>Built-in single-speed CD-ROM")
A2000_PORTS = ("<b>A2000 connectors</b><br>Video: RGB (DB23), monochrome (RCA)<br>Audio: left and right (RCA)<br>"
               "Serial: RS-232 (DB25)<br>Parallel: Centronics (DB25)<br>External floppy: DB23<br>"
               "Keyboard: 5-pin DIN<br>Slots: 5 Zorro II, CPU slot (86-pin), video slot, ISA slots for a bridgeboard<br>"
               "Bays: two 3.5 inch, one 5.25 inch<br>Built-in battery clock")
A600_PORTS = ("<b>A600 connectors</b><br>Video: RGB (DB23), composite (RCA), RF (RCA)<br>Audio: left and right (RCA)<br>"
              "Serial: RS-232 (DB25)<br>Parallel: Centronics (DB25)<br>External floppy: DB23<br>"
              "Game ports: two (DE9)<br>Keyboard: built in, 78 keys<br>Expansion: 80-pin trapdoor slot, PCMCIA type II<br>"
              "Internal: 2.5 inch IDE (44 pin)<br>No side expansion port")
A3000_PORTS = ("<b>A3000 connectors</b><br>Video: RGB (DB23), VGA (DB15) with built-in scan doubler<br>Audio: left and right (RCA)<br>"
               "Serial: RS-232 (DB25)<br>Parallel: Centronics (DB25)<br>External floppy: DB23<br>Game ports: two (DE9)<br>"
               "Keyboard: 5-pin DIN<br>SCSI: external DB25, internal 50 pin<br>"
               "Slots: 4 Zorro III, video slot, 2 ISA (bridgeboard), CPU slot (200 pin)<br>Motherboard RAM sockets (DIP and ZIP)<br>Built-in battery clock")
A1200_PORTS = ("<b>A1200 connectors</b><br>Video: RGB (DB23), composite (RCA), RF (RCA)<br>Audio: left and right (RCA)<br>"
               "Serial: RS-232 (DB25)<br>Parallel: Centronics (DB25)<br>External floppy: DB23<br>Game ports: two (DE9)<br>"
               "Keyboard: built in, 96 keys<br>Expansion: 150-pin trapdoor, PCMCIA type II, 22-pin clock port<br>"
               "Internal: 2.5 inch IDE (44 pin)")
CD32_PORTS = ("<b>CD32 connectors</b><br>Video: RF (RCA), composite (RCA), S-Video (mini-DIN)<br>Audio: left and right (RCA), headphone jack<br>"
              "Controller ports: two (DE9), on the left side<br>AUX: RS-232 (6-pin mini-DIN) for a keyboard<br>"
              "Expansion: 182-pin socket for the FMV cartridge, SX-1, SX-32<br>Built-in double-speed CD-ROM, 1 KB EEPROM for saves<br>"
              "No floppy drive, no internal IDE")
CD32_CARTS = {
    "None": {"cpus": ("Preset",), "ram": False, "floppy": False},
    "FMV module (MPEG, not emulated)": {"cpus": ("Preset",), "ram": False, "floppy": False},
    "SX-1": {"cpus": ("Preset",), "ram": True, "floppy": True},
    "SX-32": {"cpus": ("Preset", "68EC030", "68030"), "ram": True, "floppy": True},
    "TF328/TF330/TF360": {"cpus": ("Preset", "68EC030", "68030", "68EC060", "68LC060", "68060"), "ram": True, "floppy": False},
}
A4000_PORTS = ("<b>A4000 connectors</b><br>Video: RGB (DB23)<br>Audio: left and right (RCA)<br>Serial: RS-232 (DB25)<br>"
               "Parallel: Centronics (DB25)<br>External floppy: DB23<br>Game ports: two (DE9)<br>Keyboard: 6-pin mini-DIN<br>"
               "Internal: 3.5 inch IDE (40 pin)<br>Slots: 4 Zorro III, video slot, 3 ISA (bridgeboard), CPU slot (200 pin)<br>"
               "Bays: two front 3.5 inch, one front 5.25 inch, two internal 3.5 inch<br>Battery clock")
A4000T_PORTS = ("<b>A4000T connectors</b><br>Internal: SCSI (50 pin, Fast SCSI-2) and IDE (40 pin), the only Amiga with both<br>"
                "Slots: 5 Zorro III, 4 ISA, 2 video slots<br>Bays: five front 5.25 inch, one internal 5.25 inch<br>"
                "Floppy: 3.5 inch high density<br>Battery clock (lithium)")
# per model: cpus, chip KB, hidden controls, expansion name, slow RAM name, ports text, hard drive page
MODEL_RULES = {
    "A1000": {"cpus": ("Preset", "68000"), "chips": (0, 256, 512), "hide": ("slow", "z3", "proc", "rtg", "c2p", "addr24", "fpu"),
              "rom": "Kickstart 1.2 or 1.3, loaded from floppy with the boot ROM", "exp": "Expansion port", "slow": "Slow RAM", "ports": A1000_PORTS, "hd": False, "lock": ("chipset",),
              "tip": "A1000: 256 KB on board, 512 KB with the front RAM module."},
    "A500+": {"cpus": ("Preset", "68000", "68010"), "chips": (0, 512, 1024), "hide": ("z3", "proc", "rtg", "c2p", "addr24", "fpu"),
              "rom": "Kickstart 2.04 (v37.175)", "exp": "Side expansion port", "slow": "Trapdoor RAM", "ports": A500P_PORTS, "hd": True, "lock": ("chipset",),
              "tip": "A500+: 1 MB Chip RAM, ECS. Very early units had 512 KB."},
    "CDTV": {"cpus": ("Preset", "68000"), "chips": (0, 1024), "hide": ("slow", "z3", "proc", "rtg", "c2p", "addr24", "fpu"),
             "rom": "Kickstart 1.3 with the 256 KB CDTV extended ROM", "exp": "Expansion slot", "slow": "Slow RAM", "ports": CDTV_PORTS, "hd": True,
             "tip": "CDTV: 1 MB Chip RAM."},
    "A2000": {"cpus": ("Preset", "68000", "68010", "68EC020", "68020", "68030"), "chips": (0, 512, 1024, 2048), "hide": ("z3", "rtg", "c2p", "addr24"),
              "hd_units": range(2, 9), "rom": "Kickstart 1.2 or 1.3 (2.0 on later revisions)", "exp": "Zorro II slots", "slow": "Slow RAM (on board)", "ports": A2000_PORTS, "hd": True,
              "tip": "A2000: 512 KB to 1 MB Chip RAM, 2 MB with a later Agnus."},
    "A600": {"cpus": ("Preset", "68000", "68010"), "chips": (0, 1024, 2048), "hide": ("z3", "proc", "rtg", "c2p", "addr24", "fpu"), "lock": ("chipset",),
             "hd_units": range(0, 2), "rom": "Kickstart 2.05 (37.299, 37.300 or 37.350)", "exp": "Trapdoor and PCMCIA", "slow": "Trapdoor RAM", "ports": A600_PORTS, "hd": True,
             "tip": "A600: 1 MB Chip RAM, 2 MB with the trapdoor RAM as chip."},
    "A3000": {"cpus": ("Preset", "68030", "68040", "68060"), "chips": (0, 2048), "hide": ("slow", "c2p", "addr24"), "lock": ("chipset",), "fast": "Motherboard Fast RAM",
              "hd_units": range(2, 9), "rom": "512 KB Kickstart ROM, or SuperKickstart loaded from disk", "exp": "Zorro III slots", "slow": "Slow RAM", "ports": A3000_PORTS, "hd": True,
              "tip": "A3000: ECS, 2 MB Chip RAM."},
    "A1200": {"cpus": ("Preset", "68EC020", "68020", "68EC030", "68030", "68EC040", "68LC040", "68040", "68EC060", "68LC060", "68060"), "chips": (0, 2048),
              "hide": ("slow", "z3", "rtg", "c2p"), "lock": ("chipset",), "fast": "Trapdoor RAM", "hd_units": range(0, 2),
              "rom": "Kickstart 3.0 (early units) or 3.1", "exp": "Trapdoor and PCMCIA", "slow": "Slow RAM", "ports": A1200_PORTS, "hd": True,
              "tip": "A1200: AGA, 2 MB Chip RAM."},
    "CD32": {"cpus": ("Preset", "68EC020", "68EC030", "68030", "68EC060", "68LC060", "68060"), "chips": (0, 2048), "hide": ("slow", "z3", "rtg"), "lock": ("chipset",),
             "fast": "Expansion RAM", "hd_units": range(0, 2),
             "rom": "1 MB Kickstart 3.1 with CD32 firmware (or 512 KB Kickstart plus the extended ROM)", "exp": "Expansion socket", "slow": "Slow RAM", "ports": CD32_PORTS, "hd": True,
             "tip": "CD32: AGA, 2 MB Chip RAM."},
    "A4000": {"cpus": ("Preset", "68EC030", "68030", "68040", "68060"), "chips": (0, 2048), "hide": ("slow", "c2p", "addr24"), "lock": ("chipset",),
              "fast": "Motherboard Fast RAM", "hd_units": range(0, 2), "rom": "Kickstart 3.0 (512 KB), upgradable to 3.1", "exp": "Zorro III slots",
              "slow": "Slow RAM", "ports": A4000_PORTS, "hd": True, "tip": "A4000: AGA, 2 MB Chip RAM."},
    "A4000T": {"cpus": ("Preset", "68040", "68060"), "chips": (0, 2048), "hide": ("slow", "c2p", "addr24"), "lock": ("chipset",),
               "fast": "Motherboard Fast RAM", "hd_units": range(0, 9), "rom": "Kickstart 3.1", "exp": "Zorro III slots",
               "slow": "Slow RAM", "ports": A4000T_PORTS, "hd": True, "tip": "A4000T: AGA, 2 MB Chip RAM."},
    "A500": {"cpus": ("Preset", "68000", "68010"), "chips": (0, 512, 1024), "hide": ("z3", "proc", "rtg", "c2p", "addr24", "fpu"),
             "rom": "Kickstart 1.2 or 1.3", "exp": "Side expansion port", "slow": "Trapdoor RAM (A501)", "ports": A500_PORTS, "hd": True,
             "tip": "A500: 512 KB, 1 MB with a Fat Agnus."},
}
DEFAULT_CPU = {"A1200": "68EC020", "CD32": "68EC020"}
FIXED_CHIP = ("A3000", "A1200", "A4000", "A4000D", "A4000T", "CD32")
CPU_VARIANT = {"68EC020": (True, None), "68EC030": (False, None), "68EC040": (False, 0), "68LC040": (False, 0), "68EC060": (False, 0), "68LC060": (False, 0)}  # 24-bit, fpu


def cpu_number(name: str) -> int:  #vers 1
    """CPU model number from a name such as 68EC020."""
    return int(name.replace("EC", "").replace("LC", ""))
JOY_ACTIONS = (("up", "Joystick up"), ("down", "Joystick down"), ("left", "Joystick left"), ("right", "Joystick right"),
               ("fire", "Fire"), ("fire2", "Second fire"))


class KeyButton(QPushButton):
    """Click, then press the key to assign; Escape clears."""

    def __init__(self, key: int = 0):  #vers 1
        super().__init__()
        self.key = key
        self._show()

    def _show(self) -> None:  #vers 1
        self.setText(QKeySequence(self.key).toString() if self.key else "(none)")

    def mousePressEvent(self, e) -> None:  #vers 1
        self.setText("Press a key...")
        self.setFocus()
        super().mousePressEvent(e)

    def keyPressEvent(self, e) -> None:  #vers 1
        if e.isAutoRepeat():
            return
        self.key = 0 if e.key() == Qt.Key.Key_Escape else e.key()
        self._show()


class SettingsWindow(QMainWindow):
    """Profile list on the left, settings form on the right."""

    SPEEDS = (0, 7, 14, 25, 50)

    def __init__(self):  #vers 5
        super().__init__()
        self.setWindowTitle("Morosa Emulation")
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.screens = []
        self.profiles = {}
        self.list = QListWidget()
        self.list.currentTextChanged.connect(self._fill)
        self.preset = QComboBox()
        self.preset.addItems(list(PRESETS))
        self.cpu = QComboBox()
        self.cpu.addItems(CPUS)
        self.cpu.currentTextChanged.connect(self._cpu_variant)
        self.fast = QSpinBox()
        self.fast.setRange(0, 1024)
        self.fast.setSuffix(" MB")
        self.clx = [QRadioButton(t) for t in ("None", "Sprites only", "Sprites and sprites vs. playfield", "Full")]
        self.clx[3].setChecked(True)
        self.fpu = [QRadioButton(t) for t in ("None", "68881", "68882", "CPU internal")]
        self.fpu[3].setChecked(True)
        self.addr24 = QCheckBox("24-bit Addressing")
        self.speed = QComboBox()
        self.speed.addItems(["Preset", "7 MHz", "14 MHz", "25 MHz", "50 MHz"])
        self.snd_out, self.snd_rate, self.snd_bits, self.snd_ch = QComboBox(), QComboBox(), QComboBox(), QComboBox()
        self.snd_out.addItems(["Qt default", "PipeWire"])
        self.snd_rate.addItems(["22050", "44100", "48000", "96000"])
        self.snd_rate.setCurrentText("44100")
        self.snd_bits.addItems(["8 bit", "16 bit", "24 bit", "32 bit"])
        self.snd_ch.addItems(["4", "8", "16"])
        self.disp_line, self.disp_filter, self.disp_aspect = QComboBox(), QComboBox(), QComboBox()
        self.disp_line.addItems(["Single", "Scanlines"])
        self.disp_filter.addItems(["Nearest", "Smooth"])
        self.disp_aspect.addItems(["Fill window", "4:3", "16:9"])
        self.disp_scale = QComboBox()
        self.disp_scale.addItems(["Fit window", "x2", "x3", "x4"])
        self.disp_scale.setToolTip("x1 is one Amiga low-res pixel; window resizes to fit")
        self.slow = QComboBox()
        self.slow.addItems(["None", "512 KB", "1 MB", "1.8 MB"])
        self.pause_unfocus = QCheckBox("Pause when the Amiga window loses focus")
        self.rctrl = QCheckBox("Right Ctrl = Amiga key")
        self.rtg = QCheckBox("RTG: Picasso IV (Zorro III, 4 MB)")
        self.blit = [QRadioButton(t) for t in ("Normal", "Immediate", "Wait for blitter")]
        self.blit[1].setChecked(True)
        self.blit[0].setToolTip("Busy flag and interrupt follow the estimated blit time")
        self.blit[2].setEnabled(False)
        self.snd_filter = QComboBox()
        self.snd_filter.addItems(["Off", "A500", "A1200"])
        self.snd_sep = QSlider(Qt.Orientation.Horizontal)
        self.snd_sep.setRange(0, 100)
        self.snd_sep.setValue(100)
        self.hwinfo = QLabel("")
        self.port0, self.port1 = QComboBox(), QComboBox()
        self.port0.addItems(["Mouse", "Joystick", "None"])
        self.port1.addItems(["Mouse", "Joystick", "None"])
        self.port1.setCurrentIndex(1)
        self.z2, self.z3, self.proc = QComboBox(), QComboBox(), QComboBox()
        self.z2.addItems(["None", "512 KB", "1 MB", "2 MB", "4 MB", "8 MB"])
        self.z3.addItems(["None", "16 MB", "32 MB", "64 MB", "128 MB", "256 MB", "512 MB", "1 GB"])
        self.proc.addItems(["None", "4 MB", "8 MB", "16 MB", "32 MB", "64 MB", "128 MB", "256 MB"])
        self.vkbd = QCheckBox("Show the virtual keyboard when the machine starts")
        self.chip = QComboBox()
        self.chip.addItems(["Preset", "256 KB", "512 KB", "1 MB", "2 MB"])
        self.c2p = QCheckBox("Chunky to planar")
        self.c2p.setChecked(True)
        self.chipset = QComboBox()
        self.chipset.addItems(["Preset", "OCS", "ECS"])
        self.pal = QComboBox()
        self.pal.addItems(["PAL", "NTSC"])
        self.boards = QLineEdit()
        self.boards.setPlaceholderText("KB, comma separated, e.g. 8192,16384")
        self.audio = QCheckBox("Audio output")
        self.trim = QCheckBox("Auto trim to workspace")
        self.status = QCheckBox("Activity status and FPS")
        self.status.setChecked(True)
        self.hf_heads, self.hf_spt = QSpinBox(), QSpinBox()
        self.hf_heads.setRange(1, 16)
        self.hf_spt.setRange(1, 255)
        self.hdf_write = QCheckBox("Allow writes to hard drives (images and folders)")
        self.rom = QLineEdit()
        self.ext_rom = QLineEdit()
        self.xfer = QLineEdit()
        self.bootstrap = QLineEdit()
        self.bootstrap.setPlaceholderText("A1000 only; Kickstart ROM below is loaded from a built disk")
        self.rom_info = QLabel("")
        self.rom.textChanged.connect(self._rom_info)
        self.df = [QLineEdit() for _ in range(4)]
        self.dfwp = [QCheckBox("Write-protected") for _ in range(4)]
        for c in self.dfwp:
            c.setChecked(True)
            c.setToolTip("Untick to let the Amiga write back to the ADF file")
        self.hd = [QLineEdit() for _ in range(config.HD_SLOTS)]
        self.hd_ss = [QLineEdit() for _ in range(config.HD_SLOTS)]
        self.hd_pri = [QSpinBox() for _ in range(config.HD_SLOTS)]
        for sp in self.hd_pri:
            sp.setRange(-128, 127)
            sp.setPrefix("Boot Pri ")
            sp.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
            sp.setFixedWidth(80)
        self.amisys = QLineEdit(config.amisys_dir())
        self.roms = QLineEdit(config.roms_dir())
        self.roms.editingFinished.connect(lambda: (config.set_roms_dir(self.roms.text()), self._rom_scan()))
        self.romlist = QListWidget()
        col = self.palette().buttonText().color().name()
        self.pages = QStackedWidget()
        self.nav = QListWidget()
        self.nav.setIconSize(QSize(22, 22))
        for name, kind, w in (("Quickstart", "quick", self._tab_machine()), ("CPU and FPU", "cpu", self._page_cpu()),
                              ("Chipset", "chip", self._page_chipset()), ("ROM", "rom", self._tab_rom()), ("RAM", "ram", self._page_ram()),
                              ("Floppy drives", "floppy", self._tab_floppy()), ("Hard drives/CD", "drive", self._tab_drives()),
                              ("Expansions", "slot", self._page_expansions()),
                              ("Display", "display", self._page_display()),
                              ("Sound", "sound", self._page_sound()), ("Input", "input", self._tab_keys()),
                              ("IO Ports", "ports", self._page_ports()), ("Miscellaneous", "misc", self._page_misc()),
                              ("Savestates", "card", stub_page((("Slots", (("radio", "Slot 0"), ("radio", "Slot 1"))),))),
                              ("Virtual Keyboard", "input", self._page_vkbd())):
            self.pages.addWidget(w)
            it = QListWidgetItem(page_icon(kind, col), name)
            it.setData(Qt.ItemDataRole.UserRole, name)
            it.setToolTip(name)
            self.nav.addItem(it)
        self._model_labels(self.preset.currentText())
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)
        for sig in (self.preset.currentTextChanged, self.cpu.currentIndexChanged, self.chip.currentIndexChanged, self.chipset.currentIndexChanged,
                    self.fast.valueChanged, self.slow.currentIndexChanged, self.z2.currentIndexChanged, self.z3.currentIndexChanged,
                    self.proc.currentIndexChanged, self.addr24.toggled, self.speed.currentIndexChanged, self.pal.currentIndexChanged,
                    self.cart.currentIndexChanged):
            sig.connect(lambda *_a: self._hw_refresh())
        self._hw_refresh()
        self.nav.setCurrentRow(0)
        right = QVBoxLayout()
        right.addWidget(self.pages)
        body = QWidget()
        lay = QHBoxLayout(body)
        left = QVBoxLayout()
        bar = QHBoxLayout()
        bar.setSpacing(2)
        for kind, tip, fn in (("clone", "Clone config", self._clone), ("add", "Add config", self._new), ("del", "Delete config", self._delete),
                              ("import", "Import config", self._import), ("export", "Export config to configs folder", self._export)):
            b = QPushButton()
            b.setIcon(self._icon(kind))
            b.setIconSize(QSize(18, 18))
            b.setFixedSize(30, 28)
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, f=fn: f())
            bar.addWidget(b)
        bar.addStretch(1)
        left.addLayout(bar)
        left.addWidget(self.list)
        lay.addLayout(left, 2)
        lay.addWidget(self.nav, 2)
        lay.addLayout(right, 6)
        root = QWidget()
        col = QVBoxLayout(root)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        self.titlebar = TitleBar(self, self._tb_menu, self._tb_settings,
                                 lambda: self._browse(self.amisys, None, "dir"), self._tb_cog, self._run, self._pause, self._stop, self._save)
        col.addWidget(self.titlebar)
        col.addWidget(body, 1)
        col.addWidget(QSizeGrip(self), 0, Qt.AlignmentFlag.AlignRight)
        self.setCentralWidget(root)
        self._reload()
        self._responsive()

    def _responsive(self) -> None:  #vers 1
        """Narrow window: page list shows icons only."""
        narrow = self.width() < 900
        self.nav.setFixedWidth(48 if narrow else 170)
        for i in range(self.nav.count()):
            it = self.nav.item(i)
            it.setText("" if narrow else it.data(Qt.ItemDataRole.UserRole))

    def resizeEvent(self, e) -> None:  #vers 1
        super().resizeEvent(e)
        self._responsive()

    def _page_cpu(self) -> QWidget:  #vers 3
        w = QWidget()
        lo = QVBoxLayout(w)
        row = QHBoxLayout()
        row.addWidget(QLabel("CPU"))
        row.addWidget(self.cpu, 1)
        row.addWidget(QLabel("Speed"))
        self.speed.setToolTip("Preset: model default. Higher runs more CPU per chip cycle")
        row.addWidget(self.speed, 1)
        lo.addLayout(row)
        fg = QGroupBox("FPU")
        fl = QHBoxLayout(fg)
        for r in self.fpu:
            fl.addWidget(r)
        fl.addStretch(1)
        lo.addWidget(fg)
        opt = QGroupBox("CPU options")
        ol = QHBoxLayout(opt)
        self.addr24.setToolTip("68020 and up: limit to 24-bit address space, like the A1200 68EC020")
        ol.addWidget(self.addr24)
        for t in ("More compatible", "JIT"):
            c = QCheckBox(t)
            c.setEnabled(False)
            c.setToolTip("Interpreter core only" if t == "JIT" else "Not emulated yet")
            ol.addWidget(c)
        ol.addStretch(1)
        lo.addWidget(opt)
        lo.addStretch(1)
        return w

    def _page_chipset(self) -> QWidget:  #vers 3
        w = QWidget()
        grid = QGridLayout(w)
        cg = QGroupBox("Chipset")
        cl = QFormLayout(cg)
        self.chipset.setToolTip("Model default, or swap the chips on models that allowed it")
        cl.addRow(self.chipset)
        grid.addWidget(cg, 0, 0)
        bg = QGroupBox("Blitter")
        bl = QVBoxLayout(bg)
        for r in self.blit:
            bl.addWidget(r)
        grid.addWidget(bg, 0, 1)
        cg = QGroupBox("Collision level")
        cl = QVBoxLayout(cg)
        for r in self.clx:
            cl.addWidget(r)
        grid.addWidget(cg, 1, 0)
        cp = QGroupBox("Copper")
        pl = QVBoxLayout(cp)
        pl.addWidget(stub_group("", (("check", "Fast copper"),)))
        self.c2p.setToolTip("CD32 Akiko chunky to planar converter")
        pl.addWidget(self.c2p)
        pl.addWidget(stub_group("", (("check", "Planar to chunky"),)))
        grid.addWidget(cp, 1, 1)
        grid.setRowStretch(2, 1)
        return w

    def _page_ram(self) -> QWidget:  #vers 4
        w = QWidget()
        grid = QGridLayout(w)
        mg = QGroupBox("Memory")
        form = QFormLayout(mg)
        form.addRow("Chip RAM", self.chip)
        form.addRow("Slow RAM", self.slow)
        form.addRow("Fast RAM", self.fast)
        form.addRow("Zorro RAM boards", self.boards)
        self.ram_form = form
        grid.addWidget(mg, 0, 0)
        og = QGroupBox("Expansion memory")
        ol = self.ram_exp_form = QFormLayout(og)
        ol.addRow("Z2 Fast", self.z2)
        ol.addRow("Z3 Fast", self.z3)
        ol.addRow("Processor slot Fast", self.proc)
        ol.addRow("", QLabel("Motherboard Fast is the Fast RAM box"))
        grid.addWidget(og, 0, 1)
        grid.setRowStretch(1, 1)
        return w

    def _page_display(self) -> QWidget:  #vers 2
        w = QWidget()
        grid = QGridLayout(w)
        sg = QGroupBox("Screen")
        sl = QFormLayout(sg)
        sl.addRow("Line mode", self.disp_line)
        sl.addRow("Filter", self.disp_filter)
        sl.addRow("Aspect", self.disp_aspect)
        sl.addRow("Upscale", self.disp_scale)
        for c in (self.disp_line, self.disp_filter, self.disp_aspect, self.disp_scale):
            c.currentIndexChanged.connect(self._apply_view)
        sl.addRow("", QLabel("Auto trim is in [Settings]"))
        grid.addWidget(sg, 0, 0)
        grid.addWidget(stub_group("Scan doubling", (("radio", "None"), ("radio", "DblPAL"), ("radio", "DblNTSC"), ("radio", "VGA only"))), 0, 1)
        grid.setRowStretch(1, 1)
        return w

    def _page_sound(self) -> QWidget:  #vers 2
        w = QWidget()
        grid = QGridLayout(w)
        og = QGroupBox("Output")
        ol = QFormLayout(og)
        self.snd_out.setToolTip("PipeWire sends audio straight to pw-cat")
        ol.addRow("Output", self.snd_out)
        ol.addRow("Sample rate", self.snd_rate)
        ol.addRow("", QLabel("Audio on/off is in [Settings]"))
        grid.addWidget(og, 0, 0)
        pg = QGroupBox("Paula Plus")
        pl = QFormLayout(pg)
        self.snd_bits.setToolTip("Highest sample depth the Amiga can select")
        self.snd_ch.setToolTip("8 and 16 channels add registers at $DFF400")
        pl.addRow("Sample depth", self.snd_bits)
        pl.addRow("Channels", self.snd_ch)
        grid.addWidget(pg, 0, 1)
        fg = QGroupBox("Filter")
        fl = QFormLayout(fg)
        self.snd_filter.setToolTip("A500: fixed filter plus LED filter. A1200: LED filter only")
        self.snd_sep.setToolTip("100 is Amiga hard pan, 0 is mono")
        fl.addRow("Filter", self.snd_filter)
        fl.addRow("Stereo separation", self.snd_sep)
        grid.addWidget(fg, 1, 0)
        grid.setRowStretch(2, 1)
        return w

    def _page_ports(self) -> QWidget:  #vers 2
        w = QWidget()
        grid = QGridLayout(w)
        pg = QGroupBox("Game ports")
        pl = QFormLayout(pg)
        self.port0.setToolTip("Port 1, the mouse port")
        self.port1.setToolTip("Port 2, the joystick port")
        pl.addRow("Port 1", self.port0)
        pl.addRow("Port 2", self.port1)
        grid.addWidget(pg, 0, 0)
        grid.addWidget(stub_group("Parallel and serial", (("combo", "Parallel", ["None"]), ("combo", "Serial", ["None"]), ("check", "USB devices"))), 0, 1)
        self.port_info = QLabel()
        self.port_info.setTextFormat(Qt.TextFormat.RichText)
        self.port_info.setWordWrap(True)
        grid.addWidget(self.port_info, 1, 0, 1, 2)
        grid.setRowStretch(2, 1)
        return w

    def _page_vkbd(self) -> QWidget:  #vers 1
        w = QWidget()
        lo = QVBoxLayout(w)
        g = QGroupBox("Virtual keyboard")
        gl = QVBoxLayout(g)
        gl.addWidget(self.vkbd)
        gl.addWidget(QLabel("Scroll Lock shows or hides it in the Amiga window. Modifier keys stay down until clicked again."))
        lo.addWidget(g)
        lo.addStretch(1)
        return w

    def _crash_log(self, on: bool) -> None:  #vers 1
        """Save the crash.log option and apply it now."""
        from apps.methods import crashlog
        config.set_crash_log(on)
        crashlog.apply()

    def _page_misc(self) -> QWidget:  #vers 2
        w = QWidget()
        grid = QGridLayout(w)
        og = QGroupBox("Options")
        ol = QVBoxLayout(og)
        ol.addWidget(self.pause_unfocus)
        ol.addWidget(self.rctrl)
        self.crash = QCheckBox("Write crash.log when Morosa crashes")
        self.crash.setToolTip("crash.log is saved in the Morosa folder.")
        self.crash.setChecked(config.crash_log())
        self.crash.toggled.connect(self._crash_log)
        ol.addWidget(self.crash)
        ol.addWidget(stub_group("", (("check", "Show GUI on startup"),)))
        grid.addWidget(og, 0, 0)
        grid.addWidget(stub_group("Priority", (("combo", "Running", ["Normal", "High"]), ("combo", "Paused", ["Normal", "Low"]))), 0, 1)
        grid.setRowStretch(1, 1)
        return w

    def _page_expansions(self) -> QWidget:  #vers 1
        w = QWidget()
        lo = QVBoxLayout(w)
        g = QGroupBox("Fitted boards")
        gl = QVBoxLayout(g)
        self.exp_info = QLabel()
        self.exp_info.setTextFormat(Qt.TextFormat.RichText)
        gl.addWidget(self.exp_info)
        lo.addWidget(g)
        zg = self.zorro_box = QGroupBox("Zorro cards")
        zl = QFormLayout(zg)
        self.rtg.setToolTip("Zorro III graphics board with 4 MB; needs a 68030 or better and a Picasso96 driver in the guest")
        zl.addRow(self.rtg)
        zl.addRow(stub_group("", (("check", "Ethernet"),)))
        lo.addWidget(zg)
        self.cart_box = QGroupBox("CD32 cartridge")
        cl = QFormLayout(self.cart_box)
        self.cart = QComboBox()
        self.cart.addItems(list(CD32_CARTS))
        self.cart.setToolTip("Expansion socket: SX-1 and SX-32 add floppy, IDE, keyboard and RAM; SX-32 and TF add a faster CPU.")
        self.cart.currentTextChanged.connect(lambda _t: self._model_labels(self.preset.currentText()))
        cl.addRow("Cartridge", self.cart)
        lo.addWidget(self.cart_box)
        self.rtc = QCheckBox("Clock module (trapdoor)")
        self.rtc.setToolTip("Battery clock on the trapdoor connector; the stock A1200 has none.")
        lo.addWidget(self.rtc)
        lo.addStretch(1)
        return w

    def _page_hwinfo(self) -> QWidget:  #vers 2
        g = QGroupBox("This configuration")
        gl = QVBoxLayout(g)
        self.hwinfo.setTextFormat(Qt.TextFormat.RichText)
        gl.addWidget(self.hwinfo)
        return g

    def _hw_refresh(self) -> None:  #vers 1
        """Read-only summary of the settings in the form."""
        model = self.preset.currentText()
        chip = PRESETS[model][2] if model in PRESETS else 0
        chip = (0, 256, 512, 1024, 2048)[self.chip.currentIndex()] or chip
        chipset = ("preset", "OCS", "ECS")[self.chipset.currentIndex()]
        rows = (("Model", model), ("CPU", (str(DEFAULT_CPU.get(model, PRESETS[model][0])) if self.cpu.currentIndex() == 0 and model in PRESETS else self.cpu.currentText()) + (", 24-bit" if self.addr24.isChecked() else "") + f", {self.speed.currentText()}"),
                ("Chipset", chipset if chipset != "preset" else PRESETS.get(model, (0, "", 0))[1].upper()), ("Video", self.pal.currentText()),
                ("Chip RAM", f"{chip} KB"), ("Slow RAM", self.slow.currentText()), ("Fast RAM", f"{self.fast.value()} MB"),
                ("Kickstart", os.path.basename(self.rom.text()) or "none"),
                ("Floppies", ", ".join(f"DF{i}" for i, e in enumerate(self.df) if e.text()) or "none"),
                ("Hard drives", ", ".join(f"{i}" for i, e in enumerate(self.hd) if e.text()) or "none"),
                ("Sound", f"{self.snd_ch.currentText()} ch, {self.snd_bits.currentText()}, {self.snd_rate.currentText()} Hz"))
        boards = [("Zorro II RAM", self.z2.currentText()), ("Zorro III RAM", self.z3.currentText()), ("Processor slot RAM", self.proc.currentText())]
        boards += [("Picasso IV RTG", "4 MB")] if self.rtg.isChecked() else []
        boards += [("Extra RAM board", f"{k} KB") for k in self.boards.text().split(",") if k.strip().isdigit()]
        boards = [b for b in boards if not b[1].startswith(("None", "0", "Off"))]
        self.exp_info.setText("<table cellpadding=3>" + "".join(f"<tr><td><b>{k}</b></td><td>{v}</td></tr>" for k, v in boards) + "</table>" if boards else "No boards fitted. RAM boards are set on the RAM page.")
        self.hwinfo.setText("<table cellpadding=3>" + "".join(f"<tr><td><b>{k}</b></td><td>{v}</td></tr>" for k, v in rows) + "</table>")

    def _tb_cog(self) -> None:  #vers 1
        """Cog button: open App Settings dialog."""
        from apps.utils.app_settings_system import AppSettings, SettingsDialog
        SettingsDialog(AppSettings(), self, self).exec()

    def _tb_menu(self, m) -> None:  #vers 1
        """Fill the title bar Menu drop-down."""
        for label, fn in (("Save", self._save), ("Run", self._run), ("Pause", self._pause), ("Stop", self._stop),
                          ("Import config", self._import), ("Export config", self._export), ("Quit", self.close)):
            m.addAction(label).triggered.connect(lambda _=False, f=fn: f())

    def _tb_settings(self) -> None:  #vers 2
        """Settings button: open Morosa's own settings dialog."""
        if getattr(self, "app_dlg", None) is None:
            self.app_dlg = MorosaSettingsDialog(self, self.trim, self.status, self.audio, self._pick(self.amisys, None), self._pick(self.roms, None))
        self.app_dlg.show()
        self.app_dlg.raise_()
        self.app_dlg.activateWindow()

    def _tab_machine(self) -> QWidget:  #vers 7
        w = QWidget()
        outer = QVBoxLayout(w)
        top = QWidget()
        form = QFormLayout(top)
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow("Model", self.preset)
        form.addRow("Video", self.pal)
        self.qconf = QComboBox()
        self.qconf.activated.connect(self._quick_apply)
        self.preset.currentTextChanged.connect(self._quick_models)
        form.addRow("Config", self.qconf)
        self.qdf = []
        for i in range(2):
            e = QLineEdit()
            e.setPlaceholderText("ADF")
            e.textChanged.connect(lambda t, i=i: self.df[i].text() != t and self.df[i].setText(t))
            self.df[i].textChanged.connect(lambda t, e=e: e.text() != t and e.setText(t))
            wp = QCheckBox("Write-protected")
            wp.setChecked(True)
            wp.toggled.connect(lambda on, i=i: self.dfwp[i].setChecked(on))
            self.dfwp[i].toggled.connect(lambda on, wp=wp: wp.setChecked(on))
            row = QWidget()
            lo = QHBoxLayout(row)
            lo.setContentsMargins(0, 0, 0, 0)
            lo.addWidget(self._pick(e, "ADF (*.adf *.ADF *)"))
            lo.addWidget(wp)
            form.addRow(f"DF{i}", row)
            self.qdf.append(e)
        self._quick_models(self.preset.currentText())
        outer.addWidget(top)
        outer.addWidget(self._page_hwinfo())
        outer.addStretch(1)
        return w

    def _model_labels(self, model: str) -> None:  #vers 5
        """Show only what the chosen model had; see MODEL_RULES."""
        r = MODEL_RULES.get({"A4000D": "A4000"}.get(model, model))
        if hasattr(self, "rtc") and hasattr(self, "nav") and self.nav.count() >= 12:
            self.rtc.setVisible(model == "A1200")
        if model == "CD32" and hasattr(self, "cart"):
            r = {**r, **CD32_CARTS[self.cart.currentText()]}
        if model in PRESETS:
            self.cpu.setItemText(0, f"{DEFAULT_CPU.get(model, PRESETS[model][0])} (model default)")
        exp = r["exp"] if r else "Expansions"
        if hasattr(self, "ram_form"):
            self.ram_form.labelForField(self.fast).setText(r.get("fast", f"{exp} RAM") if r else "Fast RAM")
            self.ram_form.labelForField(self.boards).setText(f"{exp} boards" if r else "Zorro RAM boards")
            self.ram_form.labelForField(self.slow).setText(r["slow"] if r else "Slow RAM")
            self.ram_form.setRowVisible(self.slow, not r or "slow" not in r["hide"])
            self.ram_form.setRowVisible(self.fast, not r or r.get("ram", True))
            self.ram_exp_form.setRowVisible(self.z3, not r or "z3" not in r["hide"])
            self.ram_exp_form.setRowVisible(self.proc, not r or "proc" not in r["hide"])
        if hasattr(self, "zorro_box"):
            self.zorro_box.setTitle(f"{exp} cards" if r else "Zorro cards")
        if hasattr(self, "nav"):
            for i in range(self.nav.count()):
                key = self.nav.item(i).data(Qt.ItemDataRole.UserRole)
                if key == "Expansions":
                    self.nav.item(i).setToolTip(exp)
                    if self.nav.item(i).text():
                        self.nav.item(i).setText(exp)
                elif key == "Hard drives/CD":
                    self.nav.item(i).setHidden(bool(r) and not r["hd"])
                elif key == "Floppy drives":
                    self.nav.item(i).setHidden(bool(r) and not r.get("floppy", True))
        if hasattr(self, "port_info"):
            self.port_info.setText(r["ports"] if r else "")
        if hasattr(self, "hd_rows") and hasattr(self, "nav") and self.nav.count() >= 12:
            units = r.get("hd_units", range(len(self.hd_rows))) if r else range(len(self.hd_rows))
            for i, row in enumerate(self.hd_rows):
                for w in row:
                    w.setVisible(i in units)
        if hasattr(self, "cart_box") and hasattr(self, "nav") and self.nav.count() >= 12:
            self.cart_box.setVisible(model == "CD32")
        if hasattr(self, "rom_form"):
            self.rom_form.setRowVisible(self.ext_rom_row, model in ("CDTV", "CD32"))
            self.rom_form.setRowVisible(self.boot_row, model in ("A1000", "A3000"))
        if hasattr(self, "rom_hint"):
            self.rom_hint.setText(f"Original ROM: {r['rom']}. Newer Kickstart ROMs also work." if r and "rom" in r else "")
        if hasattr(self, "nav") and self.nav.count() >= 12:
            for key, w in (("rtg", self.rtg), ("c2p", self.c2p), ("addr24", self.addr24)) + tuple(("fpu", f) for f in self.fpu):
                w.setVisible(not r or key not in r["hide"])
        if model in PRESETS:
            base = PRESETS[model][1].upper()
            self.chipset.setItemText(0, f"{base} (model default)")
            locked = bool(r) and "chipset" in r.get("lock", ())
            for i, name in enumerate(("", "OCS", "ECS")):
                self.chipset.model().item(i).setEnabled(i == 0 or (not locked and base != "AGA" and name != base))
            if not self.chipset.model().item(self.chipset.currentIndex()).isEnabled():
                self.chipset.setCurrentIndex(0)
            self.chipset.setEnabled(any(self.chipset.model().item(i).isEnabled() for i in (1, 2)))
        for i, name in enumerate(CPUS):
            self.cpu.model().item(i).setEnabled(not r or name in r["cpus"])
        if r and self.cpu.currentIndex() > 0 and self.cpu.currentText() not in r["cpus"]:
            self.cpu.setCurrentIndex(0)
        for i, kb in enumerate((0, 256, 512, 1024, 2048)):
            self.chip.model().item(i).setEnabled(not r or kb in r["chips"])
        if r and (0, 256, 512, 1024, 2048)[self.chip.currentIndex()] not in r["chips"]:
            self.chip.setCurrentIndex(0)

    def _quick_models(self, model: str) -> None:  #vers 2
        """Fill the Config list for the chosen model; fixed chip RAM models lock it."""
        if model not in PRESETS:
            return
        fixed = model in FIXED_CHIP
        if fixed:
            self.chip.setCurrentIndex(0)
        self.chip.setEnabled(not fixed)
        self._model_labels(model)
        self.chip.setToolTip(f"{model} has 2 MB Chip RAM. More RAM comes from the trapdoor or board slots (Fast RAM)." if fixed else MODEL_RULES.get(model, {}).get("tip", ""))
        self.qconf.clear()
        self.qconf.addItem("Custom", None)
        for label, cpu, fast in quick_configs(model, PRESETS[model][2]):
            self.qconf.addItem(label, (cpu, fast))

    def _cpu_variant(self, name: str) -> None:  #vers 3
        """EC and LC types set 24-bit and FPU; leaving one resets both."""
        name = name.split()[0] if name else name
        was, self._cpu_prev = getattr(self, "_cpu_prev", ""), name
        if name in CPU_VARIANT:
            a24, fpu = CPU_VARIANT[name]
            self.addr24.setChecked(a24)
            if fpu is not None:
                self.fpu[fpu].setChecked(True)
        elif was in CPU_VARIANT:
            self.addr24.setChecked(False)
            self.fpu[3].setChecked(True)

    def _quick_apply(self, idx: int) -> None:  #vers 1
        """Apply the chosen Config: CPU and Fast RAM."""
        v = self.qconf.itemData(idx)
        if v:
            self.cpu.setCurrentIndex(0 if not v[0] else CPUS.index(str(v[0])))
            self.fast.setValue(v[1])

    def _tab_rom(self) -> QWidget:  #vers 4
        w = QWidget()
        lo = QVBoxLayout(w)
        form = QFormLayout()
        self.boot_row = self._pick(self.bootstrap, "ROM (*.rom *.bin *)")
        form.addRow("Boot ROM", self.boot_row)
        form.addRow("Kickstart ROM", self._pick(self.rom, "ROM (*.rom *.bin *)", extra=self.rom_info))
        self.ext_rom_row = self._pick(self.ext_rom, "ROM (*.rom *.bin *)")
        form.addRow("Extended ROM", self.ext_rom_row)
        self.rom_form = form
        self.rom_hint = QLabel()
        self.rom_hint.setWordWrap(True)
        form.addRow("", self.rom_hint)
        lo.addLayout(form)
        bar = QHBoxLayout()
        self.rom_count = QLabel("")
        bar.addWidget(self.rom_count, 1)
        rs = QPushButton("Rescan")
        rs.setToolTip("Scan the ROMs folder set in [Settings] Paths")
        rs.clicked.connect(lambda _=False: self._rom_scan())
        bar.addWidget(rs)
        lo.addLayout(bar)
        self.romlist.itemClicked.connect(self._rom_pick)
        lo.addWidget(self.romlist, 1)
        self._rom_scan()
        return w

    def _rom_scan(self) -> None:  #vers 1
        """Fill the list with the Kickstart ROMs found in the ROMs folder."""
        self.romlist.clear()
        found = scan_roms(self.roms.text() or config.roms_dir())
        for path, label, kb in found:
            it = QListWidgetItem(f"{os.path.basename(path)}   -   {label}, {kb} KB")
            it.setData(Qt.ItemDataRole.UserRole, path)
            it.setToolTip(path)
            self.romlist.addItem(it)
        self.rom_count.setText(f"{len(found)} ROMs in {self.roms.text() or config.roms_dir()}")

    def _rom_pick(self, it) -> None:  #vers 1
        """Click a found ROM to use it as the Kickstart."""
        self.rom.setText(it.data(Qt.ItemDataRole.UserRole))

    def _tab_floppy(self) -> QWidget:  #vers 3
        w = QWidget()
        lo = QVBoxLayout(w)
        form = QFormLayout()
        for i, e in enumerate(self.df):
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.addWidget(self._pick(e, "ADF (*.adf *.ADF *)"), 1)
            kind = QComboBox()
            kind.addItems(['3.5" DD'])
            kind.setEnabled(False)
            rl.addWidget(kind)
            rl.addWidget(self.dfwp[i])
            form.addRow(f"DF{i}", row)
        lo.addLayout(form)
        sub = QTabWidget()
        sw = QWidget()
        sl = QHBoxLayout(sw)
        self.swap = QListWidget()
        self.swap.setToolTip("Double-click to insert into DF0")
        self.swap.itemDoubleClicked.connect(lambda _it: self._swap_insert(0))
        sl.addWidget(self.swap, 1)
        side = QVBoxLayout()
        for label, fn in (("Add", self._swap_add), ("Remove", self._swap_remove), ("Remove all", self.swap.clear)):
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, f=fn: f())
            side.addWidget(b)
        self.swap_unit = QComboBox()
        self.swap_unit.addItems([f"DF{i}" for i in range(4)])
        side.addWidget(self.swap_unit)
        ins = QPushButton("Insert")
        ins.clicked.connect(lambda _=False: self._swap_insert(self.swap_unit.currentIndex()))
        side.addWidget(ins)
        side.addStretch(1)
        sl.addLayout(side)
        sub.addTab(sw, "Disk swapper")
        sub.addTab(stub_page((("WHDLoad auto-config", (("combo", "Game name", []), ("combo", "Slave", []), ("check", "Button wait"),
                                                       ("check", "Show splash"), ("check", "Write cache"), ("check", "Quit on exit"))),)), "WHDLoad")
        lo.addWidget(sub, 1)
        return w

    def _swap_add(self) -> None:  #vers 1
        """Add ADF files to the disk swapper."""
        files, _ = QFileDialog.getOpenFileNames(self, "Add disks", config.last_dir("adf"), "ADF (*.adf *.ADF *)")
        for f in files:
            self.swap.addItem(f)
        if files:
            config.set_last_dir("adf", os.path.dirname(files[0]))

    def _swap_remove(self) -> None:  #vers 1
        for it in self.swap.selectedItems():
            self.swap.takeItem(self.swap.row(it))

    def _swap_insert(self, unit: int) -> None:  #vers 2
        """Put the selected disk in a drive; a running machine gets it at once."""
        it = self.swap.currentItem()
        if it is None:
            return
        self.df[unit].setText(it.text())
        w = self._live()
        if w is not None:
            try:
                with open(it.text(), "rb") as f:
                    w.m.drives[unit].flush()
                    w.m.insert_disk(f.read(), unit, self.dfwp[unit].isChecked(), it.text())
            except OSError as e:
                QMessageBox.warning(self, "Morosa Emulation", str(e))

    def _tab_keys(self) -> QWidget:  #vers 1
        w = QWidget()
        form = QFormLayout(w)
        self.joykeys = {}
        for act, label in JOY_ACTIONS:
            self.joykeys[act] = KeyButton(config.PROFILE_DEFAULT["joykeys"][act])
            form.addRow(label, self.joykeys[act])
        reset = QPushButton("Reset keys")
        reset.clicked.connect(lambda: [b.__setattr__("key", config.PROFILE_DEFAULT["joykeys"][a]) or b._show() for a, b in self.joykeys.items()])
        form.addRow("", reset)
        form.addRow("", QLabel("Keys also reach the Amiga keyboard. Escape clears a key."))
        return w

    def _tab_drives(self) -> QWidget:  #vers 3
        w = QWidget()
        lo = QVBoxLayout(w)
        grid = QGridLayout()
        grid.setVerticalSpacing(2)
        for c, t in ((0, "Slot"), (1, "Path"), (2, "Boot Pri"), (4, "Startup-Sequence (folders)")):
            grid.addWidget(QLabel(t), 0, c)
        self.hd_rows = []
        for i, e in enumerate(self.hd):
            tag = "IDE" if i < 2 else "SCSI"
            e.setPlaceholderText("HDF, folder, or CD image (iso, cue, bin)")
            self.hd_pri[i].setToolTip("Boot priority: below 0 does not boot, 0 and up boots. Folders and plain HDF files; HDF with RDB keep their own.")
            self.hd_pri[i].setPrefix("")
            self.hd_pri[i].setFixedWidth(50)
            name, pick = QLabel(f"{tag} {i}"), self._pick(e, "HDF (*.hdf *.HDF *)", True, None, True)
            grid.addWidget(name, i + 1, 0)
            grid.addWidget(pick, i + 1, 1)
            grid.addWidget(self.hd_pri[i], i + 1, 2)
            self.hd_ss[i].setPlaceholderText("Default: S/Startup-Sequence in the folder")
            self.hd_ss[i].setToolTip("Script shown to the Amiga as S:Startup-Sequence; the folder is not changed. Full path, or relative to the folder.")
            ss = self._pick(self.hd_ss[i], "All files (*)", False, None, False)
            grid.addWidget(ss, i + 1, 4)
            ic = QLabel()
            ic.setFixedSize(24, 24)
            grid.addWidget(ic, i + 1, 3)
            self.hd_rows.append((name, pick, self.hd_pri[i], ic, ss))
            self.hd_pri[i].valueChanged.connect(lambda v, l=ic: self._boot_icon(l, v))
            self._boot_icon(ic, self.hd_pri[i].value())
        grid.setColumnStretch(1, 1)
        lo.addLayout(grid)
        xf = QFormLayout()
        self.xfer.setPlaceholderText("Host folder shared with the Amiga as Transfer:")
        self.xfer.setToolTip("Always writable, never boots. Copy files in and out of the Amiga, for example ~/Downloads.")
        xf.addRow("Transfer folder", self._pick(self.xfer, None, False, None, False))
        lo.addLayout(xf)
        bar = QHBoxLayout()
        mk = QPushButton("Create hardfile")
        mk.clicked.connect(lambda _=False: self._create_hdf())
        bar.addWidget(mk)
        bar.addStretch(1)
        lo.addLayout(bar)
        opt = QFormLayout()
        opt.addRow("Hardfile heads", self.hf_heads)
        opt.addRow("Hardfile sectors per track", self.hf_spt)
        opt.addRow("", self.hdf_write)
        turbo = QCheckBox("CDTV/CD32 turbo CD read speed")
        turbo.setEnabled(False)
        opt.addRow("", turbo)
        lo.addLayout(opt)
        lbl = QLabel("Folders mount live (Zorro II host filesystem); protection and comments are kept outside the folder. Images without an RDB get a virtual one. SCSI slots (2-8) work on the A3000.")
        lbl.setWordWrap(True)
        lo.addWidget(lbl)
        lo.addStretch(1)
        return w

    def _create_hdf(self) -> None:  #vers 1
        """Make an empty hardfile in the first free slot."""
        path, _ = QFileDialog.getSaveFileName(self, "Create hardfile", config.last_dir("hdf"), "HDF (*.hdf)")
        if not path:
            return
        mb, ok = QInputDialog.getInt(self, "Create hardfile", "Size in MB", 64, 1, 4096)
        if not ok:
            return
        try:
            with open(path, "wb") as f:
                f.truncate(mb * 1024 * 1024)
        except OSError as e:
            return QMessageBox.warning(self, "Morosa Emulation", str(e))
        config.set_last_dir("hdf", os.path.dirname(path))
        free = [e for e in self.hd if not e.text().strip()]
        if free:
            free[0].setText(path)

    def _rom_info(self, path: str) -> None:  #vers 2
        try:
            kb = f"{os.path.getsize(path) // 1024} KB" if path else ""
            self.rom_info.setText(f"{kickstart_label(path)}, {kb}" if path and kickstart_label(path) else kb)
        except OSError:
            self.rom_info.setText("file not found")

    SVG = {"file": '<path d="M5 2h8l6 6v14H5z M13 2v6h6" fill="none" stroke="{c}" stroke-width="2" stroke-linejoin="round"/>',
           "folder": '<path d="M2 6h7l2 3h11v11H2z" fill="none" stroke="{c}" stroke-width="2" stroke-linejoin="round"/>',
           "info": '<circle cx="12" cy="12" r="9" fill="none" stroke="{c}" stroke-width="2"/><path d="M12 11v6" stroke="{c}" stroke-width="2.5" stroke-linecap="round"/><circle cx="12" cy="7.5" r="1.4" fill="{c}"/>',
           "clear": '<path d="M6 6l12 12M18 6L6 18" fill="none" stroke="{c}" stroke-width="2.5" stroke-linecap="round"/>',
           "clone": '<path d="M8 8h12v12H8z M16 8V4H4v12h4" fill="none" stroke="{c}" stroke-width="2" stroke-linejoin="round"/>',
           "add": '<path d="M12 5v14M5 12h14" fill="none" stroke="{c}" stroke-width="2.5" stroke-linecap="round"/>',
           "del": '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v6M14 11v6" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
           "boot": '<path d="M12 3v8M7.5 6.5a7 7 0 1 0 9 0" fill="none" stroke="#3cb371" stroke-width="2.2" stroke-linecap="round"/>',
           "noboot": '<path d="M12 3v8M7.5 6.5a7 7 0 1 0 9 0" fill="none" stroke="#888" stroke-width="2.2" stroke-linecap="round"/><path d="M4 4l16 16" stroke="#d9534f" stroke-width="2.2" stroke-linecap="round"/>',
           "import": '<path d="M12 3v12M7 10l5 5 5-5M4 20h16" fill="none" stroke="{c}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>',
           "export": '<path d="M12 15V3M7 8l5-5 5 5M4 20h16" fill="none" stroke="{c}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>'}

    def _icon(self, kind: str) -> QIcon:  #vers 1
        col = self.palette().buttonText().color().name()
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">{self.SVG[kind].format(c=col)}</svg>'
        pm = QPixmap(48, 48)
        pm.fill(Qt.GlobalColor.transparent)
        r = QSvgRenderer(QByteArray(svg.encode()))
        p = QPainter(pm)
        r.render(p)
        p.end()
        return QIcon(pm)

    def _boot_icon(self, lab, v: int) -> None:  #vers 1
        """Power icon: green boots, slashed grey does not."""
        lab.setPixmap(self._icon("boot" if v >= 0 else "noboot").pixmap(24, 24))
        lab.setToolTip("Boots" if v >= 0 else "No boot")

    def _info(self, edit) -> None:  #vers 1
        """Scan the chosen hard disk image and show what it is."""
        from apps.methods import hardfile
        path = edit.text().strip()
        if not path:
            QMessageBox.information(self, "Disk info", "No path set.")
            return
        QMessageBox.information(self, "Disk info", os.path.basename(path.rstrip("/")) + "\n\n" + "\n".join(hardfile.describe(path)))

    def _pick(self, edit, filt, both: bool = False, extra=None, info: bool = False):  #vers 6
        kind0 = filt.split()[0].lower() if filt else "dir"
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        lay.addWidget(edit)
        if extra is not None:
            lay.addWidget(extra)
        for kind, tip, fn in (("file", "Browse file" if both else "Browse", lambda _=False: self._browse(edit, filt, kind0)),
                              ("folder", "Browse folder", lambda _=False: self._browse(edit, None, kind0 + "_folder")),
                              ("info", "Scan disk info", lambda _=False: self._info(edit)),
                              ("clear", "Clear", lambda _=False: edit.clear())):
            if kind == "info" and not info:
                continue
            if kind == "folder" and not (both or filt is None):
                continue
            if kind == "file" and filt is None:
                continue
            b = QPushButton()
            b.setIcon(self._icon(kind))
            b.setIconSize(QSize(16, 16))
            b.setFixedSize(26, 26)
            b.setToolTip(tip)
            b.clicked.connect(fn)
            lay.addWidget(b)
        return row

    def _browse(self, edit, filt, kind: str = "dir") -> None:  #vers 2
        """Open at the current entry's folder, else the last folder used for this kind."""
        cur = edit.text().strip()
        start = os.path.dirname(cur) if os.path.dirname(cur) and os.path.isdir(os.path.dirname(cur)) else config.last_dir(kind)
        if filt is None:
            path = QFileDialog.getExistingDirectory(self, "Select folder", start)
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Select file", start, filt)
        if path:
            edit.setText(path)
            config.set_last_dir(kind, path if filt is None else os.path.dirname(path))

    def _reload(self, select: str = None) -> None:  #vers 1
        self.profiles = config.profiles()
        self.list.blockSignals(True)
        self.list.clear()
        self.list.addItems(sorted(self.profiles))
        self.list.blockSignals(False)
        names = sorted(self.profiles)
        if names:
            self.list.setCurrentRow(names.index(select) if select in names else 0)
            self._fill(self.list.currentItem().text())

    def _fill(self, name: str) -> None:  #vers 19
        p = self.profiles.get(name)
        if not p:
            return
        self.preset.setCurrentText(p["preset"])
        self.cpu.setCurrentIndex(0 if not p["cpu"] else CPUS.index(p["cpu_name"] if p.get("cpu_name") in CPUS and cpu_number(p["cpu_name"]) == p["cpu"] else str(p["cpu"])))
        self.fast.setValue(p["fast_mb"])
        self.addr24.setChecked(p.get("addr24", False))
        self.fpu[min(3, max(0, p.get("fpu", 3)))].setChecked(True)
        self.clx[min(3, max(0, p.get("clx", 3)))].setChecked(True)
        self.c2p.setChecked(p.get("c2p", True))
        self.z2.setCurrentIndex({0: 0, 512: 1, 1024: 2, 2048: 3, 4096: 4, 8192: 5}.get(p.get("z2_kb", 0), 0))
        self.z3.setCurrentIndex({0: 0, 16384: 1, 32768: 2, 65536: 3, 131072: 4, 262144: 5, 524288: 6, 1048576: 7}.get(p.get("z3_kb", 0), 0))
        self.proc.setCurrentIndex({0: 0, 4096: 1, 8192: 2, 16384: 3, 32768: 4, 65536: 5, 131072: 6, 262144: 7}.get(p.get("proc_kb", 0), 0))
        self.port0.setCurrentIndex(("mouse", "joy", "none").index(p.get("port0", "mouse")))
        self.port1.setCurrentIndex(("mouse", "joy", "none").index(p.get("port1", "joy")))
        for c, v in zip(self.dfwp, p.get("df_write", [False] * 4)):
            c.setChecked(not v)
        self.vkbd.setChecked(p.get("vkeyboard", False))
        self.pause_unfocus.setChecked(p.get("pause_unfocus", False))
        self.rctrl.setChecked(p.get("rctrl", False))
        self.rtg.setChecked(p.get("rtg", False))
        self.blit[0 if p.get("blit", 0) == 1 else 1].setChecked(True)
        self.snd_filter.setCurrentIndex(min(2, max(0, p.get("snd_filter", 0))))
        self.snd_sep.setValue(p.get("snd_sep", 100))
        self.slow.setCurrentIndex({0: 0, 512: 1, 1024: 2, 1792: 3}.get(p.get("slow_kb", 0), 0))
        self.disp_line.setCurrentIndex(p.get("disp_line", 0))
        self.disp_filter.setCurrentIndex(p.get("disp_filter", 0))
        self.disp_aspect.setCurrentIndex(p.get("disp_aspect", 0))
        self.disp_scale.setCurrentIndex(min(3, max(0, p.get("disp_scale", 0))))
        self.snd_out.setCurrentIndex(1 if p.get("snd_out") == "pipewire" else 0)
        self.snd_rate.setCurrentText(str(p.get("snd_rate", 44100)))
        self.snd_bits.setCurrentIndex({8: 0, 16: 1, 24: 2, 32: 3}.get(p.get("snd_bits", 8), 0))
        self.snd_ch.setCurrentText(str(p.get("snd_ch", 4)))
        self.swap.clear()
        self.swap.addItems(p.get("swapper", []))
        self.chip.setCurrentIndex({256: 1, 512: 2, 1024: 3, 2048: 4}.get(p.get("chip_kb", 0), 0))
        self.chipset.setCurrentIndex({"ocs": 1, "ecs": 2}.get(p.get("chipset", ""), 0))
        self.speed.setCurrentIndex(self.SPEEDS.index(p.get("mhz", 0)) if p.get("mhz", 0) in self.SPEEDS else 0)
        self.pal.setCurrentIndex(0 if p["pal"] else 1)
        self.boards.setText(",".join(str(k) for k in p["boards_kb"]))
        self.audio.setChecked(p["audio"])
        self.status.setChecked(p.get("status", True))
        self.trim.setChecked(p.get("trim", False))
        for a, b in self.joykeys.items():
            b.key = p.get("joykeys", {}).get(a, config.PROFILE_DEFAULT["joykeys"][a])
            b._show()
        self.hdf_write.setChecked(p["hdf_write"])
        self.hf_heads.setValue(p["hf_heads"])
        self.hf_spt.setValue(p["hf_spt"])
        self.rom.setText(p["rom"])
        self.ext_rom.setText(p.get("ext_rom", ""))
        self.xfer.setText(p.get("xfer", ""))
        self.rtc.setChecked(bool(p.get("rtc")))
        self.cart.setCurrentText(p.get("cart", "None") if p.get("cart", "None") in CD32_CARTS else "None")
        self.bootstrap.setText(p["bootstrap"])
        for e, v in zip(self.df, p["df"]):
            e.setText(v)
        for e, v in zip(self.hd, p["hd"]):
            e.setText(v)
        for c, v in zip(self.hd_pri, p["hd_pri"]):
            c.setValue(int(v))
        for e, v in zip(self.hd_ss, p["hd_ss"]):
            e.setText(v)

    def _collect(self) -> dict:  #vers 18
        try:
            boards = [int(x) for x in self.boards.text().replace(" ", "").split(",") if x]
        except ValueError:
            raise ValueError("Zorro RAM boards must be numbers in KB")
        return {"preset": self.preset.currentText(), "cpu": 0 if self.cpu.currentIndex() == 0 else cpu_number(self.cpu.currentText()), "cpu_name": "" if self.cpu.currentIndex() == 0 else self.cpu.currentText(),
                "fast_mb": self.fast.value(), "addr24": self.addr24.isChecked(), "fpu": next(i for i, r in enumerate(self.fpu) if r.isChecked()), "clx": next(i for i, r in enumerate(self.clx) if r.isChecked()), "chipset": ("", "ocs", "ecs")[self.chipset.currentIndex()], "c2p": self.c2p.isChecked(), "z2_kb": (0, 512, 1024, 2048, 4096, 8192)[self.z2.currentIndex()], "z3_kb": (0, 16384, 32768, 65536, 131072, 262144, 524288, 1048576)[self.z3.currentIndex()],
                "proc_kb": (0, 4096, 8192, 16384, 32768, 65536, 131072, 262144)[self.proc.currentIndex()], "df_write": [not c.isChecked() for c in self.dfwp], "vkeyboard": self.vkbd.isChecked(), "pause_unfocus": self.pause_unfocus.isChecked(), "rctrl": self.rctrl.isChecked(), "rtg": self.rtg.isChecked(), "blit": int(self.blit[0].isChecked()), "snd_filter": self.snd_filter.currentIndex(), "snd_sep": self.snd_sep.value(), "port0": ("mouse", "joy", "none")[self.port0.currentIndex()], "port1": ("mouse", "joy", "none")[self.port1.currentIndex()], "slow_kb": (0, 512, 1024, 1792)[self.slow.currentIndex()], "disp_line": self.disp_line.currentIndex(), "disp_filter": self.disp_filter.currentIndex(), "disp_aspect": self.disp_aspect.currentIndex(), "disp_scale": self.disp_scale.currentIndex(),
                "snd_out": ("qt", "pipewire")[self.snd_out.currentIndex()], "snd_rate": int(self.snd_rate.currentText()),
                "snd_bits": (8, 16, 24, 32)[self.snd_bits.currentIndex()], "snd_ch": int(self.snd_ch.currentText()), "swapper": [self.swap.item(i).text() for i in range(self.swap.count())], "chip_kb": (0, 256, 512, 1024, 2048)[self.chip.currentIndex()], "mhz": self.SPEEDS[self.speed.currentIndex()], "pal": self.pal.currentIndex() == 0, "rom": self.rom.text(), "ext_rom": self.ext_rom.text(), "xfer": self.xfer.text(), "cart": self.cart.currentText(), "rtc": self.rtc.isChecked(), "bootstrap": self.bootstrap.text(),
                "df": [e.text() for e in self.df], "hd": [e.text() for e in self.hd], "hd_pri": [c.value() for c in self.hd_pri], "hd_ss": [e.text() for e in self.hd_ss], "hdf_write": self.hdf_write.isChecked(), "hf_heads": self.hf_heads.value(), "hf_spt": self.hf_spt.value(),
                "boards_kb": boards, "audio": self.audio.isChecked(), "status": self.status.isChecked(), "trim": self.trim.isChecked(),
                "joykeys": {a: b.key for a, b in self.joykeys.items() if b.key}}

    def _new(self) -> None:  #vers 2
        """New profile from the settings shown now."""
        name, ok = QInputDialog.getText(self, "New profile", "Name")
        if ok and name.strip():
            try:
                config.save_profile(name.strip(), self._collect())
            except ValueError as e:
                return QMessageBox.warning(self, "Morosa Emulation", str(e))
            self._reload(name.strip())

    def _save(self) -> None:  #vers 1
        item = self.list.currentItem()
        if item is None:
            return self._new()
        try:
            config.save_profile(item.text(), self._collect())
        except ValueError as e:
            return QMessageBox.warning(self, "Morosa Emulation", str(e))
        if self.amisys.text():
            config.set_amisys(self.amisys.text())
        self._reload(item.text())

    def _clone(self) -> None:  #vers 1
        item = self.list.currentItem()
        if item is None:
            return
        name, ok = QInputDialog.getText(self, "Clone config", "Name", text=f"{item.text()} copy")
        if ok and name.strip():
            config.save_profile(name.strip(), self.profiles[item.text()])
            self._reload(name.strip())

    def _export(self) -> None:  #vers 1
        item = self.list.currentItem()
        if item is None:
            return
        try:
            path = config.export_profile(item.text())
        except (OSError, KeyError) as e:
            return QMessageBox.warning(self, "Export config", str(e))
        QMessageBox.information(self, "Export config", f"Saved to {path}")

    def _import(self) -> None:  #vers 1
        start = str(config.configs_dir())
        path, _ = QFileDialog.getOpenFileName(self, "Import config", start, "Config (*.json)")
        if not path:
            return
        try:
            self._reload(config.import_profile(path))
        except (OSError, ValueError) as e:
            QMessageBox.warning(self, "Import config", str(e))

    def _delete(self) -> None:  #vers 1
        item = self.list.currentItem()
        if item:
            config.delete_profile(item.text())
            self._reload()

    def _apply_view(self) -> None:  #vers 1
        """Display options reach open Amiga windows at once."""
        v = {"line": self.disp_line.currentIndex(), "filter": self.disp_filter.currentIndex(), "aspect": self.disp_aspect.currentIndex(),
             "scale": (0, 2, 3, 4)[self.disp_scale.currentIndex()]}
        for w in self.screens:
            w.view.update(v)
            w._fitsz = None
            w.update()

    def _run(self) -> None:  #vers 3
        from apps.gui.screen import MachineScreen
        try:
            m = config.build_machine(self._collect())
        except (OSError, ValueError, NotImplementedError) as e:
            return QMessageBox.warning(self, "Morosa Emulation", str(e))
        w = MachineScreen(m, self.audio.isChecked(), self.status.isChecked(), self._collect()["joykeys"], self.trim.isChecked(), self._collect()["snd_out"],
                          {"vkeyboard": self.vkbd.isChecked(), "pause_unfocus": self.pause_unfocus.isChecked(), "rctrl": self.rctrl.isChecked(), "line": self.disp_line.currentIndex(), "filter": self.disp_filter.currentIndex(), "aspect": self.disp_aspect.currentIndex(), "scale": (0, 2, 3, 4)[self.disp_scale.currentIndex()]})
        w.settings = self
        w.setWindowTitle(f"Morosa {self.preset.currentText()}")
        w.show()
        w.start()
        self.screens.append(w)

    def _live(self):  #vers 1
        """Newest machine window still open, or None."""
        live = [w for w in self.screens if w.isVisible()]
        return live[-1] if live else None

    def _pause(self) -> None:  #vers 1
        w = self._live()
        if w is not None:
            self.titlebar.set_paused(w.pause())

    def _stop(self) -> None:  #vers 1
        w = self._live()
        if w is not None:
            w.stop()
            w.close()
            self.screens.remove(w)
            self.titlebar.set_paused(False)


def main() -> int:  #vers 1
    app = QApplication(sys.argv)
    w = SettingsWindow()
    w.resize(820, 560)
    w.show()
    return app.exec()
