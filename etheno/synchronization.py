import time

from .client import EthenoClient, SelfPostingClient, jsonrpc, DATA, QUANTITY
from .utils import decode_hex, format_hex_address

def _decode_value(value):
    if isinstance(value, int):
        return value
    try:
        return int(value, 16)
    except Exception:
        return None

def _remap_params(params, mapping, method, remap_data = False):
    if isinstance(params, dict):
        for key, value in params.items():
            decoded = _decode_value(value)
            if decoded is None:
                params[key] = _remap_params(value, mapping, "%s['%s']" % (method, key))
            elif decoded in mapping:
                print("Converting %s parameter '%s' from %x to %x" % (method, key, decoded, mapping[decoded]))
                params[key] = format_hex_address(mapping[decoded])
            elif remap_data and key == 'data':
                new_value = params['data']
                for old, new in mapping.items():
                    prev = new_value
                    new_value = new_value.replace(format_hex_address(old), format_hex_address(new))
                    if prev != new_value:
                        print("Converting %x in %s['data'] to %x" % (old, method, new))
                if new_value != params['data']:
                    params['data'] = new_value
    elif isinstance(params, list) or isinstance(params, tuple):
        for i, p in enumerate(params):
            decoded = _decode_value(p)
            if decoded is None:
                params[i] = _remap_params(p, mapping, "%s['%d']" % (method, i))
            elif decoded in mapping:
                print("Converting %s parameter %d from %x to %x" % (method, i, decoded, mapping[decoded]))
                params[i] = format_hex_address(mapping[decoded])
    else:
        decoded = _decode_value(params)
        if decoded is not None and decoded in mapping:
            print("Converting %s from %x to %x" % (method, decoded, mapping[decoded]))
            return mapping[decoded]
    return params

def transaction_receipt_succeeded(data):
    if not (data and 'result' in data and data['result'] and 'status' in data['result']):
        return False
    decoded = _decode_value(data['result']['status'])
    return decoded is not None and decoded > 0

class ChainSynchronizer(object):
    def __init__(self, client):
        if not isinstance(client, SelfPostingClient):
            raise TypeError('TODO: Implement support for address synchronization on clients other than SelfPostingClients')
        self.mapping = {}
        self.filter_mapping = {}
        self._old_post = getattr(client, 'post')
        self._old_create_account = getattr(client, 'create_account')
        self._client = client

    def create_account(self, balance = 0, address = None):
        try:
            # First, see if the client can handle creating this address:
            return self._old_create_account(balance = balance, address = address)
        except NotImplementedError:
            pass
        new_address = self._old_create_account(balance = balance, address = None)
        self.mapping[address] = new_address
        return new_address

    def post(self, data):
        method = data['method']

        if method == 'eth_getTransactionReceipt':
            # first, make sure the master client's transaction succeeded; if not, we can just ignore this
            if not transaction_receipt_succeeded(self._client.etheno.rpc_client_result):
                # the master client's transaction receipt command failed, so we can skip calling this client's
                return self._client.etheno.rpc_client_result
        
        uninstalling_filter = None
        if 'params' in data:
            data['params'] = _remap_params(data['params'], self.mapping, method, remap_data = True)
            if ('filter' in method.lower() and 'get' in method.lower()) or method == 'eth_uninstallFilter':
                # we are accessing a filter by its ID, so remap the ID
                old_id = data['params'][0]
                if old_id not in self.filter_mapping:
                    print("Warning: %s called on unknown filter ID %s; ignoring..." % (method, old_id))
                else:
                    print("Mapping filter ID %s to %s for %s" % (old_id, self.filter_mapping[old_id], method))
                    data['params'] = [self.filter_mapping[old_id]]
                if method == 'eth_uninstallFilter':
                    uninstalling_filter = old_id
        ret = self._old_post(data)
        if uninstalling_filter is not None:
            if ret['result']:
                # the uninstall succeeded, so we no longer need to keep the mapping:
                del self.filter_mapping[uninstalling_filter]
        elif 'filter' in method.lower() and 'new' in method.lower() and 'result' in ret:
            # a new filter was just created, so record the mapping
            self.filter_mapping[self._client.etheno.rpc_client_result['result']] = ret['result']
        elif method == 'eth_sendTransaction' or method == 'eth_sendRawTransaction':
            # record the transaction hash mapping
            if ret and 'result' in ret and ret['result']:
                old_decoded = _decode_value(self._client.etheno.rpc_client_result['result'])
                new_decoded = _decode_value(ret['result'])
                if old_decoded is not None and new_decoded is not None:
                    self.mapping[old_decoded] = new_decoded
                elif not (old_decoded is None and new_decoded is None):
                    print("Warning: call to %s returned %s from the master client but %s from %s; ignoring..." % (method, self._client.etheno.rpc_client_result['result'], ret['result'], self._client))
        elif method == 'eth_getTransactionReceipt':
            # by this point we know that the master client has already successfully mined the transaction and returned a receipt
            # so make sure that we block until this client has also mined the transaction and returned a receipt
            while not transaction_receipt_succeeded(ret):
                print("Waiting for %s to mine transaction %s..." % (self._client, data['params'][0]))
                time.sleep(5.0)
                ret = self._old_post(data)
            # update the mapping with the address if a new contract was created
            if 'contractAddress' in ret['result'] and ret['result']['contractAddress']:
                master_address = _decode_value(self._client.etheno.rpc_client_result['result']['contractAddress'])
                our_address = _decode_value(ret['result']['contractAddress'])
                if master_address is not None and our_address is not None:
                    self.mapping[master_address] = our_address
                elif not (master_address is None and our_address is None):
                    print("Warning: call to %s returned %s from the master client but %s from %s; ignoring..." % (method, self._client.etheno.rpc_client_result['result']['contractAddress'], ret['result']['contractAddress'], self._client))

        return ret

def AddressSynchronizingClient(etheno_client):
    synchronizer = ChainSynchronizer(etheno_client)

    setattr(etheno_client, 'create_account', ChainSynchronizer.create_account.__get__(synchronizer, ChainSynchronizer))
    setattr(etheno_client, 'post', ChainSynchronizer.post.__get__(synchronizer, ChainSynchronizer))
     
    return etheno_client
        
