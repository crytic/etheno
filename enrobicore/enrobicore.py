#!/usr/bin/env python2

VERSION='0.0.1'
VERSION_NAME="ToB/v%s/source/Enrobicore" % VERSION
JSONRPC_VERSION = '2.0'
VERSION_ID=67

import inspect
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
    if data is None:
        return None
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

class Filter(object):
    def __init__(self):
        self.logs = []

class BlockFilter(Filter):
    pass

class Enrobicore(object):
    def QUANTITY(to_convert):
        if to_convert is None:
            return None
        elif to_convert[:2] == '0x':
            return int(to_convert[2:], 16)
        else:
            return int(to_convert)
    def DATA(to_convert):
        return decode_hex(to_convert)

    def __init__(self, manticore = None, accounts = 10, default_balance_ether = 100.0, default_gas_price = 20000000000):
        if manticore is None:
            self.manticore = ManticoreEVM()
        else:
            self.manticore = manticore
        self.accounts = [self.manticore.create_account(balance=int(default_balance_ether * 10**18)) for i in range(accounts)]
        self.manticore = threadwrapper.MainThreadWrapper(self.manticore, _CONTROLLER)
        self.default_gas_price = default_gas_price
        self.filters = []

    def _jsonrpc(**types):
        def decorator(function):
            signature = inspect.getargspec(function).args
            def wrapper(self, *args, **kwargs):
                return_type = None
                converted_args = []
                for i, arg in enumerate(args):
                    if signature[i + 1] in types:
                        converted_args.append(types[signature[i + 1]](arg))
                    else:
                        converted_args.append(arg)
                args = tuple(converted_args)
                kwargs = dict(kwargs)
                for arg_name, conversion in types.iteritems():
                    if arg_name == 'RETURN':
                        return_type = conversion
                    elif arg_name in kwargs:
                        kwargs[arg_name] = conversion(kwargs[arg_name])
                ret = function(self, *args, **kwargs)
                if return_type is None:
                    return ret
                elif return_type.__name__ == 'DATA':
                    if isinstance(ret, int):
                        return hex(ret)
                    else:
                        return "0x%s" % ret.encode('hex')
                elif return_type.__name__ == 'QUANTITY':
                    return hex(ret)
                else:
                    return ret
            return wrapper
        return decorator
        
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

    @_jsonrpc(from_addr = QUANTITY, to = QUANTITY, gas = QUANTITY, gasPrice = QUANTITY, value = QUANTITY, data = DATA, nonce = QUANTITY, RETURN = DATA)
    def eth_sendTransaction(self, from_addr, to = None, gas = 90000, gasPrice = None, value = 0, data = None, nonce = None):
        if gasPrice is None:
            gasPrice = self.default_gas_price
        if to is None or to == 0:
            # we are creating a new contract
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

    @_jsonrpc(RETURN = QUANTITY)
    def eth_newBlockFilter(self):
        self.filters.append(BlockFilter())
        return len(self.filters) # 1 index filter IDs

    @_jsonrpc(filter_id = QUANTITY)
    def eth_getFilterChanges(self, filter_id):
        # filter_id is 1-indexed:
        filter_id -= 1
        if filter_id >= 0 and filter_id < len(self.filters):
            ret = self.filters[filter_id].logs
            self.filters[filter_id].logs = []
        else:
            ret = []
        return ret
    
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
        if isinstance(data, list):
            if len(data) == 1:
                data = data[0]
            else:
                print "Unexpected POST data: %s" % data
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
                    kwargs['from_addr'] = kwargs['from']
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
