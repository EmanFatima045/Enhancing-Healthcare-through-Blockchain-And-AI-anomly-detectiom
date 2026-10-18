// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract HealerAuth {
    enum Role { None, Patient, Doctor, LabTechnician, HospitalAdmin, SecurityAuditor }
    struct Account { Role role; bool verified; bool active; }

    address public immutable owner;
    mapping(address => Account) private accounts;

    event AccountRegistered(address indexed account, Role indexed role);
    event AccountVerificationChanged(address indexed account, bool verified, address indexed administrator);
    event AccountActiveChanged(address indexed account, bool active, address indexed administrator);

    modifier onlyAdmin() {
        Account memory caller = accounts[msg.sender];
        require(msg.sender == owner || (caller.role == Role.HospitalAdmin && caller.verified && caller.active), "ADMIN_REQUIRED");
        _;
    }

    constructor() {
        owner = msg.sender;
        accounts[msg.sender] = Account(Role.HospitalAdmin, true, true);
        emit AccountRegistered(msg.sender, Role.HospitalAdmin);
    }

    function registerPatient() external {
        require(accounts[msg.sender].role == Role.None, "ALREADY_REGISTERED");
        accounts[msg.sender] = Account(Role.Patient, true, true);
        emit AccountRegistered(msg.sender, Role.Patient);
    }

    function registerStaff(address account, Role role) external onlyAdmin {
        require(account != address(0) && accounts[account].role == Role.None, "INVALID_ACCOUNT");
        require(role == Role.Doctor || role == Role.LabTechnician || role == Role.HospitalAdmin || role == Role.SecurityAuditor, "INVALID_STAFF_ROLE");
        accounts[account] = Account(role, false, true);
        emit AccountRegistered(account, role);
    }

    function setVerified(address account, bool verified) external onlyAdmin {
        require(accounts[account].role != Role.None && accounts[account].role != Role.Patient, "INVALID_STAFF");
        accounts[account].verified = verified;
        emit AccountVerificationChanged(account, verified, msg.sender);
    }

    function setActive(address account, bool active) external onlyAdmin {
        require(accounts[account].role != Role.None, "NOT_REGISTERED");
        require(account != owner, "OWNER_CANNOT_BE_SUSPENDED");
        accounts[account].active = active;
        emit AccountActiveChanged(account, active, msg.sender);
    }

    function getAccount(address account) external view returns (Account memory) { return accounts[account]; }
    function isActiveVerifiedRole(address account, Role role) external view returns (bool) {
        Account memory value = accounts[account];
        return value.role == role && value.verified && value.active;
    }
}
