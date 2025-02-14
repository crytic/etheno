The repo is now archived. Use [medusa](https://github.com/crytic/medusa) for fuzzing. To learn more: https://secure-contracts.com/


# Etheno
[![Slack Status](https://slack.empirehacking.nyc/badge.svg)](https://slack.empirehacking.nyc)
[![PyPI version](https://badge.fury.io/py/etheno.svg)](https://badge.fury.io/py/etheno)
<p align="center">
  <img src="logo/etheno.png?raw=true" width="256" title="Etheno">
</p>
<br />


Etheno is the Ethereum testing Swiss Army knife. It’s a JSON RPC multiplexer, analysis tool wrapper, and test integration tool. It eliminates the complexity of setting up analysis tools like [Echidna](https://github.com/trailofbits/echidna) on large, multi-contract projects.

If you are a smart contract developer, you should use Etheno to test your contracts. If you are an Ethereum client developer, you should use Etheno to perform differential testing on your implementation.

Etheno is named after the Greek goddess [Stheno](https://en.wikipedia.org/wiki/Stheno), sister of Medusa, and mother of Echidna—which also happens to be the name of [our EVM property-based fuzz tester](https://github.com/trailofbits/echidna).

## Features

* **JSON RPC Multiplexing**: Etheno runs a JSON RPC server that can multiplex calls to one or more clients
  * API for filtering and modifying JSON RPC calls
  * Enables differential testing by sending JSON RPC sequences to multiple Ethereum clients
  * Deploy to and interact with multiple networks at the same time
* **Integration with Test Frameworks** like Ganache and Truffle
  * Run a local test network with a single command

## Quickstart

Use our prebuilt Docker container to quickly install and try Etheno:

```
docker pull trailofbits/etheno
docker run -it trailofbits/etheno
```

**NOTE:** Many of Etheno's capabilities will require publishing one or more ports and persisting data using volumes as part of the `docker run` command.
- To learn about publishing ports, click [here](https://docs.docker.com/storage/volumes/)
- To learn more about persisting data using volumes, click [here](https://docs.docker.com/storage/volumes/)


Alternatively, natively install Etheno in a few shell commands:

```
# Install system dependencies
sudo apt-get update && sudo apt-get install python3 python3-pip -y

# Install Etheno
pip3 install --user etheno

# Use the Etheno CLI
cd /path/to/a/truffle/project
etheno --ganache --truffle
```

## Usage

Etheno can be used in many different ways and therefore has numerous command-line argument combinations.

### Ganache Integration

A Ganache instance can automatically be run within Etheno:
```
etheno --ganache
```

* `--ganache-port` will set the port on which Ganache is run; if omitted, Etheno will choose the lowest port higher than the port on which Etheno’s JSON RPC server is running
* `--ganache-args` lets you pass additional arguments to Ganache
* `--accounts` or `-a` sets the number of accounts to create in Ganache (default is 10)
* `--balance` or `-b` sets the default balance (in Ether) to seed to each Ganache account (default is 1000.0)
* `--gas-price` or `-c` sets the default gas price in wei for Ganache (default is 20_000_000_000)

Running a Ganache instance via Etheno can be used to deploy large, multi-contract projects in tandem with Echidna. To learn more on how to use Echidna and Ganache together, click [here](https://github.com/crytic/building-secure-contracts/blob/master/program-analysis/echidna/end-to-end-testing.md).


**NOTE:** We recommend using the latest version of Ganache (v7.3.2) and Node 16.x. After the upstream bug (see below) is fixed, the Ganache package should be upgraded.


**NOTE:** Currently, there is an upstream bug in the latest version of Ganache (v7.3.2) that prevents the Etheno integration from working if the contract size that is being tested is very large (https://github.com/trufflesuite/ganache/issues/3332). 


### JSON RPC Server and Multiplexing

This command starts a JSON RPC server and forwards all messages to the given clients:

```
etheno https://client1.url.com:1234/ https://client2.url.com:8545/ http://client3.url.com:8888/
```

* `--port` or `-p` allows you to specify a port on which to run Etheno’s JSON RPC server (default is 8545)
* `--run-publicly` allows incoming JSON RPC connections from external computers on the network
* `--debug` will run a web-based interactive debugger in the event that an internal Etheno client throws an exception while processing a JSON RPC call; this should _never_ be used in conjunction with `--run-publicly`
* `--master` or `-s` will set the “master” client, which will be used for synchronizing with Etheno clients. If a master is not explicitly provided, it defaults to the first client listed.
* `--raw`, when prefixed before a client URL, will cause Etheno to auto-sign all transactions and submit them to the client as raw transactions

### Geth and Parity Integration

A Geth and/or Parity instance can be run as a private chain with
* `--geth` or `-go` for Geth
* `--parity` or `-pa` for Parity

Each will be instantiated with an autogenerated genesis block. You may provide a custom `genesis.json` file in Geth format using the `--genesis` or `-j` argument. The genesis used for each run will automatically be saved to the log directory (if one is provided using the `--log-dir` option), or it can be manually saved to a location provided with the `--save-genesis` option.

The network ID of each client will default to 0x657468656E6F (equal to the string `etheno` in ASCII). This can be overridden with the `--network-id` or `-i` option.

EIP and hard fork block numbers can be set within a custom genesis.json as usual, or they may be specified as command-line options such as `--constantinople`.

### Differential Testing

Whenever two or more clients are run within Etheno, the differential
testing plugin will automatically be loaded. This plugin checks for a
variety of different discrepancies between the clients, such as gas
usage differences. A report is printed when Etheno exits.

This plugin can be disabled with the `--no-differential-testing` option.

### Truffle Integration

Truffle migrations can automatically be run within a Truffle project:
```
etheno --truffle
```

Additional arguments can be passed to Truffle using `--truffle-args`.

### Logging

By default, Etheno only prints log messages to the console with a log
level defaulting to `INFO`. An alternative log level can be specified
with `--log-level` or `-l`.  You can specify a log file with the
`--log-file` option. In addition, you can provide the path to a
logging directory with `--log-dir` in which the following will be
saved:
* a complete log file including log messages at all log levels;
* separate log files for each Etheno client and plugin;
* the genesis file used to instantiate clients;
* a subdirectory in which each client and plugin can store additional files such as test results;
* a script to re-run Geth and/or Parity using the same genesis and chain data that Etheno used.

## Requirements

* Python 3.7 or newer 

### Optional Requirements
* [Node](https://nodejs.org/en/) 16.x or newer to install various integrations
* [Ganache](https://www.npmjs.com/package/ganache) 7.3.2 or newer for its associated integrations
* [Truffle](https://www.npmjs.com/package/truffle) for its associated integrations
* [Geth](https://github.com/ethereum/go-ethereum) and/or [Parity](https://github.com/paritytech/parity-ethereum), if you would like to have Etheno run them

## Getting Help

Feel free to stop by our [Slack channel](https://empirehacking.slack.com/) for help on using or extending Etheno.

## License

Etheno is licensed and distributed under the [AGPLv3](LICENSE) license. [Contact us](mailto:opensource@trailofbits.com) if you’re looking for an exception to the terms.
