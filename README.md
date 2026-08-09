# LandRegistry — Blockchain Module

HackLabs 2026 · AI-Verified Land Ownership · **Module: BLOCKCHAIN** · Owner: Person C

This is the complete Blockchain module: a Solidity smart contract, a Hardhat
project to compile/test/deploy it, and a small HTTP wrapper service that the
**Backend** module calls — Backend never needs a wallet or private key.

Matches the module SRS exactly:
- Smart Contract Interface → `contracts/LandRegistry.sol`
- Wrapper Service Contract (`POST /register`, `GET /ownership/{plot_number}`) → `wrapper-service/`

---

## Folder structure

```
blockchain-module/
├── contracts/
│   └── LandRegistry.sol          # the smart contract
├── scripts/
│   └── deploy.js                 # deploys + writes ABI/address for the wrapper service
├── test/
│   └── LandRegistry.test.js      # Hardhat/Chai test suite
├── hardhat.config.js
├── package.json                  # root deps: hardhat, toolbox, dotenv
├── .env.example                  # copy -> .env (RPC URL + private key for deploy)
├── .gitignore
│
├── wrapper-service/               # the HTTP service Backend calls
│   ├── src/
│   │   ├── index.js               # Express app entrypoint
│   │   ├── config.js              # env var loading
│   │   ├── contract.js            # ethers.js contract connection
│   │   ├── db.js                  # SQLite cache (better-sqlite3)
│   │   ├── contract-data/         # auto-filled by deploy.js (ABI + address)
│   │   └── routes/
│   │       ├── register.js        # POST /register
│   │       └── ownership.js       # GET /ownership/:plotNumber
│   ├── db/
│   │   └── schema.sql             # SQLite schema (see below)
│   ├── data/                      # SQLite .db file lives here (gitignored)
│   ├── package.json                # wrapper deps: express, ethers, better-sqlite3
│   └── .env.example                # copy -> .env (port, RPC URL, private key)
│
└── README.md                      # this file
```

---

## 1. Deployed Contract (Sepolia)

| | |
|---|---|
| **Network** | Ethereum Sepolia (testnet) |
| **Contract Address** | `0xCd39Cf55679024b1Cb3252Ab19B964F327F26c08` |
| **Block Explorer** | https://sepolia.etherscan.io/address/0xCd39Cf55679024b1Cb3252Ab19B964F327F26c08 |
| **Wrapper Service** | `http://localhost:4001` *(must be running locally — see Setup below)* |

Verified end-to-end against this deployment:
- ✅ `POST /register` — submits a real transaction, confirmed on Sepolia
- ✅ `GET /ownership/:plotNumber` — reads back the confirmed record
- ✅ Duplicate `plot_number` correctly rejected with `409 Conflict`
- ✅ Gas cost per registration: ~141k gas (reasonable for a testnet demo)

---

## 2. Setup

### a) Install dependencies

```bash
# from blockchain-module/
npm install

# from blockchain-module/wrapper-service/
cd wrapper-service && npm install && cd ..
```

### b) Configure environment

```bash
cp .env.example .env
cp wrapper-service/.env.example wrapper-service/.env
```

Fill in `.env` (root) with:
- `SEPOLIA_RPC_URL` — a Sepolia testnet RPC URL. `https://rpc.sepolia.org` is
  **dead** (404s as of this project) — use
  `https://ethereum-sepolia-rpc.publicnode.com` instead (free, no signup), or
  get a free Alchemy/Infura endpoint if you want something more reliable long-term.
- `PRIVATE_KEY` — a **throwaway testnet wallet's** private key, **with the
  `0x` prefix** (MetaMask exports it without one — add it yourself). Fund the
  wallet with free Sepolia ETH from a faucet — the official ones (Alchemy,
  QuickNode) often require an existing mainnet ETH balance to prevent abuse;
  if you don't have that, use a mining-based faucet instead:
  https://sepolia-faucet.pk910.de/ (no requirements, just takes a couple minutes).

Fill in `wrapper-service/.env` with:
- `RPC_URL` — same value as `SEPOLIA_RPC_URL` above (note the **different
  variable name** — this file uses `RPC_URL`, not `SEPOLIA_RPC_URL`).
- `PRIVATE_KEY` — same funded wallet's key, with `0x` prefix. The contract has
  no access control in this hackathon version, so any funded wallet can call it.

### c) Compile + test the contract

```bash
npx hardhat compile
npx hardhat test
```

> The contract has already been syntax/compile-verified with `solc` directly
> during development — `hardhat compile` just needs to download the solc
> binary once, which requires normal internet access.

### d) Deploy to testnet

```bash
npm run deploy:sepolia
# or: npm run deploy:amoy (if you'd rather use Polygon Amoy)
```

This deploys the contract **and automatically writes**
`wrapper-service/src/contract-data/LandRegistry.address.json` and
`LandRegistry.abi.json` — no manual copy-pasting needed.

### e) Start the wrapper service

```bash
cd wrapper-service
npm start
# Health check: http://localhost:4001/health
```

---

## 3. API — what Backend calls

### `POST /register`

```
body:    { owner_name, plot_number, doc_hash, ipfs_hash }
returns: { tx_hash, block_number, status: "confirmed|pending" }
```

- `doc_hash` can be sent as a `0x`-prefixed 32-byte hex string, or as a plain
  string (the service will hash it with keccak256 for you).
- Returns **202 Pending** immediately with the tx hash; the service confirms
  in the background and updates its local cache to `"confirmed"` once mined.
- Returns **409 Conflict** if `plot_number` is already registered (matches
  the contract's own duplicate-prevention rule).

### `GET /ownership/:plotNumber`

```
returns: { owner_name, doc_hash, ipfs_hash, registered_at }
```

- Returns **404** if the plot isn't registered.
- Also includes `tx_hash` and `status` (from the local cache) as bonus fields
  — harmless if Backend ignores them, useful if it doesn't want a second call
  just to check confirmation status.

### `GET /health`

Simple liveness check — `{ status: "ok" }`.

---

## 4. Database schema (local cache — NOT the source of truth)

The blockchain itself is the source of truth. This SQLite table exists so the
wrapper service can serve fast reads and track pending→confirmed status
without hitting the chain on every request. If wiped, it can be rebuilt by
replaying contract events — nothing is permanently lost.

```sql
CREATE TABLE IF NOT EXISTS registrations (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  plot_number   TEXT    NOT NULL UNIQUE,
  owner_name    TEXT    NOT NULL,
  doc_hash      TEXT    NOT NULL,
  ipfs_hash     TEXT    NOT NULL,
  tx_hash       TEXT    NOT NULL,
  block_number  INTEGER,
  status        TEXT    NOT NULL DEFAULT 'pending',  -- pending | confirmed | failed
  created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
  updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

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
```

Full file: `wrapper-service/db/schema.sql` (applied automatically on startup).

---

## 5. Smart contract functions (on-chain)

```solidity
function registerOwnership(string plotNumber, string ownerName, bytes32 docHash, string ipfsHash) public returns (bool);
function getOwnership(string plotNumber) public view returns (string ownerName, bytes32 docHash, string ipfsHash, uint256 registeredAt);
function verifyDocHash(string plotNumber, bytes32 docHash) public view returns (bool matches);
function transferOwnership(string plotNumber, string newOwnerName) public returns (bool);
function isRegistered(string plotNumber) public view returns (bool);
```

- `registerOwnership` reverts with `"LandRegistry: plot already registered"`
  if the plot number already exists — ownership can only change via the
  explicit `transferOwnership`, never by silently overwriting.
- Both `OwnershipRegistered` and `OwnershipTransferred` events are emitted,
  so the wrapper service (or anyone) can rebuild history by replaying logs.

---

## 6. Quick manual test (curl)

```bash
# Register a plot
curl -X POST http://localhost:4001/register \
  -H "Content-Type: application/json" \
  -d '{"owner_name":"Alice","plot_number":"PLOT-001","doc_hash":"sample-doc-content","ipfs_hash":"ipfs://Qm123"}'

# Look it up
curl http://localhost:4001/ownership/PLOT-001
```

---

## 7. Integration notes for the team

- **Backend** should treat this service exactly like the "Internal Contract
  — calls TO Blockchain service" block in the SRS: `POST {BLOCKCHAIN_SERVICE_URL}/register`
  and reads via `GET {BLOCKCHAIN_SERVICE_URL}/ownership/{plot_number}`.
- Set `BLOCKCHAIN_SERVICE_URL=http://localhost:4001` (or wherever this is
  deployed) in the Backend's own `.env`.
- Frontend and AI/ML never call this service directly — only Backend does.
- If you redeploy the contract (new address), just re-run `npm run deploy:sepolia`
  — it overwrites the address/ABI files the wrapper service reads, no other
  changes needed.
- **Important for the team:** the wrapper service is currently only reachable
  at `http://localhost:4001` — it only works while it's running on the
  Blockchain owner's machine. If Backend is on a different machine, either
  (a) they run this same wrapper-service code themselves, pointed at the same
  Sepolia contract address above, or (b) the wrapper service gets deployed to
  a public host (Render/Railway/Fly.io) so everyone can hit one shared URL.
  Decide this with Backend before final integration.
