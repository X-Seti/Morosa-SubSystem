#this belongs in apps/gui/settings.py - Version: 5
# X-Seti - November 17 2026 - Morosa - Settings Editor.

"""
Morosa Settings - standalone editor for machine profiles and the AmiSys folder; runs a profile in a screen window.
"""

##Methods list -
# main
# SettingsWindow
# SettingsWindow._browse
# SettingsWindow._collect
# SettingsWindow._delete
# SettingsWindow._fill
# SettingsWindow._new
# SettingsWindow._pick
# SettingsWindow._reload
# SettingsWindow._rom_info
# SettingsWindow._run
# SettingsWindow._save
# SettingsWindow._tab_drives
# SettingsWindow._tab_floppy
# SettingsWindow._tab_machine
# SettingsWindow._tab_rom

import os
import sys

from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QInputDialog,
                             QLabel, QLineEdit, QListWidget, QMainWindow, QMessageBox, QPushButton, QSpinBox, QTabWidget,
                             QVBoxLayout, QWidget)

from apps.hardware.amiga import PRESETS
from apps.methods import config

CPUS = ["Preset", "68000", "68010", "68020", "68030", "68040", "68060"]


class SettingsWindow(QMainWindow):
    """Profile list on the left, settings form on the right."""

    def __init__(self):  #vers 2
        super().__init__()
        self.setWindowTitle("Morosa Settings")
        self.screens = []
        self.profiles = {}
        self.list = QListWidget()
        self.list.currentTextChanged.connect(self._fill)
        self.preset = QComboBox()
        self.preset.addItems(list(PRESETS))
        self.cpu = QComboBox()
        self.cpu.addItems(CPUS)
        self.fast = QSpinBox()
        self.fast.setRange(0, 1024)
        self.fast.setSuffix(" MB")
        self.pal = QComboBox()
        self.pal.addItems(["PAL", "NTSC"])
        self.boards = QLineEdit()
        self.boards.setPlaceholderText("KB, comma separated, e.g. 8192,16384")
        self.audio = QCheckBox("Audio output")
        self.hf_heads, self.hf_spt = QSpinBox(), QSpinBox()
        self.hf_heads.setRange(1, 16)
        self.hf_spt.setRange(1, 255)
        self.hdf_write = QCheckBox("Allow writes to hard disk image files")
        self.rom = QLineEdit()
        self.bootstrap = QLineEdit()
        self.bootstrap.setPlaceholderText("A1000 only; Kickstart ROM below is loaded from a built disk")
        self.rom_info = QLabel("")
        self.rom.textChanged.connect(self._rom_info)
        self.df = [QLineEdit() for _ in range(4)]
        self.hd = [QLineEdit() for _ in range(config.HD_SLOTS)]
        self.amisys = QLineEdit(config.amisys_dir())
        tabs = QTabWidget()
        tabs.addTab(self._tab_machine(), "Machine")
        tabs.addTab(self._tab_rom(), "ROM")
        tabs.addTab(self._tab_floppy(), "Floppy")
        tabs.addTab(self._tab_drives(), "Hard Drives")
        buttons = QHBoxLayout()
        for label, fn in (("New", self._new), ("Save", self._save), ("Delete", self._delete), ("Run", self._run)):
            b = QPushButton(label)
            b.clicked.connect(fn)
            buttons.addWidget(b)
        right = QVBoxLayout()
        right.addWidget(tabs)
        right.addLayout(buttons)
        root = QWidget()
        lay = QHBoxLayout(root)
        lay.addWidget(self.list, 1)
        lay.addLayout(right, 3)
        self.setCentralWidget(root)
        self._reload()

    def _tab_machine(self) -> QWidget:  #vers 1
        w = QWidget()
        form = QFormLayout(w)
        form.addRow("Machine", self.preset)
        form.addRow("CPU", self.cpu)
        form.addRow("Fast RAM", self.fast)
        form.addRow("Video", self.pal)
        form.addRow("Zorro RAM boards", self.boards)
        form.addRow("", self.audio)
        form.addRow("AmiSys folder", self._pick(self.amisys, None))
        return w

    def _tab_rom(self) -> QWidget:  #vers 2
        w = QWidget()
        form = QFormLayout(w)
        form.addRow("Boot ROM (A1000)", self._pick(self.bootstrap, "ROM (*.rom *.bin *)"))
        form.addRow("Kickstart ROM", self._pick(self.rom, "ROM (*.rom *.bin *)"))
        form.addRow("", self.rom_info)
        return w

    def _tab_floppy(self) -> QWidget:  #vers 1
        w = QWidget()
        form = QFormLayout(w)
        for i, e in enumerate(self.df):
            form.addRow(f"DF{i}", self._pick(e, "ADF (*.adf *.ADF *)"))
        return w

    def _tab_drives(self) -> QWidget:  #vers 1
        w = QWidget()
        form = QFormLayout(w)
        for i, e in enumerate(self.hd):
            tag = "IDE" if i < 2 else "SCSI"
            e.setPlaceholderText("HDF, folder, or CD image (iso, cue, bin)")
            form.addRow(f"{tag} {i}", self._pick(e, "HDF (*.hdf *.HDF *)", True))
        form.addRow("Hardfile heads", self.hf_heads)
        form.addRow("Hardfile sectors per track", self.hf_spt)
        form.addRow("", self.hdf_write)
        lbl = QLabel("Folders become a bootable disk, not saved back. Images without an RDB get a virtual one. SCSI slots (2-8) work on the A3000.")
        lbl.setWordWrap(True)
        form.addRow("", lbl)
        return w

    def _rom_info(self, path: str) -> None:  #vers 1
        try:
            self.rom_info.setText(f"{os.path.getsize(path) // 1024} KB" if path else "")
        except OSError:
            self.rom_info.setText("file not found")

    def _pick(self, edit, filt, both: bool = False):  #vers 2
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        btn = QPushButton("File" if both else "Browse")
        btn.clicked.connect(lambda _=False: self._browse(edit, filt))
        lay.addWidget(edit)
        lay.addWidget(btn)
        if both:
            fb = QPushButton("Folder")
            fb.clicked.connect(lambda _=False: self._browse(edit, None))
            lay.addWidget(fb)
        return row

    def _browse(self, edit, filt) -> None:  #vers 1
        if filt is None:
            path = QFileDialog.getExistingDirectory(self, "Select folder")
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Select file", "", filt)
        if path:
            edit.setText(path)

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

    def _fill(self, name: str) -> None:  #vers 3
        p = self.profiles.get(name)
        if not p:
            return
        self.preset.setCurrentText(p["preset"])
        self.cpu.setCurrentIndex(0 if not p["cpu"] else CPUS.index(str(p["cpu"])))
        self.fast.setValue(p["fast_mb"])
        self.pal.setCurrentIndex(0 if p["pal"] else 1)
        self.boards.setText(",".join(str(k) for k in p["boards_kb"]))
        self.audio.setChecked(p["audio"])
        self.hdf_write.setChecked(p["hdf_write"])
        self.hf_heads.setValue(p["hf_heads"])
        self.hf_spt.setValue(p["hf_spt"])
        self.rom.setText(p["rom"])
        self.bootstrap.setText(p["bootstrap"])
        for e, v in zip(self.df, p["df"]):
            e.setText(v)
        for e, v in zip(self.hd, p["hd"]):
            e.setText(v)

    def _collect(self) -> dict:  #vers 3
        try:
            boards = [int(x) for x in self.boards.text().replace(" ", "").split(",") if x]
        except ValueError:
            raise ValueError("Zorro RAM boards must be numbers in KB")
        return {"preset": self.preset.currentText(), "cpu": 0 if self.cpu.currentIndex() == 0 else int(self.cpu.currentText()),
                "fast_mb": self.fast.value(), "pal": self.pal.currentIndex() == 0, "rom": self.rom.text(), "bootstrap": self.bootstrap.text(),
                "df": [e.text() for e in self.df], "hd": [e.text() for e in self.hd], "hdf_write": self.hdf_write.isChecked(), "hf_heads": self.hf_heads.value(), "hf_spt": self.hf_spt.value(),
                "boards_kb": boards, "audio": self.audio.isChecked()}

    def _new(self) -> None:  #vers 1
        name, ok = QInputDialog.getText(self, "New profile", "Name")
        if ok and name.strip():
            config.save_profile(name.strip(), dict(config.PROFILE_DEFAULT))
            self._reload(name.strip())

    def _save(self) -> None:  #vers 1
        item = self.list.currentItem()
        if item is None:
            return self._new()
        try:
            config.save_profile(item.text(), self._collect())
        except ValueError as e:
            return QMessageBox.warning(self, "Morosa Settings", str(e))
        if self.amisys.text():
            config.set_amisys(self.amisys.text())
        self._reload(item.text())

    def _delete(self) -> None:  #vers 1
        item = self.list.currentItem()
        if item:
            config.delete_profile(item.text())
            self._reload()

    def _run(self) -> None:  #vers 1
        from apps.gui.screen import MachineScreen
        try:
            m = config.build_machine(self._collect())
        except (OSError, ValueError, NotImplementedError) as e:
            return QMessageBox.warning(self, "Morosa Settings", str(e))
        w = MachineScreen(m, self.audio.isChecked())
        w.setWindowTitle(f"Morosa {self.preset.currentText()}")
        w.show()
        w.start()
        self.screens.append(w)


def main() -> int:  #vers 1
    app = QApplication(sys.argv)
    w = SettingsWindow()
    w.resize(820, 560)
    w.show()
    return app.exec()
