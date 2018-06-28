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

_CONTROLLER = threadwrapper.MainThreadController()

@app.route('/shutdown')
def _enrobicore_shutdown():
    # shut down the Flask server
    shutdown = request.environ.get('werkzeug.server.shutdown')
    if shutdown is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    shutdown()
    return ''

class Enrobicore(object):
    def __init__(self, manticore = None, accounts = 10, default_balance_ether = 100.0, default_gas_price = 20000000000):
        print "ENROBICORE!"
        if manticore is None:
            self.manticore = ManticoreEVM()
        else:
            self.manticore = manticore
        self.accounts = [self.manticore.create_account(balance=int(default_balance_ether * 10**18)) for i in range(accounts)]
        self.manticore = threadwrapper.MainThreadWrapper(self.manticore, _CONTROLLER)
        self.default_gas_price = default_gas_price

    def get_account_index(self, address):
        for i, addr in enumerate(self.accounts):
            if addr == address:
                return i
        return None

    def net_version(self):
        # For now, masquerade as the Eth mainnet
        # TODO: Figure out what Manticore uses
        return '1'

    def eth_accounts(self):
        return map(to_account_address, self.accounts)

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

    def shutdown(self, port = GETH_DEFAULT_RPC_PORT):
        # Send a web request to the server to shut down:
        import urllib2
        urllib2.urlopen("http://127.0.0.1:%d/shutdown" % port)

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

        print "Enrobicore v%s" % VERSION
        print ''
        print 'Available Accounts'
        print '=================='
        for i, addr in enumerate(self.accounts):
            print "(%d) %s" % (i, to_account_address(addr))
        print ''

        _CONTROLLER.run()
        self.shutdown()
        thread.join()

ENROBICORE = Enrobicore()

class EnrobicoreView(MethodView):
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
            else:
                args = data['params']
        if not hasattr(ENROBICORE, method):
            params = ', '.join(args + map(lambda kv : "%s = %s" % kv, kwargs.iteritems()))
            print "Unimplemented JSONRPC method: %s(%s)" % (method, params)
            abort(400)
        print method
        result = getattr(ENROBICORE, method)(*args, **kwargs)
        ret = {
            'jsonrpc' : data['jsonrpc'],
            'result' : result
        }
        if 'id' in data:
            ret['id'] = data['id']
        return jsonify(ret)

if __name__ == '__main__':
    enrobicore = EnrobicoreView()
    app.add_url_rule('/', view_func=enrobicore.as_view('enrobicore'))
    ENROBICORE.run()
