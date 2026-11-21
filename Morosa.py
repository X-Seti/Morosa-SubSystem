#!/usr/bin/env python3
#this belongs in root /Morosa.py - Version: 1
# X-Seti - November 17 2026 - Morosa - Launcher.

"""
Morosa launcher - run with python Morosa.py to open the settings editor.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from apps.gui.settings import main

raise SystemExit(main())
