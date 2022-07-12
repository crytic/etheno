from .etheno import EthenoPlugin
from .utils import ConstantTemporaryFile, format_hex_address
import subprocess
import os
class Precompiler(EthenoPlugin):
    def __init__(self, deploy_arb=False, deploy_opt=False):
        self._deploy_arb = deploy_arb
        self._deploy_opt = deploy_opt

        self._arb_sys_file = os.path.join(os.path.dirname(__file__), '..', "models/l2/arbitrum/ArbSys.sol")
        self._arb_retryable_tx_file = os.path.join(os.path.dirname(__file__), '..', "models/l2/arbitrum/ArbRetryableTx.sol")

    
    def run(self):
        if self._deploy_arb:
            with open(self._arb_sys_file, 'rb') as arb_sys_file:
                arb_sys_file_bytes = arb_sys_file.read()
            arb_sys_bytecode = self.compile(arb_sys_file_bytes)
            print(arb_sys_bytecode)
        return
    

    def compile(self, solidity):
        with ConstantTemporaryFile(solidity, prefix='echidna', suffix='.sol') as contract:
            solc = subprocess.Popen(['/usr/bin/env', 'solc', '--bin', contract], stderr=subprocess.PIPE,
                                    stdout=subprocess.PIPE, bufsize=1, universal_newlines=True)
            errors = solc.stderr.read().strip()
            output = solc.stdout.read()
            if solc.wait() != 0:
                self.logger.error(f"{errors}\n{output}")
                return None
            self.logger.warning(errors)
            # There is an interface and a contract so there are two instances of "Binary" - both need to be removed
            # TODO: do we need the interface
            # TODO: can this be done better?
            binary_key = 'Binary:'
            binary_key_len = len(binary_key)
            offset_one = output.find(binary_key)
            offset_two = output[(offset_one+binary_key_len):].find(binary_key)
            if offset_one < 0 or offset_two < 0:
                self.logger.error(f"Could not parse `solc` output:\n{output}")
                return None
            final_offset = offset_one + offset_two + (binary_key_len * 2)
            code = hex(int(output[final_offset:].strip(), 16))
            self.logger.debug(f"Compiled contract code: {code}")
            return code