from .client import SelfPostingClient
from .etheno import EthenoPlugin

class DifferentialTester(EthenoPlugin):
    def __init__(self):
        self._unprocessed_transactions = set()
    
    def after_post(self, data, client_results):
        method = data['method']
        if method == 'eth_sendTransaction' or method == 'eth_sendRawTransaction':
            if 'result' in data and data['result']:
                self._unprocessed_transactions.add(data['result'])
        elif method == 'eth_getTransactionReceipt':
            master_result = client_results[0]
            if master_result and 'result' in master_result and master_result['result']:
                # mark that we have processed the receipt for this transaction:
                if data['params'][0] in self._unprocessed_transactions:
                    self._unprocessed_transactions.remove(data['params'][0])

                if 'contractAddress' in master_result['result'] and master_result['result']['contractAddress']:
                    # the master client created a new contract
                    # so make sure that all of the other clients did, too
                    for client, client_data in zip(self.etheno.clients, client_results[1:]):
                        created = False
                        try:
                            created = client_data['result']['contractAddress']
                        except Exception:
                            pass
                        if not created:
                            print("Error: the master client created a contract for transaction %s, but %s did not!" % (data['params'][0], client))
                if 'gasUsed' in master_result['result'] and master_result['result']['gasUsed']:
                    # make sure each client used the same amount of gas
                    master_gas = int(master_result['result']['gasUsed'], 16)
                    for client, client_data in zip(self.etheno.clients, client_results[1:]):
                        try:
                            gas_used = int(client_data['result']['gasUsed'], 16)
                        except Exception:
                            pass
                        if gas_used != master_gas:
                            print("Error: transaction %s used 0x%x gas in the master client but only 0x%x gas in %s!" % (data['params'][0], master_gas, gas_used, client))

    def finalize(self):
        unprocessed = self._unprocessed_transactions
        self._unprocessed_transactions = set()
        for tx_hash in unprocessed:
            print("Requesting transaction receipt for %s to check differentials..." % tx_hash)
            if not isinstance(self.etheno.master_client, SelfPopstingClient):
                print("Warning: The DifferentialTester currently only supports master clients that extend from SelfPostingClient, but %s does not; skipping checking transaction(s) %s" % (self.etheno.master_client, ', '.join(unprocessed)))
                return
            while True:
                receipt = self.etheno.post({
                    'jsonrpc': '2.0',
                    'method': 'eth_getTransactionReceipt',
                    'params': [tx_hash]
                })
                # if this post is successful, it will trigger the `after_post` callback above
                # where were check for the differentials
                if 'result' in receipt and receipt['result']:
                    break
                # The transaction is still pending
                time.sleep(3.0)
