# HealerPlus architecture

## Current system

The application is a modular monolith: the existing React/Vite SPA calls one FastAPI application. SQLAlchemy persists identity, sessions, login attempts, appointments, encrypted record envelopes and versions, consent projections, incidents, audit events, telemetry events, simulated federated rounds, chain transaction state, and outbox jobs. SQLite is supported locally and PostgreSQL 16 is the Docker target.

```text
React SPA -> FastAPI authorization boundary -> SQLAlchemy -> SQLite/PostgreSQL
                         |                         |
                         |                         +-> durable chain intents/outbox
                         +-> local IDS model
                         +-> simulated IoMT/federated demonstrations
                         +-> optional read-only Ethereum JSON-RPC verification
```

The bearer token contains only the user subject and session identifier. Role, verification, account status, expiry and revocation are checked from current database state for every protected request. Public registration is patient-only; trusted administrators create and approve staff.

## Encrypted records

The API accepts only client-encrypted base64 ciphertext, a ciphertext hash, and a wrapped-key envelope. It verifies the hash and stores ciphertext separately from record metadata. The server does not claim to decrypt the record. IPFS is not connected, so no CID is returned. A production design would replace database ciphertext storage with an approved encrypted object store or real IPFS pinning without changing ownership checks.

## Blockchain boundary

Solidity 0.8.20 contracts compile and deploy through the dedicated Hardhat project in `blockchain`. The supported demo is chain ID 31337 on local port 8545. Deployment exports generated ABIs and addresses to each consumer. Patient consent becomes authoritative only after a patient-wallet transaction is decoded, its successful receipt/event is verified, and the current contract state is rechecked. Separately scoped backend signers are limited to explicit outbox topics; they never sign patient consent.

## Demonstration boundaries

- IDS: a development classifier trained on 40 checked-in examples; no held-out benchmark claim.
- IoMT: generated or client-submitted demonstration values; no medical device connection.
- Federated learning: in-process FedAvg simulation; zero participating hospitals and no differential-privacy guarantee.
- Attack simulation: disabled unless `HEALER_DEMO_MODE=true`, then restricted to verified auditors/admins.

## Deployment controls still required

Production use would additionally require an approved identity provider or hardened cookie sessions, CSRF/CSP controls, key management, encrypted backups, clinical validation, monitoring, incident response, data-retention rules, penetration testing, and jurisdiction-specific regulatory review.
