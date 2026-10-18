// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import './HealerAuth.sol';
import './MedicalAuditRegistry.sol';

contract BreakGlassEmergency {
    enum EmergencyType { None, CardiacArrest, Trauma, CriticalCare, Stroke }
    enum ReviewStatus { Pending, Approved, Rejected, Revoked }
    struct Session { address practitioner; address patient; bytes32 recordId; bytes32 justificationCommitment; EmergencyType emergencyType; uint64 openedAt; uint64 expiresAt; ReviewStatus review; }
    uint64 public constant DURATION = 2 hours;
    HealerAuth public immutable auth; MedicalAuditRegistry public immutable audit;
    uint256 public sessionCount; mapping(uint256 => Session) public sessions;
    event BreakGlassOpened(uint256 indexed sessionId, address indexed practitioner, address indexed patient, bytes32 recordId, bytes32 justificationCommitment, EmergencyType emergencyType, uint64 expiresAt);
    event BreakGlassReviewed(uint256 indexed sessionId, address indexed auditor, ReviewStatus status);
    constructor(address authAddress, address auditAddress) { require(authAddress != address(0) && auditAddress != address(0), "INVALID_DEPENDENCY"); auth = HealerAuth(authAddress); audit = MedicalAuditRegistry(auditAddress); }
    function open(address patient, bytes32 recordId, bytes32 justificationCommitment, EmergencyType emergencyType) external returns (uint256 id) {
        require(auth.isActiveVerifiedRole(msg.sender, HealerAuth.Role.Doctor), "ACTIVE_DOCTOR_REQUIRED");
        require(patient != address(0) && audit.recordPatient(recordId) == patient, "PATIENT_RECORD_MISMATCH");
        require(justificationCommitment != bytes32(0), "JUSTIFICATION_COMMITMENT_REQUIRED");
        require(emergencyType >= EmergencyType.CardiacArrest && emergencyType <= EmergencyType.Stroke, "INVALID_EMERGENCY_TYPE");
        id = sessionCount++; uint64 expiry = uint64(block.timestamp) + DURATION;
        sessions[id] = Session(msg.sender, patient, recordId, justificationCommitment, emergencyType, uint64(block.timestamp), expiry, ReviewStatus.Pending);
        audit.logEmergencyAccess(recordId, msg.sender);
        emit BreakGlassOpened(id, msg.sender, patient, recordId, justificationCommitment, emergencyType, expiry);
    }
    function review(uint256 id, bool legitimate) external {
        HealerAuth.Account memory account = auth.getAccount(msg.sender);
        require(account.active && account.verified && (account.role == HealerAuth.Role.SecurityAuditor || account.role == HealerAuth.Role.HospitalAdmin), "AUDITOR_REQUIRED");
        Session storage value = sessions[id]; require(value.openedAt != 0 && value.review == ReviewStatus.Pending, "SESSION_NOT_REVIEWABLE");
        value.review = legitimate ? ReviewStatus.Approved : ReviewStatus.Rejected; emit BreakGlassReviewed(id, msg.sender, value.review);
    }
    function revoke(uint256 id) external {
        HealerAuth.Account memory account = auth.getAccount(msg.sender);
        require(account.active && account.verified && (account.role == HealerAuth.Role.SecurityAuditor || account.role == HealerAuth.Role.HospitalAdmin), "AUDITOR_REQUIRED");
        Session storage value = sessions[id]; require(value.openedAt != 0 && value.review != ReviewStatus.Rejected, "SESSION_NOT_REVOCABLE"); value.review = ReviewStatus.Revoked; emit BreakGlassReviewed(id, msg.sender, value.review);
    }
    function isActive(uint256 id, address practitioner, address patient, bytes32 recordId) external view returns (bool) {
        Session memory value = sessions[id]; return value.openedAt != 0 && value.practitioner == practitioner && value.patient == patient && value.recordId == recordId && block.timestamp < value.expiresAt && value.review != ReviewStatus.Rejected && value.review != ReviewStatus.Revoked;
    }
}
