#this belongs in apps/hardware/floppy.py - Version: 4
# X-Seti - November 17 2026 - Morosa - Morosa Floppy Drive.

"""
Morosa Floppy - Amiga 3.5 inch drive on ADF and extended ADF images: head stepping, status lines and MFM track encode and decode.
"""

##Methods list -
# Floppy
# Floppy.control
# Floppy.eject
# Floppy.flush
# Floppy.insert
# Floppy.status
# Floppy.track_words
# Floppy.write_track
# Floppy._load_ext
# decode_track
# encode_track

import os

EXT_ID = b"UAE--ADF"
ADF_SIZE = 80 * 2 * 11 * 512
SECTORS = 11
TRACK_WORDS = 6400


def _split(data: bytes) -> list:  #vers 1
    """Odd then even halves of a block of longs, as raw 32-bit values without clocks."""
    longs = [int.from_bytes(data[i:i + 4], "big") for i in range(0, len(data), 4)]
    return [v >> 1 & 0x55555555 for v in longs] + [v & 0x55555555 for v in longs]


def _longs_to_words(longs: list) -> list:  #vers 1
    out = []
    for v in longs:
        out += [v >> 16, v & 0xFFFF]
    return out


def _clock(words: list, prev: int) -> tuple:  #vers 1
    """Insert clock bits into raw data words; prev is the last data bit written."""
    out = []
    for w in words:
        r = 0
        for i in range(15, -1, -2):
            bit = w >> (i - 1) & 1 if False else w >> (i - 1) & 1
            r_clock = 1 if (not prev and not bit) else 0
            r = r << 2 | r_clock << 1 | bit
            prev = bit
        out.append(r)
    return out, prev


def encode_track(image: bytes, cyl: int, side: int) -> list:  #vers 1
    """MFM words of one track, 11 sectors; sync words are literal 0x4489."""
    words, prev = [], 0
    track = cyl * 2 + side
    for sec in range(SECTORS):
        off = (track * SECTORS + sec) * 512
        data = image[off:off + 512].ljust(512, b"\0")
        gap, prev = _clock([0, 0], prev)
        words += gap + [0x4489, 0x4489]
        prev = 1
        info = bytes((0xFF, track, sec, SECTORS - sec))
        hdr = _split(info) + _split(bytes(16))
        hcs = 0
        for v in hdr:
            hcs ^= v
        hcs &= 0x55555555
        dat = _split(data)
        dcs = 0
        for v in dat:
            dcs ^= v
        dcs &= 0x55555555
        raw = _longs_to_words(hdr + [hcs >> 1 & 0x55555555, hcs & 0x55555555, dcs >> 1 & 0x55555555, dcs & 0x55555555] + dat)
        enc, prev = _clock(raw, prev)
        words += enc
    gap, prev = _clock([0] * (TRACK_WORDS - len(words)), prev)
    return words + gap


def _unclock(words: list) -> list:  #vers 1
    return [sum((w >> (2 * i) & 1) << i for i in range(16)) for w in words]


def _merge(odd: int, even: int) -> int:  #vers 1
    out = 0
    for i in range(16):
        out |= (odd >> i & 1) << (2 * i + 1) | (even >> i & 1) << (2 * i)
    return out


def decode_track(words: list) -> dict:  #vers 1
    """{track*11+sector: 512 bytes} for every sector with a valid header and data checksum found in words."""
    out = {}
    n = len(words)
    i = 0
    while i < n - 1:
        if words[i] == 0x4489 and words[i + 1] == 0x4489 and i + 2 + 540 <= n:
            body = words[i + 2:]
            while body and body[0] == 0x4489:
                body = body[1:]
            raw = [w & 0x5555 for w in body[:540]]
            longs = [raw[k] << 16 | raw[k + 1] for k in range(0, 540, 2)]
            info = (longs[0] << 1 | longs[1]) & 0xFFFFFFFF
            hcs = (longs[10] << 1 | longs[11]) & 0xFFFFFFFF
            dcs = (longs[12] << 1 | longs[13]) & 0xFFFFFFFF
            x = 0
            for v in longs[:10]:
                x ^= v
            y = 0
            for v in longs[14:270]:
                y ^= v
            if info >> 24 == 0xFF and (x & 0x55555555) == hcs & 0x55555555 and (y & 0x55555555) == dcs & 0x55555555:
                odd, even = longs[14:142], longs[142:270]
                data = b"".join(((o << 1 | e) & 0xFFFFFFFF).to_bytes(4, "big") for o, e in zip(odd, even))
                out[(info >> 16 & 0xFF) * SECTORS + (info >> 8 & 0xFF)] = data
            i += 2
        else:
            i += 1
    return out


class Floppy:
    """One drive. Lines follow the Amiga: tracks 0..79, two sides, DIR high steps towards track 0."""

    def __init__(self):  #vers 1
        self.image = None
        self.cyl = 0
        self.side = 0
        self.motor = False
        self.selected = False
        self.changed = True
        self.protected = True
        self.writes = 0
        self.saved = 0
        self.path = ""
        self._cache = {}
        self._prev_step = 1
        self.ext = None

    def _load_ext(self, data: bytes) -> None:  #vers 1
        """Extended ADF: 160 sync and length entries; sync 0 is a plain 11 sector track, else sync word then raw MFM."""
        self.ext, off = {}, 8 + 160 * 4
        adf = bytearray(ADF_SIZE)
        for t in range(160):
            sync, ln = int.from_bytes(data[8 + 4 * t:10 + 4 * t], "big"), int.from_bytes(data[10 + 4 * t:12 + 4 * t], "big")
            body = data[off:off + ln].ljust(ln, b"\0")
            off += ln
            if sync == 0:
                adf[t * SECTORS * 512:(t + 1) * SECTORS * 512] = body[:SECTORS * 512].ljust(SECTORS * 512, b"\0")
            else:
                self.ext[t] = [0xAAAA, sync] + [int.from_bytes(body[i:i + 2], "big") for i in range(0, ln - 1, 2)]
        self.image = adf

    def insert(self, data: bytes, protected: bool = True) -> None:  #vers 2
        self.ext = None
        if data[:8] == EXT_ID:
            self._load_ext(data)
            protected = True
        elif len(data) != ADF_SIZE:
            raise ValueError("not a 880K ADF image")
        else:
            self.image = bytearray(data)
        self.protected = protected
        self.changed = True
        self._cache = {}

    def eject(self) -> None:  #vers 2
        self.image, self.ext = None, None
        self.changed = True
        self._cache = {}

    def control(self, prb: int, selected: bool) -> None:  #vers 1
        """CIA-B port B for this drive: bit7 /MTR, bit2 /SIDE, bit1 DIR, bit0 /STEP; selected is the /SELx line."""
        if selected and not self.selected:
            pass
        self.selected = selected
        if selected:
            self.motor = not prb & 0x80
            self.side = 0 if prb & 4 else 1
            step = prb & 1
            if self._prev_step and not step:
                if prb & 2:
                    self.cyl = max(0, self.cyl - 1)
                else:
                    self.cyl = min(81, self.cyl + 1)
                if self.image is not None:
                    self.changed = False
            self._prev_step = step

    def status(self) -> int:  #vers 1
        """CIA-A port A input bits 5..2 (active low): /RDY, /TRK0, /PROT, /CHNG."""
        v = 0x3C
        if not self.selected:
            return v
        if self.motor and self.image is not None:
            v &= ~0x20
        if self.cyl == 0:
            v &= ~0x10
        if self.protected and self.image is not None:
            v &= ~0x08
        if self.changed:
            v &= ~0x04
        return v

    def flush(self) -> bool:  #vers 1
        """Save written sectors back to the ADF file; True when a file was written."""
        if not self.path or self.image is None or self.protected or self.ext or self.writes == self.saved:
            return False
        tmp = self.path + ".tmp"
        with open(tmp, "wb") as fh:
            fh.write(self.image)
        os.replace(tmp, self.path)
        self.saved = self.writes
        return True

    def track_words(self) -> list:  #vers 2
        if self.image is None or self.cyl > 79:
            return []
        key = (self.cyl, self.side)
        if key not in self._cache:
            t = self.cyl * 2 + self.side
            self._cache[key] = self.ext[t] if self.ext and t in self.ext else encode_track(self.image, self.cyl, self.side)
        return self._cache[key]

    def write_track(self, words: list) -> int:  #vers 1
        """Decode written MFM and store the sectors; returns the number stored."""
        if self.image is None or self.protected:
            return 0
        n = 0
        for idx, data in decode_track(words).items():
            self.image[idx * 512:(idx + 1) * 512] = data
            n += 1
        self._cache.pop((self.cyl, self.side), None)
        self.writes += n
        return n
