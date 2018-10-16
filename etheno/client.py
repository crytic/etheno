import inspect

from .utils import webserver_is_up

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

class EthenoClient(object):
    etheno = None

    def create_account(self, balance, address):
        pass

    def shutdown(self):
        pass

class SelfPostingClient(EthenoClient):
    def __init__(self, client):
        self.client = client
    def wait_until_running(self):
        pass
    def post(self, data):
        return self.client.post(data)
    def __str__(self):
        return str(self.client)
    def __repr__(self):
        return repr(self.client)

class RpcProxyClient(SelfPostingClient):
    def __init__(self, rpcurl):
        super().__init__(ganache.RpcHttpProxy(rpcurl))
    def wait_until_running(self):
        while not webserver_is_up(self.client.urlstring):
            time.sleep(1.0)

def decode_hex(data):
    if data is None:
        return None
    if data[:2] == '0x':
        data = data[2:]
    return bytes.fromhex(data)

def QUANTITY(to_convert):
    if to_convert is None:
        return None
    elif to_convert[:2] == '0x':
        return int(to_convert[2:], 16)
    else:
        return int(to_convert)

def DATA(to_convert):
    return decode_hex(to_convert)
