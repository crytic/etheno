import atexit
import os
import subprocess
import time

from . import logger
from .client import JSONRPCError
from .jsonrpcclient import JSONRPCClient
from .utils import format_hex_address

def ltrim_ansi(text):
    if text.startswith(logger.ANSI_RESET):
        return ltrim_ansi(text[len(logger.ANSI_RESET):])
    elif text.startswith(logger.ANSI_BOLD):
        return ltrim_ansi(text[len(logger.ANSI_BOLD):])
    for color in logger.CGAColors:
        ansi = logger.ANSI_COLOR % (30 + color.value)
        if text.startswith(ansi):
            return ltrim_ansi(text[len(ansi):])
    for color in logger.CGAColors:
        ansi = f"\033[{30 + color.value}m"
        if text.startswith(ansi):
            return ltrim_ansi(text[len(ansi):])
    return text

class GethClient(JSONRPCClient):
    def __init__(self, genesis, port=8546):
        super().__init__('Geth', genesis, port)
        atexit.register(GethClient.shutdown.__get__(self, GethClient))
    def initialized(self):
        def log(logger, message):
            msg = ltrim_ansi(message)
            if msg.startswith('ERROR'):
                logger.error(msg[5:].lstrip())
            elif msg.startswith('WARNING'):
                logger.warning(msg[7:].lstrip())
            elif msg.startswith('WARN'):
                logger.warning(msg[4:].lstrip())
            elif msg.startswith('DEBUG'):
                logger.debug(msg[5:].lstrip())
            elif msg.startswith('INFO'):
                logger.info(msg[4:].lstrip())
            else:
                logger.info(message)
        self.instance.log = log

    def etheno_set(self):
        super().etheno_set()
        try:
            args = ['/usr/bin/env', 'geth', 'init', self.logger.to_log_path(self.genesis_file), '--datadir', self.logger.to_log_path(self.datadir)]
            self.add_to_run_script(args)
            subprocess.check_call(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=self.log_directory)
        except Exception as e:
            self.cleanup()
            raise e

    def import_account(self, private_key):
        content = format_hex_address(private_key).encode('utf-8') + bytes([ord('\n')])
        import_dir = os.path.join(self.log_directory, 'private_keys')
        keyfile = self.logger.make_constant_logged_file(content, prefix='private', suffix='.key', dir=import_dir)
        while True:
            args = ['/usr/bin/env', 'geth', 'account', 'import', '--datadir', self.logger.to_log_path(self.datadir), '--password', self.logger.to_log_path(self.passwords), self.logger.to_log_path(keyfile)]
            self.add_to_run_script(args)
            geth = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=self.log_directory)
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
        if self.logger.log_level == logger.CRITICAL:
            verbosity = 0
        elif self.logger.log_level == logger.ERROR:
            verbosity = 1
        elif self.logger.log_level == logger.WARNING:
            verbosity = 2
        elif self.logger.log_level == logger.DEBUG:
            verbosity = 3
        else:
            verbosity = 4
        base_args = ['/usr/bin/env', 'geth', '--nodiscover', '--rpc', '--rpcport', "%d" % self.port, '--networkid', "%d" % self.genesis['config']['chainId'], '--datadir', self.logger.to_log_path(self.datadir), '--mine', '--etherbase', format_hex_address(self.miner_account.address), f"--verbosity={verbosity}", '--minerthreads=1']
        if unlock_accounts:
            addresses = filter(lambda a : a != format_hex_address(self.miner_account.address), map(format_hex_address, self.genesis['alloc']))
            unlock_args = ['--unlock', ','.join(addresses), '--password', self.passwords]
        else:
            unlock_args = []
        return base_args + unlock_args
