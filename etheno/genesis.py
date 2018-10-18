from web3.auto import w3

from .utils import format_hex_address

def make_genesis(network_id = 0x657468656E6F, difficulty = 20, gas_limit = 200000000000, accounts = None, homestead_block = 0, eip155_block = 0, eip158_block = 0):
    if accounts:
        alloc = {format_hex_address(addr): {'balance': "%d" % bal} for addr, bal in accounts}
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

def make_accounts(num_accounts):
    return [w3.eth.account.create() for i in range(num_accounts)]
