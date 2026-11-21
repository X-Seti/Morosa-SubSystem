#this belongs in apps/gui/dialog.py - Version: 3
# X-Seti - November 17 2026 - Morosa - Morosa Run Window.

"""
Morosa Run Window - shows the text output of an Amiga program run by the Morosa subsystem.
"""

##Methods list -
# QtUI
# _Worker
# find_install
# install_os
# run
# run_installer
# run_script
# show_steps

import os

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication, QCheckBox, QInputDialog, QDialog, QFileDialog, QMessageBox, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout

from apps.methods import config as morosa
from apps.gui.display import Display

_open = []


class _Worker(QThread):
    """Runs one program on the Morosa machine away from the GUI thread."""

    text = pyqtSignal(str)
    done = pyqtSignal(int)
    ready = pyqtSignal(object)

    def __init__(self, path: str, args: str):  #vers 1
        super().__init__()
        self.path, self.args, self.machine = path, args, None

    def run(self) -> None:  #vers 1
        from apps.core import machine as morosa_machine
        from apps.methods import shell as morosa_shell
        sh = morosa_shell.Shell(morosa.ensure_amisys(), out=lambda s: None)
        self.machine = morosa_machine.Machine(sh, 68020, out=lambda b: self.text.emit(b.decode("latin-1")), inp=lambda: b"")
        self.ready.emit(self.machine)
        try:
            rc = self.machine.run(self.path, self.args)
        except (morosa_machine.Unimplemented, morosa_machine.Guru) as e:
            self.text.emit(f"\nMorosa: {e}")
            rc = 20
        self.done.emit(rc)


def run(parent, path: str) -> None: #vers 2
    """Run an Amiga program and show its output; arguments can be typed before it starts."""
    dlg = QDialog(parent)
    dlg.setWindowTitle(f"Morosa - {os.path.basename(path)}")
    dlg.resize(640, 420)
    lay = QVBoxLayout(dlg)
    row = QHBoxLayout()
    row.addWidget(QLabel("Arguments:"))
    args = QLineEdit()
    go = QPushButton("Run")
    stop = QPushButton("Stop")
    row.addWidget(args, 1)
    row.addWidget(go)
    row.addWidget(stop)
    lay.addLayout(row)
    out = QPlainTextEdit()
    out.setReadOnly(True)
    out.setStyleSheet("font-family: monospace;")
    lay.addWidget(out, 1)
    state = {"w": None}
    display = Display(dlg)

    def start():
        if state["w"] is not None and state["w"].isRunning():
            return
        out.clear()
        w = _Worker(path, args.text())
        w.text.connect(out.insertPlainText)
        w.ready.connect(display.attach)
        w.done.connect(lambda code: out.appendPlainText(f"\n[finished, code {code}]"))
        state["w"] = w
        w.start()

    def halt():
        w = state["w"]
        if w is not None and w.isRunning() and w.machine is not None:
            w.machine.abort = True

    go.clicked.connect(start)
    stop.clicked.connect(halt)
    args.returnPressed.connect(start)

    def closed(_r):  #vers 1
        halt()
        if state["w"] is not None:
            state["w"].wait(2000)
        if dlg in _open:
            _open.remove(dlg)

    dlg.finished.connect(closed)
    _open.append(dlg)
    dlg.show()
    start()


def show_steps(parent, path: str) -> None: #vers 1
    """Window with the steps of an installer or AmigaDOS script; nothing is run."""
    from apps.methods import formats as morosa_formats
    dlg = QDialog(parent)
    dlg.setWindowTitle(f"Installer steps - {os.path.basename(path)}")
    dlg.resize(760, 520)
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel(f"Kind: {morosa_formats.classify(path)}"))
    box = QPlainTextEdit(morosa_formats.describe(path))
    box.setReadOnly(True)
    box.setStyleSheet("font-family: monospace;")
    lay.addWidget(box, 1)
    close = QPushButton("Close")
    close.clicked.connect(dlg.accept)
    lay.addWidget(close)
    _open.append(dlg)
    dlg.finished.connect(lambda _r: _open.remove(dlg) if dlg in _open else None)
    dlg.show()


def run_script(parent, path: str) -> None: #vers 1
    """Run an AmigaDOS script on AmiSys:; asks for a folder when a disk is needed."""
    from apps.methods import shell as morosa_shell
    here = os.path.dirname(os.path.abspath(path))
    dlg = QDialog(parent)
    dlg.setWindowTitle(f"Morosa script - {os.path.basename(path)}")
    dlg.resize(760, 520)
    lay = QVBoxLayout(dlg)
    box = QPlainTextEdit()
    box.setReadOnly(True)
    box.setStyleSheet("font-family: monospace;")
    lay.addWidget(box, 1)
    close = QPushButton("Close")
    close.clicked.connect(dlg.accept)
    lay.addWidget(close)
    _open.append(dlg)
    dlg.finished.connect(lambda _r: _open.remove(dlg) if dlg in _open else None)
    dlg.show()

    def out(t):
        box.appendPlainText(str(t))
        QApplication.processEvents()

    def volume(name):
        sib = os.path.join(os.path.dirname(here), name)
        if os.path.isdir(sib):
            return sib
        QMessageBox.information(dlg, "Insert disk", f"Choose the folder for disk {name}:")
        return QFileDialog.getExistingDirectory(dlg, f"Folder for {name}:", os.path.dirname(here)) or None

    sh = morosa_shell.Shell(morosa.ensure_amisys(), out=out, volume=volume,
                            ask=lambda q: QMessageBox.question(dlg, "Script", q) == QMessageBox.StandardButton.Yes)
    vol = os.path.basename(here).lower()
    sh.vols[vol] = here
    sh.cwd = (vol, [])
    sh.failat = 21
    rc = sh.run_file(path)
    out(f"Finished, return code {rc}")


class QtUI:
    """Installer questions as Qt dialogs; progress goes to the log window."""

    def __init__(self, dlg, out, target="AmiSys:"):
        self.dlg, self.out, self.target = dlg, out, target

    def ask_bool(self, prompt, help, default):  #vers 1
        return QMessageBox.question(self.dlg, "Installer", prompt) == QMessageBox.StandardButton.Yes

    def ask_choice(self, prompt, help, choices, default):  #vers 1
        got, ok = QInputDialog.getItem(self.dlg, "Installer", prompt.strip(), choices, default or 0, False)
        if not ok:
            raise _Cancel()
        return choices.index(got)

    def ask_options(self, prompt, help, choices, default):  #vers 1
        box = QDialog(self.dlg)
        box.setWindowTitle("Installer")
        lay = QVBoxLayout(box)
        lay.addWidget(QLabel(prompt.strip()))
        ticks = []
        for i, c in enumerate(choices):
            t = QCheckBox(c)
            t.setChecked(default == -1 or bool(default & (1 << i)))
            lay.addWidget(t)
            ticks.append(t)
        go = QPushButton("Proceed")
        go.clicked.connect(box.accept)
        lay.addWidget(go)
        if not box.exec():
            raise _Cancel()
        return sum(1 << i for i, t in enumerate(ticks) if t.isChecked())

    def ask_dir(self, prompt, help, default):  #vers 1
        got, ok = QInputDialog.getText(self.dlg, "Installer", prompt.strip(), text=default or self.target)
        if not ok:
            raise _Cancel()
        return got

    ask_file = ask_string = ask_dir

    def ask_number(self, prompt, help, default):  #vers 1
        got, ok = QInputDialog.getInt(self.dlg, "Installer", prompt.strip(), default or 0)
        if not ok:
            raise _Cancel()
        return got

    def ask_disk(self, prompt, name):  #vers 1
        QMessageBox.information(self.dlg, "Insert disk", f"{prompt}\nDisk {name}: was not found.")
        return False

    def message(self, text):  #vers 1
        self.out(text)

    def working(self, text):  #vers 1
        self.out(text)

    def complete(self, pct):  #vers 1
        pass

    def finish(self, text, ok):  #vers 1
        self.out(text if ok else f"Stopped: {text}")


class _Cancel(Exception):
    """The user closed a question."""


def _log_window(parent, title):  #vers 1
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.resize(760, 520)
    lay = QVBoxLayout(dlg)
    box = QPlainTextEdit()
    box.setReadOnly(True)
    box.setStyleSheet("font-family: monospace;")
    lay.addWidget(box, 1)
    close = QPushButton("Close")
    close.clicked.connect(dlg.accept)
    lay.addWidget(close)
    _open.append(dlg)
    dlg.finished.connect(lambda _r: _open.remove(dlg) if dlg in _open else None)
    dlg.show()

    def out(t):
        box.appendPlainText(str(t))
        QApplication.processEvents()
    return dlg, out


def run_installer(parent, script: str, folders: list, vol_path: str = "") -> None:  #vers 1
    """Run a Commodore Installer script on AmiSys:; disks come from the folders (ADF files)."""
    from apps.methods import install as morosa_install, shell as morosa_shell, volumes as morosa_volumes
    dlg, out = _log_window(parent, f"Morosa Installer - {os.path.basename(script)}")
    vols = morosa_volumes.Volumes(folders)
    sh = morosa_shell.Shell(morosa.ensure_amisys(), out=out)
    sh.finder = vols.find
    sh.failat = 21
    ins = morosa_install.Installer(sh, QtUI(dlg, out))
    try:
        ins.run_file(script, vol_path)
    except _Cancel:
        out("Cancelled.")


def find_install(folder: str):  #vers 1
    """(script, folders) when folder holds the OS disks as ADF files, else None."""
    from apps.methods import volumes as morosa_volumes
    folders = [folder, os.path.join(folder, "adf"), os.path.join(folder, "ADF")]
    vols = morosa_volumes.Volumes([f for f in folders if os.path.isdir(f)])
    root = vols.find("Install3.2")
    if not root:
        return None
    script = os.path.join(root, "Install", "Install")
    return (script, folders) if os.path.isfile(script) else None


def install_os(parent, folder: str) -> None:  #vers 1
    """Install stock Workbench from a folder of OS disks into AmiSys:."""
    got = find_install(folder)
    if not got:
        QMessageBox.information(parent, "Morosa", "No Install3.2 disk found in this folder.")
        return
    run_installer(parent, got[0], got[1], "Install3.2:Install/Install")
