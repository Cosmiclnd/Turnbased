from setuptools import setup, Extension
from Cython.Build import cythonize
import os

extensions = [
    Extension("core._item", ["core/_item.pyx"]),
    Extension("core._modifier", ["core/_modifier.pyx"])
]

setup(
    name="Turnbased",
    ext_modules=cythonize(
        extensions,
        language_level=3,
        compiler_directives={
            'boundscheck': True,
            'wraparound': True,
            'cdivision': True,
        },
        build_dir="build"
    ),
    packages=["core"],
    include_dirs=[],
)
