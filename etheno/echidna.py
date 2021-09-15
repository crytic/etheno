import os
import subprocess
import tempfile
from typing import Optional, Union

from .ascii_escapes import decode
from .etheno import EthenoPlugin
from .utils import ConstantTemporaryFile, format_hex_address

ECHIDNA_CONTRACT = b'''pragma solidity ^0.4.24;
contract C {
  mapping(int => int) public s;
  int public stored = 1337;
  function save(int key, int value) public {
    s[key] = value;
  }
  function remove(int key) public {
    delete s[key];
  }
  function setStored(int value) public {
    stored = value;
  }
  function f(uint, int, int[]) public { }
  function g(bool, int, address[]) public { }
  function echidna_() public returns (bool) {
    return true;
  }
}
'''

ECHIDNA_CONFIG = b'''outputRawTxs: true\nquiet: true\ndashboard: false\ngasLimit: 0xfffff\n'''


def echidna_exists():
    return subprocess.call(['/usr/bin/env', 'echidna-test', '--help'], stdout=subprocess.DEVNULL) == 0


def stack_exists():
    return subprocess.call(['/usr/bin/env', 'stack', '--help'], stdout=subprocess.DEVNULL) == 0


def git_exists():
    return subprocess.call(['/usr/bin/env', 'git', '--version'], stdout=subprocess.DEVNULL) == 0


def install_echidna(allow_reinstall: bool = False):
    if not allow_reinstall and echidna_exists():
        return
    elif not git_exists():
        raise Exception('Git must be installed in order to install Echidna')
    elif not stack_exists():
        raise Exception('Haskell Stack must be installed in order to install Echidna. On macOS you can easily install '
                        'it using Homebrew: `brew install haskell-stack`')

    with tempfile.TemporaryDirectory() as path:
        subprocess.check_call(['/usr/bin/env', 'git', 'clone', 'https://github.com/trailofbits/echidna.git', path])
        # TODO: Once the `dev-etheno` branch is merged into `master`, we can remove this:
        subprocess.call(['/usr/bin/env', 'git', 'checkout', 'dev-etheno'], cwd=path)
        subprocess.check_call(['/usr/bin/env', 'stack', 'install'], cwd=path)


def decode_binary_json(text: Union[str, bytes]) -> Optional[bytes]:
    orig = text
    text = decode(text).strip()
    if not text.startswith(b'['):
        return None
    offset = len(orig) - len(text)
    orig = text
    text = text[1:].strip()
    offset += len(orig) - len(text)
    if text[:1] != b'"':
        raise ValueError(
            f"Malformed JSON list! Expected '\"' but instead got '{text[0:1].decode()}' at offset {offset}"
        )
    text = text[1:]
    offset += 1
    if text[-1:] != b']':
        raise ValueError(
            f"Malformed JSON list! Expected ']' but instead got '{chr(text[-1])}' at offset {offset + len(text) - 1}"
        )
    text = text[:-1].strip()
    if text[-1:] != b'"':
        raise ValueError(
            f"Malformed JSON list! Expected '\"' but instead got '{chr(text[-1])}' at offset {offset + len(text) - 1}"
        )
    return text[:-1]


class EchidnaPlugin(EthenoPlugin):
    def __init__(self, transaction_limit: Optional[int] = None, contract_source: Optional[bytes] = None):
        self._transaction: int = 0
        self.limit: Optional[int] = transaction_limit
        self.contract_address = None
        if contract_source is None:
            self.contract_source: bytes = ECHIDNA_CONTRACT
        else:
            self.contract_source = contract_source
        self.contract_bytecode = None

    def added(self):
        # Wait until the plugin was added to Etheno so its logger is initialized
        self.contract_bytecode = self.compile(self.contract_source)

    def run(self):
        if not self.etheno.accounts:
            self.logger.info("Etheno does not know about any accounts, so Echidna has nothing to do!")
            self._shutdown()
            return
        elif self.contract_source is None:
            self.logger.error("Error compiling source contract")
            self._shutdown()
        # First, deploy the testing contract:
        self.logger.info('Deploying Echidna test contract...')
        self.contract_address = format_hex_address(self.etheno.deploy_contract(self.etheno.accounts[0],
                                                                               self.contract_bytecode), True)
        if self.contract_address is None:
            self.logger.error('Unable to deploy Echidna test contract!')
            self._shutdown()
            return
        self.logger.info("Deployed Echidna test contract to %s" % self.contract_address)
        config = self.logger.make_constant_logged_file(ECHIDNA_CONFIG, prefix='echidna', suffix='.yaml')
        sol = self.logger.make_constant_logged_file(
            self.contract_source, prefix='echidna', suffix='.sol')  # type: ignore
        echidna_args = ['/usr/bin/env', 'echidna-test', self.logger.to_log_path(sol), '--config',
                        self.logger.to_log_path(config)]
        run_script = self.logger.make_constant_logged_file(' '.join(echidna_args), prefix='run_echidna', suffix='.sh')
        # make the script executable:
        os.chmod(run_script, 0o755)

        echidna = subprocess.Popen(echidna_args, stderr=subprocess.DEVNULL, stdout=subprocess.PIPE, bufsize=1,
                                   universal_newlines=True, cwd=self.log_directory)
        while self.limit is None or self._transaction < self.limit:
            line = echidna.stdout.readline()
            if line != b'':
                txn = decode_binary_json(line)
                if txn is None:
                    continue
                self.emit_transaction(txn)
            else:
                break
        self._shutdown()

    def _shutdown(self):
        etheno = self.etheno
        self.etheno.remove_plugin(self)
        etheno.shutdown()

    def compile(self, solidity):
        with ConstantTemporaryFile(solidity, prefix='echidna', suffix='.sol') as contract:
            solc = subprocess.Popen(['/usr/bin/env', 'solc', '--bin', contract], stderr=subprocess.PIPE,
                                    stdout=subprocess.PIPE, bufsize=1, universal_newlines=True)
            errors = solc.stderr.read().strip()
            output = solc.stdout.read()
            if solc.wait() != 0:
                self.logger.error(f"{errors}\n{output}")
                return None
            elif errors:
                if solidity == ECHIDNA_CONTRACT:
                    # no need to raise a warning with our own contract:
                    self.logger.debug(errors)
                else:
                    self.logger.warning(errors)
            binary_key = 'Binary:'
            offset = output.find(binary_key)
            if offset < 0:
                self.logger.error(f"Could not parse `solc` output:\n{output}")
                return None
            code = hex(int(output[offset+len(binary_key):].strip(), 16))
            self.logger.debug(f"Compiled contract code: {code}")
            return code

    def emit_transaction(self, txn):
        self._transaction += 1
        transaction = {
            'id': 1,
            'jsonrpc': '2.0',
            'method': 'eth_sendTransaction',
            'params' : [{
                'from': format_hex_address(self.etheno.accounts[0], True),
                'to': self.contract_address,
                'gasPrice': "0x%x" % self.etheno.master_client.get_gas_price(),
                'value': '0x0',
                'data': "0x%s" % txn.hex()
            }]
        }
        gas = self.etheno.estimate_gas(transaction)
        if gas is None:
            self.logger.warning(f"All clients were unable to estimate the gas cost for transaction {self._transaction}."
                                f" This typically means that Echidna emitted a transaction that is too large.")
            return
        gas = "0x%x" % gas
        self.logger.info(f"Estimated gas cost for Transaction {self._transaction}: {gas}")
        transaction['params'][0]['gas'] = gas
        self.logger.info("Emitting Transaction %d" % self._transaction)
        self.etheno.post(transaction)


if __name__ == '__main__':
    install_echidna(allow_reinstall=True)
