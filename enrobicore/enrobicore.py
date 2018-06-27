#!/usr/bin/env python2

VERSION='0.0.1'
VERSION_NAME="ToB/v%s/source/Enrobicore" % VERSION
JSONRPC_VERSION = '2.0'
VERSION_ID=67

import sha3
from threading import Thread

from flask import Flask, g, jsonify, request, abort
from flask.views import MethodView

from manticore.ethereum import ManticoreEVM

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
    if data[:2] == '0x':
        data = data[2:]
    return data.decode('hex')

MANTICORE = ManticoreEVM()
ACCOUNTS = None
_CONTROLLER = threadwrapper.MainThreadController()

class Enrobicore(MethodView):
    def __init__(self, manticore = None, default_gas_price = 20000000000):
        if manticore is None:
            manticore = MANTICORE
        self.manticore = threadwrapper.MainThreadWrapper(manticore, _CONTROLLER)
        self.default_gas_price = default_gas_price

    def get_account_index(self, address):
        for i, addr in enumerate(ACCOUNTS):
            if addr == address:
                return i
        return None
        
    def post(self):
        data = request.get_json()
        if 'jsonrpc' not in data or 'method' not in data:
            abort(400)
        try:
            jsonrpc_version = float(data['jsonrpc'])
        except ValueError:
            abort(400)
        if jsonrpc_version < 2.0:
            abort(426)
        elif jsonrpc_version > 2.0:
            print "Warning: Client is using a newer version of the JSONRPC protocol! Expected 2.0, but got %s" % jsonrpc_version
        method = data['method']
        args = ()
        kwargs = {}
        if 'params' in data:
            params = data['params']
            if len(params) == 1 and isinstance(params[0], dict):
                kwargs = params[0]
                # handle Python reserved words:
                if 'from' in kwargs:
                    kwargs['from_addr'] = int(kwargs['from'], 16)
                    del kwargs['from']
                print kwargs
            else:
                args = data['params']
        if not hasattr(self, method):
            print "Unimplemented JSONRPC method: %s" % method
            abort(400)
        print method
        result = getattr(self, method)(*args, **kwargs)
        ret = {
            'jsonrpc' : data['jsonrpc'],
            'result' : result
        }
        if 'id' in data:
            ret['id'] = data['id']
        return jsonify(ret)

    def net_version(self):
        # For now, masquerade as the Eth mainnet
        # TODO: Figure out what Manticore uses
        return '1'

    def eth_accounts(self):
        return map(to_account_address, ACCOUNTS)

    def eth_sendTransaction(self, from_addr, to = None, gas = 90000, gasPrice = None, value = 0, data = None, nonce = None):
        if gasPrice is None:
            gasPrice = self.default_gas_price
        else:
            gasPrice = decode_hex(gasPrice)
        if to is None or to == 0:
            # we are creating a new contract
            if data is not None:
                data = decode_hex(data)
            tr = self.manticore.create_contract(owner = from_addr, balance = value, init=data)
            return 0
        else:
            args = {
                'caller' : from_addr,
                data : data
            }
            if to is not None:
                args['address'] = self.get_account_index(to)
                if value is not None:
                    args['value'] = value
                tr = self.manticore.transaction(**args)
                #print from_addr, to, gas, gasPrice, value, data
                print tr
                #abort(500)
        return tr

    def run(self, debug = True, run_publicly = False, accounts = 10, default_balance_ether = 100.0):
        global ACCOUNTS
        if ACCOUNTS is None:
            ACCOUNTS = [self.manticore.create_account(balance=int(default_balance_ether * 10**18)) for i in range(accounts)]
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

        print "Enrobicore v%s" % VERSION
        print ''
        print 'Available Accounts'
        print '=================='
        for i, addr in enumerate(ACCOUNTS):
            print "(%d) %s" % (i, to_account_address(addr))
        print ''

        _CONTROLLER.run()
        thread.join()

if __name__ == '__main__':
    enrobicore = Enrobicore()
    app.add_url_rule('/', view_func=enrobicore.as_view('enrobicore'))
    enrobicore.run()
