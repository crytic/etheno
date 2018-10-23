import subprocess
import tempfile

from .ascii_escapes import decode
from .etheno import EthenoPlugin
from .utils import ConstantTemporaryFile, format_hex_address

ECHIDNA_CONTRACT = b'''pragma solidity ^0.4.24;
contract C {
  function f(uint, int, int[]) public { }
  function g(bool, int, address[]) public { }
  function echidna_() public returns (bool) {
    return true;
  }
}
'''

ECHIDNA_CONTRACT_BYTECODE = b'608060405234801561001057600080fd5b506101c0806100206000396000f300608060405260043610610057576000357c0100000000000000000000000000000000000000000000000000000000900463ffffffff168063554c5abd1461005c5780638c9670b51461008b5780639ccb138f14610107575b600080fd5b34801561006857600080fd5b50610071610181565b604051808215151515815260200191505060405180910390f35b34801561009757600080fd5b50610105600480360381019080803515159060200190929190803590602001909291908035906020019082018035906020019080806020026020016040519081016040528093929190818152602001838360200280828437820191505050505050919291929050505061018a565b005b34801561011357600080fd5b5061017f60048036038101908080359060200190929190803590602001909291908035906020019082018035906020019080806020026020016040519081016040528093929190818152602001838360200280828437820191505050505050919291929050505061018f565b005b60006001905090565b505050565b5050505600a165627a7a72305820c33d6d41fb62e921093df0df9278328c3f1f256bac6be1400b47d233c6b1aeff0029'

ECHIDNA_CONFIG = b'''outputRawTxs: True\n'''

def echidna_exists():
    return subprocess.call(['/usr/bin/env', 'echidna-test', '--help'], stdout=subprocess.DEVNULL) == 0

def stack_exists():
    return subprocess.call(['/usr/bin/env', 'stack', '--help'], stdout=subprocess.DEVNULL) == 0

def git_exists():
    return subprocess.call(['/usr/bin/env', 'git', '--version'], stdout=subprocess.DEVNULL) == 0

def install_echidna(allow_reinstall = False):
    if not allow_reinstall and echidna_exists():
        return
    elif not git_exists():
        raise Exception('Git must be installed in order to install Echidna')
    elif not stack_exists():
        raise Exception('Haskell Stack must be installed in order to install Echidna. On OS X you can easily install it using Homebrew: `brew install haskell-stack`')

    with tempfile.TemporaryDirectory() as path:
        subprocess.check_call(['/usr/bin/env', 'git', 'clone', 'https://github.com/trailofbits/echidna.git', path])
        # TODO: Once the `dev-no-hedgehog` branch is merged into `master`, we can remove this:
        subprocess.call(['/usr/bin/env', 'git', 'checkout', 'dev-no-hedgehog'], cwd=path)
        subprocess.check_call(['/usr/bin/env', 'stack', 'install'], cwd=path)

def decode_binary_json(text):
    orig = text
    text = decode(text).strip()
    if not text.startswith(b'['):
        return None
    offset = len(orig) - len(text)
    orig = text
    text = text[1:].strip()
    offset += len(orig) - len(text)
    if text[:1] != b'"':
        raise ValueError("Malformed JSON list! Expected '%s' but instead got '%s' at offset %d" % ('"', text[0:1].decode(), offset))
    text = text[1:]
    offset += 1
    if text[-1:] != b']':
        raise ValueError("Malformed JSON list! Expected '%s' but instead got '%s' at offset %d" % (']', chr(text[-1]), offset + len(text) - 1))
    text = text[:-1].strip()
    if text[-1:] != b'"':
        raise ValueError("Malformed JSON list! Expected '%s' but instead got '%s' at offset %d" % ('"', chr(text[-1]), offset + len(text) - 1))
    return text[:-1]

class EchidnaPlugin(EthenoPlugin):
    def __init__(self, transaction_limit=None):
        self._transaction = 0
        self.limit = transaction_limit
        self.contract_address = None
    def run(self):
        if not self.etheno.accounts:
            print("Etheno does not know about any accounts, so Echidna has nothing to do!")
            self._shutdown()
            return
        # First, deploy the testing contract:
        self.contract_address = format_hex_address(self.etheno.deploy_contract(self.etheno.accounts[0], ECHIDNA_CONTRACT_BYTECODE), True)
        print("Deployed Echidna test contract to %s" % self.contract_address)
        with ConstantTemporaryFile(ECHIDNA_CONFIG, prefix='echidna', suffix='.yaml') as config:
            with ConstantTemporaryFile(ECHIDNA_CONTRACT, prefix='echidna', suffix='.sol') as sol:
                echidna = subprocess.Popen(['/usr/bin/env', 'echidna-test', sol, '--config', config], stderr=subprocess.DEVNULL, stdout=subprocess.PIPE, bufsize=1, universal_newlines=True)
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

    def emit_transaction(self, txn):
        self._transaction += 1
        print("Echidna: Emitting Transaction %d" % self._transaction)
        self.etheno.post({
            'id': 1,
            'jsonrpc': '2.0',
            'method': 'eth_sendTransaction',
            'params' : [{
                "from": format_hex_address(self.etheno.accounts[0], True),
                "to": self.contract_address,
                "gas": "0x9999",
                "gasPrice": "0x%x" % self.etheno.master_client.get_gas_price(),
                "value": "0x0",
                "data": "0x%s" % txn.hex()
            }]
        })

if __name__ == '__main__':
    install_echidna(allow_reinstall = True)
