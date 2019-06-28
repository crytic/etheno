from setuptools import setup, find_packages

setup(
    name='etheno',
    description='Etheno is a JSON RPC multiplexer, Manticore wrapper, differential fuzzer, and test framework integration tool.',
    url='https://github.com/trailofbits/etheno',
    author='Trail of Bits',
    version='0.2.4',
    packages=find_packages(),
    python_requires='>=3.6',
    install_requires=[
        'ptyprocess',
        'pysha3>=1.0.2',
        'flask>=1.0.2',
        'web3',
        # The following two requirements are for our fork of `keyfile.py`,
        # but they should already be satisfied by the `web3` requirement
        'cytoolz>=0.9.0,<1.0.0',
        'pycryptodome>=3.4.7,<4.0.0',
        'setuptools'
    ],
    extras_require={
        'manticore': ['manticore>=0.2.2']
    },
    entry_points={
        'console_scripts': [
            'etheno = etheno.__main__:main'
        ]
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU Affero General Public License v3',
        'Topic :: Security',
        'Topic :: Software Development :: Testing'
    ]
)
