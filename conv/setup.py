from setuptools import setup, find_packages

"""
https://tia.mat.br/posts/2020/06/21/converting-gwbasic-to-z80.html
"""

setup(
    name="z80conv",
    version='0.0.1',
    author="lp",
    description="Porting GW-BASIC from 8086 back to the Z80",
    license="GPLv2",
    packages=find_packages(),
    long_description="Porting GW-BASIC from 8086 back to the Z80",
    install_requires=[],
    tests_require=['pytest'],
    entry_points = {
        'console_scripts': ['z80conv=z80conv.conv:main'],
    }
)
