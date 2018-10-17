from .client import EthenoClient, SelfPostingClient, jsonrpc, DATA, QUANTITY
from .utils import decode_hex, format_hex_address

def _decode_value(value):
    if isinstance(value, int):
        return value
    try:
        return decode_hex(value)
    except Exception:
        return None

def _remap_params(params, mapping, method, remap_data = False):
    if isinstance(params, dict):
        for key, value in params.items():
            decoded = _decode_value(value)
            if decoded is None:
                params[key] = _remap_params(value, mapping, "%s['%s']" % (method, key))
            elif decoded in mapping:
                print("Converting %s parameter %s from address %x to %x" % (method, key, decoded, mapping[decoded]))
                params[key] = format_hex_address(mapping[decoded])
            elif remap_data and key == 'data':
                new_value = params['data']
                for old, new in mapping.items():
                    prev = new_value
                    new_value = new_value.replace(format_hex_address(old), format_hex_address(new))
                    if prev != new_value:
                        print("Converting address %x in %s['data'] to %x" % (old, method, new))
                if new_value != params['data']:
                    params['data'] = new_value
    elif isinstance(params, list) or isinstance(params, tuple):
        for i, p in enumerate(params):
            decoded = _decode_value(p)
            if decoded is None:
                params[i] = _remap_params(p, mapping, "%s['%d']" % (method, i))
            elif decoded in mapping:
                print("Converting %s parameter %d from address %x to %x" % (method, i, decoded, mapping[decoded]))
                params[i] = format_hex_address(mapping[decoded])
    else:
        decoded = _decode_value(params)
        if decoded is not None and decoded in mapping:
            print("Converting %s from address %x to %x" % (method, decoded, mapping[decoded]))
            return mapping[decoded]
    return params

def AddressSynchronizingClient(etheno_client):    
    old_create_account = getattr(etheno_client, 'create_account')
    mapping = {}
    filter_mapping = {}

    def create_account(balance = 0, address = None):
        try:
            # First, see if the client can handle creating this address:
            return old_create_account(balance = balance, address = address)
        except NotImplementedError:
            pass
        new_address = old_create_account(balance = balance, address = None)
        mapping[address] = new_address
        return new_address

    setattr(etheno_client, 'create_account', create_account)

    if isinstance(etheno_client, SelfPostingClient):
        old_post = getattr(etheno_client, 'post')

        def post(data):
            method = data['method']
            uninstalling_filter = None
            if 'params' in data:
                data['params'] = _remap_params(data['params'], mapping, method, remap_data = True)
                if ('filter' in method.lower() and 'get' in method.lower()) or method == 'eth_uninstallFilter':
                    # we are accessing a filter by its ID, so remap the ID
                    old_id = data['params'][0]
                    if old_id not in filter_mapping:
                        print("Warning: %s called on unknown filter ID %s; ignoring..." % (method, old_id))
                    else:
                        print("Mapping filter ID %s to %s for %s" % (old_id, filter_mapping[old_id], method))
                        data['params'] = [filter_mapping[old_id]]
                    if method == 'eth_uninstallFilter':
                        uninstalling_filter = old_id
            ret = old_post(data)
            if uninstalling_filter is not None:
                if ret['result']:
                    # the uninstall succeeded, so we no longer need to keep the mapping:
                    del filter_mapping[uninstalling_filter]
            elif 'filter' in method.lower() and 'new' in method.lower() and 'result' in ret:
                # a new filter was just created, so record the mapping
                filter_mapping[etheno_client.etheno.rpc_client_result['result']] = ret['result']
            return ret

        setattr(etheno_client, 'post', post)
    else:
        raise TypeError('TODO: Implement support for address synchronization on clients other than SelfPostingClients')
        # old_handler = getattr(etheno_client, 'eth_sendTransaction', None)

        # @jsonrpc(from_addr = QUANTITY, to = QUANTITY, gas = QUANTITY, gasPrice = QUANTITY, value = QUANTITY, data = DATA, nonce = QUANTITY, RETURN = DATA)
        # def eth_sendTransaction(self, from_addr, to = None, gas = 90000, gasPrice = None, value = 0, data = None, nonce = None, rpc_client_result = None):
        #     if to is None or to == 0:
        #         # we are creating a new contract
        #         if old_handler is None:
                    
        #     else:
     
    return etheno_client
        
