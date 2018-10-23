from web3.auto import w3

from .utils import format_hex_address

class Account(object):
    def __init__(self, address, balance = None, private_key = None):
        self._address = address
        self.balance = balance
        self._private_key = private_key
    @property
    def address(self):
        return self._address
    @property
    def private_key(self):
        return self._private_key

def make_genesis(network_id = 0x657468656E6F, difficulty = 20, gas_limit = 200000000000, accounts = None, homestead_block = 0, eip155_block = 0, eip158_block = 0):
    if accounts:
        alloc = {format_hex_address(acct.address): {'balance': "%d" % acct.balance, 'privateKey': format_hex_address(acct.private_key)} for acct in accounts}
    else:
        alloc = {}

    return {
        'config' : {
            'chainId': network_id,
            'homesteadBlock': homestead_block,
            'eip155Block': eip155_block,
            'eip158Block': eip158_block
        },
        'difficulty': "%d" % difficulty,
        'gasLimit': "%d" % gas_limit,
        'alloc': alloc
    }

def geth_to_parity(genesis):
    '''Converts a Geth style genesis to Parity style'''
    return {
        'name': 'etheno',
        'engine': {
            'Ethash': {
                'params': {
                    'minimumDifficulty': "0x%s" % genesis['difficulty'],
                    'difficultyBoundDivisor': '0x100000000',
                    'homesteadTransition': 0,
                    'eip150Transition': 0,
                    'eip160Transition': 0,
                    'eip161abcTransition': 0,
                    'eip161dTransition': 0,
                }
            }
        },
        'genesis': {
		"seal": {
                    'ethereum': {
                        'nonce': '0x0000000000000042',
                        'mixHash': '0x0000000000000000000000000000000000000000000000000000000000000000'
                    }
		},
		'difficulty': "0x%s" % genesis['difficulty'],
		'gasLimit': "0x%s" % genesis['gasLimit']
	},
        'params': {
            'networkID' : "0x%x" % genesis['config']['chainId'],
            'maximumExtraDataSize': '0x20',
            'minGasLimit': "0x%s" % genesis['gasLimit'],
            'gasLimitBoundDivisor': '1'
        },
        'accounts': dict(genesis['alloc'])
    }

def make_accounts(num_accounts, default_balance = None):
    ret = []
    for i in range(num_accounts):
        acct = w3.eth.account.create()
        ret.append(Account(address = int(acct.address, 16), private_key = int(acct.privateKey.hex(), 16), balance = default_balance))
    return ret
