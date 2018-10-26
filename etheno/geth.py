import atexit
import os
import subprocess
import time

from .client import JSONRPCError
from .jsonrpcclient import JSONRPCClient
from .utils import ConstantTemporaryFile, format_hex_address

class GethClient(JSONRPCClient):
    def __init__(self, genesis, port=8546):
        super().__init__('Geth', genesis, port)
        atexit.register(GethClient.shutdown.__get__(self, GethClient))

    def etheno_set(self):
        super().etheno_set()
        try:
            args = ['/usr/bin/env', 'geth', 'init', self.genesis_file, '--datadir', self.datadir]
            self.add_to_run_script(args)
            subprocess.check_call(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            self.cleanup()
            raise e

    def import_account(self, private_key):
        content = format_hex_address(private_key).encode('utf-8') + bytes([ord('\n')])
        with ConstantTemporaryFile(content, prefix='private', suffix='.key') as keyfile:
            if self.log_directory:
                import_dir = os.path.join(self.log_directory, 'private_keys')
                with self.make_tempfile(prefix='private', suffix='.key', dir=import_dir, delete_on_exit=False) as f:
                    f.write(content)
                    keyfile = f.name
            while True:
                args = ['/usr/bin/env', 'geth', 'account', 'import', '--datadir', self.datadir, '--password', self.passwords, keyfile]
                self.add_to_run_script(args)
                geth = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if geth.wait() == 0:
                    return
                # This sometimes happens with geth, I have no idea why, so just try again

    def post(self, data):
        # geth takes a while to unlock all of the accounts, so check to see if that caused an error and just wait a bit
        while True:
            try:
                return super().post(data)
            except JSONRPCError as e:
                if e.result['error']['code'] == -32000 and 'authentication needed' in e.result['error']['message']:
                    self.logger.info("Waiting for Geth to finish unlocking our accounts...")
                    time.sleep(3.0)
                else:
                    raise e

    def get_start_command(self, unlock_accounts=True):
        base_args = ['/usr/bin/env', 'geth', '--nodiscover', '--rpc', '--rpcport', "%d" % self.port, '--networkid', "%d" % self.genesis['config']['chainId'], '--datadir', self.datadir, '--mine', '--etherbase', format_hex_address(self.miner_account.address)]
        if unlock_accounts:
            addresses = filter(lambda a : a != format_hex_address(self.miner_account.address), map(format_hex_address, self.genesis['alloc']))
            unlock_args = ['--unlock', ','.join(addresses), '--password', self.passwords]
        else:
            unlock_args = []
        return base_args + unlock_args
