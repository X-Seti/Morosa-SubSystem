#this belongs in apps/methods/install.py - Version: 1
# X-Seti - November 17 2026 - Morosa - Morosa Commodore Installer Engine.

"""
Morosa Installer Engine - runs Commodore Installer scripts against AmiSys: through the AmigaDOS shell.
"""

##Methods list -
# Installer
# Installer.call
# Installer.ev
# Installer.f_copyfiles
# Installer.f_copylib
# Installer.f_foreach
# Installer.run_file
# Installer.run_text
# ScriptUI
# fmt

import os
import re
import shutil

from apps.methods import lzw_z, installer as morosa_installer
from apps.methods.installer import Str
from apps.methods.shell import DosError, Shell, pattern_regex

OPTS = {"prompt", "help", "source", "dest", "newname", "choices", "all", "files", "pattern", "infos", "fonts",
        "nogauge", "safe", "optional", "confirm", "compression", "delopts", "noposition", "back", "default",
        "disk", "newpath", "assigns", "range", "command", "type", "fail", "nofail", "oknodelete", "quiet",
        "append", "include", "dynopt", "setdefaulttool", "setposition", "setstack", "settooltype", "swapcolors",
        "resident", "overwrite", "askuser", "force"}
SKIP_RUN_ERR = ("safe",)


class Exit(Exception):
    """exit or abort: the script ends."""

    def __init__(self, msg="", ok=True):
        super().__init__(msg)
        self.ok = ok


class ScriptUI:
    """Answers questions with the script defaults; override `answers` to steer."""

    def __init__(self, answers=None, log=print):
        self.answers = answers or {}
        self.log = log

    def _pick(self, kind, prompt, default):
        a = self.answers.get(kind)
        if callable(a):
            got = a(prompt, default)
            return default if got is None else got
        return default if a is None else a

    def ask_bool(self, prompt, help, default):  #vers 1
        return self._pick("askbool", prompt, default)

    def ask_choice(self, prompt, help, choices, default):  #vers 1
        return self._pick("askchoice", prompt, default)

    def ask_options(self, prompt, help, choices, default):  #vers 1
        return self._pick("askoptions", prompt, default)

    def ask_dir(self, prompt, help, default):  #vers 1
        return self._pick("askdir", prompt, default)

    def ask_file(self, prompt, help, default):  #vers 1
        return self._pick("askfile", prompt, default)

    def ask_string(self, prompt, help, default):  #vers 1
        return self._pick("askstring", prompt, default)

    def ask_number(self, prompt, help, default):  #vers 1
        return self._pick("asknumber", prompt, default)

    def ask_disk(self, prompt, name):  #vers 1
        return self._pick("askdisk", prompt, True)

    def message(self, text):  #vers 1
        self.log(text)

    def working(self, text):  #vers 1
        self.log(text)

    def complete(self, pct):  #vers 1
        pass

    def finish(self, text, ok):  #vers 1
        self.log(text)


def fmt(s: str, args: list) -> str:  #vers 1
    """Installer sprintf: %s, %ld, %d and %%."""
    it = iter(args)

    def sub(m):
        if m.group(0) == "%%":
            return "%"
        try:
            return str(next(it))
        except StopIteration:
            return ""
    return re.sub(r"%%|%-?\d*l?[sd]", sub, s)


def _num(v):
    if isinstance(v, int):
        return v
    try:
        return int(str(v).strip(), 0)
    except ValueError:
        return None


class Installer:
    """One Installer script run: variables, procedures, a shell on AmiSys and a UI."""

    def __init__(self, shell: Shell, ui=None, kick: int = 47):  #vers 1
        self.sh = shell
        self.ui = ui or ScriptUI(log=shell.out)
        self.vars = {"true": 1, "false": 0, "@language": "english", "@user-level": 2, "@each-name": "",
                     "@each-type": 0, "@default-dest": "", "@icon": "", "@installer-version": 43 << 16 | 3,
                     "@app-name": "", "@pretend": 0, "@ioerr": 0, "@abort-button": "Abort Install"}
        self.procs = {}
        self.onerror = None
        self.kick = kick
        self.script_dir = ""

    # ---- running ----
    def run_file(self, path: str, vol_path: str = "") -> bool:  #vers 1
        """Run a script file; vol_path is its Amiga path, used for @icon."""
        self.vars["@icon"] = vol_path
        with open(path, "rb") as f:
            return self.run_text(f.read().decode("latin-1"))

    def run_text(self, text: str) -> bool:  #vers 1
        """Run script text; returns True when it finished without abort."""
        try:
            for node in morosa_installer.parse(text):
                self.ev(node)
            self.ui.finish("Installation finished.", True)
            return True
        except Exit as e:
            if not e.ok and self.onerror is not None:
                self._run_onerror()
            self.ui.finish(str(e) or "Installation ended.", e.ok)
            return e.ok
        except DosError as e:
            self._run_onerror()
            self.ui.finish(str(e), False)
            return False

    def _run_onerror(self):  #vers 1
        body, self.onerror = self.onerror, None
        if body is not None:
            try:
                self.ev(body)
            except (Exit, DosError):
                pass

    # ---- evaluation ----
    def var(self, name):  #vers 1
        k = name.lower()
        if k in self.vars:
            return self.vars[k]
        return 0 if re.fullmatch(r"-?\d+|0x[0-9a-f]+|\$[0-9a-f]+", k) else ""

    def ev(self, node):  #vers 1
        """Value of a node: string, number, variable or form."""
        if isinstance(node, Str):
            return str(node)
        if isinstance(node, str):
            n = _num(node.replace("$", "0x", 1) if node.startswith("$") else node)
            return n if n is not None else self.var(node)
        if not node:
            return 0
        head = node[0]
        if isinstance(head, list):
            r = 0
            for n in node:
                r = self.ev(n)
            return r
        if isinstance(head, Str) or _num(head) is not None:
            r = 0
            for n in node:
                r = self.ev(n)
            return r
        return self.call(head.lower(), node[1:], head)

    def truth(self, v) -> bool:  #vers 1
        n = _num(v)
        return bool(n) if n is not None else bool(v)

    def text(self, args) -> str:  #vers 1
        return "".join(str(self.ev(a)) for a in args)

    def opts(self, args) -> tuple:  #vers 1
        """Split args into keyword options (name -> arg list) and positional nodes."""
        o, pos = {}, []
        for a in args:
            if isinstance(a, list) and a and isinstance(a[0], str) and not isinstance(a[0], Str) and a[0].lower() in OPTS:
                o[a[0].lower()] = a[1:]
            else:
                pos.append(a)
        return o, pos

    def host(self, apath: str) -> str:  #vers 1
        return self.sh.to_host(apath)

    def call(self, name, args, raw):  #vers 1
        """Run a special form, builtin or user procedure."""
        f = getattr(self, "f_" + name.replace("-", "_").replace("<>", "ne").replace("<=", "le").replace(">=", "ge"), None)
        if name in self.procs:
            return self.call_proc(name, args)
        if f is not None:
            return f(args)
        sym = {"+": self.f_add, "-": self.f_sub, "*": self.f_mul, "/": self.f_div, "=": self.f_eq, "<>": self.f_ne,
               "<": self.f_lt, ">": self.f_gt, "<=": self.f_le, ">=": self.f_ge}.get(name)
        if sym:
            return sym(args)
        if name in self.vars and isinstance(self.vars[name], str):
            return fmt(self.vars[name], [self.ev(a) for a in args])
        if name in self.vars:
            return self.vars[name]
        raise DosError(f"Installer: unknown function {raw}", 20)

    def call_proc(self, name, args):  #vers 1
        params, body = self.procs[name]
        vals = [self.ev(a) for a in args]
        saved = {p.lower(): self.vars.get(p.lower()) for p in params}
        for p, v in zip(params, vals):
            self.vars[p.lower()] = v
        for p in params[len(vals):]:
            self.vars[p.lower()] = 0
        try:
            r = 0
            for b in body:
                r = self.ev(b)
            return r
        finally:
            for p, v in saved.items():
                if v is None:
                    self.vars.pop(p, None)
                else:
                    self.vars[p] = v

    # ---- flow ----
    def f_set(self, a):  #vers 1
        r = 0
        for i in range(0, len(a) - 1, 2):
            r = self.ev(a[i + 1])
            self.vars[str(a[i]).lower()] = r
        return r

    def f_if(self, a):  #vers 1
        if self.truth(self.ev(a[0])):
            return self.ev(a[1]) if len(a) > 1 else 0
        return self.ev(a[2]) if len(a) > 2 else 0

    def f_while(self, a):  #vers 1
        n = 0
        while self.truth(self.ev(a[0])):
            for b in a[1:]:
                self.ev(b)
            n += 1
            if n > 1000000:
                raise Exit("loop", False)
        return 0

    def f_until(self, a):  #vers 1
        while not self.truth(self.ev(a[0])):
            for b in a[1:]:
                self.ev(b)
        return 0

    def f_select(self, a):  #vers 1
        k = _num(self.ev(a[0])) or 0
        if os.environ.get("MOROSA_TRACE"):
            self.sh.out(f"[select {k} of {len(a) - 1}]")
        return self.ev(a[1 + k]) if 0 <= k < len(a) - 1 else 0

    def f_procedure(self, a):  #vers 1
        name = str(a[0]).lower()
        params, body, i = [], list(a[1:]), 0
        while i < len(body) and isinstance(body[i], str) and not isinstance(body[i], Str):
            params.append(body[i])
            i += 1
        self.procs[name] = (params, body[i:])
        return 0

    def f_onerror(self, a):  #vers 1
        self.onerror = list(a)
        return 0

    def f_trap(self, a):  #vers 1
        try:
            for b in a[1:]:
                self.ev(b)
        except DosError:
            pass
        return 0

    def f_abort(self, a):  #vers 1
        raise Exit(self.text(a), False)

    def f_exit(self, a):  #vers 1
        o, pos = self.opts(a)
        raise Exit(self.text(pos), True)

    def f_user(self, a):  #vers 1
        self.vars["@user-level"] = _num(self.ev(a[0])) or 0
        return 0

    def f_welcome(self, a):  #vers 1
        self.ui.message(self.text(a))
        return 0

    def f_message(self, a):  #vers 1
        o, pos = self.opts(a)
        self.ui.message(self.text(pos))
        return 0

    def f_working(self, a):  #vers 1
        self.ui.working(self.text(a))
        return 0

    def f_complete(self, a):  #vers 1
        self.ui.complete(_num(self.ev(a[0])) or 0)
        return 0

    def f_delopts(self, a):  #vers 1
        return 0

    def f_debug(self, a):  #vers 1
        return 0

    def f_effect(self, a):  #vers 1
        return 0

    def f_transcript(self, a):  #vers 1
        return 0

    def f_reboot(self, a):  #vers 1
        self.ui.message("Reboot requested; not needed for AmiSys.")
        return 0

    def f_startup(self, a):  #vers 1
        o, pos = self.opts(a)
        name = str(self.ev(pos[0])) if pos else ""
        cmds = "".join(str(self.ev(x)) + "\n" for x in o.get("command", []))
        us = os.path.join(self.sh.to_host("s:"), "User-Startup")
        os.makedirs(os.path.dirname(us), exist_ok=True)
        with open(us, "a", encoding="latin-1") as f:
            f.write(f"; BEGIN {name}\n{cmds}; END {name}\n")
        return 0

    def f_textfile(self, a):  #vers 1
        o, _p = self.opts(a)
        dest = self.host(str(self.ev(o["dest"][0])))
        body = self.text(o["include"]) if "include" in o else ""
        body += self.text(o["append"]) if "append" in o else ""
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        with open(dest, "a" if "include" not in o else "w", encoding="latin-1") as f:
            f.write(body)
        return 0

    # ---- strings and numbers ----
    def f_cat(self, a):  #vers 1
        return self.text(a)

    def f_strlen(self, a):  #vers 1
        return len(str(self.ev(a[0])))

    def f_substr(self, a):  #vers 1
        s, st = str(self.ev(a[0])), _num(self.ev(a[1])) or 0
        n = _num(self.ev(a[2])) if len(a) > 2 else None
        return s[st:] if n is None else s[st:st + n]

    def f_tackon(self, a):  #vers 1
        p, n = str(self.ev(a[0])), str(self.ev(a[1]))
        if not p or p.endswith((":", "/")):
            return p + n
        return p + "/" + n

    def f_fileonly(self, a):  #vers 1
        return re.split(r"[:/]", str(self.ev(a[0])))[-1]

    def f_pathonly(self, a):  #vers 1
        s = str(self.ev(a[0]))
        i = max(s.rfind("/"), s.rfind(":"))
        if i < 0:
            return ""
        return s[:i] if s[i] == "/" else s[:i + 1]

    def f_expandpath(self, a):  #vers 1
        s = str(self.ev(a[0]))
        if ":" not in s:
            return s
        vol, rest = s.split(":", 1)
        return (vol + ":" + rest) if vol.lower() not in self.sh.assigns else self._assign_path(vol, rest)

    def _assign_path(self, name, rest):  #vers 1
        v, comps = self.sh.assigns[name.lower()][0]
        base = "/".join(comps)
        label = self._vol_label(v)
        return label + ":" + "/".join(x for x in (base, rest) if x)

    def _vol_label(self, vol):  #vers 1
        if vol.startswith("_a_"):
            return vol[3:]
        return {"sys": "SYS", "amisys": "AmiSys", "ram": "RAM"}.get(vol, vol)

    def f_patmatch(self, a):  #vers 1
        return 1 if pattern_regex(str(self.ev(a[0]))).match(str(self.ev(a[1]))) else 0

    def f_getenv(self, a):  #vers 1
        return self.sh.env.get(str(self.ev(a[0])).lower(), "")

    def f_in(self, a):  #vers 1
        return (_num(self.ev(a[0])) or 0) & (1 << (_num(self.ev(a[1])) or 0)) and 1 or 0

    def f_and(self, a):  #vers 1
        return 1 if all(self.truth(self.ev(x)) for x in a) else 0

    def f_or(self, a):  #vers 1
        return 1 if any(self.truth(self.ev(x)) for x in a) else 0

    def f_not(self, a):  #vers 1
        return 0 if self.truth(self.ev(a[0])) else 1

    def f_xor(self, a):  #vers 1
        return 1 if self.truth(self.ev(a[0])) != self.truth(self.ev(a[1])) else 0

    def f_bitand(self, a):  #vers 1
        r = -1
        for x in a:
            r &= _num(self.ev(x)) or 0
        return r

    def f_bitor(self, a):  #vers 1
        r = 0
        for x in a:
            r |= _num(self.ev(x)) or 0
        return r

    def f_bitxor(self, a):  #vers 1
        return (_num(self.ev(a[0])) or 0) ^ (_num(self.ev(a[1])) or 0)

    def f_bitnot(self, a):  #vers 1
        return ~(_num(self.ev(a[0])) or 0)

    def f_shiftleft(self, a):  #vers 1
        return (_num(self.ev(a[0])) or 0) << (_num(self.ev(a[1])) or 0)

    def f_shiftright(self, a):  #vers 1
        return (_num(self.ev(a[0])) or 0) >> (_num(self.ev(a[1])) or 0)

    def _ints(self, a):  #vers 1
        return [_num(self.ev(x)) or 0 for x in a]

    def f_add(self, a):  #vers 1
        return sum(self._ints(a))

    def f_sub(self, a):  #vers 1
        v = self._ints(a)
        return v[0] - sum(v[1:]) if len(v) > 1 else -v[0]

    def f_mul(self, a):  #vers 1
        r = 1
        for x in self._ints(a):
            r *= x
        return r

    def f_div(self, a):  #vers 1
        v = self._ints(a)
        return int(v[0] / v[1]) if v[1] else 0

    def _cmp(self, a):  #vers 1
        x, y = self.ev(a[0]), self.ev(a[1])
        nx, ny = _num(x), _num(y)
        return (nx, ny) if nx is not None and ny is not None else (str(x).lower(), str(y).lower())

    def f_eq(self, a):  #vers 1
        x, y = self._cmp(a)
        return 1 if x == y else 0

    def f_ne(self, a):  #vers 1
        x, y = self._cmp(a)
        return 1 if x != y else 0

    def f_lt(self, a):  #vers 1
        x, y = self._cmp(a)
        return 1 if x < y else 0

    def f_gt(self, a):  #vers 1
        x, y = self._cmp(a)
        return 1 if x > y else 0

    def f_le(self, a):  #vers 1
        x, y = self._cmp(a)
        return 1 if x <= y else 0

    def f_ge(self, a):  #vers 1
        x, y = self._cmp(a)
        return 1 if x >= y else 0

    # ---- system ----
    def f_getversion(self, a):  #vers 1
        if not a:
            return (self.kick << 16) | 1
        o, pos = self.opts(a)
        p = str(self.ev(pos[0]))
        try:
            h = self.host(p)
            with open(h, "rb") as f:
                m = re.search(rb"\$VER: \S+ (\d+)\.(\d+)", f.read())
            return (int(m.group(1)) << 16 | int(m.group(2))) if m else 0
        except (OSError, DosError):
            return 0

    def f_database(self, a):  #vers 1
        k = str(self.ev(a[0])).lower()
        return {"total-mem": 64 * 1024 * 1024, "vblank": 50, "cpu": self.sh.cpu, "graphics-mem": 2 * 1024 * 1024,
                "chip-mem": 2 * 1024 * 1024}.get(k, "")

    def f_exists(self, a):  #vers 1
        o, pos = self.opts(a)
        p = str(self.ev(pos[0]))
        try:
            h = self.host(p)
        except DosError:
            return 0
        return 2 if os.path.isdir(h) else 1 if os.path.exists(h) else 0

    def f_getsize(self, a):  #vers 1
        try:
            return os.path.getsize(self.host(str(self.ev(a[0]))))
        except (OSError, DosError):
            return -1

    def f_getdiskspace(self, a):  #vers 1
        return shutil.disk_usage(self.sh.amisys).free

    def f_getassign(self, a):  #vers 1
        name = str(self.ev(a[0])).rstrip(":")
        kinds = str(self.ev(a[1])).lower() if len(a) > 1 else "a"
        low = name.lower()
        if "a" in kinds and low in self.sh.assigns:
            return self._assign_path(low, "")
        if "v" in kinds and (low in self.sh.vols or self.sh.known(name)):
            return self._vol_label(low) if low in ("sys", "ram") else name
        if "d" in kinds and re.fullmatch(r"df\d|dh\d", low):
            return ""
        return ""

    def f_getdevice(self, a):  #vers 1
        n = str(self.ev(a[0])).split(":")[0]
        return "DH0" if n.lower() in ("sys", "amisys") else n

    def f_makeassign(self, a):  #vers 1
        name = str(self.ev(a[0])).rstrip(":").lower()
        if len(a) > 1 and not (isinstance(a[1], list) and a[1] and str(a[1][0]).lower() in OPTS):
            tgt = str(self.ev(a[1]))
            if tgt:
                vol = f"_a_{name}"
                self.sh.vols[vol] = self.host(tgt)
                self.sh.assigns[name] = [(vol, [])]
                return 0
        self.sh.assigns.pop(name, None)
        return 0

    def f_makedir(self, a):  #vers 1
        o, pos = self.opts(a)
        p = self.host(str(self.ev(pos[0])))
        os.makedirs(p, exist_ok=True)
        if "infos" in o:
            self._copy_def_info(p)
        return 0

    def _copy_def_info(self, p):  #vers 1
        return None

    def f_protect(self, a):  #vers 1
        return 0

    def f_delete(self, a):  #vers 1
        o, pos = self.opts(a)
        spec = str(self.ev(pos[0]))
        found = self.sh._expand_sources(spec)
        for h in found:
            if os.path.isdir(h):
                shutil.rmtree(h) if "all" in o else os.rmdir(h)
            else:
                os.remove(h)
            if "infos" in o and os.path.exists(h + ".info"):
                os.remove(h + ".info")
        return 0

    def f_rename(self, a):  #vers 1
        o, pos = self.opts(a)
        s, d = self.host(str(self.ev(pos[0]))), self.host(str(self.ev(pos[1])))
        if os.path.exists(s):
            os.makedirs(os.path.dirname(d) or ".", exist_ok=True)
            if os.path.isdir(d):
                d = os.path.join(d, os.path.basename(s))
            shutil.move(s, d)
        return 0

    def f_run(self, a):  #vers 1
        o, pos = self.opts(a)
        line = str(self.ev(pos[0]))
        self.sh.rc = 0
        old, self.sh.failat = self.sh.failat, 100
        rc = self.sh.run_text(line)
        self.sh.failat = old
        if rc and "safe" not in o and "fail" not in o and rc >= 20:
            raise DosError(f"{line}: failed", rc)
        return rc

    f_execute = f_run

    # ---- asking ----
    def _ph(self, o):  #vers 1
        return self.text(o.get("prompt", [])), self.text(o.get("help", []))

    def f_askbool(self, a):  #vers 1
        o, _p = self.opts(a)
        p, h = self._ph(o)
        d = _num(self.ev(o["default"][0])) if "default" in o else 1
        return 1 if self.ui.ask_bool(p, h, d) else 0

    def f_askchoice(self, a):  #vers 1
        o, _p = self.opts(a)
        p, h = self._ph(o)
        ch = [str(self.ev(x)) for x in o.get("choices", [])]
        d = _num(self.ev(o["default"][0])) if "default" in o else 0
        return self.ui.ask_choice(p, h, ch, d)

    def f_askoptions(self, a):  #vers 1
        o, _p = self.opts(a)
        p, h = self._ph(o)
        ch = [str(self.ev(x)) for x in o.get("choices", [])]
        d = _num(self.ev(o["default"][0])) if "default" in o else 0
        return self.ui.ask_options(p, h, ch, d)

    def f_askdir(self, a):  #vers 1
        o, _p = self.opts(a)
        p, h = self._ph(o)
        d = str(self.ev(o["default"][0])) if "default" in o else ""
        return self.ui.ask_dir(p, h, d)

    def f_askfile(self, a):  #vers 1
        o, _p = self.opts(a)
        p, h = self._ph(o)
        d = str(self.ev(o["default"][0])) if "default" in o else ""
        return self.ui.ask_file(p, h, d)

    def f_askstring(self, a):  #vers 1
        o, _p = self.opts(a)
        p, h = self._ph(o)
        d = str(self.ev(o["default"][0])) if "default" in o else ""
        return self.ui.ask_string(p, h, d)

    def f_asknumber(self, a):  #vers 1
        o, _p = self.opts(a)
        p, h = self._ph(o)
        d = _num(self.ev(o["default"][0])) if "default" in o else 0
        return self.ui.ask_number(p, h, d)

    def f_askdisk(self, a):  #vers 1
        o, _p = self.opts(a)
        p, _h = self._ph(o)
        name = str(self.ev(o["dest"][0])).rstrip(":") if "dest" in o else ""
        if self.sh.known(name):
            return 1
        return 1 if self.ui.ask_disk(p, name) and self.sh.known(name) else 0

    # ---- files ----
    def f_foreach(self, a):  #vers 1
        folder, pat = self.host(str(self.ev(a[0]))), str(self.ev(a[1]))
        rx = pattern_regex(pat)
        try:
            names = sorted(os.listdir(folder), key=str.lower)
        except OSError:
            return 0
        for n in names:
            if rx.match(n):
                self.vars["@each-name"] = n
                self.vars["@each-type"] = 2 if os.path.isdir(os.path.join(folder, n)) else 1
                for b in a[2:]:
                    self.ev(b)
        return 0

    def _copy_one(self, src, dst, infos, unpack=False):  #vers 2
        os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
        if os.path.lexists(dst) and os.path.isdir(dst):
            shutil.rmtree(dst)
        if unpack:
            with open(src, "rb") as f, open(dst, "wb") as g:
                g.write(lzw_z.decompress(f.read()))
        else:
            shutil.copyfile(src, dst)
        if infos and os.path.isfile(src + ".info"):
            shutil.copyfile(src + ".info", dst + ".info")

    def _copy_dir(self, src, dst, o, rx, allsub, infos):  #vers 1
        os.makedirs(dst, exist_ok=True)
        for e in sorted(os.listdir(src), key=str.lower):
            s = os.path.join(src, e)
            if rx and not rx.match(e):
                continue
            d = os.path.join(dst, self.sh._find(dst, e) or e)
            if os.path.isdir(s):
                if allsub or rx:
                    self._copy_dir(s, d, o, None, True, infos)
            else:
                self._copy_one(s, d, infos)

    def f_copyfiles(self, a):  #vers 1
        o, _p = self.opts(a)
        src = self.host(str(self.ev(o["source"][0])))
        dest = str(self.ev(o["dest"][0])) if "dest" in o else ""
        dst = self.host(dest)
        if not os.path.lexists(src):
            if "nofail" in [str(self.ev(x)).lower() for x in o.get("optional", [])] or "nofail" in o:
                return 0
            raise DosError(f"Can't find {self.ev(o['source'][0])}", 20)
        if os.environ.get("MOROSA_TRACE"):
            self.sh.out(f"[copyfiles {self.ev(o['source'][0])} -> {dest} {sorted(o)}]")
        infos = "infos" in o
        newname = str(self.ev(o["newname"][0])) if "newname" in o else None
        if os.path.isdir(src):
            rx = pattern_regex(str(self.ev(o["pattern"][0]))) if "pattern" in o else None
            if "choices" in o:
                names = {str(self.ev(x)).lower() for x in o["choices"]}
                sel = self.ui.ask_options(*self._ph(o), [str(self.ev(x)) for x in o["choices"]], -1)
                chosen = {n for i, n in enumerate(sorted(names)) if sel == -1 or sel & (1 << i)}
                rx = re.compile("^(" + "|".join(re.escape(n) for n in chosen) + ")$", re.I) if chosen else re.compile("^$")
            self._copy_dir(src, dst if newname is None else os.path.join(dst, newname), o, rx, "all" in o, infos)
        else:
            os.makedirs(dst, exist_ok=True)
            leaf = newname or os.path.basename(src)
            self._copy_one(src, os.path.join(dst, self.sh._find(dst, leaf) or leaf), infos, "compression" in o)
        return 0

    def f_copylib(self, a):  #vers 1
        o, _p = self.opts(a)
        src = self.host(str(self.ev(o["source"][0])))
        dst = self.host(str(self.ev(o["dest"][0])))
        name = str(self.ev(o["newname"][0])) if "newname" in o else os.path.basename(src)
        if not os.path.isfile(src):
            raise DosError(f"Can't find {self.ev(o['source'][0])}", 20)
        target = os.path.join(dst, name)
        if os.path.isfile(target) and self._ver(src) < self._ver(target):
            return 0
        os.makedirs(dst, exist_ok=True)
        shutil.copyfile(src, target)
        return 0

    def _ver(self, path):  #vers 1
        try:
            with open(path, "rb") as f:
                m = re.search(rb"\$VER: \S+ (\d+)\.(\d+)", f.read())
            return (int(m.group(1)), int(m.group(2))) if m else (0, 0)
        except OSError:
            return (0, 0)
