from setuptools import setup, find_packages

setup(
    name='etheno',
    description='Etheno is a JSON RPC multiplexer, differential fuzzer, and test framework integration tool.',
    url='https://github.com/trailofbits/etheno',
    author='Trail of Bits',
    version='0.3.0',
    packages=find_packages(),
    python_requires='>=3.6',
    install_requires=[
        'ptyprocess',
        'pysha3>=1.0.2',
        'flask>=2.1.0',
        # Pinning web3 to a much higher version to prevent potential conflicts with the below packages
        'web3>=5.29.2',
        # Contextual version conflicts between eth-hash, eth-utils, eth-rlp, and rusty-rlp
        # This works only if `--platform linux/amd64` is set since rusty-rlp==0.1.15 is not available for ARM architectures
        # This is super hacky but it works for now 
        'eth-hash>=0.3.1,<0.4.0',
        'eth-utils==1.9.5',
        'eth-rlp==0.2.0',
        # Commenting out these dependencies since we will be removing the parity integration soon enough
        #"""
        ## The following two requirements are for our fork of `keyfile.py`,
        ## but they should already be satisfied by the `web3` requirement
        #'cytoolz>=0.9.0,<1.0.0',
        #'pycryptodome>=3.4.7,<4.0.0',
        #"""
        'setuptools'
    ],
    # rusty-rlp==0.1.15 has to be downloaded as a tarball
    dependency_links = ['https://github.com/cburgdorf/rusty-rlp/archive/refs/tags/0.1.15.tar.gz'],
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
