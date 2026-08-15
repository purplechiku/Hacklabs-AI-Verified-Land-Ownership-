const express = require("express");
const { ethers } = require("ethers");
const router = express.Router();
const { getContract } = require("../contract");
const { upsertRegistration } = require("../db");

// POST /register
// body: { owner_name, plot_number, doc_hash, ipfs_hash }
// returns: { tx_hash, block_number, status: "confirmed|pending" }
//
// Matches the Wrapper Service Contract in the module SRS exactly — this is
// the endpoint the Backend's {BLOCKCHAIN_SERVICE_URL}/register call hits.
router.post("/register", async (req, res) => {
  try {
    const { owner_name, plot_number, doc_hash, ipfs_hash } = req.body || {};

    if (!owner_name || !plot_number || !doc_hash ) {
      return res.status(400).json({
        error: "owner_name, plot_number, and doc_hash are all required"
      });
    }

    const { landRegistry } = getContract();

    const alreadyRegistered = await landRegistry.isRegistered(plot_number);
    if (alreadyRegistered) {
      return res.status(409).json({
        error: `plot_number "${plot_number}" is already registered`
      });
    }

    // doc_hash can arrive as a 0x-prefixed bytes32 hex string (preferred) or
    // as a plain string, in which case we hash it ourselves.
    const docHashBytes32 = /^0x[0-9a-fA-F]{64}$/.test(doc_hash)
      ? doc_hash
      : ethers.keccak256(ethers.toUtf8Bytes(doc_hash));

    const tx = await landRegistry.registerOwnership(
      plot_number,
      owner_name,
      docHashBytes32,
      ipfs_hash
    );

    upsertRegistration({
      plotNumber: plot_number,
      ownerName: owner_name,
      docHash: docHashBytes32,
      ipfsHash: ipfs_hash,
      txHash: tx.hash,
      blockNumber: null,
      status: "pending"
    });

    // Respond immediately with "pending" — Backend can poll GET /ownership/:plotNumber
    // or the Backend's own status endpoint to see when it flips to "confirmed".
    res.status(202).json({ tx_hash: tx.hash, block_number: null, status: "pending" });

    // Confirm in the background and update the cache once mined.
    tx.wait()
      .then((receipt) => {
        upsertRegistration({
          plotNumber: plot_number,
          ownerName: owner_name,
          docHash: docHashBytes32,
          ipfsHash: ipfs_hash,
          txHash: tx.hash,
          blockNumber: receipt.blockNumber,
          status: "confirmed"
        });
      })
      .catch((err) => {
        console.error(`Transaction ${tx.hash} failed to confirm:`, err.message);
        upsertRegistration({
          plotNumber: plot_number,
          ownerName: owner_name,
          docHash: docHashBytes32,
          ipfsHash: ipfs_hash,
          txHash: tx.hash,
          blockNumber: null,
          status: "failed"
        });
      });
  } catch (err) {
    console.error("POST /register error:", err);
    if (err.reason) {
      return res.status(400).json({ error: err.reason });
    }
    res.status(500).json({ error: "Internal error while registering ownership" });
  }
});

module.exports = router;
