import json
from typing import Dict, TextIO, Union

from .etheno import EthenoPlugin
from .utils import format_hex_address

class JSONExporter:
    def __init__(self, out_stream: Union[str, TextIO]):
        self._was_path = isinstance(out_stream, str)
        if self._was_path:
            self.output = open(out_stream, 'w', encoding='utf8')
        else:
            self.output = out_stream
        self.output.write('[')
        self._count = 0
        self._finalized = False

    def finalize(self):
        if self._finalized:
            return
        if self._count:
            self.output.write('\n')
        self.output.write(']')
        self.output.flush()
        if self._was_path:
            self.output.close()
        self._finalized = True

    def write_entry(self, entry):
        if self._finalized:
            return
        if self._count > 0:
            self.output.write(',')
        self._count += 1
        self.output.write('\n')
        json.dump(entry, self.output)
        self.output.flush()
        

class JSONRPCExportPlugin(EthenoPlugin):
    def __init__(self, out_stream: Union[str, TextIO]):
        self._exporter = JSONExporter(out_stream)
    
    def after_post(self, post_data, client_results):
        self._exporter.write_entry([post_data, client_results])

    def finalize(self):
        self._exporter.finalize()
        if hasattr(self._exporter.output, 'name'):
            self.logger.info(f'Raw JSON RPC messages dumped to {self._exporter.output.name}')


class EventSummaryPlugin(EthenoPlugin):
    def __init__(self):
        self._transactions: Dict[int, Dict[str, object]] = {} # Maps transaction hashes to their eth_sendTransaction arguments

    def handle_contract_created(self, creator_address: str, contract_address: str, gas_used: str, gas_price: str, data: str, value: str):
        self.logger.info(f'Contract created at {contract_address} with {(len(data)-2)//2} bytes of data by account {creator_address} for {gas_used} gas with a gas price of {gas_price}')

    def handle_function_call(self, from_address: str, to_address: str, gas_used: str, gas_price: str, data: str, value: str):
        self.logger.info(f'Function call with {value} wei from {from_address} to {to_address} with {(len(data)-2)//2} bytes of data for {gas_used} gas with a gas price of {gas_price}')

    def after_post(self, post_data, result):
        if len(result):
            result = result[0]
        if 'method' not in post_data:
            return
        elif post_data['method'] == 'eth_sendTransaction' and 'result' in result:
            try:
                transaction_hash = int(result['result'], 16)
            except ValueError:
                return
            self._transactions[transaction_hash] = post_data
        elif post_data['method'] == 'eth_getTransactionReceipt':
            transaction_hash = int(post_data['params'][0], 16)
            if transaction_hash not in self._transactions:
                self.logger.error(f'Received transaction receipt {result} for unknown transaction hash {post_data["params"][0]}')
                return
            original_transaction = self._transactions[transaction_hash]['params'][0]
            if 'value' not in original_transaction or original_transaction['value'] is None:
                value = '0x0'
            else:
                value = original_transaction['value']
            if 'to' not in result['result'] or result['result']['to'] is None:
                # this transaction is creating a contract:
                contract_address = result['result']['contractAddress']
                self.handle_contract_created(original_transaction['from'], contract_address, result['result']['gasUsed'], original_transaction['gasPrice'], original_transaction['data'], value)
            else:
                self.handle_function_call(original_transaction['from'], original_transaction['to'], result['result']['gasUsed'], original_transaction['gasPrice'], original_transaction['data'], value)


class EventSummaryExportPlugin(EventSummaryPlugin):
    def __init__(self, out_stream: Union[str, TextIO]):
        super().__init__()
        self._exporter = JSONExporter(out_stream)

    def run(self):
        for address in self.etheno.accounts:
            self._exporter.write_entry({
                'event' : 'AccountCreated',
                'address' : format_hex_address(address)
            })
        super().run()

    def handle_contract_created(self, creator_address: str, contract_address: str, gas_used: str, gas_price: str, data: str, value: str):
        self._exporter.write_entry({
            'event' : 'ContractCreated',
            'from' : creator_address,
            'contract_address' : contract_address,
            'gas_used' : gas_used,
            'gas_price' : gas_price,
            'data' : data,
            'value' : value
        })
        super().handle_contract_created(creator_address, contract_address, gas_used, gas_price, data, value)

    def handle_function_call(self, from_address: str, to_address: str, gas_used: str, gas_price: str, data: str, value: str):
        self._exporter.write_entry({
            'event' : 'FunctionCall',
            'from' : from_address,
            'to' : to_address,
            'gas_used' : gas_used,
            'gas_price' : gas_price,
            'data' : data,
            'value' : value
        })
        super().handle_function_call(from_address, to_address, gas_used, gas_price, data, value)

    def finalize(self):
        self._exporter.finalize()
        if hasattr(self._exporter.output, 'name'):
            self.logger.info(f'Event summary JSON saved to {self._exporter.output.name}')
