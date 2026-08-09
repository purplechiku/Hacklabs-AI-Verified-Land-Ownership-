# AI-Verified Land Ownership

**Team: Momo Warriors** · HackLabs 2026

An end-to-end system for verifying and registering land ownership records, combining OCR/AI document extraction, a backend orchestration API, and an on-chain registry for tamper-proof ownership records.

---

## How it fits together

```
┌───────────┐      ┌───────────┐      ┌────────────────┐      ┌──────────────────┐
│  Frontend │ ───▶ │  Backend  │ ───▶ │  AI/ML Service  │      │  Blockchain       │
│           │      │           │ ───▶ │  (extraction)   │      │  Wrapper Service  │
│           │ ◀─── │           │ ◀─── └────────────────┘      │  ──▶ Smart        │
│           │      │           │ ───────────────────────────▶ │      Contract      │
└───────────┘      └───────────┘                              └──────────────────┘
```

- **Frontend** — the user-facing app. Uploads land documents, shows extraction results, and displays verified ownership records. Never talks to the AI/ML service or Blockchain directly — everything goes through the Backend.
- **Backend** — the orchestrator. Receives uploads from the Frontend, sends them to the AI/ML service for extraction/duplicate-checking, and (once verified) registers the record with the Blockchain module. This is the only module that talks to every other module.
- **AI/ML Service** — extracts structured fields (owner name, plot number, survey number, etc.) from uploaded land documents and flags duplicates.
- **Blockchain Module** — a Solidity smart contract + wrapper service that gives the Backend a simple REST interface (`POST /register`, `GET /ownership/{plot_number}`) without it ever needing to hold a wallet or private key.

---

## Repository structure

```
├── frontend/           # User-facing web app
├── backend/             # Orchestration API — talks to AI/ML + Blockchain
├── contracts/           # Solidity smart contract (LandRegistry.sol)
├── scripts/              # Hardhat deploy scripts
├── test/                  # Hardhat/Chai contract tests
├── wrapper-service/  # HTTP wrapper the Backend calls for blockchain reads/writes
├── docs_contracts_aiml.md  # AI/ML service API contract (for Backend integration)
├── hardhat.config.js
├── package.json
└── README.md            # this file
```

---

## Module 1 — Frontend

> Fill in with your actual stack (React / Vite / Next.js etc.) and exact scripts — the section below is a starting template.

### Responsibilities
- Upload land ownership documents (PDF/image) for verification
- Display AI-extracted fields (owner name, plot number, survey number, address, area, registration date) with the returned confidence score
- Surface duplicate/partial-match warnings returned by the Backend
- Show verified, on-chain ownership records looked up by plot number

### Setup
```bash
cd frontend
npm install
npm run dev
```

### Environment variables
| Variable | Purpose |
|---|---|
| `VITE_BACKEND_URL` / `REACT_APP_BACKEND_URL` | Base URL of the Backend API (never call AI/ML or Blockchain directly) |

---

## Module 2 — Backend

> Fill in with your actual stack (Node/Express, FastAPI, etc.) and exact scripts — the integration contracts below are what's already agreed with the other modules.

### Responsibilities
- Receives document uploads from the Frontend
- Calls the **AI/ML service** to extract fields and check for duplicates
- Applies verification rules (e.g. treat `confidence_score < 0.5` as "needs manual review"; block or flag on `duplicate_flag`)
- Calls the **Blockchain wrapper service** to register verified ownership on-chain, and to look up existing records

### Integration — AI/ML Service
```
POST {AIML_SERVICE_URL}/extract     (multipart/form-data, field: file — PDF/PNG/JPG/JPEG/TIF/TIFF/BMP/WEBP, max 20MB)
GET  {AIML_SERVICE_URL}/health
```
Key response fields: `owner_name`, `plot_number`, `survey_number`, `address`, `area_sqft`, `registration_date`, `confidence_score` (0.0–1.0), `duplicate_flag`, `duplicate_matches[]`. Any extracted field may be `null` — a partial extraction with a low confidence score still returns `200 OK`. Full contract: [`docs_contracts_aiml.md`](./docs_contracts_aiml.md).

### Integration — Blockchain Wrapper Service
```
POST {BLOCKCHAIN_SERVICE_URL}/register
GET  {BLOCKCHAIN_SERVICE_URL}/ownership/{plot_number}
```
Full contract: see [Module 3 — Blockchain](#module-3--blockchain) below.

### Setup
```bash
cd backend
npm install
npm run dev
```

### Environment variables
| Variable | Purpose |
|---|---|
| `AIML_SERVICE_URL` | Base URL of the AI/ML extraction service |
| `BLOCKCHAIN_SERVICE_URL` | Base URL of the Blockchain wrapper service (e.g. `http://localhost:4001`) |

---

## Module 3 — Blockchain

A Solidity smart contract, a Hardhat project to compile/test/deploy it, and an HTTP wrapper service that the Backend calls — Backend never needs a wallet or private key.

### Deployed contract (Sepolia)
| | |
|---|---|
| **Network** | Ethereum Sepolia (testnet) |
| **Contract address** | `0xCd39Cf55679024b1Cb3252Ab19B964F327F26c08` |
| **Block explorer** | https://sepolia.etherscan.io/address/0xCd39Cf55679024b1Cb3252Ab19B964F327F26c08 |
| **Wrapper service** | `http://localhost:4001` (must be running locally) |

Verified end-to-end: `POST /register` submits and confirms a real Sepolia transaction, `GET /ownership/:plotNumber` reads it back, duplicate `plot_number` is rejected with `409`, and gas cost is ~141k per registration.

### Setup
```bash
# from repo root
npm install

# wrapper service
cd wrapper-service && npm install && cd ..

# configure env
cp .env.example .env
cp wrapper-service/.env.example wrapper-service/.env
```
Fill in `.env` (root):
- `SEPOLIA_RPC_URL` — e.g. `https://ethereum-sepolia-rpc.publicnode.com` (the official `rpc.sepolia.org` is dead)
- `PRIVATE_KEY` — a **throwaway testnet wallet** key, with the `0x` prefix. Fund it via https://sepolia-faucet.pk910.de/ if the usual faucets require a mainnet balance.

Fill in `wrapper-service/.env`:
- `RPC_URL` — same value as `SEPOLIA_RPC_URL` (note the different variable name)
- `PRIVATE_KEY` — same funded wallet key, with `0x` prefix

```bash
# compile + test
npx hardhat compile
npx hardhat test

# deploy (writes ABI/address into wrapper-service automatically)
npm run deploy:sepolia   # or npm run deploy:amoy for Polygon Amoy

# run the wrapper service
cd wrapper-service && npm start   # health check: http://localhost:4001/health
```

### API — what the Backend calls
**`POST /register`**
```
body:    { owner_name, plot_number, doc_hash, ipfs_hash }
returns: { tx_hash, block_number, status: "confirmed|pending" }
```
Returns `202` immediately with a pending status and confirms in the background; returns `409` if `plot_number` is already registered.

**`GET /ownership/:plotNumber`**
```
returns: { owner_name, doc_hash, ipfs_hash, registered_at, tx_hash, status }
```
Returns `404` if the plot isn't registered.

**`GET /health`** — `{ status: "ok" }`

### On-chain contract functions
```solidity
function registerOwnership(string plotNumber, string ownerName, bytes32 docHash, string ipfsHash) public returns (bool);
function getOwnership(string plotNumber) public view returns (string ownerName, bytes32 docHash, string ipfsHash, uint256 registeredAt);
function verifyDocHash(string plotNumber, bytes32 docHash) public view returns (bool matches);
function transferOwnership(string plotNumber, string newOwnerName) public returns (bool);
function isRegistered(string plotNumber) public view returns (bool);
```
`registerOwnership` reverts if the plot is already registered — ownership can only change via `transferOwnership`. Both `OwnershipRegistered` and `OwnershipTransferred` events are emitted for full history replay.

### Quick manual test
```bash
curl -X POST http://localhost:4001/register \
  -H "Content-Type: application/json" \
  -d '{"owner_name":"Alice","plot_number":"PLOT-001","doc_hash":"sample-doc-content","ipfs_hash":"ipfs://Qm123"}'

curl http://localhost:4001/ownership/PLOT-001
```

### Notes for the team
The wrapper service currently only runs at `http://localhost:4001` on the Blockchain owner's machine. If Backend runs elsewhere, either run this same wrapper-service code pointed at the Sepolia contract above, or deploy it to a shared public host (Render/Railway/Fly.io) before final integration.

---

## Team — Momo Warriors

| Module | Owner |
|---|---|
| Frontend | — |
| Backend | — |
| AI/ML | Person B |
| Blockchain | Person C |

Built for HackLabs 2026.
