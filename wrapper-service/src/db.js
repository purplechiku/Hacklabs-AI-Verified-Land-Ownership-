const Database = require("better-sqlite3");
const fs = require("fs");
const path = require("path");
const config = require("./config");

const dbDir = path.dirname(config.dbPath);
fs.mkdirSync(dbDir, { recursive: true });

const db = new Database(config.dbPath);
db.pragma("journal_mode = WAL");

const schema = fs.readFileSync(path.join(__dirname, "..", "db", "schema.sql"), "utf-8");
db.exec(schema);

function upsertRegistration({ plotNumber, ownerName, docHash, ipfsHash, txHash, blockNumber, status }) {
  const stmt = db.prepare(`
    INSERT INTO registrations (plot_number, owner_name, doc_hash, ipfs_hash, tx_hash, block_number, status)
    VALUES (@plotNumber, @ownerName, @docHash, @ipfsHash, @txHash, @blockNumber, @status)
    ON CONFLICT(plot_number) DO UPDATE SET
      tx_hash      = excluded.tx_hash,
      block_number = excluded.block_number,
      status       = excluded.status,
      updated_at   = datetime('now')
  `);
  stmt.run({ plotNumber, ownerName, docHash, ipfsHash, txHash, blockNumber, status });
}

function getRegistrationByPlot(plotNumber) {
  return db.prepare("SELECT * FROM registrations WHERE plot_number = ?").get(plotNumber);
}

function insertTransfer({ plotNumber, previousOwner, newOwner, txHash, blockNumber, status }) {
  const stmt = db.prepare(`
    INSERT INTO transfers (plot_number, previous_owner, new_owner, tx_hash, block_number, status)
    VALUES (@plotNumber, @previousOwner, @newOwner, @txHash, @blockNumber, @status)
  `);
  stmt.run({ plotNumber, previousOwner, newOwner, txHash, blockNumber, status });
}

module.exports = { db, upsertRegistration, getRegistrationByPlot, insertTransfer };
