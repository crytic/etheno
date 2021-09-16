from collections.abc import Sequence
import copy
import json
import os

from .client import RpcProxyClient
from .genesis import make_accounts
from .logger import PtyLogger
from .utils import format_hex_address, is_port_free


class JSONRPCClient(RpcProxyClient):
    def __init__(self, name, genesis, port=8546):
        super().__init__("http://localhost:%d/" % port)
        self._basename = name
        self.short_name = "%s@%d" % (name, port)
        self.port = port
        self.genesis = copy.deepcopy(genesis)
        self.miner_account = make_accounts(1)[0]
        self.genesis['alloc'][format_hex_address(self.miner_account.address)] = {
            'balance': '0',
            'privateKey': format_hex_address(self.miner_account.private_key)
        }
        self._accounts = []
        self._created_address_index = -1
        self._runscript = []
        # These are set in self.etheno_set():
        self.genesis_file = None
        self.passwords = None
        self.datadir = None
        # This is set when self.start() is called:
        self.instance = None

    def write_genesis(self, outfile):
        outfile.write(json.dumps(self.genesis).encode('utf-8'))

    def write_passwords(self, outfile):
        for i in range(len(self.genesis['alloc'])):
            outfile.write(b'etheno\n')
        
    def etheno_set(self):
        super().etheno_set()
        self.datadir = os.path.join(self.log_directory, 'chain_data')
        os.makedirs(self.datadir)
        with self.logger.make_logged_file(prefix='genesis', suffix='.json') as genesis_output:
            self.genesis_file = genesis_output.name
            self.write_genesis(genesis_output)
            genesis_output.close()
        with self.logger.make_logged_file(prefix=self._basename, suffix='.passwd') as password_output:
            self.passwords = password_output.name
            self.write_passwords(password_output)

    def add_to_run_script(self, command):
        if isinstance(command, Sequence):
            command = ' '.join(command)
        self._runscript.append(command)

    def import_account(self, private_key):
        raise NotImplementedError()

    @property
    def accounts(self):
        for addr, bal in self.genesis['alloc'].items():
            yield int(addr, 16)

    def create_account(self, balance: int = 0, address=None):
        accounts = list(self.accounts)
        if address is None:
            self._created_address_index += 1
            if self._created_address_index >= len(accounts):
                raise Exception("Ran out of %s genesis accounts and could not create a new one!" % self.short_name)
            return accounts[self._created_address_index]
        elif address not in accounts:
            valid_accounts = '\n'.join(map(hex, accounts))
            raise ValueError(f"Account {address!s} did not exist in the genesis for client {self.short_name}! "
                             f"Valid accounts:\n{valid_accounts}")
        else:
            return address

    def get_start_command(self, unlock_accounts=True):
        raise NotImplementedError()
    
    def save_run_script(self):
        run_script = os.path.join(self.log_directory, "run_%s.sh" % self._basename.lower())
        with open(run_script, 'w') as f:
            script = '\n'.join(self._runscript)
            f.write(script)
        # make the script executable:
        os.chmod(run_script, 0o755)

    def start(self, unlock_accounts=True):
        start_args = self.get_start_command(unlock_accounts)
        self.instance = PtyLogger(self.logger, start_args, cwd=self.log_directory)
        if self.log_directory:
            self.add_to_run_script(start_args)
            self.save_run_script()
        self.initialized()
        self.instance.start()
        self.wait_until_running()

    def initialized(self):
        """Called once the client is completely intialized but before it is started"""
        pass

    def is_running(self):
        return not is_port_free(self.port)

    def stop(self):
        if self.instance is not None:
            instance = self.instance
            self.instance = None
            instance.terminate()
            instance.wait()
            instance.close()

    def shutdown(self):
        self.stop()
