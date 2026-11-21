# Morosa

Amiga compatibility subsystem for Python. Two parts:

- **OS layer** (`apps/core`, `apps/methods`): runs m68k Amiga programs on a built-in 68000-68060 CPU emulator with reimplemented libraries. No ROM needed.
- **Hardware** (`apps/hardware`): custom chips and machine presets (A1000 to A4000T, CD32, CDTV). Boots Kickstart ROMs you supply.

Run the settings editor: `python -m apps`. Needs PyQt6.
