#this belongs in apps/methods/kickstart_disk.py - Version: 1
# X-Seti - November 18 2026 - Morosa - Morosa Kickstart Disk.

"""
Morosa Kickstart Disk - builds the A1000 Kickstart floppy image the boot ROM loads into its control store.
"""

##Methods list -
# build_image


def build_image(rom: bytes) -> bytes:  #vers 1
    """ADF with a KICK boot sector and the 256K Kickstart from sector 1."""
    if len(rom) != 0x40000:
        raise ValueError("Kickstart for the A1000 must be a 256 KB image")
    adf = bytearray(901120)
    adf[0:4] = b"KICK"
    adf[512:512 + len(rom)] = rom
    return bytes(adf)
