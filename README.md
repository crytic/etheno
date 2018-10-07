# Etheno
<p align="center">
  <img src="logo/etheno.png?raw=true" width="256" title="Etheno">
</p>
<br />


Etheno is a JSON RPC multiplexer, analysis tool wrapper, and test integration tool. It eliminates the complexity of setting up analysis tools on large, multi-contract projects, like [Manticore](https://github.com/trailofbits/manticore/). In particular, custom Manticore analysis scripts require less code, are simpler to write, and integrate with Truffle.

It is named after the Greek goddess [Stheno](https://en.wikipedia.org/wiki/Stheno), sister of Medusa, and mother of Echidna—which also happens to be the name of [our EVM property-based fuzz tester](https://github.com/trailofbits/echidna).

## Features

* **JSON RPC Multiplexing**: Etheno runs a JSON RPC server that can multiplex calls to one or more clients
  * API for filtering and modifying JSON RPC calls
  * Enables differential testing by sending JSON RPC sequences to multiple Ethereum clients
  * Deploy to and interact with multiple networks at the same time
* **Analysis Tool Wrapper**: Etheno provides a JSON RPC client for advanced analysis tools like [Manticore](https://github.com/trailofbits/manticore/)
  * Lowers barrier to entry for using advanced analysis tools
  * No need for custom scripts to set up account and contract state
  * Analyze arbitrary transactions without Solidity source code
* **Integration with Test Frameworks** like Ganache and Truffle
  * Run a local test network with a single command
  * Use Truffle migrations to bootstrap Manticore analyses
  * Symbolic semantic annotations within unit tests

## Quickstart

Use Docker to quickly install and try Etheno:

```
# Clone the Etheno repo
git clone https://github.com/trailofbits/etheno.git && cd etheno

# Build the Docker image
docker build . -t etheno

# Start a new Etheno Docker container
docker run -it etheno:latest

# Run one of the examples
etheno@982abdc96791:~$ cd examples/BrokenMetaCoin/
etheno@982abdc96791:~/examples/BrokenMetaCoin$ etheno --truffle --ganache --manticore --manticore-max-depth 2 --manticore-script ExploitMetaCoinManticoreScript.py
```

Alternatively, install Etheno in a few shell commands:

```
# Install system dependencies
sudo apt-get update && sudo apt-get install python3 python3-pip -y

# Install Manticore
# Note: This will not work until Manticore 0.2.3 is released
# pip3 install manticore --user

# Clone and install Etheno
git clone https://github.com/trailofbits/etheno.git
cd etheno
pip3 install -e '.'

# Use the Etheno CLI
cd /path/to/a/truffle/project
etheno --manticore --ganache --truffle
```

## Usage

Etheno can be used in many different ways and therefore has numerous command line argument combinations.

### JSON RPC Server and Multiplexing

This command starts a JSON RPC server and forwards all messages to the given clients:

```
etheno https://client1.url.com:1234/ https://client2.url.com:8545/ http://client3.url.com:8888/
```

* `--port` or `-p` allows you to specify a port on which to run Etheno's JSON RPC server (default is 8545)
* `--run-publicly` allows incoming JSON RPC connections from external computers on the network
* `--debug` will run a web-based interactive debugger in the event that an internal Etheno client throws an exception while processing a JSON RPC call; this should _never_ be used in conjunction with `--run-publicly`
* `--master` or `-s` will set the “master” client, which will be used for synchronizing with Etheno clients like Manticore. If a master is not explicitly provided, it defaults to the first client listed.

### Ganache Integration

A Ganache instance can automatically be run within Etheno:
```
etheno --ganache
```

* `--ganache-port` will set the port on which Ganache is run; if omitted, Etheno will choose the lowest port higher than the port on which Etheno's JSON RPC server is running
* `--ganache-args` lets you pass additional arguments to Ganache
* `--accounts` or `-a` sets the number of accounts to create in Ganache (default is 10)
* `--balance` or `-b` sets the default balance (in Ether) to seed to each Ganache account (default is 100.0)
* `--gas-price` or `-c` sets the default gas price for Ganache (default is 20000000000)

### Manticore Client

Manticore—which, by itself, does not implemnent a JSON RPC interface—can be run as an Etheno client, synchronizing its accounts with Etheno's master client and symbolically executing all transactions sent to Etheno.
```
etheno --manticore
```
This alone will not run any Manticore analyses; they must either be run manually, or automated through [the `--truffle` command](#truffle-integration);

* `--manticore-verbosity` sets Manticore's logging verbosity (default is 3)
* `--manticore-max-depth` sets the maximum state depth for Manticore to explore; if omitted, Manticore will have no depth limit

### Truffle Integration

Truffle migrations can automatically be run within a Truffle project:
```
etheno --truffle
```

When combined with the `--manticore` option, this will automatically run Manticore's default analyses on all contracts created once the Truffle migration completes:
```
etheno --truffle --manticore
```

This requires a master JSON RPC client, so will most often be used in conjunction with Ganache. If a local Ganache server is not running, you can simply add that to the command:
```
etheno --truffle --manticore --ganache
```

If you would like to run a custom Manticore script instead of the standard Manticore analysis and detectors, it can be specified using the `--manticore-script` or `-r` command.

This script does not need to import Manticore or create a `ManticoreEVM` object; Etheno will run the script with a global variable called `manticore` that already contains all of the accounts and contracts automatically provisioned.  See the [`BrokenMetaCoin` Manticore script](examples/BrokenMetaCoin/ExploitMetaCoinManticoreScript.py) for an example.

Additional arguments can be passed to Truffle using `--truffle-args`.

## Requirements

* Python 3.6 or newer
* [Manticore](https://github.com/trailofbits/manticore/) (Note: Use the docker image or wait for Manticore 0.2.3)
* [Flask](http://flask.pocoo.org/), which is used to run the JSON RPC server
* [Truffle and Ganache](https://truffleframework.com/) for their associated integrations

## Getting Help

Feel free to stop by our [Slack channel](https://empirehacking.slack.com/) for help on using or extending Etheno.

Documentation is available in several places:

  * The [wiki](https://github.com/trailofbits/etheno/wiki) contains some basic information about getting started with Etheno and contributing

  * The [examples](examples) directory has some very minimal examples that showcase API features

## License

Etheno is licensed and distributed under the [AGPLv3](LICENSE) license. [Contact us](mailto:opensource@trailofbits.com) if you're looking for an exception to the terms.
