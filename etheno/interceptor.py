from etheno import EthenoPlugin
from flask import render_template
from web3.auto import w3
import json

class TransactionParams():
    def __init__(self, contract, fun, params):
        self.contract = contract
        self.fun = fun
        self.params = params

    def encode(self):
        return self.fun(*self.params.values()).buildTransaction()

class Interceptor(EthenoPlugin):
    def __init__(self, network_id, contract_paths, scripts):
        self._network_id = str(network_id)
        self._contract_paths = contract_paths
        self._contracts = {}
        self._bytecode = {}
        self._scripts = scripts

        self.__reload_compiled_contracts()

    def before_post(self, post_data):
        if post_data['method'] != 'eth_sendTransaction':
            return

        for idx, params in enumerate(post_data['params']):
            if is_new_contract(params):
                continue

            contract, fun, decoded_params = self.__decode_transaction(params)
            if contract and fun and decoded_params:
                new_params = TransactionParams(contract, fun, decoded_params)
                new_encoded_params = self.__run_scripts(new_params).encode()
                post_data['params'][idx]['data'] = new_encoded_params['data']
                post_data['params'][idx]['gas'] = self.etheno.estimate_gas(post_data)

        return post_data

    def after_post(self, post_data, client_results):
        if post_data['method'] != 'eth_sendTransaction':
            return

        for params in post_data['params']:
            if not is_new_contract(params):
                continue

            self.__reload_compiled_contracts()
            self.__record_deployed_contract(params, client_results)

        return post_data

    def __decode_transaction(self, params):
        address = params['to'].lower()

        if address not in self._contracts:
            self.logger.warn("Could not find compiled contract associated with {}".format(params['to']))
            return False, False, False

        try:
            contract = self._contracts[address]
            fun, params = contract.decode_function_input(params['data'])
            return contract, fun, params
        except:
            self.logger.warn("Could not decode function input: {}".format(params['data']))
            return False, False, False

    def __reload_compiled_contracts(self):
        for contract_path in self._contract_paths:
            file = open(contract_path, 'r')

            try:
                contract = json.load(file)
                contract_abi = contract['abi']

                if 'networks' not in contract:
                    self.logger.warn("No deployments made for compiled {}".format(contract_path))
                    continue

                if self._network_id not in contract['networks']:
                    self.logger.warn("Deployment made to other network(s): {}".format(
                        ','.join(contract['networks'].keys())
                    ))
                    continue

                address = contract['networks'][self._network_id]['address']
                self._contracts[address.lower()] = w3.eth.contract(address=address, abi=contract_abi)

                bytecode = contract['bytecode']
                self._bytecode[bytecode] = w3.eth.contract(address=address, abi=contract_abi)

            finally:
                file.close()

    def __record_deployed_contract(self, params, client_results):
        for client_result in client_results:
            receipt = w3.eth.waitForTransactionReceipt(client_result['result'])
            address = receipt['contractAddress']

            if params['data'] in self._bytecode:
                self._contracts[address.lower()] = self._bytecode[params['data']]

    def __run_scripts(self, tx):
        for script in self._scripts:
            tx = script['run'](tx)

        return tx

def is_new_contract(params):
    return 'to' not in params