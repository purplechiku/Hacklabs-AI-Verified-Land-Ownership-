// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title LandRegistry
/// @notice Stores verified land ownership records immutably. Once a plot is
///         registered it cannot be silently overwritten — ownership can only
///         change via the explicit transferOwnership() function.
contract LandRegistry {
    struct Record {
        string ownerName;
        bytes32 docHash;
        string ipfsHash;
        uint256 registeredAt;
        bool exists;
    }

    mapping(string => Record) private records;

    event OwnershipRegistered(
        string indexed plotNumber,
        string ownerName,
        bytes32 docHash,
        string ipfsHash,
        uint256 registeredAt
    );

    event OwnershipTransferred(
        string indexed plotNumber,
        string previousOwner,
        string newOwner,
        uint256 transferredAt
    );

    modifier plotNotRegistered(string memory plotNumber) {
        require(!records[plotNumber].exists, "LandRegistry: plot already registered");
        _;
    }

    modifier plotIsRegistered(string memory plotNumber) {
        require(records[plotNumber].exists, "LandRegistry: plot not registered");
        _;
    }

    /// @notice Register a brand-new ownership record for a plot.
    /// @dev Reverts if the plot is already registered — use transferOwnership() instead.
    function registerOwnership(
        string memory plotNumber,
        string memory ownerName,
        bytes32 docHash,
        string memory ipfsHash
    ) public plotNotRegistered(plotNumber) returns (bool) {
        require(bytes(plotNumber).length > 0, "LandRegistry: plotNumber required");
        require(bytes(ownerName).length > 0, "LandRegistry: ownerName required");

        records[plotNumber] = Record({
            ownerName: ownerName,
            docHash: docHash,
            ipfsHash: ipfsHash,
            registeredAt: block.timestamp,
            exists: true
        });

        emit OwnershipRegistered(plotNumber, ownerName, docHash, ipfsHash, block.timestamp);
        return true;
    }

    /// @notice Read back the ownership record for a plot.
    function getOwnership(string memory plotNumber)
        public
        view
        plotIsRegistered(plotNumber)
        returns (
            string memory ownerName,
            bytes32 docHash,
            string memory ipfsHash,
            uint256 registeredAt
        )
    {
        Record memory r = records[plotNumber];
        return (r.ownerName, r.docHash, r.ipfsHash, r.registeredAt);
    }

    /// @notice Check whether a given document hash matches what's on record for a plot.
    function verifyDocHash(string memory plotNumber, bytes32 docHash)
        public
        view
        plotIsRegistered(plotNumber)
        returns (bool matches)
    {
        return records[plotNumber].docHash == docHash;
    }

    /// @notice Explicitly transfer ownership of an already-registered plot to a new owner.
    function transferOwnership(string memory plotNumber, string memory newOwnerName)
        public
        plotIsRegistered(plotNumber)
        returns (bool)
    {
        require(bytes(newOwnerName).length > 0, "LandRegistry: newOwnerName required");
        string memory previousOwner = records[plotNumber].ownerName;
        records[plotNumber].ownerName = newOwnerName;
        emit OwnershipTransferred(plotNumber, previousOwner, newOwnerName, block.timestamp);
        return true;
    }

    /// @notice Convenience check used by the wrapper service before attempting a write.
    function isRegistered(string memory plotNumber) public view returns (bool) {
        return records[plotNumber].exists;
    }
}
