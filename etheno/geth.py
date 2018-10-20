import atexit
import json
import os
import subprocess
import tempfile
import time

from .client import JSONRPCError, RpcHttpProxy, SelfPostingClient
from .genesis import make_accounts
from .utils import format_hex_address, is_port_free

class make_password(object):
    def __init__(self, num_accounts = 1):
        self._tmpfile = None
        self._num_accounts = num_accounts
    def __enter__(self):
        self._tmpfile = tempfile.NamedTemporaryFile(delete=False)
        for i in range(self._num_accounts):
            self._tmpfile.write(b'etheno\n')
        self._tmpfile.close()
        return self._tmpfile.name
    def __exit__(self, *args, **kwargs):
        if self._tmpfile:
            os.remove(self._tmpfile.name)
            self._tmpfile = None

class GethClient(SelfPostingClient):
    def __init__(self, genesis, port=8546):
        super().__init__(RpcHttpProxy("http://localhost:%d/" % port))
        # Create a miner etherbase account:
        self.etherbase = make_accounts(1)[0]
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
        self.passwords = tempfile.NamedTemporaryFile(prefix='geth', suffix='.passwd', delete=False)
        try:
            for i in range(len(self.genesis['alloc'])):
                self.passwords.write(b'etheno\n')
        finally:
            self.passwords.close()

        try:
            subprocess.check_call(['/usr/bin/env', 'geth', 'init', self.genesis_file, '--datadir', self.datadir.name])
        except Exception as e:
            self.cleanup()
            raise e
        self._created_address_index = -1

        self.geth = None

        atexit.register(GethClient.shutdown.__get__(self, GethClient))

    def import_account(self, private_key):
        keyfile = tempfile.NamedTemporaryFile(prefix='private', suffix='.key', delete=False)
        try:
            private_key = format_hex_address(private_key)
            keyfile.write(private_key.encode('utf-8'))
            keyfile.close()
            with make_password() as p:
                subprocess.check_call(['/usr/bin/env', 'geth', 'account', 'import', '--datadir', self.datadir.name, '--password', self.passwords.name, keyfile.name])
        finally:
            os.remove(keyfile.name)
            pass

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

    def post(self, data):
        # geth takes a while to unlock all of the accounts, so check to see if that caused an error and just wait a bit
        while True:
            try:
                return super().post(data)
            except JSONRPCError as e:
                if e.result['error']['code'] == -32000 and 'authentication needed' in e.result['error']['message']:
                    print("Waiting for Geth to finish unlocking our accounts...")
                    time.sleep(3.0)
                else:
                    raise e

    def start(self, unlock_accounts = True):
        if self.geth:
            return        
        base_args = ['/usr/bin/env', 'geth', '--nodiscover', '--rpc', '--rpcport', "%d" % self.port, '--networkid', "%d" % self.genesis['config']['chainId'], '--datadir', self.datadir.name, '--mine', '--etherbase', format_hex_address(self.etherbase.address)]
        if unlock_accounts:
            addresses = filter(lambda a : a != format_hex_address(self.etherbase.address), map(format_hex_address, self.genesis['alloc']))
            unlock_args = ['--unlock', ','.join(addresses), '--password', self.passwords.name]
        else:
            unlock_args = []
        self.geth = subprocess.Popen(base_args + unlock_args)
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
        if os.path.exists(self.passwords.name):
            os.remove(self.passwords.name)

    def shutdown(self):
        self.stop()
        self.cleanup()

    def wait_until_running(self):
        while is_port_free(self.port):
            time.sleep(0.25)
