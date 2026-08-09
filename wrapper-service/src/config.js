require("dotenv").config();

module.exports = {
  port: process.env.PORT || 4001,
  rpcUrl: process.env.RPC_URL || "https://rpc-amoy.polygon.technology",
  privateKey: process.env.PRIVATE_KEY,
  // Optional override — if not set, the wrapper reads the address written by
  // `npm run deploy:amoy` (or deploy:sepolia / deploy:local) automatically.
  contractAddress: process.env.CONTRACT_ADDRESS || "",
  dbPath: process.env.DB_PATH || "./data/registry-cache.db"
};
