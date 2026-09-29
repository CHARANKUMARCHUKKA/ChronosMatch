from setuptools import setup, Extension
from Cython.Build import cythonize

extensions = [
    Extension(
        "chronosmatch.engine.matcher",
        sources=["chronosmatch/engine/matcher.pyx"],
        language="c"
    )
]

setup(
    name="chronosmatch",
    ext_modules=cythonize(extensions, compiler_directives={'language_level': "3"})
)

# formatted cython imports
