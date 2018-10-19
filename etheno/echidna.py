import subprocess

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

ECHIDNA_CONFIG = b'''outputRawTxs: True\n'''

def echidna_exists():
    return subprocess.call(['/usr/bin/env', 'echidna', '--help'], stdout=subprocess.PIPE) == 0

def stack_exists():
    return subprocess.call(['/usr/bin/env', 'stack', '--help'], stdout=subprocess.PIPE) == 0

def git_exists():
    return subprocess.call(['/usr/bin/env', 'git', '--version'], stdout=subprocess.PIPE) == 0

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
    def run(self):
        if not self.etheno.accounts:
            print("Etheno does not know about any accounts, so Echidna has nothing to do!")
            self._shutdown()
            return
        with ConstantTemporaryFile(ECHIDNA_CONFIG, prefix='echidna', suffix='.yaml') as config:
            with ConstantTemporaryFile(ECHIDNA_CONTRACT, prefix='echidna', suffix='.sol') as sol:
                echidna = subprocess.Popen(['/usr/bin/env', 'echidna-test', sol, '--config', config], stderr=subprocess.DEVNULL, stdout=subprocess.PIPE, bufsize=1, universal_newlines=True)
                while True:
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
        self.etheno.post({
            'id': 1,
            'jsonrpc': '2.0',
            'method': 'eth_sendTransaction',
            'params' : [{
                "from": format_hex_address(self.etheno.accounts[0]),
                "to": "0x0",
                "gas": "0x76c0",
                "gasPrice": "0x9184e72a000",
                "value": "0x0",
                "data": "0x%s" % txn.hex()
            }]
        })

if __name__ == '__main__':
    install_echidna(allow_reinstall = True)
