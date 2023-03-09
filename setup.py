
from setuptools import setup

with open("README.md", "r") as fh:
    long_description = fh.read()

__version__ = '0.3.0'

setup(
    name='NetworXum',
    version=__version__,
    author='Ashot Vardanian',
    author_email='ashvardanian@gmail.com',
    url='https://github.com/unumam/NetworXum',
    description='A NetworkX-like Python wrapper for graphs persisted in a DBMS',
    long_description=long_description,
    packages=['networkxum', 'networkxum.helpers'],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)
