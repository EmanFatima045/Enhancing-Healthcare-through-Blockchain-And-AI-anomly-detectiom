# Cyber-security analysis

## Implemented controls

| Risk | Implemented control | Residual limitation |
|---|---|---|
| Privilege escalation | Patient-only public signup; verified-admin staff workflow; database roles checked on every request | Initial admin is a local CLI trust bootstrap |
| Token theft/reuse | Explicit JWT algorithm, issuer, audience, expiry and JTI; persistent revocation on logout | SPA uses `sessionStorage`; production should use secure HTTP-only cookies and CSRF protection |
| Brute force | Persistent IP/email-hash attempt accounting and identical throttling before successful or failed login | Single-database limiter is appropriate for this monolith, not a global multi-region deployment |
| Proxy spoofing | Forwarded IP is ignored unless proxy trust is explicitly enabled and the direct peer is trusted | Proxy allow-list must match deployment topology |
| Horizontal record access | Ownership and confirmed-consent checks use authenticated database identities | Chain consent cannot become confirmed until real receipt verification exists |
| Sensitive logging | Audit metadata excludes record plaintext, passwords, keys and raw IP addresses | Operational log configuration still needs deployment review |
| Fake chain/storage proof | No synthetic CID, transaction hash, block or confirmation is returned | IPFS and signed transactions remain unavailable |

## Model evidence

The IDS CSV has 40 examples and the IoMT CSV has 30 examples. These are demonstration datasets, not adequate clinical or security benchmarks. Previous fixed claims such as 98.8% accuracy were not derived from a reproducible held-out evaluation and have been removed from the API. The current API reports `NOT_EVALUATED_ON_A_HELD_OUT_SET`.

Federated learning is simulated in one process. No real hospital, secure aggregation protocol, differential-privacy accountant, or privacy budget is connected; consequently the project makes no privacy guarantee.

## Solidity authorization findings repaired

- An unverified caller could previously self-register as `HospitalAdmin` and pass `onlyAdmin`; public on-chain registration is now patient-only and `onlyAdmin` requires verification.
- Staff identities are created unverified by a verified admin and explicitly approved.
- Consent can target only verified doctors or lab technicians and can be granted only by a verified patient.
- Third-party record registration requires verified clinical status plus active `ReadAndWrite` consent.
- Emergency audit entries can come only from an owner-authorized logger, and the deployment script authorizes the deployed BreakGlass contract.
- Break-glass checks that the record belongs to the supplied patient; auditors must be verified.

These controls have compilation coverage, not a completed independent smart-contract audit.
