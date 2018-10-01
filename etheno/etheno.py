#!/usr/bin/env python2

VERSION='0.0.1'
VERSION_NAME="ToB/v%s/source/Etheno" % VERSION
JSONRPC_VERSION = '2.0'
VERSION_ID=67

import inspect
import sha3
from threading import Thread

from flask import Flask, g, jsonify, request, abort
from flask.views import MethodView

from manticore.ethereum import ManticoreEVM, DetectInvalid, DetectIntegerOverflow, DetectUninitializedStorage, DetectUninitializedMemory, FilterFunctions#, DetectReentrancy
from manticore.core.smtlib import visitors

import ganache
import threadwrapper

app = Flask(__name__)

GETH_DEFAULT_RPC_PORT = 8545
ETH_DEFAULT_RPC_PORT = 8545
PARITY_DEFAULT_RPC_PORT = 8545
PYETHAPP_DEFAULT_RPC_PORT = 4000

def to_account_address(raw_address):
    addr = "%x" % raw_address
    return "0x%s%s" % ('0'*(40 - len(addr)), addr)

def decode_hex(data):
    if data is None:
        return None
    if data[:2] == '0x':
        data = data[2:]
    return bytes.fromhex(data)

def encode_hex(data):
    if data is None:
        return None
    elif isinstance(data, int) or isinstance(data, long):
        encoded = hex(data)
        if encoded[-1] == 'L':
            encoded = encoded[:-1]
        return encoded
    else:
        return "0x%s" % data.encode('hex')

_CONTROLLER = threadwrapper.MainThreadController()

@app.route('/shutdown')
def _etheno_shutdown():
    # shut down the Flask server
    shutdown = request.environ.get('werkzeug.server.shutdown')
    if shutdown is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    shutdown()
    return ''

class Etheno(object):
    def QUANTITY(to_convert):
        if to_convert is None:
            return None
        elif to_convert[:2] == '0x':
            return int(to_convert[2:], 16)
        else:
            return int(to_convert)
    def DATA(to_convert):
        return decode_hex(to_convert)

    def __init__(self, manticore = None, json_rpc_client = None, accounts = 10, default_balance_ether = 100.0, default_gas_price = 20000000000):
        if manticore is None:
            self.manticore = ManticoreEVM()
            self.manticore.register_detector(DetectInvalid())
            self.manticore.register_detector(DetectIntegerOverflow())
            self.manticore.register_detector(DetectUninitializedStorage())
            self.manticore.register_detector(DetectUninitializedMemory())
            #self.manticore.register_detector(DetectReentrancy())
            #m.multi_tx_analysis(args.argv[0], contract_name=args.contract, tx_limit=args.txlimit, tx_use_coverage=not args.txnocoverage, tx_account=args.txaccount)
        else:
            self.manticore = manticore
        if json_rpc_client is None:
            json_rpc_client = ganache.Ganache(args = ['-a', str(accounts), '-g', str(default_gas_price), '-e', str(default_balance_ether)], port = ganache.find_open_port(GETH_DEFAULT_RPC_PORT + 1))
        self.json_rpc_client = json_rpc_client
        self.accounts = map(lambda a : int(a, 16), json_rpc_client.post({
            'id': 1,
            'jsonrpc': '2.0',
            'method': 'eth_accounts'
        })['result'])
        assert len(list(self.accounts)) == accounts
        for account in self.accounts:
            self.manticore.create_account(balance=int(default_balance_ether * 10**18), address=account)
        self.manticore = threadwrapper.MainThreadWrapper(self.manticore, _CONTROLLER)
        self.default_gas_price = default_gas_price

    def _jsonrpc(**types):
        def decorator(function):
            signature = inspect.getfullargspec(function).args
            def wrapper(self, *args, **kwargs):
                rpc_kwargs = dict(kwargs)
                return_type = None
                converted_args = []
                for i, arg in enumerate(args):
                    if signature[i + 1] in types:
                        converted_args.append(types[signature[i + 1]](arg))
                    else:
                        converted_args.append(arg)
                    rpc_kwargs[signature[i + 1]] = arg
                args = tuple(converted_args)
                kwargs = dict(kwargs)
                for arg_name, conversion in types.items():
                    if arg_name == 'RETURN':
                        return_type = conversion
                    elif arg_name in kwargs:
                        kwargs[arg_name] = conversion(kwargs[arg_name])              
                return function(self, *args, **kwargs)
            return wrapper
        return decorator

    @_jsonrpc(from_addr = QUANTITY, to = QUANTITY, gas = QUANTITY, gasPrice = QUANTITY, value = QUANTITY, data = DATA, nonce = QUANTITY, RETURN = DATA)
    def eth_sendTransaction(self, from_addr, to = None, gas = 90000, gasPrice = None, value = 0, data = None, nonce = None, rpc_client_result = None):
        if gasPrice is None:
            gasPrice = self.default_gas_price
        if to is None or to == 0:
            # we are creating a new contract
            if rpc_client_result is not None:
                tx_hash = rpc_client_result['result']
                receipt = self.json_rpc_client.post({
                    'method' : 'eth_getTransactionReceipt',
                    'params' : [tx_hash]
                })
                address = int(receipt['result']['contractAddress'], 16)
            else:
                address = None
            contract_address = self.manticore.create_contract(owner = from_addr, balance = value, init=data)
            print("")
            print("  Manticore contract created: %s" % encode_hex(contract_address.address))
            print(map(lambda a : hex(a.address), self.manticore.accounts._main.values()))
            #print("  Block number: %s" % self.manticore.world.block_number())
            print("")
        else:
            self.manticore.transaction(address = to, data = data, caller=from_addr, value = value)

    def shutdown(self, port = GETH_DEFAULT_RPC_PORT):
        # Send a web request to the server to shut down:
        #self.manticore.finalize()
        from urllib.request import urlopen
        urlopen("http://127.0.0.1:%d/shutdown" % port)

    def run(self, debug = True, run_publicly = False):
        # Manticore only works in the main thread, so use a threadsafe wrapper:
        def flask_thread():
            if run_publicly:
                host='0.0.0.0'
            else:
                host = None        
            # Do not use the reloader, because Flask needs to run in the main thread to use the reloader
            app.run(debug=debug, host=host, port = GETH_DEFAULT_RPC_PORT, use_reloader = False)
        thread = Thread(target = flask_thread)
        thread.start()

        print("Etheno v%s" % VERSION)

        _CONTROLLER.run()
        self.shutdown()
        thread.join()

ETHENO = Etheno()

class EthenoView(MethodView):
    def post(self):
        data = request.get_json()
        was_list = False
        if isinstance(data, list):
            if len(data) == 1:
                was_list = True
                data = data[0]
            else:
                print("Unexpected POST data: %s" % data)
                abort(400)
        if 'jsonrpc' not in data or 'method' not in data:
            abort(400)
        try:
            jsonrpc_version = float(data['jsonrpc'])
        except ValueError:
            abort(400)
        if jsonrpc_version < 2.0:
            abort(426)
        elif jsonrpc_version > 2.0:
            print("Warning: Client is using a newer version of the JSONRPC protocol! Expected 2.0, but got %s" % jsonrpc_version)
        method = data['method']
        args = ()
        kwargs = {}
        if 'params' in data:
            params = data['params']
            if len(params) == 1 and isinstance(params[0], dict):
                kwargs = dict(params[0])
                # handle Python reserved words:
                if 'from' in kwargs:
                    kwargs['from_addr'] = kwargs['from']
                    del kwargs['from']
            else:
                args = data['params']
        if hasattr(ETHENO, method):
            print("Enrobing JSON RPC call to %s" % method)
            function = getattr(ETHENO, method)
        else:
            function = None
        ret = ETHENO.json_rpc_client.post(data)
        if function is not None:
            kwargs['rpc_client_result'] = ret
            function(*args, **kwargs)
        if was_list:
            ret = [ret]
        return jsonify(ret)

if __name__ == '__main__':
    etheno = EthenoView()
    app.add_url_rule('/', view_func=etheno.as_view('etheno'))
    ETHENO.run()
