#this belongs in apps/__main__.py - Version: 1
# X-Seti - November 17 2026 - Morosa - Entry point.

"""
Morosa entry point - python -m apps opens the settings editor.
"""

from apps.gui.settings import main

raise SystemExit(main())
