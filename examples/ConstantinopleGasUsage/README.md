# Constantinople Gas Usage Consensus Bug

This example is able to automatically reproduce [the Constantinople
gas usage
discrepancy](https://github.com/paritytech/parity-ethereum/pull/9746)
that caused a hard-fork on Ropsten in October of 2018. This bug was
related to how clients interpreted [a new
EIP](https://eips.ethereum.org/EIPS/eip-1283) changing how gas refunds
are accounted across calls.

Run this example by using the included
[`run_etheno.sh`](run_etheno.sh) script.

This example uses [Echidna](https://github.com/trailofbits/echidna), a
property-based fuzzer, so results are nondeterminstic. But generally
running this example should result in at least one failed differential
test. You can get additional details of the transaction that triggered
the bug by examining `log/DifferentialTester/GAS_USAGE/FAILED.log`.

Note that this example was tested with Geth 1.8.17-stable and Parity
v2.0.8-stable. Newer versions of these clients will likely have
patched the Constantinople consensus bug and Etheno's differential
tester will therefore pass all tests.