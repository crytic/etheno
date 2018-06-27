#!/usr/bin/env python2

VERSION='0.0.1'
VERSION_NAME="ToB/v%s/source/Enrobicore" % VERSION
JSONRPC_VERSION = '2.0'
VERSION_ID=67

from flask import Flask, g, jsonify, request, abort
from flask.views import MethodView
from manticore.ethereum import ManticoreEVM

app = Flask(__name__)

GETH_DEFAULT_RPC_PORT = 8545
ETH_DEFAULT_RPC_PORT = 8545
PARITY_DEFAULT_RPC_PORT = 8545
PYETHAPP_DEFAULT_RPC_PORT = 4000

def to_account_address(raw_address):
    addr = "%x" % raw_address
    return "0x%s%s" % ('0'*(40 - len(addr)), addr)

class Enrobicore(MethodView):
    def __init__(self, accounts = 10, default_balance_ether = 100.0, default_gas_price = 20000000000):
        self.manticore = ManticoreEVM()
        self.accounts = [self.manticore.create_account(balance=int(default_balance_ether * 10**18)) for i in range(accounts)]
        self.default_gas_price = default_gas_price

    def get_account_index(self, address):
        for i, addr in enumerate(self.accounts):
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
                    kwargs['from_addr'] = kwargs['from']
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
        return map(to_account_address, self.accounts)

    def eth_sendTransaction(self, from_addr, to = None, gas = 90000, gasPrice = None, value = 0, data = None, nonce = None):
        if gasPrice is None:
            gasPrice = self.default_gas_price
        if to is None or to == 0:
            # we are creating a new contract
            tr = self.manticore.create_contract(owner = from_addr, balance = value, init=data)
            print tr
        else:
            args = {
                'caller' : self.get_account_index(from_addr),
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


enrobicore = Enrobicore()

app.add_url_rule('/', view_func=Enrobicore.as_view('enrobicore'))
    
# @app.route('/', methods=['POST'])
# def index():
#     print request.data, request.args
#     return "index"

# def set_manticore(manticore):
#     with app.app_context():
#         g.manticore = manticore

# def jsonrpc(api_name, methods=['POST','GET']):
#     def decorator(handler):
#         @app.route("/web3_%s" % api_name, methods=methods)
#         def wrapper(*args, **kwargs):
#             # lazily instantiate g.manticore if the user didn't manually call set_manticore:
#             if not hasattr(g, 'manticore'):
#                 set_manticore(ManticoreEVM())
#             return jsonify(handler(*args, **kwargs))
#         return wrapper
#     return decorator

# @jsonrpc('clientVersion')
# def web3_clientVersion():
#     return {
#         'id' : VERSION_ID,
#         'jsonrpc' : JSONRPC_VERSION,
#         'result' : VERSION_NAME
#     }

# @app.after_request
# def after_request(response):
#     #timestamp = strftime('[%Y-%b-%d %H:%M]')
#     print "%s %s %s %s %s" % (request.remote_addr, request.method, request.scheme, request.full_path, response.status)
#     return response

if __name__ == '__main__':
    run_publicly = False
    if run_publicly:
        host='0.0.0.0'
    else:
        host = None
    app.run(debug=True, host=host, port = GETH_DEFAULT_RPC_PORT)
