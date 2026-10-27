# HealerPlus operations runbook

HealerPlus is deployable as three runtime processes: the Nginx frontend, the FastAPI API, and the durable outbox worker. PostgreSQL is the production database target.

## Verification

From the repository root, run `bash scripts/verify_local.sh`. The script runs available syntax, whitespace, frontend, backend, and Solidity gates and explicitly reports skipped gates when local dependencies are absent. Use `bash scripts/verify_local.sh --strict` to fail if any required toolchain is missing; CI remains the authoritative full-toolchain check.

## Local production-like stack

1. Set `POSTGRES_PASSWORD`, `HEALER_SECRET_KEY`, and `HEALER_TRUSTED_HOSTS` in the environment.
2. Run `docker compose up --build`.
3. Check `http://localhost/api/v1/health/ready` before accepting traffic.
4. Confirm worker logs show `HealerPlus outbox worker started`.

The readiness endpoint confirms database and outbox storage availability and reports pending/failed queue counts. Blockchain is reported separately because local deployments may intentionally run without an RPC node.

To run the complete local integration lab, use `docker compose --profile integrations --profile test up --build`. This adds a Hardhat JSON-RPC node on port 8545, Mailpit SMTP/UI on 1025/8025, Kubo IPFS on 5001/8080, Prometheus on 9090, and a disposable pytest container. Set `HEALER_NOTIFICATION_SINK=smtp`, `HEALER_SMTP_HOST=smtp`, `HEALER_SMTP_PORT=1025`, `HEALER_SMTP_STARTTLS=false`, `HEALER_SMTP_FROM=no-reply@healerplus.local`, and `HEALER_CARE_TEAM_EMAIL=care@healerplus.local` to exercise local email delivery. Set `HEALER_CIPHERTEXT_STORAGE=kubo` and `KUBO_API_URL=http://ipfs:5001` to exercise local IPFS storage. The local chain still requires `npm run deploy:local` in `blockchain/` to generate contract addresses before blockchain API flows can be exercised.

Hospital administrators and security auditors can inspect the redacted queue view at `/api/v1/operations/outbox`. It exposes counts and recent topic/status metadata only; job payloads and secrets remain server-side.

## Blockchain activation

Configure `ETH_RPC_URL`, `CHAIN_ID`, all four contract addresses, and scoped signer credentials only on the API/worker services. Never put private signer keys in frontend variables or source control. Start the worker after the contracts and generated ABIs/addresses are available.

Patient consent remains patient-wallet-signed. Backend signers are limited to explicitly scoped staff registration, record anchoring, and incident attestation jobs.

## Production checklist

- Use PostgreSQL with encrypted storage and automated backups.
- Configure TLS at the hosting edge and set the real domain in `HEALER_TRUSTED_HOSTS` and `HEALER_CORS_ORIGINS`.
- Rotate `HEALER_SECRET_KEY` only with a planned session invalidation event.
- Configure a reviewed notification provider instead of the local notification sink.
- For SMTP delivery, set `HEALER_NOTIFICATION_SINK=smtp`, SMTP credentials, `HEALER_SMTP_FROM`, and `HEALER_CARE_TEAM_EMAIL` on the API/worker services. The worker uses TLS and authenticates before sending.
- Configure reviewed encrypted object storage before uploading large ciphertext envelopes.
- Monitor API readiness, worker retry/failed-job counts, database capacity, and blockchain confirmation lag.
- Review audit events and emergency-access events regularly.
- Do not use real patient data until security, privacy, retention, clinical-safety, and jurisdictional reviews are complete.

## Recovery

Restore PostgreSQL and encrypted storage from coordinated backups. Browser-held private record keys and encrypted key backups are separate from the database; losing both makes the corresponding records unrecoverable. Re-run Alembic migrations before starting the API after a restore.
