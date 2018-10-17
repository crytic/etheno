VERSION='0.0.1'
VERSION_NAME="ToB/v%s/source/Etheno" % VERSION
JSONRPC_VERSION = '2.0'
VERSION_ID=67

import sha3
from threading import Thread
import time

from flask import Flask, g, jsonify, request, abort
from flask.views import MethodView

from manticore.ethereum import ManticoreEVM

from . import threadwrapper
from .client import EthenoClient, SelfPostingClient, RpcProxyClient, DATA, QUANTITY, jsonrpc

app = Flask(__name__)

GETH_DEFAULT_RPC_PORT = 8545
ETH_DEFAULT_RPC_PORT = 8545
PARITY_DEFAULT_RPC_PORT = 8545
PYETHAPP_DEFAULT_RPC_PORT = 4000

def to_account_address(raw_address):
    addr = "%x" % raw_address
    return "0x%s%s" % ('0'*(40 - len(addr)), addr)

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
    _CONTROLLER.quit()
    shutdown()
    return ''

class ManticoreClient(EthenoClient):
    def __init__(self, manticore=None):
        if manticore is None:
            manticore = ManticoreEVM()
        self.manticore = threadwrapper.MainThreadWrapper(manticore, _CONTROLLER)
        self.contracts = []

    def create_account(self, balance, address):
        self.manticore.create_account(balance=balance, address=address)        

    @jsonrpc(from_addr = QUANTITY, to = QUANTITY, gas = QUANTITY, gasPrice = QUANTITY, value = QUANTITY, data = DATA, nonce = QUANTITY, RETURN = DATA)
    def eth_sendTransaction(self, from_addr, to = None, gas = 90000, gasPrice = None, value = 0, data = None, nonce = None, rpc_client_result = None):
        if to is None or to == 0:
            # we are creating a new contract
            if rpc_client_result is not None:
                tx_hash = rpc_client_result['result']
                while True:
                    receipt = self.etheno.master_client.post({
                        'id' : "%s_receipt" % rpc_client_result['id'],
                        'method' : 'eth_getTransactionReceipt',
                        'params' : [tx_hash]
                    })
                    if 'result' in receipt and receipt['result']:
                        address = int(receipt['result']['contractAddress'], 16)
                        break
                    # The transaction is still pending
                    time.sleep(1.0)
            else:
                address = None
            contract_address = self.manticore.create_contract(owner = from_addr, balance = value, init=data)
            self.contracts.append(contract_address)
            print("")
            print("  Manticore contract created: %s" % encode_hex(contract_address.address))
            print(map(lambda a : hex(a.address), self.manticore.accounts.values()))
            #print("  Block number: %s" % self.manticore.world.block_number())
            print("")
        else:
            self.manticore.transaction(address = to, data = data, caller=from_addr, value = value)

    def multi_tx_analysis(self, contract_address = None, tx_limit=None, tx_use_coverage=True, args=None):
        if contract_address is None:
            for contract_address in self.contracts:
                self.multi_tx_analysis(contract_address = contract_address, tx_limit = tx_limit, tx_use_coverage = tx_use_coverage, args = args)
            return

        tx_account = self.etheno.accounts

        prev_coverage = 0
        current_coverage = 0
        tx_no = 0
        while (current_coverage < 100 or not tx_use_coverage) and not self.manticore.is_shutdown():
            try:
                print("Starting symbolic transaction: %d" % tx_no)

                # run_symbolic_tx
                symbolic_data = self.manticore.make_symbolic_buffer(320)
                symbolic_value = self.manticore.make_symbolic_value()
                self.manticore.transaction(caller=tx_account[min(tx_no, len(tx_account) - 1)],
                                 address=contract_address,
                                 data=symbolic_data,
                                 value=symbolic_value)
                print("%d alive states, %d terminated states" % (self.manticore.count_running_states(), self.manticore.count_terminated_states()))
            except NoAliveStates:
                break

            # Check if the maximun number of tx was reached
            if tx_limit is not None and tx_no + 1 >= tx_limit:
                break

            # Check if coverage has improved or not
            if tx_use_coverage:
                prev_coverage = current_coverage
                current_coverage = self.manticore.global_coverage(contract_address)
                found_new_coverage = prev_coverage < current_coverage

                if not found_new_coverage:
                    break

            tx_no += 1
            
    def __str__(self): return 'manticore'
    __repr__ = __str__

class Etheno(object):
    def __init__(self, master_client=None):
        self.accounts = []
        self._master_client = None
        if master_client is None:
            self.master_client = None
        else:
            self.master_client = master_client
        self.clients = []
        self.rpc_client_result = None

    @property
    def master_client(self):
        return self._master_client

    @master_client.setter
    def master_client(self, client):
        if client is None:
            if self._master_client is not None:
                self._master_client.etheno = None
                self._master_client = None
            return
        if not isinstance(client, SelfPostingClient):
            raise Exception('The master client must be an instance of a SelfPostingClient')
        client.etheno = self
        self._master_client = client
        self.accounts = list(map(lambda a : int(a, 16), client.post({
            'id': 1,
            'jsonrpc': '2.0',
            'method': 'eth_accounts'
        })['result']))
        for client in self.clients:
            self._create_accounts(client)

    def _create_accounts(self, client):
        for account in self.accounts:
            # TODO: Actually get the correct balance from the JSON RPC client instead of using hard-coded 100.0 ETH
            client.create_account(balance=int(100.0 * 10**18), address=account)

    def add_client(self, client):
        client.etheno = self
        self.clients.append(client)
        self._create_accounts(client)
            
    def shutdown(self, port = GETH_DEFAULT_RPC_PORT):
        # Send a web request to the server to shut down:
        #self.manticore.finalize()
        if self.master_client:
            self.master_client.shutdown()
        for client in self.clients:
            client.shutdown()
        from urllib.request import urlopen
        import socket
        try:
            urlopen("http://127.0.0.1:%d/shutdown" % port, timeout = 2)
        except socket.timeout:
            pass

    def run(self, debug=True, run_publicly=False, port=GETH_DEFAULT_RPC_PORT):
        # Manticore only works in the main thread, so use a threadsafe wrapper:
        def flask_thread():
            if run_publicly:
                host='0.0.0.0'
            else:
                host = None        
            # Do not use the reloader, because Flask needs to run in the main thread to use the reloader
            app.run(debug=debug, host=host, port = port, use_reloader = False)
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
        if ETHENO.master_client is None:
            ret = None
        else:
            ret = ETHENO.master_client.post(data)

        ETHENO.rpc_client_result = ret

        for client in ETHENO.clients:
            if hasattr(client, method):
                print("Enrobing JSON RPC call to %s.%s" % (client, method))
                function = getattr(client, method)
                if function is not None:
                    kwargs['rpc_client_result'] = ret
                    function(*args, **kwargs)
            elif isinstance(client, SelfPostingClient):
                client.post(data)
        if ret is None:
            return None
        elif was_list:
            ret = [ret]
        return jsonify(ret)
