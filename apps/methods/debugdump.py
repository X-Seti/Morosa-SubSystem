#this belongs in apps/methods/debugdump.py - Version: 2
# X-Seti - November 23 2026 - Morosa - Display State Dump.

"""
Morosa Debugdump - writes cpu registers, display registers, sprite state and the active copper list to a text file.
"""

##Methods list -
# _scalars
# _copper_list
# dump_text
# next_name

from pathlib import Path


def next_name(folder: Path) -> str:  #vers 1
    """Next free dumpNN stem in folder."""
    folder.mkdir(exist_ok=True)
    n = 1
    while (folder / f"dump{n:02d}.txt").exists() or (folder / f"dump{n:02d}.png").exists():
        n += 1
    return f"dump{n:02d}"


def _scalars(obj) -> list:  #vers 1
    """name = value for every int, bool or small list attribute."""
    out = []
    for k in sorted(vars(obj)):
        v = getattr(obj, k)
        if isinstance(v, bool):
            out.append(f"  {k} = {v}")
        elif isinstance(v, int):
            out.append(f"  {k} = {v:#x}")
        elif isinstance(v, (list, tuple)) and len(v) <= 16 and all(isinstance(x, int) for x in v):
            out.append(f"  {k} = [{', '.join(f'{x:#x}' for x in v)}]")
    return out


def _copper_list(agnus, start: int, limit: int = 600) -> list:  #vers 1
    """Decode MOVE, WAIT and SKIP words from start until the end marker."""
    out = []
    a = start
    for _ in range(limit):
        w1, w2 = agnus.read16(a), agnus.read16(a + 2)
        if w1 & 1:
            kind = "SKIP" if w2 & 1 else "WAIT"
            out.append(f"  {a:06X}: {kind} v={w1 >> 8:02X} h={w1 & 0xFE:02X} mask={w2:04X}")
        else:
            out.append(f"  {a:06X}: MOVE {w1 & 0x1FE:03X} <- {w2:04X}")
        if w1 == 0xFFFF and w2 == 0xFFFE:
            break
        a += 4
    return out


def dump_text(m) -> str:  #vers 5
    """Everything needed to see why a line is drawn wrong."""
    a, d, c = m.agnus, m.agnus.denise, m.agnus.copper
    t = [f"frame {a.frames} vpos {a.vpos} lines {a.lines} lof {a.lof}", "cpu"]
    try:
        from apps.core import musashi_ext as x
        r = m.cpu.core.reg
        t.append(f"  pc {m.cpu.pc:08X} sr {r(x.REG_SR):04X} sp {r(x.REG_SP):08X} stopped {m.cpu.stopped} irq {m.cpu.irq_level}")
        t.append("  d " + " ".join(f"{r(x.REG_D0 + i):08X}" for i in range(8)))
        t.append("  a " + " ".join(f"{r(x.REG_A0 + i):08X}" for i in range(8)))
    except Exception as e:
        t.append(f"  unavailable: {e}")
    t.append("paula")
    t += _scalars(m.paula)
    for n, c2 in (("ciaa", m.ciaa), ("ciab", m.ciab)):
        t.append(n)
        t += _scalars(c2)
    t.append("keyboard")
    t += _scalars(m.keyboard)
    t.append(f"  queued = {len(m.keyboard.queue)}")
    t.append("ports")
    t += _scalars(m.ports)
    t.append(f"  devs = {m.ports.devs}")
    t.append("agnus")
    t += _scalars(a)
    t.append("denise")
    t += _scalars(d)
    t.append("copper")
    t += _scalars(c)
    t.append("blitter")
    t += _scalars(a.blitter)
    t.append("blit log: con0 con1 afwm alwm apt bpt cpt dpt amod bmod cmod dmod w h busy")
    for b in a.blitter.log:
        t.append("  " + " ".join(f"{x:X}" if i < 8 else str(x) for i, x in enumerate(b)))
    t.append("sprite pointers and state")
    t += [f"  spr{n} ptr {a.sprpt[n]:06X} {a.sprstate[n]} pos {d.spr[n]['pos']:04X} ctl {d.spr[n]['ctl']:04X}" for n in range(8)]
    t.append("bitplane pointers")
    t += [f"  plane{n} {a.bplpt[n]:06X}" for n in range(8)]
    t.append("colours")
    t.append("  " + " ".join(f"{x:06X}" for x in d.color[:256]))
    for name, ptr in (("copper list 1", c.lc1), ("copper list 2", c.lc2)):
        t.append(f"{name} at {ptr:06X}")
        t += _copper_list(a, ptr)
    return "\n".join(t) + "\n"
