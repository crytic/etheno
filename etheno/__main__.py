import argparse
from threading import Thread
import time
import sys

from web3.auto import w3

from .client import RpcProxyClient
from .etheno import app, EthenoView, GETH_DEFAULT_RPC_PORT, ManticoreClient, ETHENO
from .synchronization import AddressSynchronizingClient
from .utils import find_open_port
from . import Etheno
from . import ganache
from . import manticoreutils
from . import truffle

def main(argv = None):
    parser = argparse.ArgumentParser(description='An Ethereum JSON RPC multiplexer and Manticore wrapper')
    parser.add_argument('--debug', action='store_true', default=False, help='Enable debugging from within the web server')
    parser.add_argument('--run-publicly', action='store_true', default=False, help='Allow the web server to accept external connections')
    parser.add_argument('-p', '--port', type=int, default=GETH_DEFAULT_RPC_PORT, help='Port on which to run the JSON RPC webserver (default=%d)' % GETH_DEFAULT_RPC_PORT)
    parser.add_argument('-a', '--accounts', type=int, default=10, help='Number of accounts to create in Ganache (default=10)')
    parser.add_argument('-b', '--balance', type=float, default=100.0, help='Default balance (in Ether) to seed to each account (default=100.0)')
    parser.add_argument('-c', '--gas-price', type=int, default=20000000000, help='Default gas price (default=20000000000)')
    parser.add_argument('-i', '--network-id', type=int, default=None, help='Specify a network ID (default is the network ID of the master client)')
    parser.add_argument('-m', '--manticore', action='store_true', default=False, help='Run all transactions through manticore')
    parser.add_argument('-r', '--manticore-script', type=argparse.FileType('rb'), default=None, help='Instead of running automated detectors and analyses, run this Manticore script')
    parser.add_argument('--manticore-max-depth', type=int, default=None, help='Maximum state depth for Manticore to explore')
    parser.add_argument('--manticore-verbosity', type=int, default=3, help='Manticore verbosity (default=3)')
    parser.add_argument('-t', '--truffle', action='store_true', default=False, help='Run the truffle migrations in the current directory and exit')
    parser.add_argument('--truffle-args', type=str, default='migrate', help='Arguments to pass to truffle (default=migrate)')
    parser.add_argument('-g', '--ganache', action='store_true', default=False, help='Run Ganache as a master JSON RPC client (cannot be used in conjunction with --master)')
    parser.add_argument('--ganache-args', type=str, default=None, help='Additional arguments to pass to Ganache')
    parser.add_argument('--ganache-port', type=int, default=None, help='Port on which to run Ganache (defaults to the closest available port to the port specified with --port plus one)')
    parser.add_argument('-v', '--version', action='store_true', default=False, help='Print version information and exit')
    parser.add_argument('client', type=str, nargs='*', help='One or more JSON RPC client URLs to multiplex; if no client is specified for --master, the first client in this list will default to the master (format="http://foo.com:8545/")')
    parser.add_argument('-s', '--master', type=str, default=None, help='A JSON RPC client to use as the master (format="http://foo.com:8545/")')

    if argv is None:
        argv = sys.argv
    
    args = parser.parse_args(argv[1:])

    if args.version:
        print(VERSION_NAME)
        sys.exit(0)

    accounts = [w3.eth.account.create() for i in range(args.accounts)]

    if args.ganache and args.master:
        parser.print_help()
        sys.stderr.write('\nError: You cannot specify both --ganache and --master at the same time!\n')
        sys.exit(1)        
    elif args.ganache:
        if args.ganache_port is None:
            args.ganache_port = find_open_port(args.port + 1)

        if args.network_id is None:
            args.network_id = 0x657468656E6F # 'etheno' in hex

        ganache_accounts = ["--account=%s,0x%x" % (acct.privateKey.hex(), int(args.balance * 1000000000000000000)) for acct in accounts]

        ganache_instance = ganache.Ganache(args = ganache_accounts + ['-g', str(args.gas_price), '-i', str(args.network_id)], port=args.ganache_port)

        ETHENO.master_client = ganache.GanacheClient(ganache_instance)

        ganache_instance.start()
    elif args.master:
        ETHENO.master_client = AddressSynchronizingClient(RpcProxyClient(args.master))
    elif args.client:
        ETHENO.master_client = AddressSynchronizingClient(RpcProxyClient(args.client[0]))
        args.client = args.client[1:]

    if args.network_id is None:
        if ETHENO.master_client:
            args.network_id = int(ETHENO.master_client.post({
                'id': 1,
                'jsonrpc': '2.0',
                'method': 'net_version'
            })['result'], 16)
        else:
            args.network_id = 0x657468656E6F # 'etheno' in hex

    for client in args.client:
        ETHENO.add_client(AddressSynchronizingClient(RpcProxyClient(client)))

    manticore_client = None
    if args.manticore:
        manticore_client = ManticoreClient()
        ETHENO.add_client(manticore_client)
        if args.manticore_max_depth is not None:
            manticore_client.manticore.register_detector(manticoreutils.StopAtDepth(args.manticore_max_depth))
        manticore_client.manticore.verbosity(args.manticore_verbosity)

    if args.truffle:
        truffle_controller = truffle.Truffle()
        def truffle_thread():
            if ETHENO.master_client:
                ETHENO.master_client.wait_until_running()
            print("Etheno Started! Running Truffle...")
            ret = truffle_controller.run(args.truffle_args)
            if ret != 0:
                # TODO: Print a warning/error
                pass

            if manticore_client is not None:
                if args.manticore_script is not None:
                    exec(args.manticore_script.read(), {'manticore' : manticore_client.manticore, 'manticoreutils' : manticoreutils})
                else:
                    manticoreutils.register_all_detectors(manticore_client.manticore)
                    manticore_client.multi_tx_analysis()
                    manticore_client.manticore.finalize()
                print(manticore_client.manticore.global_findings)
                print("Results are in %s" % manticore_client.manticore.workspace)
                ETHENO.shutdown()

        thread = Thread(target=truffle_thread)
        thread.start()

    etheno = EthenoView()
    app.add_url_rule('/', view_func=etheno.as_view('etheno'))

    etheno_thread = ETHENO.run(debug = args.debug, run_publicly = args.run_publicly, port = args.port)
    truffle_controller.terminate()

if __name__ == '__main__':
    main()
