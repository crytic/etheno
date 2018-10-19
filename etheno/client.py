import inspect
import json
from urllib.request import Request, urlopen

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

class RpcHttpProxy(object):
    def __init__(self, urlstring):
        self.urlstring = urlstring
        self.rpc_id = 0
    def post(self, data):
        data = dict(data)
        self.rpc_id += 1
        rpc_id = self.rpc_id
        return_id = None
        if 'jsonrpc' not in data:
            data['jsonrpc'] = '2.0'
        if 'id' in data:
            return_id = data['id']
            data['id'] = self.rpc_id
        request = Request(self.urlstring, data = bytearray(json.dumps(data), 'utf8'), headers={'Content-type': 'application/json'})
        ret = json.loads(urlopen(request).read())
        if return_id is not None and 'id' in ret:
            ret['id'] = return_id
        return ret
    def __str__(self):
        return "%s<%s>" % (self.__class__.__name__, self.urlstring)
    __repr__ = __str__

class EthenoClient(object):
    etheno = None

    def create_account(self, balance = 0, address = None):
        '''
        A request for the client to create a new account.

        Subclasses implementing this function should raise a NotImplementedError if an address
        was provided that the client is unable to create an account at that address

        :param balance: The initial balance for the account
        :param address: The address for the account, or None if the address should be auto-generated
        :return: returns the address of the account created
        '''
        raise NotImplementedError('Clients must extend this function')

    def shutdown(self):
        pass

class SelfPostingClient(EthenoClient):
    def __init__(self, client):
        self.client = client
        self._accounts = None
        self._created_account_index = -1
    def create_account(self, balance = 0, address = None):
        if address is not None:
            raise NotImplementedError()
        if self._accounts is None:
            self._accounts = list(map(lambda a : int(a, 16), self.post({
                'id': 1,
                'jsonrpc': '2.0',
                'method': 'eth_accounts'
            })['result']))
        self._created_account_index += 1
        return self._accounts[self._created_account_index]
    def wait_until_running(self):
        pass
    def post(self, data):
        return self.client.post(data)
    def get_gas_price(self):
        return int(self.post({
            'id': 1,
            'jsonrpc': '2.0',
            'method': 'eth_gasPrice'
        })['result'], 16)
    def get_net_version(self):
        return int(self.post({
            'id': 1,
            'jsonrpc': '2.0',
            'method': 'net_version'
        })['result'], 16)
    def get_transaction_count(self, from_address):
        return int(self.post({
            'id': 1,
            'jsonrpc': '2.0',
            'method': 'eth_getTransactionCount',
            'params': [format_hex_address(from_address), 'latest']
        })['result'], 16)
    def __str__(self):
        return str(self.client)
    def __repr__(self):
        return repr(self.client)
    def __str__(self):
        return "%s[%s]" % (self.__class__.__name__, str(self.client))
    __repr__ = __str__

class RpcProxyClient(SelfPostingClient):
    def __init__(self, rpcurl):
        super().__init__(RpcHttpProxy(rpcurl))
    def wait_until_running(self):
        while not webserver_is_up(self.client.urlstring):
            time.sleep(1.0)

def QUANTITY(to_convert):
    if to_convert is None:
        return None
    elif to_convert[:2] == '0x':
        return int(to_convert[2:], 16)
    else:
        return int(to_convert)

def DATA(to_convert):
    return decode_hex(to_convert)
