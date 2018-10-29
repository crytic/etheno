from .client import RpcProxyClient
from .etheno import EthenoPlugin
from .utils import format_hex_address

class ContractSynchronizer(EthenoPlugin):
    def __init__(self, source_client, contract_address):
        if isintsance(source_client, str):
            source_client = RpcProxyClient(source_client)
        self.source = source_client
        self.contract = format_hex_address(contract_address, True)
        
    def added(self):
        # get the contract:
        pass
