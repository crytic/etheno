// SPDX-License-Identifier: MIT
pragma solidity ^0.8.10;


contract ToDeploy {
    uint256 myVal = 42;
    constructor() {}

}

contract Deployer {
    ToDeploy public toDeploy;
    constructor() {}

    function getAddress(uint256 _salt) public view returns(address) {
        bytes32 hash = keccak256(abi.encodePacked(bytes1(0xff), address(this), _salt, keccak256(type(ToDeploy).creationCode)));
        return address(uint160(uint256(hash)));
    }

    function deploy(uint256 _salt) public {
        toDeploy = new ToDeploy{
            salt: bytes32(_salt)
        }();
    }
}
