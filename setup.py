import sys
from setuptools import setup, Extension, find_packages
from Cython.Build import cythonize

# Native compiler optimization flags
extra_compile_args = []
extra_link_args = []

if sys.platform == "win32":
    extra_compile_args = ["/O2", "/GL", "/MD"]
    extra_link_args = ["/LTCG"]
else:
    extra_compile_args = ["-O3", "-march=native", "-pipe"]

extensions = [
    Extension(
        "chronosmatch.engine.matcher",
        sources=["chronosmatch/engine/matcher.pyx"],
        include_dirs=["chronosmatch/engine"],
        extra_compile_args=extra_compile_args,
        extra_link_args=extra_link_args,
        language="c"
    )
]

setup(
    name="chronosmatch",
    version="3.1.0",
    packages=find_packages(),
    ext_modules=cythonize(
        extensions,
        compiler_directives={
            'language_level': "3",
            'boundscheck': False,
            'wraparound': False,
            'cdivision': True,
            'nonecheck': False,
            'initializedcheck': False
        }
    )
)
