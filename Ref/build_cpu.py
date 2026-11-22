#this belongs in root /build_cpu.py - Version: 1
# X-Seti - Nov 21 2026 - Morosa-SubSystem - Compile CPU core with Cython.
"""Build: python3 build_cpu.py  (needs cython, gcc). Delete the .so to run plain Python."""
from setuptools import Extension, setup
from Cython.Build import cythonize

setup(ext_modules=cythonize([Extension("apps.core.cpu", ["apps/core/cpu.py"], extra_compile_args=["-O3"])],
      language_level=3, compiler_directives={"boundscheck": False, "wraparound": False, "binding": False}),
      script_args=["build_ext", "--inplace"])
