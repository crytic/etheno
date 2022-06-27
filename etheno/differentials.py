from enum import Enum
import os

from .client import JSONRPCError, SelfPostingClient
from .etheno import EthenoPlugin

class DifferentialTest(object):
    def __init__(self, tester, test_name, success, message = ''):
        self.tester = tester
        self.test_name = test_name
        self.message = message
        self.success = success
        self.tester.logger.make_constant_logged_file(self.message, prefix=['FAILED', 'PASSED'][self.success.value], suffix='.log', dir=os.path.join(self.tester.logger.directory, self.test_name))
    def __str__(self):
        return "[%s] %s\t%s" % (self.test_name, self.success, self.message)
    __repr__ = __str__

class TestResult(Enum):
    FAILED = 0
    PASSED = 1

class DifferentialTester(EthenoPlugin):
    def __init__(self):
        self._transactions_by_hash = {}
        self._unprocessed_transactions = set()
        self.tests = {}
        self._printed_summary = False

    def add_test_result(self, result):
        if result.test_name not in self.tests:
            self.tests[result.test_name] = {}
        if result.success not in self.tests[result.test_name]:
            self.tests[result.test_name][result.success] = []
        self.tests[result.test_name][result.success].append(result)

    def after_post(self, data, client_results):
        method = data['method']

        # First, see if any of the clients returned an error. If one did, they all should!
        clients_with_errors = tuple(i for i, result in enumerate(client_results) if isinstance(result, JSONRPCError))
        clients_without_errors = tuple(sorted(frozenset(range(len(client_results))) - frozenset(clients_with_errors)))

        if clients_with_errors:
            clients = [self.etheno.master_client] + self.etheno.clients
            if clients_without_errors:
                test = DifferentialTest(self, 'JSON_RPC_ERRORS', TestResult.FAILED, "%s executed JSON RPC call %s with no errors, but %s executed the same transaction with errors:\n%s" % (
                    ', '.join(str(clients[client]) for client in clients_without_errors),
                    data,
                    ', '.join(str(clients[client]) for client in clients_with_errors),
                    '\n'.join(str(client_results[client]) for client in clients_with_errors)
                ))
            else:
                test = DifferentialTest(self, 'JSON_RPC_ERRORS', TestResult.PASSED, "All clients executed JSON RPC call %s with errors" % data)
            self.add_test_result(test)
            self.logger.error(test.message)
            return
        else:
            self.add_test_result(DifferentialTest(self, 'JSON_RPC_ERRORS', TestResult.PASSED, "All clients executed transaction %s without error" % data))
        
        master_result = client_results[0]
        if method == 'eth_sendTransaction' or method == 'eth_sendRawTransaction':
            if not isinstance(master_result, JSONRPCError) and 'result' in master_result and master_result['result']:
                self._unprocessed_transactions.add(master_result['result'])
                self._transactions_by_hash[master_result['result']] = data
        elif method == 'eth_getTransactionReceipt':
            if master_result and 'result' in master_result and master_result['result']:
                # mark that we have processed the receipt for this transaction:
                if data['params'][0] in self._unprocessed_transactions:
                    self._unprocessed_transactions.remove(data['params'][0])

                if 'contractAddress' in master_result['result'] and master_result['result']['contractAddress']:
                    # the master client created a new contract
                    # so make sure that all of the other clients did, too
                    for client, client_data in zip(self.etheno.clients, client_results[1:]):
                        created = False
                        try:
                            created = client_data['result']['contractAddress']
                        except Exception:
                            pass
                        if not created:
                            test = DifferentialTest(self, 'CONTRACT_CREATION', TestResult.FAILED, f"{self.etheno.master_client} created a contract for transaction {data['params'][0]}, but {client} did not")
                            self.add_test_result(test)
                            self.logger.error(test.message)
                        else:
                            self.add_test_result(DifferentialTest(self, 'CONTRACT_CREATION', TestResult.PASSED,  "client %s transaction %s" % (client, data['params'][0])))
                if 'gasUsed' in master_result['result'] and master_result['result']['gasUsed']:
                    # make sure each client used the same amount of gas
                    master_gas = int(master_result['result']['gasUsed'], 16)
                    for client, client_data in zip(self.etheno.clients, client_results[1:]):
                        gas_used = 0
                        try:
                            gas_used = int(client_data['result']['gasUsed'], 16)
                        except Exception:
                            pass
                        if gas_used != master_gas:
                            test = DifferentialTest(self, 'GAS_USAGE', TestResult.FAILED, f"""Transaction {data['params'][0]} used:

    {hex(master_gas)} gas in {self.etheno.master_client} but
    {hex(gas_used)} gas in {client}

while mining this transaction:

{self._transactions_by_hash.get(data['params'][0], 'UNKNOWN TRANSACTION')}""")
                            self.add_test_result(test)
                            self.logger.error(test.message)
                        else:
                            self.add_test_result(DifferentialTest(self, 'GAS_USAGE', TestResult.PASSED, "client %s transaction %s used 0x%x gas" % (client, data['params'][0], gas_used)))

                # we have processed this transaction, so no need to keep its original arguments around:
                if data['params'][0] in self._transactions_by_hash:
                    del self._transactions_by_hash[data['params'][0]]

    def finalize(self):
        unprocessed = self._unprocessed_transactions
        self._unprocessed_transactions = set()
        for tx_hash in unprocessed:
            self.logger.info("Requesting transaction receipt for %s to check differentials..." % tx_hash)
            if not isinstance(self.etheno.master_client, SelfPostingClient):
                self.logger.warn("The DifferentialTester currently only supports master clients that extend from SelfPostingClient, but %s does not; skipping checking transaction(s) %s" % (self.etheno.master_client, ', '.join(unprocessed)))
                return
            while True:
                receipt = self.etheno.post({
                    'jsonrpc': '2.0',
                    'method': 'eth_getTransactionReceipt',
                    'params': [tx_hash]
                })
                # if this post is successful, it will trigger the `after_post` callback above
                # where were check for the differentials
                if 'result' in receipt and receipt['result']:
                    break
                # The transaction is still pending
                time.sleep(3.0)

    def shutdown(self):
        # super().shutdown() should automatically call self.finalize()
        super().shutdown()
        if self.tests and not self._printed_summary:
            self._printed_summary = True
            ret = '\nDifferential Test Summary:\n\n'
            for test in sorted(self.tests):
                ret += "    %s\n" % test
                total = sum(map(len, self.tests[test].values()))
                for result in self.tests[test]:
                    ret += "        %s\t%d / %d\n" % (result, len(self.tests[test][result]), total)
                ret += '\n'
            self.logger.info(ret)
