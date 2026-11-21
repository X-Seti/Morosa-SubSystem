#this belongs in apps/methods/installer.py - Version: 1
# X-Seti - November 17 2026 - Morosa - Morosa Installer Script Reader.

"""
Morosa Installer Script Reader - parses Commodore Installer scripts (Lisp style) and lists their steps; nothing is run.
"""

##Methods list -
# is_installer
# parse
# render
# steps
# tokens
# _text

import re

ACTIONS = {
    "copyfiles", "copylib", "makedir", "startup", "run", "execute", "delete", "rename", "tooltype", "textfile",
    "makeassign", "protect", "foreach", "welcome", "message", "working", "complete", "abort", "exit", "set",
    "askdir", "askfile", "askstring", "asknumber", "askchoice", "askoptions", "askbool", "askdisk", "user",
    "transcript", "debug", "database", "getdevice", "getdiskspace", "getenv", "getsize", "getsum", "getversion",
    "icon", "patmatch", "reboot", "rexx", "textfile",
}
QUIET = {"set", "getenv", "getsize", "getsum", "getversion", "patmatch", "getdevice", "getdiskspace", "debug",
         "user", "transcript", "database", "complete", "working"}
KEYS = ("source", "dest", "newname", "prompt", "help", "pattern", "choices", "default", "files", "infos", "all",
        "confirm", "safe", "optional", "fail", "nofail", "oknodelete", "delopts", "assigns", "disk", "range",
        "back", "newpath", "command", "prompt", "type")


class Str(str):
    """A quoted string in the script, apart from a bare symbol."""


def tokens(text: str):  #vers 1
    """Parentheses, strings, numbers and symbols; comments dropped."""
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
        elif c == ";":
            while i < n and text[i] != "\n":
                i += 1
        elif c in "()":
            yield c
            i += 1
        elif c in "\"'":
            q, j, out = c, i + 1, []
            while j < n and text[j] != q:
                if text[j] == "\\" and j + 1 < n:
                    out.append({"n": "\n", "t": "\t", "\\": "\\", '"': '"', "'": "'"}.get(text[j + 1], text[j + 1]))
                    j += 2
                else:
                    out.append(text[j])
                    j += 1
            yield Str("".join(out))
            i = j + 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in "()\";":
                j += 1
            yield text[i:j]
            i = j


def parse(text: str) -> list:  #vers 1
    """Nested lists of Str, symbols and numbers; unbalanced parentheses are closed at the end."""
    stack, cur = [], []
    for t in tokens(text):
        if t == "(":
            stack.append(cur)
            cur = []
        elif t == ")":
            if stack:
                done, cur = cur, stack.pop()
                cur.append(done)
        else:
            cur.append(t)
    while stack:
        done, cur = cur, stack.pop()
        cur.append(done)
    return cur


def is_installer(text: str) -> bool:  #vers 1
    """True when the text looks like an Installer script."""
    body = re.sub(r";[^\n]*", "", text)
    s = body.lstrip()[:4000].lower()
    return s.startswith("(") and bool(re.search(r"\((copyfiles|welcome|set|procedure|makedir|startup|complete|askdir|askchoice)\b", s))


def _text(node) -> str:  #vers 1
    """Node as short text: strings plain, expressions kept as written."""
    if isinstance(node, Str):
        return str(node)
    if isinstance(node, list):
        return "(" + " ".join(_text(x) if not isinstance(x, Str) else '"' + x + '"' for x in node) + ")"
    return str(node)


def _args(form: list) -> dict:  #vers 1
    """Keyword arguments of an action: (source x) (dest y) (all) ..."""
    out = {}
    for item in form[1:]:
        if isinstance(item, list) and item and not isinstance(item[0], list) and str(item[0]).lower() in KEYS:
            out[str(item[0]).lower()] = " ".join(_text(x) for x in item[1:]) or "yes"
    return out


def steps(tree: list, depth: int = 0, cond: str = "") -> list:  #vers 1
    """[(depth, action, detail)] in script order; conditions appear as their own lines."""
    out = []
    for node in tree:
        if not isinstance(node, list) or not node or isinstance(node[0], list):
            if isinstance(node, list) and node:
                out += steps(node, depth, cond)
            continue
        head = str(node[0]).lower()
        if head == "if":
            out.append((depth, "if", _text(node[1]) if len(node) > 1 else ""))
            for part in node[2:]:
                out += steps([part], depth + 1, cond)
        elif head in ("while", "until", "select", "trap"):
            out.append((depth, head, _text(node[1]) if len(node) > 1 else ""))
            out += steps(node[2:], depth + 1, cond)
        elif head == "procedure":
            out.append((depth, "procedure", str(node[1]) if len(node) > 1 else ""))
            out += steps(node[2:], depth + 1, cond)
        elif head in ACTIONS and head not in QUIET:
            a = _args(node)
            plain = [_text(x) for x in node[1:] if not (isinstance(x, list) and x and str(x[0]).lower() in KEYS)]
            detail = " ".join(plain)
            if a:
                detail = (detail + "  " if detail else "") + "  ".join(f"{k}={v}" for k, v in a.items())
            out.append((depth, head, detail))
            out += steps([x for x in node[1:] if isinstance(x, list) and x and isinstance(x[0], list)], depth + 1, cond)
        elif head in QUIET:
            continue
        else:
            out += steps(node[1:], depth, cond)
    return out


def render(text: str) -> str:  #vers 1
    """Readable step list of an Installer script."""
    lines = [f"{'  ' * d}{act} {det}".rstrip() for d, act, det in steps(parse(text))]
    return "\n".join(lines) if lines else "No installer steps found."
