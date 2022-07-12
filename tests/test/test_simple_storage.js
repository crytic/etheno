const {expect} = require("chai");
const {ethers} = require("hardhat")

describe("Test logging feature of Etheno", function() {
  // TODO: Need to isolate deployment, setting of state variable, and second deployment
  it("Deploy and test logging", async function() {
    // Get Factory
    const SimpleStorageFactory = await ethers.getContractFactory("SimpleStorage");
    // Deploy
    const SimpleStorage = await SimpleStorageFactory.deploy();

    const [account] = await ethers.getSigners()
    await SimpleStorage.set(89, { from: account.address });
    // Check stored value
    expect(await SimpleStorage.storedData()).to.equal(89);
    // Deploy another
    const SimpleStorageTwo = await SimpleStorageFactory.deploy();
  });
});
