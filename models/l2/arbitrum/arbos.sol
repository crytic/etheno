pragma solidity >=0.4.21 <0.9.0;

/**
* @title Precompiled contract that exists in every Arbitrum chain at address(100), 0x0000000000000000000000000000000000000064. Exposes a variety of system-level functionality.
 */
interface ArbSys {
    /**
    * @notice Get internal version number identifying an ArbOS build
    * @return version number as int
     */
    function arbOSVersion() external pure returns (uint);

    function arbChainID() external view returns(uint);

    /**
    * @notice Get Arbitrum block number (distinct from L1 block number; Arbitrum genesis block has block number 0)
    * @return block number as int
     */ 
    function arbBlockNumber() external view returns (uint);

    /** 
    * @notice Send given amount of Eth to dest from sender.
    * This is a convenience function, which is equivalent to calling sendTxToL1 with empty calldataForL1.
    * @param destination recipient address on L1
    * @return unique identifier for this L2-to-L1 transaction.
    */
    function withdrawEth(address destination) external payable returns(uint);

    /** 
    * @notice Send a transaction to L1
    * @param destination recipient address on L1 
    * @param calldataForL1 (optional) calldata for L1 contract call
    * @return a unique identifier for this L2-to-L1 transaction.
    */
    function sendTxToL1(address destination, bytes calldata calldataForL1) external payable returns(uint);

    /** 
    * @notice get the number of transactions issued by the given external account or the account sequence number of the given contract
    * @param account target account
    * @return the number of transactions issued by the given external account or the account sequence number of the given contract
    */
    function getTransactionCount(address account) external view returns(uint256);

    /**  
    * @notice get the value of target L2 storage slot 
    * This function is only callable from address 0 to prevent contracts from being able to call it
    * @param account target account
    * @param index target index of storage slot 
    * @return stotage value for the given account at the given index
    */
    function getStorageAt(address account, uint256 index) external view returns (uint256);

    /**
    * @notice check if current call is coming from l1
    * @return true if the caller of this was called directly from L1
    */
    function isTopLevelCall() external view returns (bool);

    /**
     * @notice check if the caller (of this caller of this) is an aliased L1 contract address
     * @return true iff the caller's address is an alias for an L1 contract address
     */
    function wasMyCallersAddressAliased() external view returns (bool);

    /**
     * @notice return the address of the caller (of this caller of this), without applying L1 contract address aliasing
     * @return address of the caller's caller, without applying L1 contract address aliasing
     */
    function myCallersAddressWithoutAliasing() external view returns (address);

    /**
     * @notice map L1 sender contract address to its L2 alias
     * @param sender sender address
     * @param dest destination address
     * @return aliased sender address
     */
    function mapL1SenderContractAddressToL2Alias(address sender, address dest) external pure returns(address);

    /**
     * @notice get the caller's amount of available storage gas
     * @return amount of storage gas available to the caller
     */
    function getStorageGasAvailable() external view returns(uint);

    event L2ToL1Transaction(address caller, address indexed destination, uint indexed uniqueId,
                            uint indexed batchNumber, uint indexInBatch,
                            uint arbBlockNum, uint ethBlockNum, uint timestamp,
                            uint callvalue, bytes data);
}

contract ArbSysEmulated is ArbSys {
    // Simulates a unique identifier for L2-to-L1 transactions
    uint256 private id = 1;

    function arbOSVersion() external pure returns (uint) {
        return 1;
    }

    function arbChainID() external view returns(uint) {
        return 42161;
    }

    /**
    * @notice Get Arbitrum block number (distinct from L1 block number; Arbitrum genesis block has block number 0)
    * @return block number as int
     */ 
    function arbBlockNumber() external view returns (uint) {
        return 0;
    }

    /** 
    * @notice Send given amount of Eth to dest from sender.
    * This is a convenience function, which is equivalent to calling sendTxToL1 with empty calldataForL1.
    * @param destination recipient address on L1
    * @return unique identifier for this L2-to-L1 transaction.
    */
    function withdrawEth(address destination) external payable returns(uint) {
        return this.sendTxToL1(destination, "");
    }

    /** 
    * @notice Send a transaction to L1
    * @param destination recipient address on L1 
    * @param calldataForL1 (optional) calldata for L1 contract call
    * @return a unique identifier for this L2-to-L1 transaction.
    */
    function sendTxToL1(address destination, bytes calldata calldataForL1) public payable returns(uint) {
       return id++;
    }

    /** 
    * @notice get the number of transactions issued by the given external account or the account sequence number of the given contract
    * @param account target account
    * @return the number of transactions issued by the given external account or the account sequence number of the given contract
    */
    function getTransactionCount(address account) external view returns(uint256) {
        return 0;
    }

    /**  
    * @notice get the value of target L2 storage slot 
    * This function is only callable from address 0 to prevent contracts from being able to call it
    * @param account target account
    * @param index target index of storage slot 
    * @return stotage value for the given account at the given index
    */
    function getStorageAt(address account, uint256 index) external view returns (uint256) {
        revert(); // Not callable from Echidna
    }

    /**
    * @notice check if current call is coming from l1
    * @return true if the caller of this was called directly from L1
    */
    function isTopLevelCall() external view returns (bool) {
        return false; // Not sure if this is possible to emulate
    }

    /**
     * @notice check if the caller (of this caller of this) is an aliased L1 contract address
     * @return true iff the caller's address is an alias for an L1 contract address
     */
    function wasMyCallersAddressAliased() external view returns (bool) {
        return false; // Not sure if this is possible to emulate
    }

    /**
     * @notice return the address of the caller (of this caller of this), without applying L1 contract address aliasing
     * @return address of the caller's caller, without applying L1 contract address aliasing
     */
    function myCallersAddressWithoutAliasing() external view returns (address)  {
        return address(0x0); // Not sure if this is possible to emulate
    }

    /**
     * @notice map L1 sender contract address to its L2 alias
     * @param sender sender address
     * @param dest destination address
     * @return aliased sender address
     */
    function mapL1SenderContractAddressToL2Alias(address sender, address dest) external pure returns(address) {
        return address(0x0); // Not sure if this is possible to emulate
    }


    /**
     * @notice get the caller's amount of available storage gas
     * @return amount of storage gas available to the caller
     */
    function getStorageGasAvailable() external view returns(uint) {
        return 0; // Not sure if this is possible to emulate
    }

}


/**
* @title precompiled contract in every Arbitrum chain for retryable transaction related data retrieval and interactions. Exists at 0x000000000000000000000000000000000000006E 
*/
interface ArbRetryableTx {

    /**
    * @notice Redeem a redeemable tx.
    * Revert if called by an L2 contract, or if userTxHash does not exist, or if userTxHash reverts.
    * If this returns, userTxHash has been completed and is no longer available for redemption.
    * If this reverts, userTxHash is still available for redemption (until it times out or is canceled).
    * @param userTxHash unique identifier of retryable message: keccak256(keccak256(ArbchainId, inbox-sequence-number), uint(0) )
    */
    function redeem(bytes32 userTxHash) external;

    /** 
    * @notice Return the minimum lifetime of redeemable txn.
    * @return lifetime in seconds
    */
    function getLifetime() external view returns(uint);

    /**
    * @notice Return the timestamp when userTxHash will age out, or zero if userTxHash does not exist.
    * The timestamp could be in the past, because aged-out tickets might not be discarded immediately.
    * @param userTxHash unique ticket identifier
    * @return timestamp for ticket's deadline
    */
    function getTimeout(bytes32 userTxHash) external view returns(uint);

    /** 
    * @notice Return the price, in wei, of submitting a new retryable tx with a given calldata size.
    * @param calldataSize call data size to get price of (in wei)
    * @return (price, nextUpdateTimestamp). Price is guaranteed not to change until nextUpdateTimestamp.
    */ 
    function getSubmissionPrice(uint calldataSize) external view returns (uint, uint);

    /** 
     * @notice Return the price, in wei, of extending the lifetime of userTxHash by an additional lifetime period. Revert if userTxHash doesn't exist.
     * @param userTxHash unique ticket identifier
     * @return (price, nextUpdateTimestamp). Price is guaranteed not to change until nextUpdateTimestamp.
    */
    function getKeepalivePrice(bytes32 userTxHash) external view returns(uint, uint);

    /** 
    @notice Deposits callvalue into the sender's L2 account, then adds one lifetime period to the life of userTxHash.
    * If successful, emits LifetimeExtended event.
    * Revert if userTxHash does not exist, or if the timeout of userTxHash is already at least one lifetime period in the future, or if the sender has insufficient funds (after the deposit).
    * @param userTxHash unique ticket identifier
    * @return New timeout of userTxHash.
    */
    function keepalive(bytes32 userTxHash) external payable returns(uint);

    /**
    * @notice Return the beneficiary of userTxHash.
    * Revert if userTxHash doesn't exist.
    * @param userTxHash unique ticket identifier
    * @return address of beneficiary for ticket
    */
    function getBeneficiary(bytes32 userTxHash) external view returns (address);

    /** 
    * @notice Cancel userTxHash and refund its callvalue to its beneficiary.
    * Revert if userTxHash doesn't exist, or if called by anyone other than userTxHash's beneficiary.
    * @param userTxHash unique ticket identifier
    */
    function cancel(bytes32 userTxHash) external;

    event TicketCreated(bytes32 indexed userTxHash);
    event LifetimeExtended(bytes32 indexed userTxHash, uint newTimeout);
    event Redeemed(bytes32 indexed userTxHash);
    event Canceled(bytes32 indexed userTxHash);
}

contract ArbRetryableTxEmulated is ArbRetryableTx {
    mapping(bytes32 => uint256) private ticketTimeout;
    mapping(bytes32 => address) private ticketBeneficiary;


    function createTicket(bytes32 userTxHash, address beneficiary) public {
         require(ticketTimeout[userTxHash] == 0);
         ticketTimeout[userTxHash] = block.timestamp + 1 days;
         ticketBeneficiary[userTxHash] = beneficiary;
    }

    /**
    * @notice Redeem a redeemable tx.
    * Revert if called by an L2 contract, or if userTxHash does not exist, or if userTxHash reverts.
    * If this returns, userTxHash has been completed and is no longer available for redemption.
    * If this reverts, userTxHash is still available for redemption (until it times out or is canceled).
    * @param userTxHash unique identifier of retryable message: keccak256(keccak256(ArbchainId, inbox-sequence-number), uint(0) )
    */
    function redeem(bytes32 userTxHash) external {
        require(ticketTimeout[userTxHash] > 0);
        delete ticketTimeout[userTxHash];
        delete ticketBeneficiary[userTxHash]; 
    }

    /** 
    * @notice Return the minimum lifetime of redeemable txn.
    * @return lifetime in seconds
    */
    function getLifetime() external view returns(uint) {
        return 1 days;
    }

    /**
    * @notice Return the timestamp when userTxHash will age out, or zero if userTxHash does not exist.
    * The timestamp could be in the past, because aged-out tickets might not be discarded immediately.
    * @param userTxHash unique ticket identifier
    * @return timestamp for ticket's deadline
    */
    function getTimeout(bytes32 userTxHash) external view returns(uint) {
        return ticketTimeout[userTxHash];
    }

    /** 
    * @notice Return the price, in wei, of submitting a new retryable tx with a given calldata size.
    * @param calldataSize call data size to get price of (in wei)
    * @return (price, nextUpdateTimestamp). Price is guaranteed not to change until nextUpdateTimestamp.
    */ 
    function getSubmissionPrice(uint calldataSize) external view returns (uint, uint) {
        return (1, 1);
     }

    /** 
     * @notice Return the price, in wei, of extending the lifetime of userTxHash by an additional lifetime period. Revert if userTxHash doesn't exist.
     * @param userTxHash unique ticket identifier
     * @return (price, nextUpdateTimestamp). Price is guaranteed not to change until nextUpdateTimestamp.
    */
    function getKeepalivePrice(bytes32 userTxHash) external view returns(uint, uint) {
        return (1, 1);
    }

    /** 
    @notice Deposits callvalue into the sender's L2 account, then adds one lifetime period to the life of userTxHash.
    * If successful, emits LifetimeExtended event.
    * Revert if userTxHash does not exist, or if the timeout of userTxHash is already at least one lifetime period in the future, or if the sender has insufficient funds (after the deposit).
    * @param userTxHash unique ticket identifier
    * @return New timeout of userTxHash.
    */
    function keepalive(bytes32 userTxHash) external payable returns(uint) {
        require(msg.value > 0);
        require(ticketTimeout[userTxHash] > 0);
        ticketTimeout[userTxHash] += 1 days; 
        return ticketTimeout[userTxHash];
    }

    /**
    * @notice Return the beneficiary of userTxHash.
    * Revert if userTxHash doesn't exist.
    * @param userTxHash unique ticket identifier
    * @return address of beneficiary for ticket
    */
    function getBeneficiary(bytes32 userTxHash) external view returns (address) {
        require(ticketTimeout[userTxHash] > 0); 
        return ticketBeneficiary[userTxHash];
    }

    /** 
    * @notice Cancel userTxHash and refund its callvalue to its beneficiary.
    * Revert if userTxHash doesn't exist, or if called by anyone other than userTxHash's beneficiary.
    * @param userTxHash unique ticket identifier
    */
    function cancel(bytes32 userTxHash) external {
        require(ticketTimeout[userTxHash] > 0);
        delete ticketTimeout[userTxHash];
        delete ticketBeneficiary[userTxHash];
    }
}
