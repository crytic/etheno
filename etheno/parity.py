import atexit
import json
import os
import subprocess
import tempfile
import time

from web3.auto import w3

from .client import JSONRPCError, RpcHttpProxy, SelfPostingClient
from .genesis import geth_to_parity, make_accounts
from .keyfile import create_keyfile_json
from .utils import ConstantTemporaryFile, find_open_port, format_hex_address, int_to_bytes, is_port_free

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

class ParityClient(SelfPostingClient):
    def __init__(self, genesis, port=8546):
        super().__init__(RpcHttpProxy("http://localhost:%d/" % port))
        self.miner_account = make_accounts(1)[0]
        self.genesis = dict(genesis)
        # Add the etherbase account to genesis:
        self.genesis['alloc'][format_hex_address(self.miner_account.address)] = {'balance' : '0', 'privateKey' : format_hex_address(self.miner_account.private_key)}
        self.port = port
        self.parity = None
        self.datadir = tempfile.TemporaryDirectory()
        self._accounts = []
        self._created_address_index = -1
        self._tempfiles = []
        
        self.passwords = tempfile.NamedTemporaryFile(prefix='parity', suffix='.passwd', delete=False)
        try:
            self.passwords.write(b'etheno')
        finally:
            self.passwords.close()
        self._tempfiles.append(self.passwords)

        self.genesis_file = tempfile.NamedTemporaryFile(prefix='etheno', suffix='.genesis', delete=False)
        try:
            parity_genesis = geth_to_parity(self.genesis)
            parity_genesis['genesis']['author'] = format_hex_address(self.miner_account.address, True)
            self.genesis_file.write(json.dumps(parity_genesis).encode('utf-8'))
        finally:
            self.genesis_file.close()
        self._tempfiles.append(self.genesis_file)
        
        self.config = tempfile.NamedTemporaryFile(prefix='config', suffix='.toml', delete=False)
        try:
            self.config.write(make_config(
                genesis_path=self.genesis_file.name,
                base_path=self.datadir.name,
                port=self.port,
                chainId=self.genesis['config']['chainId'],
                accounts=tuple(self.accounts),
                password_file=self.passwords.name
            ))
        finally:
            self.config.close()
        self._tempfiles.append(self.config)

        self.import_account(self.miner_account.private_key)
        
        atexit.register(ParityClient.shutdown.__get__(self, ParityClient))

    def create_account(self, balance = 0, address = None):
        accounts = list(self.accounts)
        if address is None:
            self._created_address_index += 1
            if self._created_address_index >= len(accounts):
                raise Exception('Ran out of Parity genesis accounts and could not create a new one!')
            return accounts[self._created_address_index]
        elif address not in accounts:
            raise Exception("Account %s did not exist in the Parity genesis! Valid accounts:\n%s" % (address, '\n'.join(map(hex, accounts))))
        else:
            return address

    def import_account(self, private_key):
        keyfile = create_keyfile_json(int_to_bytes(private_key), b'etheno')
        keyfile_json = json.dumps(keyfile)
        keysdir = os.path.join(self.datadir.name, 'keys', 'etheno')
        os.makedirs(keysdir, exist_ok=True)
        output = tempfile.NamedTemporaryFile(prefix='account', suffix='.key', dir=keysdir, delete=False)
        try:
            output.write(keyfile_json.encode('utf-8'))
        finally:
            output.close()
        self._tempfiles.append(output)

    @property
    def accounts(self):
        for addr, bal in self.genesis['alloc'].items():
            yield int(addr, 16)

    def unlock_account(self, account):
        addr = format_hex_address(account, True)
        print("Unlocking Parity account %s..." % addr)
        return self.post({
            'id': addr,
            'jsonrpc': '2.0',
            'method': 'personal_unlockAccount',
            'params': [addr, 'etheno', None] # Unlock the account for one day
        })        

    def post(self, data, unlock_if_necessary=True):
        try:
            return super().post(data)
        except JSONRPCError as e:
            if unlock_if_necessary and 'data' in e.result['error'] and e.result['error']['data'].lower() == 'notunlocked':
                self.unlock_account(int(data['params'][0]['from'], 16))
                return self.post(data, unlock_if_necessary=False)
            else:
                raise e
    
    def start(self, unlock_accounts = True):
        if self.parity:
            return
        base_args = ['/usr/bin/env', 'parity', '--config', self.config.name, '--fast-unlock', '--jsonrpc-apis=all']
        self.parity = subprocess.Popen(base_args)
        self.wait_until_running()

    def stop(self):
        if self.parity is not None:
            parity = self.parity
            self.parity = None
            parity.terminate()
            parity.wait()

    def cleanup(self):
        if os.path.exists(self.datadir.name):
            self.datadir.cleanup()
        for tmpfile in self._tempfiles:
            if os.path.exists(tmpfile.name):
                os.remove(tmpfile.name)
        self._tempfiles = []

    def shutdown(self):
        self.stop()
        self.cleanup()
            
    def wait_until_running(self):
        while is_port_free(self.port):
            time.sleep(0.25)
