#this belongs in root /build_musashi.py - Version: 3
# X-Seti - Nov 21 2026 - Morosa-SubSystem - Compile the Musashi 68k core.
"""Build: python3 build_musashi.py  (needs gcc, python dev headers). Generates m68kops first."""
import os
import subprocess
from setuptools import Extension, setup

D = "apps/core/musashi"
if not os.path.exists(f"{D}/m68kops.c") or os.path.getmtime(f"{D}/m68k_in.c") > os.path.getmtime(f"{D}/m68kops.c"):
    subprocess.check_call(["gcc", "-O2", "-o", f"{D}/m68kmake", f"{D}/m68kmake.c"])
    subprocess.check_call([f"./m68kmake", ".", "m68k_in.c"], cwd=D)
src = ["glue.c", "m68kcpu.c", "m68kdasm.c", "m68kops.c", "softfloat/softfloat.c"]
setup(name="musashi_ext", ext_modules=[
    Extension("apps.core.musashi_ext", [f"{D}/{s}" for s in src], include_dirs=[D], extra_compile_args=["-O3", "-w"]),
    Extension("apps.core.video_ext", ["apps/core/video.c"], extra_compile_args=["-O3", "-w"])],
    script_args=["build_ext", "--inplace", "--force"])
