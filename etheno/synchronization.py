from .client import EthenoClient, SelfPostingClient, jsonrpc, DATA, QUANTITY

def AddressSynchronizingClient(etheno_client):    
    old_create_account = getattr(etheno_client, 'create_account')
    mapping = {}

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
            if 'params' in data:
                params = data['params']
                if len(params) == 1 and isinstance(params[0], dict):
                    for key, value in params[0].items():
                        if value in mapping:
                            print("Converting %s parameter %s from address %x to %x" % (method, key, value, mapping[value]))
                            params[0][key] = "%x" % mapping[value]
                else:
                    for i, p in enumerate(params):
                        if p in mapping:
                            print("Converting %s parameter %d from address %x to %x" % (method, i, p, mapping[p]))
                            params[i] = mapping[p]
            # TODO: Rewrite transaction
            return old_post(data)

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
        
