import http
import inspect
import json
import time
from typing import Any, Dict, List, Optional, Set, Union
from urllib.request import Request, urlopen

from . import logger
from .utils import decode_hex, format_hex_address, webserver_is_up


def jsonrpc(**types):
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


class RpcHttpProxy:
    def __init__(self, urlstring):
        self.urlstring = urlstring
        self.rpc_id = 0

    def post(self, data) -> Dict[str, Union[int, str, Dict[str, Any]]]:
        data = dict(data)
        self.rpc_id += 1
        return_id = None
        if 'jsonrpc' not in data:
            data['jsonrpc'] = '2.0'
        if 'id' in data:
            return_id = data['id']
            data['id'] = self.rpc_id
        request = Request(
            self.urlstring,
            data=bytearray(json.dumps(data), 'utf8'),
            headers={'Content-type': 'application/json'}
        )
        ret = json.loads(urlopen(request).read())
        if return_id is not None and 'id' in ret:
            ret['id'] = return_id
        return ret

    def __str__(self):
        return f"{self.__class__.__name__}<{self.urlstring}>"

    def __repr__(self):
        return f"{self.__class__.__name__}({self.urlstring})"


class JSONRPCError(RuntimeError):
    def __init__(self, client, data, result):
        super().__init__(
            "JSON RPC Error in Client %s when processing transaction:\n%s\n%s" % (client, data, result['error'])
        )
        self.client = client
        self.json = data
        self.result = result


def transaction_receipt_succeeded(data):
    if not (data and 'result' in data and data['result']):
        return None
    elif 'contractAddress' in data['result'] and data['result']['contractAddress']:
        return True
    elif 'blockHash' in data['result'] and data['result']['blockHash']:
        return True
    elif 'status' not in data['result']:
        return None
    status = data['result']['status']
    if status is None:
        return None
    elif not isinstance(status, int):
        status = int(status, 16)
    return status > 0


class EthenoClient:
    _etheno = None
    logger = None
    _short_name = None

    @property
    def etheno(self):
        return self._etheno

    @etheno.setter
    def etheno(self, instance):
        if self._etheno is not None:
            if instance is None:
                self._etheno = None
                return
            elif instance == self._etheno:
                return
            raise ValueError('An Etheno client can only ever be associated with a single Etheno instance')
        self._etheno = instance
        self.logger = logger.EthenoLogger(self.short_name, parent=self._etheno.logger)
        self.etheno_set()

    @property
    def log_directory(self) -> Optional[str]:
        """Returns a log directory that this client can use to save additional files, or None if one is not available"""
        if self.logger is None:
            return None
        else:
            return self.logger.directory

    def etheno_set(self):
        """A callback for once the etheno instance and logger for this client is set"""
        pass

    def create_account(self, balance = 0, address = None):
        """A request for the client to create a new account.

        Subclasses implementing this function should raise a NotImplementedError if an address
        was provided that the client is unable to create an account at that address

        :param balance: The initial balance for the account
        :param address: The address for the account, or None if the address should be auto-generated
        :return: returns the address of the account created
        """
        raise NotImplementedError('Clients must extend this function')

    def shutdown(self):
        pass

    def wait_for_transaction(self, tx_hash):
        return None

    @property
    def short_name(self):
        if self._short_name is None:
            return str(self)
        else:
            return self._short_name

    @short_name.setter
    def short_name(self, name):
        self._short_name = name


class SelfPostingClient(EthenoClient):
    def __init__(self, client):
        self.client = client
        self._accounts: Optional[List[int]] = None
        self._created_account_index = -1
        # maintain a set of failed transactions so we know not to block on eth_getTransactionReceipt
        self._failed_transactions: Set[str] = set()

    def create_account(self, balance: int = 0, address: Optional[int] = None):
        if address is not None:
            raise NotImplementedError()
        if self._accounts is None:
            self._accounts = list(int(a, 16) for a in self.post({
                'id': 1,
                'jsonrpc': '2.0',
                'method': 'eth_accounts'
            })['result'])
        self._created_account_index += 1
        return self._accounts[self._created_account_index]

    def wait_until_running(self):
        pass

    def post(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        ret = self.client.post(data)
        if ret is not None and 'error' in ret:
            if 'method' in data and (
                    data['method'] == 'eth_sendTransaction' or data['method'] == 'eth_sendRawTransaction'
            ):
                if self.etheno.master_client != self and self.etheno.rpc_client_result \
                        and not isinstance(self.etheno.rpc_client_result, JSONRPCError) \
                        and 'result' in self.etheno.rpc_client_result:
                    self.logger.error(f"{self!s}: Failed transaction associated with master client transaction "
                                      f"{self.etheno.rpc_client_result['result']}")
                    self._failed_transactions.add(self.etheno.rpc_client_result['result'].lower())
            # TODO: Figure out a better way to handle JSON RPC errors
            raise JSONRPCError(self, data, ret)
        return ret

    def estimate_gas(self, transaction: Dict[str, Any]) -> int:
        """Estimates the gas cost for the given transaction or call

        :param transaction: a dict containing the entire transaction as if it were to be sent to `post()`
        :return: the gas cost in wei as an int
        """
        return int(self.post({
            'id': 1,
            'jsonrpc': '2.0',
            'method': 'eth_estimateGas',
            'params': transaction['params']
        })['result'], 16)

    def get_gas_price(self) -> int:
        return int(self.post({
            'id': 1,
            'jsonrpc': '2.0',
            'method': 'eth_gasPrice'
        })['result'], 16)

    def get_net_version(self) -> int:
        return int(self.post({
            'id': 1,
            'jsonrpc': '2.0',
            'method': 'net_version'
        })['result'], 16)

    def get_transaction_count(self, from_address) -> int:
        return int(self.post({
            'id': 1,
            'jsonrpc': '2.0',
            'method': 'eth_getTransactionCount',
            'params': [format_hex_address(from_address, True), 'latest']
        })['result'], 16)

    def wait_for_transaction(self, tx_hash):
        """Blocks until the given transaction has been mined
        :param tx_hash: the transaction hash for the transaction to monitor
        :return: The transaction receipt
        """
        if isinstance(tx_hash, int):
            tx_hash = "0x%x" % tx_hash
        tx_hash = tx_hash.lower()
        while True:
            receipt = self.post({
                'id': 1,
                'jsonrpc': '2.0',
                'method': 'eth_getTransactionReceipt',
                'params': [tx_hash]
            })
            if tx_hash in self._failed_transactions or transaction_receipt_succeeded(receipt) is not None:
                return receipt
            self.logger.info("Waiting to mine transaction %s..." % tx_hash)
            time.sleep(5.0)

    def __str__(self):
        return f"{self.__class__.__name__}[{self.client!s}]"

    def __repr__(self):
        return f"{self.__class__.__name__}[{self.client!r}]"


class RpcProxyClient(SelfPostingClient):
    def __init__(self, rpcurl):
        super().__init__(RpcHttpProxy(rpcurl))

    def post(self, data):
        while True:
            try:
                return super().post(data)
            except http.client.RemoteDisconnected as e:
                self.logger.warning(str(e))
                time.sleep(1.0)
                self.logger.info(f"Retrying JSON RPC call to {self.client.urlstring}")

    def is_running(self) -> bool:
        return webserver_is_up(self.client.urlstring)

    def wait_until_running(self):
        slept = 0.0
        while not self.is_running():
            time.sleep(0.25)
            slept += 0.25
            if slept % 5 == 0:
                self.logger.info("Waiting for the client to start...")


def QUANTITY(to_convert: Optional[str]) -> Optional[int]:
    if to_convert is None:
        return None
    elif to_convert[:2] == '0x':
        return int(to_convert[2:], 16)
    else:
        return int(to_convert)


def DATA(to_convert: Optional[str]) -> Optional[bytes]:
    return decode_hex(to_convert)
