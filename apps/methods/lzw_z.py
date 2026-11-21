#this belongs in apps/methods/lzw_z.py - Version: 1
# X-Seti - November 17 2026 - Morosa - Unix compress (.Z) Decoder.

"""
Unix compress (.Z) Decoder - unpacks LZW files as used by the Amiga Installer compression option.
"""

##Methods list -
# decompress

MAGIC = b"\x1f\x9d"


def decompress(data: bytes) -> bytes:  #vers 1
    """Bytes of a .Z file expanded."""
    if data[:2] != MAGIC:
        raise ValueError("not a .Z file")
    maxbits = data[2] & 0x1F
    block = bool(data[2] & 0x80)
    buf = data[3:]
    nbits_total = len(buf) * 8
    bits, pos, start, count = 9, 0, 0, 0
    free = 257 if block else 256
    prefix = [0] * (1 << maxbits)
    suffix = list(range(256)) + [0] * ((1 << maxbits) - 256)
    out = bytearray()
    prev, first = None, 0
    stack = bytearray()
    big = int.from_bytes(buf, "little")
    while pos + bits <= nbits_total:
        code = (big >> pos) & ((1 << bits) - 1)
        pos += bits
        count += 1
        if count == 8:
            count, start = 0, pos
        if prev is None:
            out.append(code)
            prev = first = code
            continue
        if block and code == 256:
            if count:
                pos = start + bits * 8
            count, start = 0, pos
            bits, free, prev = 9, 257, None
            continue
        cur = code
        stack.clear()
        if code >= free:
            stack.append(first)
            cur = prev
        while cur >= 256:
            stack.append(suffix[cur])
            cur = prefix[cur]
        stack.append(cur)
        first = cur
        out.extend(reversed(stack))
        if free < (1 << maxbits):
            prefix[free] = prev
            suffix[free] = first
            free += 1
            if free > (1 << bits) - 1 and bits < maxbits:
                if count:
                    pos = start + bits * 8
                count, start = 0, pos
                bits += 1
        prev = code
    return bytes(out)
