#!/usr/bin/env python3
#this belongs in root /Morosa.py - Version: 3
# X-Seti - November 17 2026 - Morosa - Launcher.

"""
Morosa launcher - run with python Morosa.py to open the settings editor.
"""

import os
import sys

# Mouse capture needs pointer warping, which Wayland blocks; use XWayland unless told otherwise.
if os.environ.get("XDG_SESSION_TYPE") == "wayland" and os.environ.get("DISPLAY"):
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from apps.gui.settings import main
from apps.methods import crashlog

crashlog.apply()

raise SystemExit(main())
