const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("LandRegistry", function () {
  let landRegistry;

  beforeEach(async function () {
    const LandRegistry = await ethers.getContractFactory("LandRegistry");
    landRegistry = await LandRegistry.deploy();
    await landRegistry.waitForDeployment();
  });

  it("registers a new ownership record and emits an event", async function () {
    const docHash = ethers.keccak256(ethers.toUtf8Bytes("sample-doc"));

    await expect(
      landRegistry.registerOwnership("PLOT-001", "Alice", docHash, "ipfs://Qm123")
    ).to.emit(landRegistry, "OwnershipRegistered");

    const record = await landRegistry.getOwnership("PLOT-001");
    expect(record.ownerName).to.equal("Alice");
    expect(record.docHash).to.equal(docHash);
    expect(record.ipfsHash).to.equal("ipfs://Qm123");
  });

  it("rejects a duplicate plot registration", async function () {
    const docHash = ethers.keccak256(ethers.toUtf8Bytes("sample-doc"));
    await landRegistry.registerOwnership("PLOT-001", "Alice", docHash, "ipfs://Qm123");

    await expect(
      landRegistry.registerOwnership("PLOT-001", "Bob", docHash, "ipfs://Qm456")
    ).to.be.revertedWith("LandRegistry: plot already registered");
  });

  it("verifies a matching document hash and rejects a mismatched one", async function () {
    const docHash = ethers.keccak256(ethers.toUtf8Bytes("sample-doc"));
    const wrongHash = ethers.keccak256(ethers.toUtf8Bytes("other-doc"));
    await landRegistry.registerOwnership("PLOT-001", "Alice", docHash, "ipfs://Qm123");

    expect(await landRegistry.verifyDocHash("PLOT-001", docHash)).to.equal(true);
    expect(await landRegistry.verifyDocHash("PLOT-001", wrongHash)).to.equal(false);
  });

  it("reverts getOwnership() for an unregistered plot", async function () {
    await expect(landRegistry.getOwnership("PLOT-999")).to.be.revertedWith(
      "LandRegistry: plot not registered"
    );
  });

  it("reports isRegistered() correctly", async function () {
    expect(await landRegistry.isRegistered("PLOT-001")).to.equal(false);
    const docHash = ethers.keccak256(ethers.toUtf8Bytes("sample-doc"));
    await landRegistry.registerOwnership("PLOT-001", "Alice", docHash, "ipfs://Qm123");
    expect(await landRegistry.isRegistered("PLOT-001")).to.equal(true);
  });

  it("allows an explicit ownership transfer and emits an event", async function () {
    const docHash = ethers.keccak256(ethers.toUtf8Bytes("sample-doc"));
    await landRegistry.registerOwnership("PLOT-001", "Alice", docHash, "ipfs://Qm123");

    await expect(landRegistry.transferOwnership("PLOT-001", "Bob")).to.emit(
      landRegistry,
      "OwnershipTransferred"
    );

    const record = await landRegistry.getOwnership("PLOT-001");
    expect(record.ownerName).to.equal("Bob");
  });

  it("rejects transferOwnership() for an unregistered plot", async function () {
    await expect(
      landRegistry.transferOwnership("PLOT-999", "Bob")
    ).to.be.revertedWith("LandRegistry: plot not registered");
  });
});
