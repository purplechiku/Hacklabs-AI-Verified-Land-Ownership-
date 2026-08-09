-- LandRegistry wrapper service — local cache DB
--
-- The blockchain is the source of truth for ownership records. This table
-- exists purely so the wrapper service can:
--   1. Serve fast reads without hitting the chain on every request.
--   2. Track transaction status (pending -> confirmed) for the Backend to poll.
--   3. Give the team a simple audit log of every registration attempt.
--
-- If this DB is ever wiped, nothing is lost — it can be rebuilt by replaying
-- OwnershipRegistered / OwnershipTransferred events from the contract.

CREATE TABLE IF NOT EXISTS registrations (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  plot_number   TEXT    NOT NULL UNIQUE,
  owner_name    TEXT    NOT NULL,
  doc_hash      TEXT    NOT NULL,          -- bytes32 hash, stored as hex string (0x...)
  ipfs_hash     TEXT    NOT NULL,
  tx_hash       TEXT    NOT NULL,
  block_number  INTEGER,                   -- NULL until the tx is mined
  status        TEXT    NOT NULL DEFAULT 'pending',  -- pending | confirmed | failed
  created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
  updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_registrations_plot_number ON registrations (plot_number);
CREATE INDEX IF NOT EXISTS idx_registrations_tx_hash      ON registrations (tx_hash);
CREATE INDEX IF NOT EXISTS idx_registrations_status        ON registrations (status);

-- Optional: raw transfer history, separate from the current-owner table above.
CREATE TABLE IF NOT EXISTS transfers (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  plot_number     TEXT    NOT NULL,
  previous_owner  TEXT    NOT NULL,
  new_owner       TEXT    NOT NULL,
  tx_hash         TEXT    NOT NULL,
  block_number    INTEGER,
  status          TEXT    NOT NULL DEFAULT 'pending',
  created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_transfers_plot_number ON transfers (plot_number);
