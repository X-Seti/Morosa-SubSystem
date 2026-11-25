#this belongs in apps/gui/settings_pages.py - Version: 2
# X-Seti - November 22 2026 - Morosa - Settings Page Helpers.

"""
Morosa Emulation Pages - SVG page icons and greyed placeholder pages for options not emulated yet.
"""

##Methods list -
# page_icon
# quick_configs
# stub_group
# stub_page

from PyQt6.QtCore import QByteArray, Qt
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QGridLayout, QGroupBox, QLabel, QRadioButton, QSlider, QVBoxLayout,
                             QWidget)

S = 'fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"'
ICONS = {
    "start": '<path d="M7 4l13 8-13 8z"/>', "pause": '<path d="M8 5v14M16 5v14"/>', "stop": '<rect x="6" y="6" width="12" height="12"/>',
    "save": '<path d="M5 4h12l3 3v13H5zM8 4v5h8V4M8 20v-6h8v6"/>',
    "quick": '<path d="M13 3L5 14h6l-1 7 8-11h-6z"/>', "cpu": '<rect x="7" y="7" width="10" height="10"/><path d="M10 3v4M14 3v4M10 17v4M14 17v4M3 10h4M3 14h4M17 10h4M17 14h4"/>',
    "chip": '<rect x="5" y="5" width="14" height="14"/><path d="M9 9h6v6H9z"/>', "rom": '<rect x="6" y="3" width="12" height="18"/><path d="M9 7h6M9 11h6M9 15h6"/>',
    "ram": '<rect x="3" y="8" width="18" height="8"/><path d="M6 16v3M10 16v3M14 16v3M18 16v3M7 11h2M11 11h2M15 11h2"/>',
    "floppy": '<path d="M5 4h12l3 3v13H5z"/><rect x="8" y="4" width="8" height="5"/><rect x="8" y="13" width="8" height="7"/>',
    "drive": '<rect x="3" y="8" width="18" height="9" rx="2"/><path d="M6 14h4M17 12.5h.01"/>', "display": '<rect x="3" y="5" width="18" height="12"/><path d="M9 21h6M12 17v4"/>',
    "sound": '<path d="M4 9h4l5-4v14l-5-4H4zM16 9c1.5 1.5 1.5 4.5 0 6M18.5 6.5c3 3 3 8 0 11"/>',
    "input": '<rect x="3" y="7" width="18" height="10" rx="2"/><path d="M6 11h.01M9 11h.01M12 11h.01M15 11h.01M18 11h.01M7 14h10"/>',
    "ports": '<rect x="4" y="8" width="16" height="8"/><path d="M8 8V5M12 8V5M16 8V5M8 16v3M16 16v3"/>', "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5h.01"/>',
    "misc": '<path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/>',
    "card": '<path d="M6 3h9l4 4v14H6z"/><path d="M9 3v4M12 3v4"/>', "slot": '<rect x="3" y="9" width="18" height="8"/><path d="M7 9V6h10v3"/>',
}


def page_icon(kind: str, color: str) -> QIcon:  #vers 1
    """Page or ribbon icon in the given colour."""
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><g {S.format(c=color)}>{ICONS[kind]}</g></svg>'
    pm = QPixmap(48, 48)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    QSvgRenderer(QByteArray(svg.encode())).render(p)
    p.end()
    return QIcon(pm)


def quick_configs(model: str, chip_kb: int) -> list:  #vers 1
    """Quickstart configs for a model: (label, cpu, fast MB); cpu 0 keeps the model default."""
    chip = f"{chip_kb // 1024} MB" if chip_kb >= 1024 else f"{chip_kb} KB"
    out = [(f"Default, {chip} Chip", 0, 0)]
    if model in ("A500", "A500+", "A600", "A2000", "A1000"):
        out.append((f"{chip} Chip + 8 MB Fast", 0, 8))
    elif model == "A1200":
        out += [(f"{chip} Chip + 8 MB Fast", 0, 8), ("68030, 2 MB Chip + 8 MB Fast", 68030, 8), ("68040, 2 MB Chip + 16 MB Fast", 68040, 16)]
    elif model.startswith("A4000") or model == "A3000":
        out.append((f"{chip} Chip + 16 MB Fast", 0, 16))
    return out


def stub_group(title: str, rows) -> QGroupBox:  #vers 1
    """Greyed group. Row kinds: radio, check, combo (label, [items]), slider (label)."""
    g = QGroupBox(title)
    lo = QGridLayout(g)
    for i, (kind, label, *opt) in enumerate(rows):
        if kind == "radio":
            w = QRadioButton(label)
        elif kind == "check":
            w = QCheckBox(label)
        elif kind == "combo":
            lo.addWidget(QLabel(label), i, 0)
            w = QComboBox()
            w.addItems(opt[0] if opt else [])
            lo.addWidget(w, i, 1)
            continue
        else:
            lo.addWidget(QLabel(label), i, 0)
            w = QSlider(Qt.Orientation.Horizontal)
            lo.addWidget(w, i, 1)
            continue
        lo.addWidget(w, i, 0, 1, 2)
    g.setEnabled(False)
    return g


def stub_page(groups, note: str = "Not emulated yet.") -> QWidget:  #vers 1
    """Page of greyed groups with a note."""
    w = QWidget()
    lo = QVBoxLayout(w)
    for title, rows in groups:
        lo.addWidget(stub_group(title, rows))
    lo.addWidget(QLabel(note))
    lo.addStretch(1)
    return w
