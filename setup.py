from setuptools import setup, find_packages

setup(
    name="etheno",
    description="Etheno is a JSON RPC multiplexer, differential fuzzer, and test framework integration tool.",
    url="https://github.com/trailofbits/etheno",
    author="Trail of Bits",
    version="0.3.2",
    packages=find_packages(),
    python_requires=">=3.7",
    install_requires=[
        "ptyprocess",
        "pysha3>=1.0.2",
        # TODO: identify what is the oldest flask version that the new shutdown mechanism is compatible with
        "flask",
        # Pinning web3 to a low version to prevent conflicts with other packages
        "web3>=3.16.4",
        # Contextual version conflicts between eth-hash, eth-utils, eth-rlp, and rusty-rlp
        # This works only if `--platform linux/amd64` is set since rusty-rlp==0.1.15 is not available for ARM architectures
        # This is super hacky but it works for now
        # This is likely going to cause conflicts with other packages :(
        "eth-hash>=0.3.1,<0.4.0",
        "eth-utils==1.10.0",
        "eth-rlp<0.3.0",
        "setuptools",
    ],
    entry_points={"console_scripts": ["etheno = etheno.__main__:main"]},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU Affero General Public License v3",
        "Topic :: Security",
        "Topic :: Software Development :: Testing",
    ],
)
