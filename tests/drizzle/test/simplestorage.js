const {expect} = require("chai");
const {ethers} = require("hardhat")

describe("Deploy SimpleStorage", function() {
  it("Deploy", async function() {
    // Get Factory
    const SimpleStorageFactory = await ethers.getContractFactory("SimpleStorage");
    // Deploy
    const SimpleStorage = await SimpleStorageFactory.deploy();

    const [account] = await ethers.getSigners()
    await SimpleStorage.set(89, { from: account.address });
    // Check stored value
    expect(await SimpleStorage.storedData()).to.equal(89);
  });
});
