pragma solidity ^0.5.0;

import "./ConvertLib.sol";

/**
 * This is a simple example token with several vulnerabilities added.
 */
contract MetaCoin {
	mapping (address => uint) balances;
        uint256[] metadata;

	event Transfer(address indexed _from, address indexed _to, uint256 _value);

	constructor() public {
		balances[tx.origin] = 10000;
	}

        function setMetadata(uint256 key, uint256 value) public {
                if (metadata.length <= key) {
                       metadata.length = key + 1;
                }
                metadata[key] = value;
        }

        function getMetadata(uint256 key) public view returns (uint256) {
                 return metadata[key];
        }

        function backdoor() public {
                 selfdestruct(msg.sender);
        }

	function sendCoin(address receiver, uint amount) public returns(bool sufficient) {
		if (balances[msg.sender] < amount) return false;
		balances[msg.sender] -= amount;
		balances[receiver] += amount;
		emit Transfer(msg.sender, receiver, amount);
		return true;
	}

	function getBalanceInEth(address addr) public view returns(uint){
		return ConvertLib.convert(getBalance(addr),2);
	}

	function getBalance(address addr) public view returns(uint) {
		return balances[addr];
	}
}
