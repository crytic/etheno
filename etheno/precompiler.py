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
        from_address = self._etheno.accounts[0]
        if self._deploy_arb:
            # Deploy ArbSys
            # TODO: could decrease cyclomatic complexity here a bit
            if os.path.exists(self._arb_sys_file):
                with open(self._arb_sys_file, 'rb') as arb_sys_file:
                    arb_sys_file_bytes = arb_sys_file.read()
                arb_sys_bytecode = self.compile(arb_sys_file_bytes)   
                # If solc returns None, throw error and move on.
                if arb_sys_bytecode:
                    arb_sys_contract_address = self._etheno.deploy_contract(from_address=from_address, bytecode=arb_sys_bytecode)
                else:
                    self.logger.error(f"Could not deploy ArbSys due to compilation issues")
            else:
                self.logger.error(f"Could not find ArbSys.sol file at:\n{self._arb_sys_file}")
            
            # Deploy ArbRetryableTx
            if os.path.exists(self._arb_retryable_tx_file):
                with open(self._arb_retryable_tx_file, 'rb') as arb_retryable_tx_file:
                    arb_retryable_tx_file_bytes = arb_retryable_tx_file.read()
                arb_retryable_tx_file_bytecode = self.compile(arb_retryable_tx_file_bytes)
                # If solc returns None, throw error and move on.   
                if arb_retryable_tx_file_bytecode:
                    arb_retryable_tx_contract_address = self._etheno.deploy_contract(from_address=from_address, bytecode=arb_retryable_tx_file_bytecode)
                    print(arb_retryable_tx_contract_address)
                else:
                    self.logger.error(f"Could not deploy ArbRetryableTx due to compilation issues")        
        return
    

    def compile(self, solidity):
        # TODO: Why was prefix and suffix given?
        with ConstantTemporaryFile(solidity) as contract:
            solc = subprocess.Popen(['/usr/bin/env', 'solc', '--bin', contract], stderr=subprocess.PIPE,
                                    stdout=subprocess.PIPE, bufsize=1, universal_newlines=True)
            errors = solc.stderr.read().strip()
            output = solc.stdout.read()
            if solc.wait() != 0:
                self.logger.error(f"{errors}\n{output}")
                return None
            self.logger.warning(errors)
            # Only the last contract in the compiled bytecode is deployed.
            # TODO: do we need the interface?
            binary_key = 'Binary:'
            binary_key_len = len(binary_key)
            total_offset = 0
            while True:
                offset = output[total_offset:].find(binary_key)
                if offset < 0:
                    break
                total_offset += (offset + binary_key_len)
            try:
                code = hex(int(output[total_offset:].strip(), 16))
                self.logger.debug(f"Compiled contract code: {code}")
                return code
            except Exception as e:
                self.logger.error(f"Could not parse `solc` output:\n{output}\n with this error:\n{e}")
                return None
