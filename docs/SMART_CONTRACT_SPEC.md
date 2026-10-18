# Smart-contract security specification

The maintained contracts are in `blockchain/contracts` and target Solidity 0.8.20. The supported demonstration network is a local Hardhat node only: chain ID 31337 at `http://127.0.0.1:8545`. Public-network deployment is out of scope. Generated ABI and address outputs are under each consumer's `generated/contracts/31337` directory and must be regenerated with `npm run deploy:local`, never edited by hand.

## Public data boundary

Contracts publish only wallet addresses, opaque `bytes32` record/category/storage/justification commitments, envelope digests, roles, action enums, consent levels, and timestamps. They do not accept or emit patient names, national identifiers, diagnosis or summary text, emergency justification text, CIDs, encryption keys, or fabricated transaction hashes. Receipt transaction hashes and block metadata are indexed off chain from real receipts.

## Authorization invariants

- `HealerAuth`: only patients self-register. The owner or an active verified hospital administrator assigns staff roles, verifies staff, and suspends/reactivates accounts. Public callers cannot assign or verify privileged roles.
- `ConsentManager`: only an active registered patient grants access to an active verified doctor/lab technician. Expiry is bounded to one year and exclusive. An active category grant takes precedence; when it is absent, revoked, or expired, an active `ALL` grant applies. Read and write checks are separate and always recheck current practitioner state.
- `MedicalAuditRegistry`: a patient may register their own record; a practitioner requires write consent. Audit actions bind `msg.sender` as actor. Only the authorized emergency contract may log an emergency for the explicit doctor supplied by that contract.
- `BreakGlassEmergency`: sessions bind doctor, patient, record, emergency type, and a nonzero off-chain-justification commitment. They expire after two hours and become inactive immediately when rejected or revoked.

Break-glass itself does not deliver a key. The backend fails closed unless the optional institutional RSA escrow is explicitly configured and the record contains an escrow recipient envelope. That escrow is a documented trust boundary: after verifying the current bound session on chain, it rewraps the data key to the doctor's registered RSA key and persists the delivery state.
