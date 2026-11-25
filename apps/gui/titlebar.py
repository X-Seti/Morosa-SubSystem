#this belongs in apps/gui/titlebar.py - Version: 5
# X-Seti - November 22 2026 - Morosa - Custom Title Bar.

"""
Morosa Title Bar - frameless window bar: menu, settings, title, cog, minimize, maximize, close.
"""

##Methods list -
# TitleBar
# TitleBar.__init__
# TitleBar._btn
# TitleBar._icon
# TitleBar.set_paused
# TitleBar._toggle_max
# TitleBar.mouseDoubleClickEvent
# TitleBar.mousePressEvent
# TitleBar.set_title

from pathlib import Path

from apps.gui.settings_pages import ICONS, page_icon
from PyQt6.QtCore import QByteArray, QSize, Qt
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMenu, QPushButton, QToolButton

APP_ICON = Path(__file__).resolve().parents[2] / "App_icon.webp"
S = 'fill="none" stroke="{c}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"'
SVG = {"menu": f'<path d="M4 6h16M4 12h16M4 18h16" {S}/>',
       "settings": f'<path d="M4 7h10M18 7h2M4 17h2M10 17h10" {S}/><circle cx="16" cy="7" r="2" {S}/><circle cx="8" cy="17" r="2" {S}/>',
       "cog": f'<circle cx="12" cy="12" r="3.5" {S}/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2" {S}/>',
       "folder": f'<path d="M3 7h6l2 2h10v10H3z" {S}/>',
       "save": f'<path d="M5 4h12l3 3v13H5zM8 4v5h8V4M8 20v-6h8v6" {S}/>',
       "min": f'<path d="M5 18h14" {S}/>',
       "max": f'<rect x="5" y="5" width="14" height="14" {S}/>',
       "close": f'<path d="M5 5l14 14M19 5L5 19" {S}/>'}


class TitleBar(QFrame):
    """Left: Menu, Settings. Centre: title. Right: cog, minimize, maximize, close."""

    def __init__(self, win, menu_fn, settings_fn, amisys_fn, cog_fn, play_fn, pause_fn, stop_fn, save_fn):  #vers 5
        super().__init__(win)
        self.win = win
        self.setObjectName("titlebar")
        self.setFixedHeight(40)
        lo = QHBoxLayout(self)
        lo.setContentsMargins(6, 3, 6, 3)
        lo.setSpacing(4)
        self.menu_btn = QToolButton()
        self.menu_btn.setText("Menu")
        self.menu_btn.setIcon(self._icon("menu"))
        self.menu_btn.setIconSize(QSize(18, 18))
        self.menu_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.menu_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.menu_btn.setMenu(QMenu(self.menu_btn))
        self.menu_btn.menu().aboutToShow.connect(lambda: (self.menu_btn.menu().clear(), menu_fn(self.menu_btn.menu())))
        lo.addWidget(self.menu_btn)
        sb = QPushButton(" Settings")
        sb.setIcon(self._icon("settings"))
        sb.setIconSize(QSize(18, 18))
        sb.clicked.connect(lambda _=False: settings_fn())
        lo.addWidget(sb)
        lo.addStretch(1)
        self.logo = QLabel()
        logo = QPixmap(str(APP_ICON))
        self.logo.setPixmap(logo.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        win.setWindowIcon(QIcon(logo))
        lo.addWidget(self.logo)
        self.label = QLabel("Morosa Emulator")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f = self.label.font()
        f.setBold(True)
        self.label.setFont(f)
        lo.addWidget(self.label)
        lo.addStretch(1)
        self.pause_btn = None
        for kind, tip, fn in (("start", "Play", play_fn), ("pause", "Pause", pause_fn), ("stop", "Stop", stop_fn), ("save", "Save config", save_fn)):
            b = self._btn(kind, tip, fn)
            if kind == "pause":
                self.pause_btn = b
            lo.addWidget(b)
        lo.addSpacing(8)
        ab = QPushButton(" AmiSys")
        ab.setIcon(self._icon("folder"))
        ab.setIconSize(QSize(18, 18))
        ab.setToolTip("Pick the AmiSys folder")
        ab.clicked.connect(lambda _=False: amisys_fn())
        lo.addWidget(ab)
        for kind, tip, fn in (("cog", "App Settings", cog_fn), ("min", "Minimize", win.showMinimized),
                              ("max", "Maximize/Restore", self._toggle_max), ("close", "Close", win.close)):
            lo.addWidget(self._btn(kind, tip, fn))

    def _icon(self, kind: str) -> QIcon:  #vers 2
        col = self.palette().buttonText().color().name()
        if kind in ICONS:
            return page_icon(kind, col)
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">{SVG[kind].format(c=col)}</svg>'
        pm = QPixmap(48, 48)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        QSvgRenderer(QByteArray(svg.encode())).render(p)
        p.end()
        return QIcon(pm)

    def _btn(self, kind: str, tip: str, fn) -> QPushButton:  #vers 1
        b = QPushButton()
        b.setIcon(self._icon(kind))
        b.setIconSize(QSize(18, 18))
        b.setFixedSize(36, 30)
        b.setToolTip(tip)
        b.clicked.connect(lambda _=False, f=fn: f())
        return b

    def _toggle_max(self) -> None:  #vers 1
        self.win.showNormal() if self.win.isMaximized() else self.win.showMaximized()

    def mouseDoubleClickEvent(self, e) -> None:  #vers 1
        self._toggle_max()

    def mousePressEvent(self, e) -> None:  #vers 1
        if e.button() == Qt.MouseButton.LeftButton and self.win.windowHandle():
            self.win.windowHandle().startSystemMove()

    def set_paused(self, paused: bool) -> None:  #vers 1
        self.pause_btn.setIcon(self._icon("start" if paused else "pause"))
        self.pause_btn.setToolTip("Resume" if paused else "Pause")

    def set_title(self, t: str) -> None:  #vers 1
        self.label.setText(t)
