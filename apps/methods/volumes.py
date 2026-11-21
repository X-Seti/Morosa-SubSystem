#this belongs in apps/methods/volumes.py - Version: 1
# X-Seti - November 17 2026 - Morosa - Morosa Volume Finder.

"""
Morosa Volume Finder - maps Amiga volume names to host folders, unpacking ADF disks on demand.
"""

##Methods list -
# Volumes
# Volumes.find
# Volumes.scan

import os
from pathlib import Path

from apps.methods import amiga_disk

CACHE = Path.home() / ".cache" / "Morosa" / "disks"


class Volumes:
    """Volume name -> folder. Sources are folders holding .adf files, or a CD root folder."""

    def __init__(self, sources: list, roots: dict = None):  #vers 1
        self.sources = list(sources)
        self.roots = {k.lower(): v for k, v in (roots or {}).items()}
        self.labels = {}
        self.scan()

    def scan(self) -> None:  #vers 1
        """Read the disk label of every ADF in the sources."""
        for src in self.sources:
            try:
                names = sorted(os.listdir(src))
            except OSError:
                continue
            for n in names:
                if n.lower().endswith(".adf"):
                    p = os.path.join(src, n)
                    try:
                        lab = amiga_disk.info(p)[0]["name"]
                    except (amiga_disk.DiskError, OSError, IndexError, KeyError):
                        continue
                    self.labels.setdefault(lab.lower(), p)

    def find(self, name: str):  #vers 1
        """Host folder for a volume name, or None."""
        k = name.rstrip(":").lower()
        if k in self.roots:
            return self.roots[k]
        adf = self.labels.get(k)
        if not adf:
            return None
        dest = CACHE / k
        if not dest.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
            amiga_disk.extract(adf, str(dest))
        return str(dest)
