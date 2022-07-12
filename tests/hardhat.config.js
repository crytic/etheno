require("@nomiclabs/hardhat-waffle");

module.exports = {
  networks: {
    localhost: {
        host: "127.0.0.1",
        port: 8545,
    }
  },
  solidity: {
      compilers: [
        {
          version: "0.8.10",
        },
        {
          version: "0.6.12",
        },
        {
          version: "0.5.0",
        }
      ]
  }
};
