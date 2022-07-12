const {expect} = require("chai");
const {ethers} = require("hardhat")

describe("Test Create2 logging", function() {
  // TODO: Need to isolate deployment, calling of function, etc.
  it("Deploy Deployer and ToDeploy contracts", async function() {
    // Get DeployerFactory
    const DeployerFactory = await ethers.getContractFactory("Deployer");
    // Deploy Deployer
    const mySalt = 12345
    const Deployer = await DeployerFactory.deploy();
    console.log("Deployer address is " + Deployer.address);

    // Deploy ToDeploy using create2
    const [account] = await ethers.getSigners();
    const tx = await Deployer.deploy(mySalt, { from: account.address });
    /*
    tx.wait();
    //console.log(tx.hash);
    const data = await ethers.provider.send("debug_traceTransaction", [tx.hash,]);
    //console.log(data);
    //console.log(data.structLogs)
    for (var i = 0; i < data.structLogs.length; i++) {
      // console.log(data.structLogs[i])
      // console.log(data.structLogs[i].op)
      if (data.structLogs[i].op == 'CREATE2') {
        console.log("i is " + i);
        console.log(data.structLogs[i]);
      }
      if (data.structLogs[i].pc == 245) {
        console.log("i is " + i);
        console.log(data.structLogs[i]);
      }
    } 
    */
    // Get address of ToDeploy address and compare to expectedAddress
    const expectedAddress = await Deployer.getAddress(mySalt);
    const actualAddress = await Deployer.toDeploy();
    console.log("Expected ToDeploy address is " + expectedAddress);
    console.log("Actual address is " + actualAddress);
    expect(expectedAddress).to.equal(actualAddress);
  });
});
