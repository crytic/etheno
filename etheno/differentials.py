from .etheno import EthenoPlugin

class DifferentialTester(EthenoPlugin):
    def after_post(self, data, client_results):
        method = data['method']
        if method == 'eth_getTransactionReceipt':
            master_result = client_results[0]
            if master_result and 'result' in master_result and master_result['result']:                
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
