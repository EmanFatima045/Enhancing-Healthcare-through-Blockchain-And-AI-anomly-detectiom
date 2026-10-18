# HealerPlus implementation report

## Abstract

HealerPlus is an academic implementation that explores authorization, encrypted healthcare-record handling, auditable consent state, anomaly analysis, simulated connected-device telemetry, and Solidity access controls. The project deliberately separates working capabilities from demonstrations and unavailable integrations.

## Delivered implementation

The active React interface is preserved and integrated with FastAPI. Patient accounts, revocable sessions and appointment requests persist across restarts. Staff identities require administrator creation and approval. Medical record endpoints accept only client-encrypted envelopes and enforce ownership or confirmed consent. Security, telemetry and federated endpoints require verified roles appropriate to the resource.

SQLAlchemy supports SQLite development and PostgreSQL deployment. Alembic supplies the schema migration, while a narrow startup compatibility path upgrades the original SQLite users table. Atomic database transactions persist audit events alongside business changes. Chain intents and their outbox state are durable and never represented as submitted when signing infrastructure is absent.

Four Solidity 0.8.20 contracts compile reproducibly through the pinned npm toolchain. The deployment script deploys in dependency order and reports only real RPC receipts. No contract was deployed during local acceptance because an RPC endpoint and signer were not supplied.

## Evaluation

Automated API acceptance tests cover registration, login, authenticated telemetry, durable appointments, encrypted record upload/retrieval, logout revocation, staff approval, and immediate stored-role enforcement. The React production build and Solidity compilation complete successfully.

The available datasets contain only 40 IDS and 30 IoMT rows. They support classroom demonstration but not credible accuracy, generalization, clinical-safety or privacy claims. Federated training is a labelled simulation with zero real institutions.

## Limitations and future work

IPFS pinning, patient-wallet signing, chain receipt projection, real IoMT ingestion, independent model evaluation, real federated nodes, secure aggregation, differential privacy, email recovery, production monitoring and regulatory validation remain future work. Until these are delivered and independently reviewed, HealerPlus must not be represented as HIPAA/GDPR compliant, production ready, clinically validated, or suitable for real patient information.
