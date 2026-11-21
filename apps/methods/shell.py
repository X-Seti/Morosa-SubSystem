#this belongs in apps/methods/shell.py - Version: 2
# X-Seti - November 17 2026 - Morosa - Morosa AmigaDOS Shell.

"""
Morosa AmigaDOS Shell - runs AmigaDOS scripts natively: volumes and assigns map to host folders.
"""

##Methods list -
# Shell
# Shell.cmd_assign
# Shell.cmd_copy
# Shell.cmd_cpu
# Shell.cmd_delete
# Shell.cmd_makedir
# Shell.cmd_rename
# Shell.cmd_unzip
# Shell.run_file
# Shell.run_text
# Shell.known
# Shell.to_host
# match
# pattern_regex
# split_args
# split_redirect

import fnmatch
import os
import re
import shutil
import tempfile
import zipfile

WILD = set("#?~(|)%")
KEYWORDS = {"to", "all", "quiet", "clone", "force", "nopro", "dates", "com", "nofilenote", "buf", "noreq"}


class Abort(Exception):
    """The user cancelled, or the script stopped for good."""


class DosError(Exception):
    """An AmigaDOS error with its return code."""

    def __init__(self, msg, rc=20):
        super().__init__(msg)
        self.rc = rc


def split_redirect(line: str) -> tuple:  #vers 1
    """Line without its >target redirection, and the target."""
    m = re.search(r'(?:^|\s)>\s*("[^"]*"|\S+)', line)
    if not m:
        return line, ""
    return line[:m.start()] + line[m.end():], m.group(1).strip('"')


def pattern_regex(pat: str):  #vers 2
    """AmigaDOS pattern (#? ? #x (a|b) ~x) as a compiled case-insensitive regex."""
    pos = 0

    def alt():
        nonlocal pos
        parts = [seq()]
        while pos < len(pat) and pat[pos] == "|":
            pos += 1
            parts.append(seq())
        return "|".join(parts)

    def seq():
        out = []
        while pos < len(pat) and pat[pos] not in "|)":
            out.append(atom())
        return "".join(out)

    def atom():
        nonlocal pos
        c = pat[pos]
        pos += 1
        if c == "#" and pos < len(pat):
            return f"(?:{atom()})*"
        if c == "~" and pos < len(pat):
            return f"(?!(?:{atom()})$).*"
        if c == "?":
            return "."
        if c == "%":
            return ""
        if c == "(":
            r = alt()
            if pos < len(pat) and pat[pos] == ")":
                pos += 1
            return f"(?:{r})"
        return re.escape(c)

    rx = ""
    while pos < len(pat):
        rx += alt()
        if pos < len(pat):
            rx += re.escape(pat[pos])
            pos += 1
    return re.compile("^(?:" + rx + ")$", re.IGNORECASE | re.DOTALL)


def match(pat: str, name: str) -> bool:  #vers 1
    """True when name matches the AmigaDOS pattern."""
    return bool(pattern_regex(pat).match(name))


def split_args(line: str) -> list:  #vers 1
    """Words of a command line; quotes group; redirections like >NIL: are dropped."""
    out, cur, q, i = [], "", False, 0
    started = False
    while i < len(line):
        c = line[i]
        if c == '"':
            q = not q
            started = True
        elif c.isspace() and not q:
            if started:
                out.append(cur)
                cur, started = "", False
        else:
            cur += c
            started = True
        i += 1
    if started:
        out.append(cur)
    return [w for w in out if not (w.startswith(">") or w.startswith("<"))]


class Shell:
    """One AmigaDOS process: current directory, variables, volumes, assigns and a return code."""

    def __init__(self, amisys: str, out=print, ask=None, volume=None, cpu: str = "68020", wait=None):  #vers 1
        self.amisys = amisys
        self.out = out
        self.ask = ask or (lambda prompt: False)
        self.volume = volume or (lambda name: None)
        self.cpu = cpu
        self.wait = wait or (lambda secs: None)
        self.vols = {"sys": amisys, "amisys": amisys}
        self.assigns = {}
        self.env = {}
        self.vars = {}
        self.cwd = ("sys", [])
        self.finder = None
        self.model = "A1200"
        self.rc = 0
        self.failat = 10
        self.ram = tempfile.mkdtemp(prefix="morosa_ram_")
        self.vols["ram"] = self.ram
        for a, d in (("c", "C"), ("s", "S"), ("libs", "Libs"), ("devs", "Devs"), ("l", "L"), ("fonts", "Fonts"),
                     ("t", "T"), ("prefs", "Prefs"), ("classes", "Classes"), ("locale", "Locale")):
            self.assigns[a] = [("sys", [d])]

    # ---- paths ----
    def _find(self, folder: str, name: str):  #vers 1
        """Existing entry of folder matching name in any letter case, else None."""
        try:
            if os.path.lexists(os.path.join(folder, name)):
                return name
            low = name.lower()
            for e in os.listdir(folder):
                if e.lower() == low:
                    return e
        except OSError:
            pass
        return None

    def _root(self, vol: str) -> str:  #vers 1
        """Host folder of a volume name; asks for the disk when it is not mounted."""
        v = vol.lower()
        if v in self.vols:
            return self.vols[v]
        if v == "nil":
            return os.devnull
        if v in self.assigns:
            first = self.assigns[v][0]
            return os.path.join(self._root(first[0]), *first[1])
        got = (self.finder(vol) if self.finder else None) or self.volume(vol)
        if not got:
            raise DosError(f"Volume {vol}: is not mounted", 20)
        self.vols[v] = got
        return got

    def known(self, vol: str) -> bool:  #vers 1
        """True when the volume or assign is available; mounts it silently if findable."""
        v = vol.rstrip(":").lower()
        if v in self.vols or v in self.assigns:
            return True
        got = self.finder(vol) if self.finder else None
        if got:
            self.vols[v] = got
        return bool(got)

    def to_host(self, apath: str, create: bool = False) -> str:  #vers 1
        """Host path of an Amiga path; letter case is matched against what exists."""
        if ":" in apath:
            vol, rest = apath.split(":", 1)
            if vol == "":
                vol = self.cwd[0]
            base, comps = self._root(vol), []
        else:
            vol, rest = self.cwd[0], apath
            base, comps = self._root(vol), list(self.cwd[1])
        parts = rest.split("/")
        for k, p in enumerate(parts):
            if p == "":
                if k < len(parts) - 1 or (k == 0 and rest.startswith("/")):
                    if comps:
                        comps.pop()
                continue
            comps.append(p)
        cur = base
        for k, c in enumerate(comps):
            real = self._find(cur, c)
            cur = os.path.join(cur, real if real is not None else c)
        return cur

    # ---- running ----
    def expand(self, line: str) -> str:  #vers 1
        """$name from variables and environment."""
        def sub(m):
            n = m.group(1).lower()
            return str(self.vars.get(n, self.env.get(n, m.group(0))))
        return re.sub(r"\$([A-Za-z0-9_\-\.]+)", sub, line)

    def run_file(self, path: str, args: str = "") -> int:  #vers 1
        """Run a script file given by host path."""
        with open(path, "rb") as f:
            return self.run_text(f.read().decode("latin-1"), args)

    def _cond(self, words: list) -> bool:  #vers 1
        """Value of an IF condition: NOT, WARN, ERROR, FAIL, EXISTS, VAL, EQ, GT, GE."""
        neg = False
        if words and words[0].lower() == "not":
            neg, words = True, words[1:]
        w0 = words[0].lower() if words else ""
        if w0 == "warn":
            val = self.rc >= 5
        elif w0 == "error":
            val = self.rc >= 10
        elif w0 == "fail":
            val = self.rc >= 20
        elif w0 == "exists":
            try:
                val = os.path.exists(self.to_host(words[1])) if len(words) > 1 else False
            except DosError:
                val = False
        elif w0 == "val":
            val = (len(words) > 1 and words[1].lstrip("-").isdigit() and int(words[1]) != 0)
        elif len(words) >= 3 and words[1].lower() in ("eq", "gt", "ge"):
            a, op, b = words[0], words[1].lower(), words[2]
            try:
                a, b = float(a), float(b)
            except ValueError:
                a, b = a.lower(), b.lower()
            val = a == b if op == "eq" else a > b if op == "gt" else a >= b
        else:
            val = False
        return (not val) if neg else val

    def run_text(self, text: str, args: str = "") -> int:  #vers 1
        """Run script text: if/else/endif, lab/skip, quit, failat and the commands below."""
        lines = text.splitlines()
        if lines and lines[0].lower().startswith(".key"):
            lines = lines[1:]
        pc, depth_guard = 0, 0
        labels = {}
        for i, ln in enumerate(lines):
            p = ln.split(None, 2)
            if len(p) >= 2 and p[0].lower() == "lab":
                labels[p[1].lower()] = i

        def block_end(start):
            """Index of the else or endif that belongs to the if on line start."""
            d = 0
            for j in range(start + 1, len(lines)):
                w = lines[j].split(None, 1)
                if not w:
                    continue
                c = w[0].lower()
                if c == "if":
                    d += 1
                elif c == "endif":
                    if d == 0:
                        return j, j
                    d -= 1
                elif c == "else" and d == 0:
                    k = j
                    dd = 0
                    for m in range(j + 1, len(lines)):
                        ww = lines[m].split(None, 1)
                        if not ww:
                            continue
                        cc = ww[0].lower()
                        if cc == "if":
                            dd += 1
                        elif cc == "endif":
                            if dd == 0:
                                return k, m
                            dd -= 1
            return len(lines), len(lines)

        try:
            while pc < len(lines):
                raw = lines[pc]
                pc += 1
                code = raw if raw.lstrip().lower().startswith("echo") else raw.split(";", 1)[0]
                code = code.strip()
                if not code:
                    continue
                code, redir = split_redirect(self.expand(code))
                words = split_args(code)
                if not words:
                    continue
                cmd, rest = words[0].lower(), words[1:]
                if cmd == "if":
                    if not self._cond(rest):
                        els, end = block_end(pc - 1)
                        pc = (els + 1) if els != end else end + 1
                elif cmd == "else":
                    _e, end = block_end_from_else(lines, pc - 1)
                    pc = end + 1
                elif cmd in ("endif", "lab", "endskip"):
                    pass
                elif cmd == "skip":
                    label = next((w for w in rest if w.lower() != "back"), None)
                    if label is None:
                        nxt = [i for i in labels.values() if i >= pc]
                        pc = (min(nxt) + 1) if nxt else len(lines)
                    else:
                        tgt = labels.get(label.lower())
                        if tgt is None:
                            raise DosError(f"Label {label} not found", 20)
                        pc = tgt + 1
                    depth_guard += 1
                    if depth_guard > 100000:
                        raise Abort("script loops")
                elif cmd == "quit":
                    self.rc = int(rest[0]) if rest and rest[0].isdigit() else 0
                    return self.rc
                else:
                    self._command(cmd, rest, redir)
                    if self.rc >= self.failat:
                        self.out(f"Script stopped: {cmd} returned {self.rc}")
                        return self.rc
        except DosError as e:
            self.out(str(e))
            self.rc = e.rc
        return self.rc

    def _command(self, cmd: str, args: list, redir: str = "") -> None:  #vers 2
        """Run one command: a native one, else the Amiga program from C: through vamos."""
        self.rc = 0
        low = [w.lower() for w in args]
        if "to" in low and low.index("to") + 1 < len(args) and low[low.index("to") + 1].startswith("env:") \
                and re.split(r"[:/]", cmd)[-1] in ("amigamodel", "cpu", "guessbootdev", "avail", "version", "eval"):
            i = low.index("to")
            redir = args[i + 1]
            args = args[:i] + args[i + 2:]
        fn = getattr(self, "cmd_" + re.split(r"[:/]", cmd)[-1], None)
        saved, buf = self.out, []
        if redir:
            self.out = buf.append
        try:
            if fn is not None:
                fn(args)
            else:
                self._external(cmd, args)
        except DosError as e:
            self.out(str(e))
            self.rc = e.rc
        finally:
            self.out = saved
        if redir:
            self._redirect(redir, "\n".join(buf) + ("\n" if buf else ""))

    def _redirect(self, target: str, text: str) -> None:  #vers 1
        """Store captured output: ENV:name sets a variable, NIL: drops it, else a file."""
        t = target.lower()
        if t.startswith("nil:"):
            return
        if t.startswith("env:") or t.startswith("envarc:"):
            self.env[t.split(":", 1)[1]] = text
            return
        h = self.to_host(target)
        os.makedirs(os.path.dirname(h) or ".", exist_ok=True)
        with open(h, "w", encoding="latin-1") as f:
            f.write(text)

    def _external(self, cmd: str, args: list) -> None:  #vers 2
        """Program found on C: or by path runs on the Morosa CPU and libraries."""
        from apps.core import machine as morosa_machine
        from apps.methods import config as morosa
        try:
            c = self.to_host("c:" + cmd) if ":" not in cmd else self.to_host(cmd)
        except DosError:
            c = ""
        if not (c and os.path.isfile(c) and morosa.is_exe(c)):
            self.out(f"Unknown command {cmd}")
            self.rc = 20
            return
        buf = bytearray()
        if getattr(self, "machine", None) is None:
            self.machine = morosa_machine.Machine(self, self.model_cpu(), out=buf.extend, inp=lambda: b"")
        m = self.machine
        m.dos.out = buf.extend
        try:
            self.rc = m.run(c, " ".join(args))
        except (morosa_machine.Unimplemented, morosa_machine.Guru) as e:
            buf.extend(f"\nMorosa: {e}".encode())
            self.rc = 20
            self.machine = None
        self.out(buf.decode("latin-1").rstrip())

    def model_cpu(self) -> int:  #vers 1
        """Emulated CPU as a model number."""
        m = re.search(r"68\d\d\d", str(self.cpu))
        return int(m.group(0)) if m and int(m.group(0)) in (68000, 68010, 68020, 68030, 68040, 68060) else 68020

    # ---- commands ----
    def cmd_echo(self, a):  #vers 1
        self.out(" ".join(w for w in a if w.lower() != "noline"))

    def cmd_setenv(self, a):  #vers 1
        if len(a) >= 2:
            self.env[a[0].lower()] = " ".join(a[1:])

    cmd_set = cmd_setenv

    def cmd_unsetenv(self, a):  #vers 1
        self.env.pop(a[0].lower(), None) if a else None

    def cmd_failat(self, a):  #vers 1
        self.failat = int(a[0]) if a and a[0].isdigit() else self.failat

    def cmd_wait(self, a):  #vers 1
        n = float(a[0]) if a and a[0].replace(".", "", 1).isdigit() else 1
        unit = a[1].lower() if len(a) > 1 else "sec"
        self.wait(n * (60 if unit.startswith("min") else 1))

    def cmd_cpu(self, a):  #vers 1
        """CPU CHECK <model>: return code 0 when the emulated CPU is that model, else 5."""
        low = [w.lower() for w in a]
        if "cputype" in low:
            self.out(self.cpu)
        if "check" in low and len(a) > low.index("check") + 1:
            self.rc = 0 if a[low.index("check") + 1] == self.cpu else 5

    def cmd_resident(self, a):  #vers 1
        pass

    def cmd_amigamodel(self, a):  #vers 1
        self.out(self.model)

    def cmd_guessbootdev(self, a):  #vers 1
        self.out(":")

    def cmd_avail(self, a):  #vers 1
        self.out("67108864")

    def cmd_daccontrol(self, a):  #vers 1
        pass

    cmd_iconpos = cmd_copytooltypes = cmd_addbuffers = cmd_updatewbfiles = cmd_loadwb = cmd_binddrivers = cmd_daccontrol

    def cmd_stack(self, a):  #vers 1
        pass

    def cmd_path(self, a):  #vers 1
        pass

    def cmd_setpatch(self, a):  #vers 1
        pass

    def cmd_protect(self, a):  #vers 1
        """Flags are not stored on the host; only checks that the target exists."""
        t = [w for w in a if not w.startswith(("+", "-")) and w.lower() not in ("all", "quiet")]
        if t and "#?" not in t[0] and not os.path.exists(self.to_host(t[0])):
            self.rc = 20

    def cmd_ask(self, a):  #vers 1
        self.rc = 5 if self.ask(" ".join(a)) else 0

    def cmd_cd(self, a):  #vers 1
        if not a:
            return
        h = self.to_host(a[0])
        if not os.path.isdir(h):
            raise DosError(f"Can't find {a[0]}", 20)
        vol = a[0].split(":", 1)[0].lower() if ":" in a[0] else self.cwd[0]
        comps = [c for c in (a[0].split(":", 1)[1] if ":" in a[0] else a[0]).split("/") if c]
        self.cwd = (vol, comps if ":" in a[0] else self.cwd[1] + comps)

    def cmd_makedir(self, a):  #vers 1
        for p in a:
            if p.lower() == "all":
                continue
            h = self.to_host(p)
            if os.path.isdir(h):
                raise DosError(f"A subdirectory or file {p} already exists", 20)
            os.makedirs(h, exist_ok=True)

    def cmd_assign(self, a):  #vers 1
        words = [w for w in a if w.lower() not in ("add", "remove", "list", "exists", "defer", "path", "global")]
        low = [w.lower() for w in a]
        if not words:
            return
        name = words[0].rstrip(":").lower()
        if "remove" in low and len(words) == 1:
            self.assigns.pop(name, None)
            self.vols.pop(name, None)
        elif len(words) > 1:
            host = self.to_host(words[1])
            vol = f"_a_{name}"
            self.vols[vol] = host
            if "add" in low and name in self.assigns:
                self.assigns[name].append((vol, []))
            else:
                self.assigns[name] = [(vol, [])]

    def _expand_sources(self, spec: str) -> list:  #vers 1
        """Host paths matched by a source spec, wildcards in the last part only."""
        head, _, last = spec.rpartition("/") if "/" in spec else ("", "", spec)
        if ":" in spec and "/" not in spec:
            head, last = spec.split(":", 1)[0] + ":", spec.split(":", 1)[1]
        if any(c in last for c in WILD):
            folder = self.to_host(head if head else "")
            rx = pattern_regex(last)
            try:
                return sorted(os.path.join(folder, e) for e in os.listdir(folder) if rx.match(e))
            except OSError:
                return []
        h = self.to_host(spec)
        return [h] if os.path.lexists(h) else []

    def _put(self, src: str, dst: str, allsub: bool, quiet: bool) -> None:  #vers 1
        """Copy one file, or a directory's contents, onto dst."""
        if os.path.isdir(src):
            os.makedirs(dst, exist_ok=True)
            for e in sorted(os.listdir(src)):
                s = os.path.join(src, e)
                if os.path.isdir(s) and not allsub:
                    continue
                self._put(s, os.path.join(dst, self._find(dst, e) or e), allsub, quiet)
        else:
            os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
            shutil.copyfile(src, dst)
            if not quiet:
                self.out(f"  {os.path.basename(src)}  ..copied")

    def cmd_copy(self, a):  #vers 1
        """COPY [FROM] src... [TO] dest [ALL] [QUIET] [BUF n] [CLONE] [FORCE]."""
        pos, allsub, quiet, i, to_seen = [], False, False, 0, False
        while i < len(a):
            w, lw = a[i], a[i].lower()
            if lw == "buf":
                i += 2
                continue
            if lw == "all":
                allsub = True
            elif lw == "quiet":
                quiet = True
            elif lw == "to":
                to_seen = True
            elif lw in KEYWORDS:
                pass
            else:
                pos.append((w, to_seen))
            i += 1
        if len(pos) < 2:
            raise DosError("COPY needs a source and a destination", 20)
        dest = pos[-1][0]
        srcs = [w for w, _t in pos[:-1]]
        dhost = self.to_host(dest)
        for spec in srcs:
            found = self._expand_sources(spec)
            if not found:
                raise DosError(f"Can't open {spec}: object not found", 20)
            for s in found:
                if os.path.isdir(s):
                    target = dhost
                elif os.path.isdir(dhost) or dest.endswith((":", "/")) or len(found) > 1 or len(srcs) > 1:
                    target = os.path.join(dhost, os.path.basename(s))
                else:
                    target = dhost
                self._put(s, target, allsub, quiet)

    def cmd_delete(self, a):  #vers 1
        quiet = any(w.lower() == "quiet" for w in a)
        allsub = any(w.lower() == "all" for w in a)
        for spec in [w for w in a if w.lower() not in ("quiet", "all", "force")]:
            found = self._expand_sources(spec)
            if not found:
                self.rc = 5
                continue
            for h in found:
                try:
                    if os.path.isdir(h):
                        shutil.rmtree(h) if allsub else os.rmdir(h)
                    else:
                        os.remove(h)
                    if not quiet:
                        self.out(f"  {os.path.basename(h)}  deleted")
                except OSError as e:
                    self.out(f"Can't delete {spec}: {e.strerror}")
                    self.rc = 10

    def cmd_rename(self, a):  #vers 1
        w = [x for x in a if x.lower() not in ("from", "to", "quiet")]
        if len(w) < 2:
            raise DosError("RENAME needs two names", 20)
        src, dst = self.to_host(w[0]), self.to_host(w[1])
        if not os.path.lexists(src):
            raise DosError(f"Can't rename {w[0]}: object not found", 20)
        if os.path.isdir(dst):
            dst = os.path.join(dst, os.path.basename(src))
        shutil.move(src, dst)

    def cmd_unzip(self, a):  #vers 1
        """UNZIP [-o] file.zip [-d dest] [patterns]."""
        zipf, dest, pats, i = None, "", [], 0
        while i < len(a):
            w = a[i]
            if w == "-d" and i + 1 < len(a):
                dest = a[i + 1]
                i += 2
                continue
            if w.startswith("-"):
                i += 1
                continue
            if zipf is None:
                zipf = w
            else:
                pats.append(w)
            i += 1
        if zipf is None:
            return
        zh = self.to_host(zipf)
        if not os.path.isfile(zh):
            raise DosError(f"unzip: cannot find {zipf}", 9)
        base = self.to_host(dest) if dest else self.to_host("")
        os.makedirs(base, exist_ok=True)
        with zipfile.ZipFile(zh) as z:
            for info in z.infolist():
                name = info.filename
                if pats and not any(fnmatch.fnmatch(name, p) for p in pats):
                    continue
                cur = base
                parts = [p for p in name.split("/") if p]
                for k, p in enumerate(parts):
                    last = k == len(parts) - 1
                    real = self._find(cur, p) or p
                    cur = os.path.join(cur, real)
                    if (not last) or info.is_dir():
                        os.makedirs(cur, exist_ok=True)
                if not info.is_dir():
                    with z.open(info) as src, open(cur, "wb") as dst:
                        shutil.copyfileobj(src, dst)
        self.out(f"  {os.path.basename(zh)}  unpacked")

    def cmd_execute(self, a):  #vers 1
        if not a:
            return
        h = self.to_host(a[0])
        if not os.path.isfile(h):
            raise DosError(f"Can't open {a[0]}", 20)
        sub = Shell.__new__(Shell)
        sub.__dict__.update(self.__dict__)
        sub.rc = 0
        self.rc = sub.run_file(h, " ".join(a[1:]))


def block_end_from_else(lines: list, idx: int):  #vers 1
    """Index of the endif that closes the else on line idx."""
    d = 0
    for j in range(idx + 1, len(lines)):
        w = lines[j].split(None, 1)
        if not w:
            continue
        c = w[0].lower()
        if c == "if":
            d += 1
        elif c == "endif":
            if d == 0:
                return j, j
            d -= 1
    return len(lines), len(lines)
