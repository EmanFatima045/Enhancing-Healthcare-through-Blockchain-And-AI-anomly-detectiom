// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import './HealerAuth.sol';

contract ConsentManager {
    enum AccessLevel { None, ReadOnly, ReadAndWrite }
    struct Consent { AccessLevel accessLevel; uint64 validUntil; bool revoked; uint64 grantedAt; }
    uint256 public constant MAX_DURATION = 365 days;
    bytes32 public constant ALL = keccak256('ALL');
    HealerAuth public immutable auth;
    mapping(address => mapping(address => mapping(bytes32 => Consent))) private consents;

    event ConsentGranted(address indexed patient, address indexed practitioner, bytes32 indexed categoryCommitment, AccessLevel accessLevel, uint64 validUntil);
    event ConsentRevoked(address indexed patient, address indexed practitioner, bytes32 indexed categoryCommitment);

    constructor(address authAddress) { require(authAddress != address(0), "INVALID_AUTH"); auth = HealerAuth(authAddress); }

    function grantConsent(address practitioner, bytes32 categoryCommitment, AccessLevel level, uint64 validUntil) external {
        HealerAuth.Account memory patient = auth.getAccount(msg.sender);
        HealerAuth.Account memory staff = auth.getAccount(practitioner);
        require(patient.role == HealerAuth.Role.Patient && patient.verified && patient.active, "ACTIVE_PATIENT_REQUIRED");
        require(staff.verified && staff.active && (staff.role == HealerAuth.Role.Doctor || staff.role == HealerAuth.Role.LabTechnician), "ACTIVE_PRACTITIONER_REQUIRED");
        require(categoryCommitment != bytes32(0), "INVALID_CATEGORY");
        require(level == AccessLevel.ReadOnly || level == AccessLevel.ReadAndWrite, "INVALID_ACCESS");
        require(validUntil > block.timestamp && validUntil <= block.timestamp + MAX_DURATION, "INVALID_EXPIRY");
        consents[msg.sender][practitioner][categoryCommitment] = Consent(level, validUntil, false, uint64(block.timestamp));
        emit ConsentGranted(msg.sender, practitioner, categoryCommitment, level, validUntil);
    }

    function revokeConsent(address practitioner, bytes32 categoryCommitment) external {
        Consent storage consent = consents[msg.sender][practitioner][categoryCommitment];
        require(consent.grantedAt != 0 && !consent.revoked, "NO_ACTIVE_GRANT");
        consent.revoked = true;
        emit ConsentRevoked(msg.sender, practitioner, categoryCommitment);
    }

    function resolveConsent(address patient, address practitioner, bytes32 categoryCommitment) public view returns (bool, AccessLevel) {
        HealerAuth.Account memory staff = auth.getAccount(practitioner);
        if (!staff.active || !staff.verified || (staff.role != HealerAuth.Role.Doctor && staff.role != HealerAuth.Role.LabTechnician)) return (false, AccessLevel.None);
        Consent memory exact = consents[patient][practitioner][categoryCommitment];
        if (_active(exact)) return (true, exact.accessLevel); // active category grant has precedence
        Consent memory allGrant = consents[patient][practitioner][ALL];
        if (_active(allGrant)) return (true, allGrant.accessLevel); // revoked/expired/missing category falls back to ALL
        return (false, AccessLevel.None);
    }

    function canRead(address patient, address practitioner, bytes32 categoryCommitment) external view returns (bool) {
        (bool active,) = resolveConsent(patient, practitioner, categoryCommitment); return active;
    }
    function canWrite(address patient, address practitioner, bytes32 categoryCommitment) external view returns (bool) {
        (bool active, AccessLevel level) = resolveConsent(patient, practitioner, categoryCommitment); return active && level == AccessLevel.ReadAndWrite;
    }
    function _active(Consent memory consent) private view returns (bool) { return consent.grantedAt != 0 && !consent.revoked && block.timestamp < consent.validUntil; }
}
