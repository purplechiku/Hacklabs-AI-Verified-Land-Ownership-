const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  console.log(`Deploying LandRegistry to network: ${hre.network.name} ...`);

  const LandRegistry = await hre.ethers.getContractFactory("LandRegistry");
  const contract = await LandRegistry.deploy();
  await contract.waitForDeployment();

  const address = await contract.getAddress();
  console.log("LandRegistry deployed to:", address);

  // Export address + ABI so the wrapper-service can pick them up without
  // any manual copy/paste — run this script, then just start the service.
  const artifact = await hre.artifacts.readArtifact("LandRegistry");
  const outDir = path.join(__dirname, "..", "wrapper-service", "src", "contract-data");
  fs.mkdirSync(outDir, { recursive: true });

  fs.writeFileSync(
    path.join(outDir, "LandRegistry.address.json"),
    JSON.stringify({ address, network: hre.network.name }, null, 2)
  );
  fs.writeFileSync(
    path.join(outDir, "LandRegistry.abi.json"),
    JSON.stringify(artifact.abi, null, 2)
  );

  console.log("Address + ABI written to wrapper-service/src/contract-data/");
  console.log("\nNext step: set CONTRACT_ADDRESS in wrapper-service/.env (or leave blank —");
  console.log("the wrapper service will auto-read the address file written above).");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
