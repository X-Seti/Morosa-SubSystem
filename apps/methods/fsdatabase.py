#this belongs in apps/methods/fsdatabase.py - Version: 2
# X-Seti - November 23 2026 - Morosa - Host Folder Metadata Database.

"""
Fsdatabase - keeps Amiga protection bits and comments for a mounted host folder outside that folder.
"""

##Methods list -
##class FsDatabase: -
# __init__
# comment
# delete
# flush
# get
# protection
# rename
# set
# _key
# _load
# adopt
# database_dir

import hashlib
import json
import os
from pathlib import Path


def database_dir() -> Path:  #vers 1
    """Morosa/fsdatabase next to the profiles directory."""
    from apps.methods import config
    d = config.configs_dir().parent / "fsdatabase"
    d.mkdir(parents=True, exist_ok=True)
    return d


class FsDatabase:
    """One JSON file per mounted folder, keyed by the folder path; entries are keyed by relative path."""

    def __init__(self, folder: str, directory=None):  #vers 1
        root = os.path.abspath(folder)
        name = hashlib.sha1(root.encode()).hexdigest()[:16]
        self.path = Path(directory or database_dir()) / f"{os.path.basename(root) or 'root'}-{name}.json"
        self.folder = root
        self.data = {}
        self.done = set()
        self.dirty = False
        self._load()

    def _load(self) -> None:  #vers 1
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                j = json.load(f)
            self.data = j.get("entries", {})
            self.done = set(j.get("imported", []))
        except (OSError, ValueError):
            self.data = {}

    def flush(self) -> None:  #vers 1
        if not self.dirty:
            return
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({"folder": self.folder, "imported": sorted(self.done), "entries": self.data}, f, indent=1)
            self.dirty = False
        except OSError:
            pass

    def adopt(self, host_dir: str, rel_dir) -> None:  #vers 1
        """Once per folder: take protection bits and comments from an Amiberry _UAEFSDB.___ file."""
        k = self._key(tuple(rel_dir)) or "/"
        if k in self.done:
            return
        self.done.add(k)
        self.dirty = True
        try:
            with open(os.path.join(host_dir, "_UAEFSDB.___"), "rb") as f:
                raw = f.read()
        except OSError:
            self.flush()
            return
        for i in range(0, len(raw) - 599, 600):
            r = raw[i:i + 600]
            if not r[0]:
                continue
            name = r[262:519].split(b"\0")[0].decode("latin-1")
            com = r[519:600].split(b"\0")[0].decode("latin-1")
            key = self._key(tuple(rel_dir) + (name,))
            if key in self.data:
                continue
            prot = int.from_bytes(r[1:5], "big") & 0xFF
            if prot or com:
                self.data[key] = {"prot": prot, "comment": com[:79]} if com else {"prot": prot}
        self.flush()

    @staticmethod
    def _key(rel) -> str:  #vers 1
        return "/".join(rel).lower() if not isinstance(rel, str) else rel.lower()

    def get(self, rel) -> dict:  #vers 1
        return self.data.get(self._key(rel), {})

    def protection(self, rel) -> int:  #vers 1
        return int(self.get(rel).get("prot", 0))

    def comment(self, rel) -> str:  #vers 1
        return self.get(rel).get("comment", "")

    def set(self, rel, prot=None, comment=None) -> None:  #vers 1
        e = self.data.setdefault(self._key(rel), {})
        if prot is not None:
            e["prot"] = int(prot) & 0xFF
        if comment is not None:
            e["comment"] = comment[:79]
        if not e.get("prot") and not e.get("comment"):
            self.data.pop(self._key(rel), None)
        self.dirty = True
        self.flush()

    def delete(self, rel) -> None:  #vers 1
        k = self._key(rel)
        gone = [x for x in self.data if x == k or x.startswith(k + "/")]
        for x in gone:
            del self.data[x]
        if gone:
            self.dirty = True
            self.flush()

    def rename(self, old, new) -> None:  #vers 1
        a, b = self._key(old), self._key(new)
        moved = {x: v for x, v in self.data.items() if x == a or x.startswith(a + "/")}
        for x in moved:
            del self.data[x]
        for x, v in moved.items():
            self.data[b + x[len(a):]] = v
        if moved:
            self.dirty = True
            self.flush()
