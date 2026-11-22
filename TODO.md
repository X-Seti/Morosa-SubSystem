# Morosa TODO

- Split the Motarolla CPU into M68000.py M68010.py, M68020.py so on as this links in with the Virtual Emulation project where you seen the Virtual components on a Virtual PCB
- 
- Kickstart 1.3 idles at STOP after chip setup; find missing interrupt or device.
- NCR 53C710 datasheet for SCRIPTS engine; WD33C93 timing is unchecked.
- Buster, Amber, Fat Gary timeouts, Gayle PCMCIA.
- CD32/CDTV: CD audio, subcode, real boot discs untested; CDTV logo letters look doubled.
- AGA sprite widths, BPLCON4 sprite banks.
- ADF write-back to disk.
- PowerPC 603e core (Cyberstorm PPC).
- OS layer: gadtools, BOOPSI, asl, commodities, expansion, ExAll.

- KS 1.3 hand-disk label text is upside down; confirm against real hardware screenshot.
- Folder disks are not written back. CD audio playback, CD-ROM boot untested on real drivers.
- ROM files named A1200 3.0 and A4000 3.0 are swapped; A3000 3.1 file is the A500 3.1 ROM.
- A4000T KS 3.1 boots but the SCSI scan takes about 9000 frames; 53C710 SCRIPTS still unimplemented, so no SCSI disks.
- A3000: no Kickstart 1.4 bootstrap ROM available; SuperKickstart boot not implemented.
- CDTV: SimCity CD gameplay after title untested; check later screens.
- CDTV: memory card contents are not saved to a file between runs.
- Appicon needed - Links to App_Settings_System.py themes.
- Native core: no bus errors on unmapped access; 68060 runs as 68040; Gary timeout and MMU faults untested.
- Extended ADF: no writes; Turrican II title shows thin raster glitches.
