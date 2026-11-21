# Morosa ChangeLog

- Nov 17 2026 - Split from TC Workshop into its own repo. Settings editor with machine profiles (JSON). Kickstart 1.3 boots into its idle loop.

- CIA: one-shot timer starts on high-byte write. KS 1.3 now boots to its first screen (garbled, rotated 180 degrees).
- Nov 17 2026 - Repo renamed Morosa-SubSystem; package morosa/ now apps/. Imports and headers updated.
- CIA one-shot timer starts on high-byte write; KS 1.3 reaches first screen (rotated 180).
- Nov 18 2026 - OCS/ECS: unmapped reads return 0xFFFF; custom-chip mirrors at 0xC0F000 pages. KS 1.2 A500 boots.
- Nov 18 2026 - Open-bus 0xFFFF and custom mirrors only on OCS/ECS; DE0003 latch for non-Ramsey. 3.0 ROM files labelled A1200/A4000 are swapped. A1200 3.0/3.1.4 boot.
- Nov 18 2026 - CDTV: 32K NVRAM at 0xDC8000; 0xB80000-0xBEFFFF reads 0 on non-CD32. CDTV KS 1.3 and 3.2 reach logo screen.
- Nov 18 2026 - SDMAC: word/long writes at 0xDD0040 select WD33C93 register. A3000 KS 2.0 boots; A4000 KS 3.1.4 boots (slow).
- Nov 18 2026 - Hires display starts at 2*DDFSTRT+9 (was +17, shifted 16 px right). KS 3.x screens now centred, no stray fragment.
- Nov 18 2026 - A1000: boot ROM at 0xF80000, writable control store at 0xFC0000 locked by boot ROM write. Boots KS 1.2 from Kickstart disk (image at offset 512).
- Nov 18 2026 - NCR 710: ISTAT abort raises DSTAT abort interrupt. A4000T KS 3.1 boots to insert-disk screen.
- Nov 18 2026 - Settings: A1000 boot ROM entry; Kickstart ROM is built into a Kickstart disk in DF0 when DF0 is empty.
- Nov 18 2026 - A3000 SCSI: WD33C93 select, PIO, DMA; hard drive slots 2-8 map to SCSI IDs 0-6. KS 2.04 boots from SCSI disk.
- Nov 18 2026 - CD images ISO, IMG/BIN, CUE/BIN as SCSI CD-ROM (A3000) and ATAPI (IDE). Images without RDB get a virtual RDB; heads and sectors set in Settings.
- Nov 19 2026 - CD32 Akiko and CDTV DMAC read CD images: command set, TOC, sector DMA. CDTV DMAC now autoconfig board. Tested only with synthetic ISO.
- Nov 19 2026 - Settings: hardfile DOS type override for images without an RDB (hex, blank is auto).
- Nov 19 2026 - CD32: sector header byte 2 cleared (ROM rejected sync byte); cue pregap counted. SimCity CD32 disc boots to intro picture.
- Nov 19 2026 - Hardfile without RDB: geometry chosen so partition size is exact (root block position). Non-RDB HDF boots from A3000 SCSI. Xenon 2 CD32 reaches title.
- Nov 19 2026 - AGA: 64-bit fetch (FMODE 3) display delayed 8 pixels; CD32/A1200 Workbench windows no longer clipped at left.
- CDTV: 1MB chip uses wide blitter pointers; SimCity CD title draws correctly.
- CDTV: 64K memory card at $E00000; SimCity save and load to RAM card work.
- A3000/A4000: unmapped accesses no longer bus error until Gary timeout is enabled; KS 2.04, 3.1, 3.2 boot to insert-disk.
