const express = require("express");
const router = express.Router();
const { getContract } = require("../contract");
const { getRegistrationByPlot } = require("../db");

// GET /ownership/:plotNumber
// returns: { owner_name, doc_hash, ipfs_hash, registered_at }
//
// Matches the Wrapper Service Contract in the module SRS exactly — this is
// the endpoint the Backend's {BLOCKCHAIN_SERVICE_URL}/ownership/{plot_number}
// call hits.
router.get("/ownership/:plotNumber", async (req, res) => {
  try {
    const { plotNumber } = req.params;
    const { landRegistry } = getContract();

    const isRegistered = await landRegistry.isRegistered(plotNumber);
    if (!isRegistered) {
      return res.status(404).json({ error: `plot_number "${plotNumber}" is not registered` });
    }

    const [ownerName, docHash, ipfsHash, registeredAt] = await landRegistry.getOwnership(plotNumber);
    const cached = getRegistrationByPlot(plotNumber);

    res.json({
      owner_name: ownerName,
      doc_hash: docHash,
      ipfs_hash: ipfsHash,
      registered_at: new Date(Number(registeredAt) * 1000).toISOString(),
      // extra fields — harmless for consumers that only read the 4 documented fields,
      // useful for the Backend if it wants tx status without a second call.
      tx_hash: cached ? cached.tx_hash : null,
      status: cached ? cached.status : "confirmed"
    });
  } catch (err) {
    console.error("GET /ownership/:plotNumber error:", err);
    res.status(500).json({ error: "Internal error while fetching ownership record" });
  }
});

module.exports = router;
