import atexit
import json
import os
import subprocess
import tempfile
import time
from web3.auto import w3

from .client import SelfPostingClient, RpcHttpProxy

from .utils import is_port_free

def format_hex_address(addr):
    if isinstance(addr, int):
        addr = "%x" % addr
    if addr.lower().startswith('0x'):
        addr = addr[2:]
    if len(addr) % 2 != 0:
        addr = "0%s" % addr
    return addr

def make_genesis(network_id = 0x657468656E6F, difficulty = 40, gas_limit = 2100000, accounts = None):
    if accounts:
        alloc = {format_hex_address(addr): {'balance': "%d" % bal} for addr, bal in accounts}
    else:
        alloc = {}
    
    return {
        'config' : {
            'chainId': network_id,
            'homesteadBlock': 0,
            'eip155Block': 0,
            'eip158Block': 0
        },
        'difficulty': "%d" % difficulty,
        'gasLimit': "%d" % gas_limit,
        'alloc': alloc
    }

class GethClient(SelfPostingClient):
    def __init__(self, genesis, port=8546):
        super().__init__(RpcHttpProxy("http://localhost:%d/" % port))
        # Create a miner etherbase account:
        self.etherbase = w3.eth.account.create()
        self.port = port
        self.genesis = dict(genesis)
        # Add the etherbase account to genesis:
        self.genesis['alloc'][format_hex_address(self.etherbase.address)] = {'balance' : '0'}
        self.datadir = tempfile.TemporaryDirectory()
        genesis_output = tempfile.NamedTemporaryFile(prefix='genesis', suffix='.json', delete=False)
        self.genesis_file = genesis_output.name
        try:
            genesis_output.write(json.dumps(genesis).encode('utf-8'))
        finally:
            genesis_output.close()

        try:
            subprocess.check_call(['/usr/bin/env', 'geth', 'init', self.genesis_file, '--datadir', self.datadir.name])
        except Exception as e:
            self.cleanup()
            raise e
        self._created_address_index = -1

        self.geth = None

        atexit.register(GethClient.shutdown.__get__(self, GethClient))

    @property
    def accounts(self):
        for addr, bal in self.genesis['alloc'].items():
            yield int(addr, 16)

    def create_account(self, balance = 0, address = None):
        accounts = list(self.accounts)
        if address is None:
            self._created_address_index += 1
            if self._created_address_index >= len(accounts):
                raise Exception('Ran out of Geth genesis accounts and could not create a new one!')
            return accounts[self._created_address_index]
        elif address not in accounts:
            raise Exception("Account %s did not exist in the Geth genesis! Valid accounts:\n%s" % (address, '\n'.join(map(hex, accounts))))
        else:
            return address

    def start(self):
        if self.geth:
            return
        self.geth = subprocess.Popen(['/usr/bin/env', 'geth', '--nodiscover', '--rpc', '--rpcport', "%d" % self.port, '--networkid', "%d" % self.genesis['config']['chainId'], '--datadir', self.datadir.name, '--mine', '--etherbase', self.etherbase.address])
        self.wait_until_running()

    def stop(self):
        if self.geth is not None:
            geth = self.geth
            self.geth = None
            geth.terminate()
            geth.wait()

    def cleanup(self):
        if os.path.exists(self.genesis_file):
            os.remove(self.genesis_file)
        if os.path.exists(self.datadir.name):
            self.datadir.cleanup()
            
    def shutdown(self):
        self.stop()
        self.cleanup()

    def wait_until_running(self):
        while is_port_free(self.port):
            time.sleep(0.25)
