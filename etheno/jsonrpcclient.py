from collections.abc import Sequence
import copy
import json
import os
import shutil
import tempfile
import time

from .client import RpcHttpProxy, SelfPostingClient
from .genesis import make_accounts
from .logger import PtyLogger
from .utils import ConstantTemporaryFile, format_hex_address, is_port_free

class JSONRPCClient(SelfPostingClient):
    def __init__(self, name, genesis, port=8546):
        super().__init__(RpcHttpProxy("http://localhost:%d/" % port))
        self._basename = name
        self.short_name = "%s@%d" % (name, port)
        self.port = port
        self.genesis = copy.deepcopy(genesis)
        self.miner_account = make_accounts(1)[0]
        self.genesis['alloc'][format_hex_address(self.miner_account.address)] = {'balance' : '0', 'privateKey' : format_hex_address(self.miner_account.private_key)}
        self._tempfiles = []
        self._accounts = []
        self._created_address_index = -1
        genesis_output = self.make_tempfile(prefix='genesis', suffix='.json')
        self.genesis_file = genesis_output.name
        password_output = self.make_tempfile(prefix=name, suffix='.passwd')
        self.passwords = password_output.name
        self._runscript = []

        try:
            self.write_genesis(genesis_output)
        finally:
            genesis_output.close()

        try:
            self.write_passwords(password_output)
        finally:
            password_output.close()

        # This is set in self.etheno_set():
        self.datadir = None
        self._datadir_tmp = None

        # This is set when self.start() is called:
        self.instance = None

    def write_genesis(self, outfile):
        outfile.write(json.dumps(self.genesis).encode('utf-8'))

    def write_passwords(self, outfile):
        for i in range(len(self.genesis['alloc'])):
            outfile.write(b'etheno\n')
        
    def etheno_set(self):
        super().etheno_set()
        if self.log_directory:
            self.datadir = os.path.join(self.log_directory, 'chain_data')
            os.makedirs(self.datadir)
        else:
            self._datadir_tmp = tempfile.TemporaryDirectory()
            self.datadir = self._datadir_tmp.name

    def add_to_run_script(self, command):
        if isinstance(command, Sequence):
            command = ' '.join(command)
        self._runscript.append(command)
            
    def make_tempfile(self, save_to_log=True, **kwargs):
        if 'dir' in kwargs:
            # make sure the dir exists:
            os.makedirs(kwargs['dir'], exist_ok=True)
        delete_on_exit = kwargs.get('delete_on_exit', True)
        if 'delete_on_exit' in kwargs:
            del kwargs['delete_on_exit']
        kwargs['delete'] = False
        tmpfile = tempfile.NamedTemporaryFile(**kwargs)
        requested_name = ''
        if save_to_log:
            if 'prefix' in kwargs:
                requested_name = kwargs['prefix']
            if 'suffix' in kwargs:
                requested_name += kwargs['suffix']
            if not requested_name:
                requested_name = tmpfile.name
        self._tempfiles.append((tmpfile.name, requested_name, delete_on_exit))
        return tmpfile

    def import_account(self, private_key):
        raise NotImplementedError()

    @property
    def accounts(self):
        for addr, bal in self.genesis['alloc'].items():
            yield int(addr, 16)

    def create_account(self, balance=0, address=None):
        accounts = list(self.accounts)
        if address is None:
            self._created_address_index += 1
            if self._created_address_index >= len(accounts):
                raise Exception("Ran out of %s genesis accounts and could not create a new one!" % self.short_name)
            return accounts[self._created_address_index]
        elif address not in accounts:
            raise Exception("Account %s did not exist in the genesis for client %s! Valid accounts:\n%s" % (address, self.short_name, '\n'.join(map(hex, accounts))))
        else:
            return address

    def get_start_command(self, unlock_accounts=True):
        raise NotImplementedError()

    def save_logs(self):
        if not self.log_directory:
            raise ValueError("A log directory has not been set for %s" % str(self))
        path_mapping = {}
        for path, name, delete_on_exit in self._tempfiles:
            if name and not path.startswith(self.log_directory):
                newpath = os.path.join(self.log_directory, name)
                shutil.copyfile(path, newpath)
                path_mapping[path] = newpath
        run_script = os.path.join(self.log_directory, "run_%s.sh" % self._basename.lower())
        with open(run_script, 'w') as f:
            runscript = '\n'.join(self._runscript)
            for oldpath, newpath in path_mapping.items():
                if oldpath.startswith(self.log_directory):
                    # This file is already in the log directory, so skip it
                    continue
                runscript = runscript.replace(oldpath, os.path.basename(newpath))
            runscript = runscript.replace(self.log_directory, '.')
            f.write(runscript)
        # make the script executable:
        os.chmod(run_script, 0o755)

    def start(self, unlock_accounts=True):
        start_args = self.get_start_command(unlock_accounts)
        self.instance = PtyLogger(self.logger, start_args)
        if self.log_directory:
            self.add_to_run_script(start_args)
            self.save_logs()
        self.wait_until_running()

    def stop(self):
        if self.instance is not None:
            instance = self.instance
            self.instance = None
            instance.terminate()
            instance.wait()
            instance.close()

    def cleanup(self):
        if self._datadir_tmp and os.path.exists(self.datadir):
            self._datadir_tmp.cleanup()
        for tmpfile, log_name, delete_on_exit in self._tempfiles:
            if delete_on_exit and os.path.exists(tmpfile):
                os.remove(tmpfile)
        self._tempfiles = []

    def shutdown(self):
        self.stop()
        self.cleanup()

    def wait_until_running(self):
        slept = 0.0
        while is_port_free(self.port):
            time.sleep(0.25)
            slept += 0.25
            if slept % 5 == 0:
                self.logger.info("Waiting for the process to start...")
