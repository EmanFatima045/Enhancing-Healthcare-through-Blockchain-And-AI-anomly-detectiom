// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import './HealerAuth.sol';
import './ConsentManager.sol';

contract MedicalAuditRegistry {
    enum ActionType { RecordCreated, RecordRead, RecordUpdated, ConsentRevoked, EmergencyRead, AnomalyFlagged }
    struct RecordMeta { address patient; address createdBy; bytes32 envelopeDigest; bytes32 storageCommitment; bytes32 categoryCommitment; uint64 createdAt; bool archived; }
    struct AuditEntry { bytes32 recordId; address actor; address patient; ActionType action; uint64 timestamp; }
    HealerAuth public immutable auth;
    ConsentManager public immutable consent;
    address public immutable owner;
    mapping(address => bool) public emergencyLoggers;
    mapping(address => bool) public serviceWriters;
    mapping(bytes32 => bool) public incidentAttested;
    mapping(bytes32 => RecordMeta) public records;
    AuditEntry[] private audits;

    event RecordRegistered(bytes32 indexed recordId, address indexed patient, bytes32 envelopeDigest, bytes32 storageCommitment, bytes32 categoryCommitment);
    event AuditLogged(uint256 indexed auditId, bytes32 indexed recordId, address indexed actor, address patient, ActionType action);
    event EmergencyLoggerSet(address indexed logger, bool allowed);
    event ServiceWriterSet(address indexed writer, bool allowed);
    event IncidentAttested(bytes32 indexed incidentCommitment, address indexed writer, uint64 timestamp);

    constructor(address authAddress, address consentAddress) {
        require(authAddress != address(0) && consentAddress != address(0), "INVALID_DEPENDENCY");
        auth = HealerAuth(authAddress); consent = ConsentManager(consentAddress); owner = msg.sender;
    }
    function setEmergencyLogger(address logger, bool allowed) external { require(msg.sender == owner && logger != address(0), "OWNER_REQUIRED"); emergencyLoggers[logger] = allowed; emit EmergencyLoggerSet(logger, allowed); }
    function setServiceWriter(address writer, bool allowed) external { require(msg.sender == owner && writer != address(0), "OWNER_REQUIRED"); serviceWriters[writer] = allowed; emit ServiceWriterSet(writer, allowed); }
    function attestIncident(bytes32 incidentCommitment) external { require(serviceWriters[msg.sender], "SERVICE_WRITER_REQUIRED"); require(incidentCommitment != bytes32(0), "INVALID_INCIDENT"); require(!incidentAttested[incidentCommitment], "INCIDENT_ALREADY_ATTESTED"); incidentAttested[incidentCommitment]=true; emit IncidentAttested(incidentCommitment, msg.sender, uint64(block.timestamp)); }

    function registerRecord(bytes32 recordId, address patient, bytes32 envelopeDigest, bytes32 storageCommitment, bytes32 categoryCommitment) external {
        require(recordId != bytes32(0) && envelopeDigest != bytes32(0) && categoryCommitment != bytes32(0), "INVALID_RECORD");
        require(records[recordId].patient == address(0), "RECORD_EXISTS");
        HealerAuth.Account memory patientAccount = auth.getAccount(patient);
        require(patientAccount.role == HealerAuth.Role.Patient && patientAccount.active, "INVALID_PATIENT");
        if (msg.sender != patient && !serviceWriters[msg.sender]) require(consent.canWrite(patient, msg.sender, categoryCommitment), "WRITE_CONSENT_REQUIRED");
        records[recordId] = RecordMeta(patient, msg.sender, envelopeDigest, storageCommitment, categoryCommitment, uint64(block.timestamp), false);
        emit RecordRegistered(recordId, patient, envelopeDigest, storageCommitment, categoryCommitment);
        _log(recordId, msg.sender, patient, ActionType.RecordCreated);
    }

    function logRecordAction(bytes32 recordId, ActionType action) external {
        RecordMeta memory record = records[recordId]; require(record.patient != address(0), "RECORD_NOT_FOUND");
        require(action == ActionType.RecordRead || action == ActionType.RecordUpdated, "INVALID_ACTION");
        if (msg.sender != record.patient) {
            if (action == ActionType.RecordUpdated) require(consent.canWrite(record.patient, msg.sender, record.categoryCommitment), "WRITE_CONSENT_REQUIRED");
            else require(consent.canRead(record.patient, msg.sender, record.categoryCommitment), "READ_CONSENT_REQUIRED");
        }
        _log(recordId, msg.sender, record.patient, action);
    }

    function logEmergencyAccess(bytes32 recordId, address practitioner) external {
        require(emergencyLoggers[msg.sender], "EMERGENCY_LOGGER_REQUIRED");
        RecordMeta memory record = records[recordId]; require(record.patient != address(0), "RECORD_NOT_FOUND");
        require(auth.isActiveVerifiedRole(practitioner, HealerAuth.Role.Doctor), "ACTIVE_DOCTOR_REQUIRED");
        _log(recordId, practitioner, record.patient, ActionType.EmergencyRead);
    }
    function recordPatient(bytes32 recordId) external view returns (address) { return records[recordId].patient; }
    function auditCount() external view returns (uint256) { return audits.length; }
    function auditAt(uint256 index) external view returns (AuditEntry memory) { return audits[index]; }
    function _log(bytes32 recordId, address actor, address patient, ActionType action) private { audits.push(AuditEntry(recordId, actor, patient, action, uint64(block.timestamp))); emit AuditLogged(audits.length - 1, recordId, actor, patient, action); }
}
