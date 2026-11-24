#this belongs in apps/methods/crashlog.py - Version: 1
# X-Seti - November 24 2026 - Morosa - Crash Log.

"""
Morosa Crashlog - writes Python errors and hard crashes to crash.log beside the program.
"""

##Methods list -
# _hook
# _thread_hook
# apply
# log_path

import faulthandler
import sys
import threading
import time
import traceback

from apps.methods import config

_file = None


def log_path():  #vers 1
    """crash.log in the program folder."""
    return config.ROOT / "crash.log"


def _write(text: str) -> None:  #vers 1
    try:
        with open(log_path(), "a", encoding="utf-8") as f:
            f.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n{text}")
    except OSError:
        pass


def _hook(kind, value, tb) -> None:  #vers 1
    _write("".join(traceback.format_exception(kind, value, tb)))
    sys.__excepthook__(kind, value, tb)


def _thread_hook(args) -> None:  #vers 1
    _hook(args.exc_type, args.exc_value, args.exc_traceback)


def apply() -> None:  #vers 1
    """Turn logging on or off to match the crash_log setting."""
    global _file
    if config.crash_log():
        if _file is None:
            try:
                _file = open(log_path(), "a", encoding="utf-8")
                _file.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} started ---\n")
                _file.flush()
                faulthandler.enable(file=_file, all_threads=True)
            except OSError:
                _file = None
        sys.excepthook = _hook
        threading.excepthook = _thread_hook
    else:
        faulthandler.disable()
        if _file is not None:
            _file.close()
            _file = None
        sys.excepthook = sys.__excepthook__
        threading.excepthook = threading.__excepthook__
