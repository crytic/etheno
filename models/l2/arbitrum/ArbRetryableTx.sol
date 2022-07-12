pragma solidity >=0.4.21 <0.9.0;

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
