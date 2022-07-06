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


def make_genesis(network_id=0x657468656E6F, difficulty=20, gas_limit=200000000000, accounts=None, byzantium_block=0, dao_fork_block=0, homestead_block=0, eip150_block=0, eip155_block=0, eip158_block=0, constantinople_block=None):
    if accounts:
        alloc = {format_hex_address(acct.address): {'balance': "%d" % acct.balance, 'privateKey': format_hex_address(acct.private_key)} for acct in accounts}
    else:
        alloc = {}

    ret = {
        'config' : {
            'chainId': network_id,
            'byzantiumBlock': byzantium_block,
            'daoForkBlock': dao_fork_block,
            'homesteadBlock': homestead_block,
            'eip150Block': eip150_block,
            'eip155Block': eip155_block,
            'eip158Block': eip158_block
        },
        'difficulty': "%d" % difficulty,
        'gasLimit': "%d" % gas_limit,
        'alloc': alloc
    }

    if constantinople_block is not None:
        ret['config']['constantinopleBlock'] = constantinople_block

    return ret

DEFAULT_PRIVATE_KEYS = [0xf2f48ee19680706196e2e339e5da3491186e0c4c5030670656b0e0164837257d,
                        0x5d862464fe9303452126c8bc94274b8c5f9874cbd219789b3eb2128075a76f72,
                        0xdf02719c4df8b9b8ac7f551fcb5d9ef48fa27eef7a66453879f4d8fdc6e78fb1,
                        0xff12e391b79415e941a94de3bf3a9aee577aed0731e297d5cfa0b8a1e02fa1d0,
                        0x752dd9cf65e68cfaba7d60225cbdbc1f4729dd5e5507def72815ed0d8abc6249,
                        0xefb595a0178eb79a8df953f87c5148402a224cdf725e88c0146727c6aceadccd,
                        0x83c6d2cc5ddcf9711a6d59b417dc20eb48afd58d45290099e5987e3d768f328f,
                        0xbb2d3f7c9583780a7d3904a2f55d792707c345f21de1bacb2d389934d82796b2,
                        0xb2fd4d29c1390b71b8795ae81196bfd60293adf99f9d32a0aff06288fcdac55f,
                        0x23cb7121166b9a2f93ae0b7c05bde02eae50d64449b2cbb42bc84e9d38d6cc89]

def make_accounts(num_accounts, default_balance = None):
    ret = []
    if num_accounts > len(DEFAULT_PRIVATE_KEYS):
        raise Exception('TODO: Too many accounts')
    for i in range(num_accounts):
        acct = w3.eth.account.from_key(DEFAULT_PRIVATE_KEYS[i])
        ret.append(Account(address=int(acct.address, 16), private_key=int(acct.privateKey.hex(), 16), balance=default_balance))
    return ret
