# HealerPlus healthcare security project

HealerPlus is a final-year-project implementation of a React healthcare portal backed by FastAPI, persistent authorization controls, encrypted-record envelopes, local anomaly-analysis demonstrations, and deployable Solidity contracts. The interface remains the existing React application in `frontend/src/App.tsx`.

## Capability status

| Capability | Status |
|---|---|
| Accounts, revocable sessions, roles, appointments, audits | Real; persisted with SQLAlchemy |
| Local database | SQLite is supported for development |
| Docker database | PostgreSQL 16 |
| Record storage | Real persistence of client-encrypted ciphertext and wrapped-key envelopes |
| Ciphertext storage | Durable database `LOCAL`; optional Kubo/Pinata upload reports a CID only after provider success |
| Solidity | Hardhat local deployment on chain 31337 with generated ABIs/manifests |
| Blockchain API | Live read-only RPC verification when configured; no server-side signer |
| Consent | Durable pending intent; not active until a genuine wallet transaction is confirmed |
| IDS | Local development model trained on the checked-in 40-row demonstration CSV |
| IoMT | Simulated; no clinical device is connected |
| Federated learning | Simulated; no hospital participates and no differential-privacy guarantee is claimed |

Do not enter real patient data. This repository is not a regulated clinical system, diagnostic tool, or emergency service.

## Supported versions

- Python 3.11
- Node.js 20, 22, or 24 (the checked environment uses Node 24)
- Solidity 0.8.20, pinned through the `solc` npm package
- PostgreSQL 16 for Docker; SQLite 3 for local development

## Local setup

1. Copy `.env.example` to `.env` and replace `HEALER_SECRET_KEY` with at least 32 random characters. There is no non-test fallback secret.
2. Install and migrate the backend:

   ```powershell
   python -m pip install -r backend/requirements.txt
   cd backend
   python -m alembic -c alembic.ini upgrade head
   cd ..
   ```

3. Create the first administrator. The command prompts without echoing the password:

   ```powershell
   python backend/manage.py create-admin --email admin@example.test --name "Local Administrator"
   ```

4. Start `start_backend.bat` and `start_frontend.bat`, or run:

   ```powershell
   python backend/run_backend.py
   cd frontend
   npm install
   npm run dev
   ```

The app is at `http://127.0.0.1:3000`; API documentation is at `http://127.0.0.1:8000/docs`.

Public signup can create only a verified Patient. A HospitalAdmin creates staff through `POST /api/v1/auth/staff`, then explicitly approves them through `POST /api/v1/auth/staff/{email}/approve`.

## Browser token handling

The current SPA keeps its short-lived bearer token in `sessionStorage`, so it is cleared when the browser session ends but remains readable to JavaScript. Logout revokes the server-side session. Production deployment should use a same-site, secure, HTTP-only cookie plus CSRF protection and a strict Content Security Policy; local/session storage should not be used for production healthcare sessions.

## Database and Docker

`DATABASE_URL` selects the database. SQLite is the local default. `docker-compose.yml` runs PostgreSQL and the API:

```powershell
$env:POSTGRES_PASSWORD = "choose-a-strong-password"
$env:HEALER_SECRET_KEY = "choose-at-least-32-random-characters"
docker compose up --build
```

Run Alembic migrations before upgrading a deployment. The application also performs a narrow compatibility upgrade for the repository's legacy SQLite `users` table.

## Encrypted record lifecycle

The browser creates one fresh AES-256-GCM key and fresh 12-byte nonce for every record version. The authenticated associated data is the canonical JSON encoding of `{format, record_id, record_version}`. Ciphertext includes the 128-bit GCM tag. The envelope digest is `sha256:` plus the lowercase SHA-256 hex digest of canonical UTF-8 JSON for the envelope excluding its `digest` member. Both browser and backend sort object keys and emit no insignificant JSON whitespace for this fixed schema.

Each recipient uses a real RSA-3072 OAEP/SHA-256 key pair. The public SPKI is registered with the backend; the private key is stored as a non-extractable WebCrypto key in that browser's IndexedDB. Initial setup downloads an AES-GCM encrypted PKCS#8 backup derived from a user passphrase with PBKDF2-SHA-256 (310,000 iterations). Recovery requires that file and passphrase. Losing both makes old records cryptographically unrecoverable: the server has no private key and an Ethereum wallet cannot substitute for it.

A patient decrypts their own wrapped data key locally. To share a record, the browser unwraps that data key locally and rewraps it to the selected verified doctor's current RSA public key, uploads the recipient-specific key envelope, then grants consent. A consent-authorized doctor receives only their envelope and decrypts locally. Missing private keys, invalid digest, invalid base64, RSA unwrap failure, and GCM authentication failure all stop without displaying plaintext. Revocation prevents future API delivery but cannot erase keys or plaintext that a recipient already downloaded. New record versions always rotate to a new AES key and require new recipient envelopes.

The complete ciphertext envelope and recipient key envelopes are durable off-chain data. `LOCAL` honestly means the database copy; `LOCAL_REMOTE_FAILED` means that copy survived a failed optional upload. Kubo and Pinata credentials are backend-only. Ciphertext is not assumed secret merely because an API route uses a JWT.

Emergency decryption is unavailable by default. It becomes available only when the explicitly documented institutional RSA escrow settings and per-record escrow envelope are present; otherwise the API persists and reports `UNAVAILABLE_NO_ESCROW` rather than inventing a key.

## Wallet transactions and receipt verification

The React client uses pinned Viem with MetaMask. Linking uses a single-use, expiring EIP-191 message containing the authenticated application account, application domain, wallet, nonce, and expected chain. The backend recovers the address before linking and rejects replay. Patient registration, consent grant, and consent revoke are submitted by that patient's MetaMask account; the backend never receives wallet secrets and never substitutes an administrator signer.

Submitted hashes are untrusted. The web3.py verifier checks RPC connectivity, `eth_chainId`, deployed bytecode, receipt success, confirmations, sender, destination, decoded function and arguments, and exactly one expected decoded event. Indexed logs use a chain/block-hash/transaction/log-index uniqueness boundary. Confirmed rows retain block hashes so a worker can detect chain resets and invalidate orphaned projections. Protected key delivery re-reads `resolveConsent` from the contract.

Backend writers use the idempotent outbox and an optional environment-only key with explicit `HEALER_SERVICE_SIGNER_SCOPES`; supported scopes are `STAFF_ADMIN` and `RECORD_ANCHOR`. They cannot sign patient consent. `python backend/manage.py process-outbox` processes pending work outside API handlers.

Emergency escrow is optional and explicit. When configured, patients include an institutional RSA recipient envelope on new records. After a doctor-signed, receipt-verified, currently active break-glass session, the backend escrow key unwraps and rewraps the data key to the doctor's registered RSA key. Delivery state is persisted. Detailed justification remains off chain while its commitment is emitted. Notifications are separate outbox jobs, and the default local sink records deterministic `DELIVERED` rows rather than treating a contract event as notification delivery. Without escrow, delivery remains `UNAVAILABLE_NO_ESCROW`.

## Contracts

```powershell
cd blockchain
npm install
npm test
```

The contracts store opaque identifiers and commitments only—never names, national IDs, diagnoses, summaries, emergency justification text, CIDs, or keys. Authorization enforces patient-only public registration, trusted staff assignment/verification/suspension, current practitioner status, category-before-`ALL` consent precedence, exclusive expiry boundaries, separate write permission, restricted audit writers, and a narrowly authorized break-glass logger that records the actual doctor.

Deployment requires a real JSON-RPC endpoint and funded development/testnet signer:

```powershell
npm run node
# second terminal
npm run deploy:local
```

The local node uses chain ID 31337 and RPC port 8545. The script deploys in dependency order, authorizes the BreakGlass contract in the audit registry, and exports generated ABIs plus a chain-specific address manifest to the blockchain, backend, and frontend trees. The funded accounts printed by Hardhat are throwaway local accounts only. Public-network deployment is deliberately unsupported.

## Demo mode and datasets

Set `HEALER_DEMO_MODE=true` only for a restricted local demonstration. This enables attack scenarios, abnormal IoMT modes, and simulated federated rounds for verified SecurityAuditor or HospitalAdmin accounts. Client-supplied feature values are never accepted as proof of authority.

The repository contains 40 IDS rows and 30 IoMT rows. The API intentionally reports IDS benchmark metrics as unevaluated because there is no adequate held-out evaluation set.

## Verification

```powershell
python -m pytest backend/tests -q
cd frontend; npm run build
cd ../blockchain; npm test
```

Offline detection experiments and the optional CICIoMT2024 placement procedure are documented in `docs/ML_EXPERIMENTS.md`. The checked-in 40-row CSV is a synthetic toy fixture; its measured report must not be presented as evidence of real-world generalization.
