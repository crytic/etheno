pragma solidity ^0.4.24;
contract C {
  int public stored = 1337;
  function setStored(int value) public {
    stored = value;
  }
  function increment() public {
    int newValue = stored + 1;
    stored = 0;
    address(this).call(bytes4(keccak256("setStored(int256)")), newValue);
  }
  function echidna_() public returns (bool) {
    return true;
  }
}
