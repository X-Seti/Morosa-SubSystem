#this belongs in apps/gui/settings_dialog.py - Version: 2
# X-Seti - November 22 2026 - Morosa - App Settings Dialog.

"""
Morosa App Settings Dialog - Morosa's own options: display, audio, paths.
"""

##Methods list -
# MorosaSettingsDialog
# MorosaSettingsDialog.__init__

from PyQt6.QtWidgets import QDialog, QFormLayout, QHBoxLayout, QPushButton, QTabWidget, QVBoxLayout, QWidget


class MorosaSettingsDialog(QDialog):
    """Tabs: Display, Audio, Paths. Widgets are owned by the settings window."""

    def __init__(self, parent, trim, status, audio, amisys_row, roms_row):  #vers 2
        super().__init__(parent)
        self.setWindowTitle("Morosa Settings")
        tabs = QTabWidget()
        for name, rows in (("Display", (trim, status)), ("Audio", (audio,)), ("Paths", (amisys_row, roms_row))):
            w = QWidget()
            form = QFormLayout(w)
            for r in rows:
                form.addRow({id(amisys_row): "AmiSys folder", id(roms_row): "ROMs folder"}.get(id(r), ""), r)
            tabs.addTab(w, name)
        close = QPushButton("Close")
        close.clicked.connect(self.hide)
        bar = QHBoxLayout()
        bar.addStretch(1)
        bar.addWidget(close)
        lo = QVBoxLayout(self)
        lo.addWidget(tabs)
        lo.addLayout(bar)
        self.resize(460, 240)
