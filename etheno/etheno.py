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
from .client import EthenoClient, JSONRPCError, RpcProxyClient, SelfPostingClient, DATA, QUANTITY, transaction_receipt_succeeded, jsonrpc
from .utils import format_hex_address

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
        # Just mimic the result from the master client
        # We need to return something valid to appease the differential tester
        return rpc_client_result

    @jsonrpc(TX_HASH = QUANTITY)
    def eth_getTransactionReceipt(self, tx_hash, rpc_client_result = None):
        # Mimic the result from the master client
        # to appease the differential tester
        return rpc_client_result
    
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

class EthenoPlugin():
    etheno = None

    def added(self):
        '''
        A callback when this plugin is added to an Etheno instance
        '''
        pass
    
    def before_post(self, post_data):
        '''
        A callback when Etheno receives a JSON RPC POST, but before it is processed.
        :param post_data: The raw JSON RPC data
        :return: the post_data to be used by Etheno (can be modified)
        '''
        pass

    def after_post(self, post_data, client_results):
        '''
        A callback when Etheno receives a JSON RPC POST after it is processed by all clients.
        :param post_data: The raw JSON RPC data
        :param client_results: A lost of the results returned by each client
        '''
        pass

    def run(self):
        '''
        A callback when Etheno is running and all other clients and plugins are initialized
        '''
        pass
    
    def finalize(self):
        '''
        Called when an analysis pass should be finalized (e.g., after a Truffle migration completes).
        Subclasses implementing this function should support it to be called multiple times in a row.
        '''
        pass

    def shutdown(self):
        '''
        Called before Etheno shuts down.
        The default implementation calls `finalize()`.
        '''
        self.finalize()

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
        self.plugins = []
        self._shutting_down = False

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

    def post(self, data):
        for plugin in self.plugins:
            plugin.before_post(data)

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
        if self.master_client is None:
            ret = None
        else:
            if method == 'eth_getTransactionReceipt':
                # for eth_getTransactionReceipt, make sure we block until all clients have mined the transaction
                ret = self.master_client.wait_for_transaction(data['params'][0])
            else:
                try:
                    ret = self.master_client.post(data)
                except JSONRPCError as e:
                    print(e)
                    ret = None
    
        self.rpc_client_result = ret

        results = []

        for client in self.clients:
            try:
                if hasattr(client, method):
                    print("Enrobing JSON RPC call to %s.%s" % (client, method))
                    function = getattr(client, method)
                    if function is not None:
                        kwargs['rpc_client_result'] = ret
                        results.append(function(*args, **kwargs))
                    else:
                        results.append(None)
                elif isinstance(client, SelfPostingClient):
                    if method == 'eth_getTransactionReceipt':
                        # for eth_getTransactionReceipt, make sure we block until all clients have mined the transaction
                        results.append(client.wait_for_transaction(data['params'][0]))
                    else:
                        results.append(client.post(data))
                else:
                    results.append(None)
            except JSONRPCError as e:
                print(e)
                results.append(None)

        if ret is None:
            return None

        results = [ret] + results
        for plugin in self.plugins:
            plugin.after_post(data, results)

        return ret
            
    def add_plugin(self, plugin):
        plugin.etheno = self
        self.plugins.append(plugin)
        plugin.added()

    def remove_plugin(self, plugin):
        '''
        Removes a plugin, automatically calling plugin.shutdown() in the process
        :param plugin: The plugin to remove
        '''
        self.plugins.remove(plugin)
        plugin.shutdown()
        plugin.etheno = None
        
    def _create_accounts(self, client):
        for account in self.accounts:
            # TODO: Actually get the correct balance from the JSON RPC client instead of using hard-coded 100.0 ETH
            client.create_account(balance=int(100.0 * 10**18), address=account)

    def add_client(self, client):
        client.etheno = self
        self.clients.append(client)
        self._create_accounts(client)

    def wait_for_transaction(self, tx_hash):
        while True:
            receipt = self.post({
                'id': 1,
                'jsonrpc': '2.0',
                'method': 'eth_getTransactionReceipt',
                'params': [tx_hash]
            })
            if transaction_receipt_succeeded(receipt) is not None:
                return receipt
            print("Waiting for %s to mine transaction %s..." % (self.master_client, data['params'][0]))
            time.sleep(5.0)

    def deploy_contract(self, from_address, bytecode, gas = 0x99999, gas_price = None, value = 0):
        if gas_price is None:
            gas_price = self.master_client.get_gas_price()
        if isinstance(bytecode, bytes):
            bytecode = bytecode.decode()
        if not bytecode.startswith('0x'):
            bytecode = "0x%s" % bytecode
        tx_hash = self.post({
            'id': 1,
            'jsonrpc': '2.0',
            'method': 'eth_sendTransaction',
            'params': [{ 
                "from": format_hex_address(from_address, True),
                "gas": "0x%x" % gas,
                "gasPrice": "0x%x" % gas_price,
                "value": "0x0",
                "data": bytecode
            }]
        })['result']
        receipt = self.wait_for_transaction(tx_hash)
        if 'result' in receipt and receipt['result'] and 'contractAddress' in receipt['result'] and receipt['result']['contractAddress']:
            return int(receipt['result']['contractAddress'], 16)
        else:
            return None

    def shutdown(self, port = GETH_DEFAULT_RPC_PORT):
        if self._shutting_down:
            return
        self._shutting_down = True
        for plugin in self.plugins:
            plugin.shutdown()
        # Send a web request to the server to shut down:
        if self.master_client:
            self.master_client.shutdown()
        for client in self.clients:
            client.shutdown()
        from urllib.request import urlopen
        import socket
        import urllib
        try:
            urlopen("http://127.0.0.1:%d/shutdown" % port, timeout = 2)
        except socket.timeout:
            pass
        except urllib.error.URLError:
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

        for plugin in self.plugins:
            plugin.run()

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

        ret = ETHENO.post(data)

        if ret is None:
            return None

        if was_list:
            ret = [ret]
        ret = jsonify(ret)
        
        return ret
