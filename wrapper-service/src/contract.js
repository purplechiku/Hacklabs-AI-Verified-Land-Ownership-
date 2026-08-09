const { ethers } = require("ethers");
const fs = require("fs");
const path = require("path");
const config = require("./config");

function loadAbi() {
  const abiPath = path.join(__dirname, "contract-data", "LandRegistry.abi.json");
  if (!fs.existsSync(abiPath)) {
    throw new Error(
      "LandRegistry ABI not found at wrapper-service/src/contract-data/LandRegistry.abi.json. " +
        "Run `npm run deploy:amoy` (or deploy:sepolia / deploy:local) from the project root first — " +
        "the deploy script writes the ABI here automatically."
    );
  }
  return JSON.parse(fs.readFileSync(abiPath, "utf-8"));
}

function loadAddress() {
  if (config.contractAddress) return config.contractAddress;

  const addrPath = path.join(__dirname, "contract-data", "LandRegistry.address.json");
  if (!fs.existsSync(addrPath)) {
    throw new Error(
      "No CONTRACT_ADDRESS set in .env and no deployed-address file found. " +
        "Either set CONTRACT_ADDRESS manually, or run the deploy script first."
    );
  }
  return JSON.parse(fs.readFileSync(addrPath, "utf-8")).address;
}

function createContract() {
  if (!config.privateKey) {
    throw new Error("PRIVATE_KEY is not set in wrapper-service/.env");
  }

  const provider = new ethers.JsonRpcProvider(config.rpcUrl);
  const wallet = new ethers.Wallet(config.privateKey, provider);
  const abi = loadAbi();
  const address = loadAddress();
  const landRegistry = new ethers.Contract(address, abi, wallet);

  return { landRegistry, provider, wallet, address };
}

let cached = null;

function getContract() {
  if (!cached) {
    cached = createContract();
  }
  return cached;
}

module.exports = { createContract, getContract };
