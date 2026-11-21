#this belongs in apps/methods/dos.py - Version: 1
# X-Seti - November 17 2026 - Morosa - Morosa AmigaDOS Script Reader.

"""
Morosa AmigaDOS Script Reader - parses AmigaDOS shell scripts (Execute scripts) and lists their steps; nothing is run.
"""

##Methods list -
# is_dos_script
# parse
# render
# volumes

import re

COMMANDS = {
    "copy", "delete", "makedir", "protect", "assign", "setenv", "set", "echo", "ask", "run", "execute", "unzip",
    "lha", "lzx", "wait", "quit", "cpu", "resident", "path", "rename", "makelink", "filenote", "type", "cd", "dir",
    "if", "else", "endif", "skip", "lab", "endskip", "failat", "stack", "version", "avail", "join", "list", "which",
    "unsetenv", "unset", "getenv", "newshell", "ed", "more", "iconx", "loadwb", "mount", "binddrivers", "setpatch",
    "addbuffers", "fault", "date", "sort", "search", "info", "relabel", "format", "diskcopy", "install", "ask",
}
SHOWN = {"copy", "delete", "makedir", "protect", "assign", "setenv", "run", "execute", "unzip", "lha", "lzx", "rename",
         "makelink", "mount", "resident", "path", "cd", "relabel", "format", "install", "loadwb"}


def is_dos_script(text: str) -> bool:  #vers 1
    """True when most lines are AmigaDOS commands, labels or comments."""
    lines = [ln.strip() for ln in text.splitlines()[:200] if ln.strip() and not ln.strip().startswith(";")]
    if not lines or lines[0].startswith("("):
        return False
    hits = sum(1 for ln in lines if ln.split()[0].lower().lstrip(">").lstrip(".") in COMMANDS or ln.startswith("."))
    return hits >= max(2, len(lines) // 3)


def parse(text: str) -> list:  #vers 1
    """[(depth, command, arguments)] with if/endif nesting; ; comments dropped."""
    out, depth = [], 0
    for raw in text.splitlines():
        ln = raw.split(";", 1)[0].strip() if not raw.lstrip().lower().startswith("echo") else raw.strip()
        if not ln:
            continue
        parts = ln.split(None, 1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""
        if cmd in ("else",):
            out.append((max(depth - 1, 0), cmd, arg))
            continue
        if cmd in ("endif", "endskip"):
            depth = max(depth - 1, 0)
        out.append((depth, cmd, arg))
        if cmd == "if" and not arg.lower().rstrip().endswith("then"):
            depth += 1
    return out


def volumes(steps: list) -> list:  #vers 1
    """Volume names the script uses, apart from SYS and the usual system ones."""
    seen = []
    for _d, _c, arg in steps:
        for m in re.finditer(r"([A-Za-z0-9_\-]+):", arg):
            v = m.group(1)
            if v.lower() not in ("sys", "c", "s", "libs", "devs", "l", "env", "envarc", "t", "ram", "fonts", "prefs", "nil") and v not in seen:
                seen.append(v)
    return seen


def render(text: str) -> str:  #vers 1
    """Readable step list of an AmigaDOS script."""
    steps = parse(text)
    lines = []
    for d, cmd, arg in steps:
        if cmd in SHOWN or cmd in ("if", "else", "endif", "lab", "skip", "ask", "wait", "quit", "cpu", "echo", "setenv"):
            lines.append(f"{'  ' * d}{cmd} {arg}".rstrip())
    vols = volumes(steps)
    if vols:
        lines.append("")
        lines.append("Volumes used: " + ", ".join(v + ":" for v in vols))
    return "\n".join(lines) if lines else "No script steps found."
