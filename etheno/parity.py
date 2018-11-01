import atexit
import json
import os
import tempfile

from .client import JSONRPCError
from .genesis import geth_to_parity
from .jsonrpcclient import JSONRPCClient
from .keyfile import create_keyfile_json
from .utils import find_open_port, format_hex_address, int_to_bytes

def make_config(genesis_path, base_path, port, accounts, password_file, **kwargs):
    return """[parity]
public_node = false
no_download = false
no_consensus = false
no_persistent_txqueue = false

chain = "{genesis_path}"
base_path = "{base_path}"
db_path = "{base_path}/chains"
keys_path = "{base_path}/keys"

[account]
unlock = [{account_addresses}]
password = ["{password_file}"]

[network]
port = {port}
min_peers = 1
max_peers = 1
id = {chainId}
discovery = false

[rpc]
disable = false
port = {rpc_port}
interface = "local"
apis = ["web3", "eth", "pubsub", "net", "parity", "parity_pubsub", "traces", "rpc", "shh", "shh_pubsub"]
hosts = ["none"]

[websockets]
disable = true

[ipc]
disable = true

[secretstore]
disable = true

[ipfs]
enable = false

[mining]
author = "{miner}"
engine_signer = "{miner}"
force_sealing = true
reseal_on_txs = "all"
#reseal_min_period = 4000
#reseal_max_period = 60000
#gas_floor_target = "4700000"
#gas_cap = "6283184"
#tx_queue_gas = "off"
#tx_gas_limit = "6283184"
#tx_time_limit = 500 #ms
#remove_solved = false
#notify_work = ["http://localhost:3001"]
refuse_service_transactions = false

[footprint]
tracing = "auto"
pruning = "auto"
pruning_history = 64
pruning_memory = 32
cache_size_db = 128
cache_size_blocks = 8
cache_size_queue = 40
cache_size_state = 25
cache_size = 128 # Overrides above caches with total size
fast_and_loose = false
db_compaction = "ssd"
fat_db = "auto"
scale_verifiers = true
num_verifiers = 6

[snapshots]
disable_periodic = false

[misc]
logging = "own_tx=trace"
log_file = "{log_path}"
color = true
""".format(
    genesis_path=genesis_path,
    base_path=base_path,
    port=find_open_port(30303),
    rpc_port=port,
    log_path=kwargs.get('log_path', "%s/parity.log" % base_path),
    chainId=kwargs.get('chainId', 1),
    miner=format_hex_address(accounts[-1], True),
    account_addresses=', '.join(map(lambda s : "\"0x%s\"" % s, map(format_hex_address, accounts))),
    password_file=password_file
    ).encode('utf-8')

class ParityClient(JSONRPCClient):
    def __init__(self, genesis, port=8546):
        super().__init__('Parity', genesis, port)
        self._unlock_accounts = True

        self.config = None
        
        atexit.register(ParityClient.shutdown.__get__(self, ParityClient))

    def etheno_set(self):
        super().etheno_set()
        self.import_account(self.miner_account.private_key)
        self.config = self.logger.make_constant_logged_file(
            make_config(
                genesis_path=self.logger.to_log_path(self.genesis_file),
                base_path=self.logger.to_log_path(self.datadir),
                port=self.port,
                chainId=self.genesis['config']['chainId'],
                accounts=tuple(self.accounts),
                password_file=self.logger.to_log_path(self.passwords)
            ),
            prefix='config',
            suffix='.toml'
        )
        
    def write_passwords(self, outfile):
        outfile.write(b'etheno')

    def write_genesis(self, outfile):
        parity_genesis = geth_to_parity(self.genesis)
        parity_genesis['genesis']['author'] = format_hex_address(self.miner_account.address, True)
        outfile.write(json.dumps(parity_genesis).encode('utf-8'))

    def import_account(self, private_key):
        keyfile = create_keyfile_json(int_to_bytes(private_key), b'etheno')
        keyfile_json = json.dumps(keyfile)
        keysdir = os.path.join(self.datadir, 'keys', 'etheno')
        os.makedirs(keysdir, exist_ok=True)
        output = tempfile.NamedTemporaryFile(prefix='account', suffix='.key', dir=keysdir, delete=False)
        try:
            output.write(keyfile_json.encode('utf-8'))
        finally:
            output.close()
        if self.log_directory is None:
            self._tempfiles.append(output)

    def unlock_account(self, account):
        addr = format_hex_address(account, True)
        self.logger.info("Unlocking Parity account %s..." % addr)
        return self.post({
            'id': addr,
            'jsonrpc': '2.0',
            'method': 'personal_unlockAccount',
            'params': [addr, 'etheno', None] # Unlock the account for one day
        })        

    def post(self, data, unlock_if_necessary=None):
        if unlock_if_necessary is None:
            unlock_if_necessary = self._unlock_accounts
        try:
            return super().post(data)
        except JSONRPCError as e:
            if unlock_if_necessary and 'data' in e.result['error'] and e.result['error']['data'].lower() == 'notunlocked':
                self.unlock_account(int(data['params'][0]['from'], 16))
                return self.post(data, unlock_if_necessary=False)
            else:
                raise e

    def get_start_command(self, unlock_accounts=True):
        return ['/usr/bin/env', 'parity', '--config', self.logger.to_log_path(self.config), '--fast-unlock', '--jsonrpc-apis=all']
            
    def start(self, unlock_accounts=True):
        self._unlock_accounts = unlock_accounts
        super().start(unlock_accounts=unlock_accounts)
