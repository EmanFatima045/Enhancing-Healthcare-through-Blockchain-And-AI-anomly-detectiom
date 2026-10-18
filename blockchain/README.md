# Local blockchain demo

This Hardhat project is intentionally local-only. It uses chain ID `31337` and RPC `http://127.0.0.1:8545`.

```powershell
npm install
npm test
npm run node
# in a second terminal
npm run deploy:local
```

Deployment order is `HealerAuth`, `ConsentManager(auth)`, `MedicalAuditRegistry(auth, consent)`, then `BreakGlassEmergency(auth, audit)`. The deployer then grants the break-glass contract the narrow emergency-audit role. Deployment generates ABIs and `deployments/31337/addresses.json`, then exports the same generated files to `frontend/src/generated/contracts/31337` and `backend/app/generated/contracts/31337`; these files are outputs, not hand-maintained source.

Only opaque record/category/storage commitments, wallet addresses, envelope digests, roles, timestamps and action enums are public. Names, national identifiers, clinical text, summaries, emergency justification text, CIDs and cryptographic keys remain off chain. Transaction hashes and receipt metadata are naturally available from node receipts and should be indexed off chain; the contract does not fabricate them as data fields.

An emergency session is an auditable authorization signal, not a decryption key. This project deliberately has no emergency key escrow: the backend returns no emergency key envelope. Consequently break-glass cannot decrypt a record unless a separately governed escrow/recovery service is later implemented. This avoids falsely claiming both exclusive patient key control and automatic emergency decryption.

Consent resolution uses an active category grant first. If it is absent, revoked, or expired, an active `ALL` grant applies. Expiry is exclusive (`block.timestamp < validUntil`). Read/write is checked independently, and practitioner verification/active status is rechecked every time.
