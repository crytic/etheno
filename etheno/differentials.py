from .etheno import EthenoPlugin

class DifferentialTester(EthenoPlugin):
    def after_post(self, data, client_results):
        method = data['method']
        if method == 'eth_getTransactionReceipt':
            master_result = client_results[0]
            if master_result and 'result' in master_result and master_result['result'] and 'contractAddress' in master_result['result'] and master_result['result']['contractAddress']:
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

