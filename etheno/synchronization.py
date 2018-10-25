import time

import eth_utils
from web3.auto import w3

from .client import EthenoClient, SelfPostingClient, jsonrpc, JSONRPCError, DATA, QUANTITY, transaction_receipt_succeeded
from .utils import decode_hex, format_hex_address, int_to_bytes

def _decode_value(value):
    if isinstance(value, int):
        return value
    try:
        return int(value, 16)
    except Exception:
        return None

def _remap_params(client, params, mapping, method, remap_data = False):
    if isinstance(params, dict):
        for key, value in params.items():
            decoded = _decode_value(value)
            if decoded is None:
                params[key] = _remap_params(client, value, mapping, "%s['%s']" % (method, key))
            elif decoded in mapping:
                client.logger.debug("Converting %s parameter '%s' from %x to %x" % (method, key, decoded, mapping[decoded]))
                params[key] = format_hex_address(mapping[decoded], True)
            elif remap_data and key == 'data':
                new_value = params['data']
                for old, new in mapping.items():
                    prev = new_value
                    new_value = new_value.replace(format_hex_address(old), format_hex_address(new))
                    if prev != new_value:
                        client.logger.debug("Converting %x in %s['data'] to %x" % (old, method, new))
                if new_value != params['data']:
                    params['data'] = new_value
    elif isinstance(params, list) or isinstance(params, tuple):
        for i, p in enumerate(params):
            decoded = _decode_value(p)
            if decoded is None:
                params[i] = _remap_params(client, p, mapping, "%s['%d']" % (method, i))
            elif decoded in mapping:
                client.logger.debug("Converting %s parameter %d from %x to %x" % (method, i, decoded, mapping[decoded]))
                params[i] = format_hex_address(mapping[decoded], True)
    else:
        decoded = _decode_value(params)
        if decoded is not None and decoded in mapping:
            client.logger.debug("Converting %s from %x to %x" % (method, decoded, mapping[decoded]))
            return mapping[decoded]
    return params

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
        if self._client == self._client.etheno.master_client:
            return self._old_create_account(data)
        try:
            # First, see if the client can handle creating this address:
            return self._old_create_account(balance = balance, address = address)
        except NotImplementedError:
            pass
        new_address = self._old_create_account(balance = balance, address = None)
        if address is not None and address != new_address:
            self.mapping[address] = new_address
        return new_address

    def post(self, data, *args, **kwargs):
        if self._client == self._client.etheno.master_client:
            return self._old_post(data, *args, **kwargs)
        
        method = data['method']

        if method == 'eth_getTransactionReceipt':
            # first, make sure the master client's transaction succeeded; if not, we can just ignore this
            if not transaction_receipt_succeeded(self._client.etheno.rpc_client_result):
                # the master client's transaction receipt command failed, so we can skip calling this client's
                return self._client.etheno.rpc_client_result
            elif _decode_value(data['params'][0]) not in self.mapping:
                # we don't know about this transaction receipt, which probably means that the transaction failed
                # on this client. So return the receipt here, because below we will block on a result:
                return self._old_post(data, *args, **kwargs)
        
        uninstalling_filter = None
        if 'params' in data:
            data['params'] = _remap_params(self._client, data['params'], self.mapping, method, remap_data = True)
            if ('filter' in method.lower() and 'get' in method.lower()) or method == 'eth_uninstallFilter':
                # we are accessing a filter by its ID, so remap the ID
                old_id = data['params'][0]
                if old_id not in self.filter_mapping:
                    self._client.logger.warn("%s called on unknown filter ID %s; ignoring..." % (method, old_id))
                else:
                    self._client.logger.info("Mapping filter ID %s to %s for %s" % (old_id, self.filter_mapping[old_id], method))
                    data['params'] = [self.filter_mapping[old_id]]
                if method == 'eth_uninstallFilter':
                    uninstalling_filter = old_id
        ret = self._old_post(data, *args, **kwargs)
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
                if self._client.etheno.rpc_client_result and not isinstance(self._client.etheno.rpc_client_result, JSONRPCError) and 'result' in self._client.etheno.rpc_client_result and self._client.etheno.rpc_client_result['result']:
                    old_decoded = _decode_value(self._client.etheno.rpc_client_result['result'])
                    new_decoded = _decode_value(ret['result'])
                    if old_decoded is not None and new_decoded is not None:
                        self._client.logger.info("Mapping transaction hash %x to %x" % (old_decoded, new_decoded))
                        self.mapping[old_decoded] = new_decoded
                    elif not (old_decoded is None and new_decoded is None):
                        self._client.logger.warn("Call to %s returned %s from the master client but %s from this client; ignoring..." % (method, self._client.etheno.rpc_client_result['result'], ret['result']))
        elif method == 'eth_getTransactionReceipt':
            # by this point we know that the master client has already successfully mined the transaction and returned a receipt
            # so make sure that we block until this client has also mined the transaction and returned a receipt
            while transaction_receipt_succeeded(ret) is None:
                self._client.logger.info("Waiting to mine transaction %s..." % data['params'][0])
                time.sleep(5.0)
                ret = self._old_post(data, *args, **kwargs)
            # update the mapping with the address if a new contract was created
            if 'contractAddress' in ret['result'] and ret['result']['contractAddress']:
                master_address = _decode_value(self._client.etheno.rpc_client_result['result']['contractAddress'])
                our_address = _decode_value(ret['result']['contractAddress'])
                if master_address is not None and our_address is not None:
                    self.mapping[master_address] = our_address
                elif not (master_address is None and our_address is None):
                    self._client.logger.warn("Call to %s returned %s from the master client but %s from this client; ignoring..." % (method, self._client.etheno.rpc_client_result['result']['contractAddress'], ret['result']['contractAddress']))

        return ret

def AddressSynchronizingClient(etheno_client):
    synchronizer = ChainSynchronizer(etheno_client)

    setattr(etheno_client, 'create_account', ChainSynchronizer.create_account.__get__(synchronizer, ChainSynchronizer))
    setattr(etheno_client, 'post', ChainSynchronizer.post.__get__(synchronizer, ChainSynchronizer))

    return etheno_client
        
class RawTransactionSynchronizer(ChainSynchronizer):
    def __init__(self, client, accounts):
        super().__init__(client)
        self.accounts = accounts
        self._private_keys = {}
        self._account_index = -1
        self._chain_id = client.get_net_version()

    def create_account(self, balance = 0, address = None):
        self._account_index += 1
        new_address = self.accounts[self._account_index].address
        self._private_keys[new_address] = int_to_bytes(self.accounts[self._account_index].private_key)
        if address is not None and address != new_address:
            self.mapping[address] = new_address
        return new_address

    def post(self, data, *args, **kwargs):
        method = data['method']

        if method == 'eth_sendTransaction':
            # This client does not support sendTransaction because it does not have any of the requisite accounts.
            # So let's manually sign the transaction and send it to the client using eth_sendRawTransaction, instead.
            params = _remap_params(self._client, dict(data['params'][0]), self.mapping, method, remap_data = True)
            from_str = params['from']
            from_address = int(from_str, 16)
            if from_address in self._private_keys:
                private_key = self._private_keys[from_address]
            else:
                # see if it is in self.accounts:
                for account in self.accounts:
                    if from_address == account.address:
                        private_key = account.private_key
                        break
                else:
                    raise Exception("Error: eth_sendTransaction sent from unknown address %s:\n%s" % (from_str, data))
            params['chainId'] = self._client.get_net_version()
            # Workaround for a bug in web3.eth.account:
            # the signTransaction function checks to see if the 'from' field is present, and if so it validates that it
            # corresponds to the address of the private key. However, web3.eth.account doesn't perform this check case
            # insensitively, so it can erroneously fail. Therefore, set the 'from' field using the same value that
            # this call validates against:
            params['from'] = w3.eth.account.privateKeyToAccount(private_key).address
            # web3.eth.acount.signTransaction expects the `to` field to be a checksum address:
            if 'to' in params:
                params['to'] = eth_utils.address.to_checksum_address(params['to'])
            transaction_count = self._client.get_transaction_count(from_address)
            params['nonce'] = transaction_count
            signed_txn = w3.eth.account.signTransaction(params, private_key=private_key)
            return super().post({
                'id': 1,
                'jsonrpc': '2.0',
                'method': 'eth_sendRawTransaction',
                'params': [signed_txn.rawTransaction.hex()]
            })
        else:
            return super().post(data, *args, **kwargs)

def RawTransactionClient(etheno_client, accounts):
    synchronizer = RawTransactionSynchronizer(etheno_client, accounts)

    setattr(etheno_client, 'create_account', RawTransactionSynchronizer.create_account.__get__(synchronizer, RawTransactionSynchronizer))
    setattr(etheno_client, 'post', RawTransactionSynchronizer.post.__get__(synchronizer, RawTransactionSynchronizer))
     
    return etheno_client
