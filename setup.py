import os
from setuptools import setup, find_packages

setup(
    name='etheno',
    description='Etheno is a JSON RPC multiplexer, Manticore wrapper, and test framework integration tool.',
    url='https://github.com/trailofbits/etheno',
    author='Trail of Bits',
    version='0.0.1',
    packages=find_packages(),
    python_requires='>=3.6',
    install_requires=[
        'manticore', # TODO: specify a specific manticore version once https://github.com/trailofbits/manticore/pull/1054 makes it into a release
        'pysha3>=1.0.2',
        'flask>=1.0.2'
    ],
    entry_points={
        'console_scripts': [
            'etheno = etheno.__main__:main'
        ]
    }
)
