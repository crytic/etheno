VERSION='0.2.0'
VERSION_NAME="ToB/v%s/source/Etheno" % VERSION
JSONRPC_VERSION = '2.0'
VERSION_ID=67

import logging
from threading import Thread

from flask import Flask, g, jsonify, request, abort
from flask.views import MethodView

from . import logger
from . import threadwrapper
from .client import JSONRPCError, SelfPostingClient
from .utils import format_hex_address

app = Flask(__name__)

GETH_DEFAULT_RPC_PORT = 8545
ETH_DEFAULT_RPC_PORT = 8545
PARITY_DEFAULT_RPC_PORT = 8545
PYETHAPP_DEFAULT_RPC_PORT = 4000

def to_account_address(raw_address):
    addr = "%x" % raw_address
    return "0x%s%s" % ('0'*(40 - len(addr)), addr)

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

class EthenoPlugin(object):
    _etheno = None
    logger = None

    @property
    def etheno(self):
        return self._etheno

    @etheno.setter
    def etheno(self, instance):
        if self._etheno is not None:
            if instance is None:
                self._etheno = None
                return
            raise ValueError('An Etheno plugin can only ever be associated with a single Etheno instance')
        self._etheno = instance
        self.logger = logger.EthenoLogger(self.__class__.__name__, parent=self._etheno.logger)

    @property
    def log_directory(self):
        """Returns a log directory that this client can use to save additional files, or None if one is not available"""
        if self.logger is None:
            return None
        else:
            return self.logger.directory

    def added(self):
        """
        A callback when this plugin is added to an Etheno instance
        """
        pass
    
    def before_post(self, post_data):
        """
        A callback when Etheno receives a JSON RPC POST, but before it is processed.
        :param post_data: The raw JSON RPC data
        :return: the post_data to be used by Etheno (can be modified)
        """
        pass

    def after_post(self, post_data, client_results):
        """
        A callback when Etheno receives a JSON RPC POST after it is processed by all clients.
        :param post_data: The raw JSON RPC data
        :param client_results: A lost of the results returned by each client
        """
        pass

    def run(self):
        """
        A callback when Etheno is running and all other clients and plugins are initialized
        """
        pass
    
    def finalize(self):
        """
        Called when an analysis pass should be finalized (e.g., after a Truffle migration completes).
        Subclasses implementing this function should support it to be called multiple times in a row.
        """
        pass

    def shutdown(self):
        """
        Called before Etheno shuts down.
        The default implementation calls `finalize()`.
        """
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
        self.logger = logger.EthenoLogger('Etheno', logger.INFO)

    @property
    def log_level(self):
        return self.logger.log_level

    @log_level.setter
    def log_level(self, level):
        self.logger.log_level = level

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

    def estimate_gas(self, transaction):
        """
        Estimates the gas cost of a transaction.
        Iterates through all clients until it finds a client that is capable of estimating the gas cost without error.
        If all clients return an error, this function will return None.
        """
        clients = [self.master_client] + self.clients
        for client in clients:
            try:
                return self.master_client.estimate_gas(transaction)
            except JSONRPCError:
                continue
        return None
            
    def post(self, data):
        self.logger.debug(f"Handling JSON RPC request {data}")

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
                if 'id' in data and 'id' in ret:
                    ret['id'] = data['id']
            else:
                try:
                    ret = self.master_client.post(data)
                except JSONRPCError as e:
                    self.logger.error(e)
                    ret = e
    
        self.rpc_client_result = ret
        self.logger.debug(f"Result from the master client ({self.master_client}): {ret}")

        results = []

        for client in self.clients:
            try:
                if hasattr(client, method):
                    self.logger.info("Enrobing JSON RPC call to %s.%s" % (client, method))
                    function = getattr(client, method)
                    if function is not None:
                        kwargs['rpc_client_result'] = ret
                        results.append(function(*args, **kwargs))
                    else:
                        self.logger.warn(f"Function {method} of {client} is None!")
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
                self.logger.error(e)
                results.append(e)
            self.logger.debug(f"Result from client {client}: {results[-1]}")

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

    def deploy_contract(self, from_address, bytecode, gas=0x99999, gas_price=None, value=0):
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
        receipt = self.master_client.wait_for_transaction(tx_hash)
        if 'result' in receipt and receipt['result'] and 'contractAddress' in receipt['result'] and receipt['result']['contractAddress']:
            return int(receipt['result']['contractAddress'], 16)
        else:
            return None

    def shutdown(self, port=GETH_DEFAULT_RPC_PORT):
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
        self.logger.close()
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

        self.logger.info("Etheno v%s" % VERSION)

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
                ETHENO.logger.error("Unexpected POST data: %s" % data)
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
            ETHENO.logger.warn("Client is using a newer version of the JSONRPC protocol! Expected 2.0, but got %s" % jsonrpc_version)

        ret = ETHENO.post(data)

        ETHENO.logger.debug(f"Returning {ret}")

        if ret is None:
            return None

        if isinstance(ret, JSONRPCError):
            ret = ret.result

        if was_list:
            ret = [ret]
        ret = jsonify(ret)
        
        return ret
