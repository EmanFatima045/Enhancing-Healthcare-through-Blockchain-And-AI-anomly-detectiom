/**
 * Healer Plus Web3 deployment configuration.
 *
 * Keep addresses empty until the contracts in /contracts are deployed.
 * The UI will clearly run in Demo Ledger mode until a valid address is set.
 */
window.HEALER_WEB3_CONFIG = {
  chainId: "0xaa36a7",
  chainName: "Sepolia",
  rpcUrl: "https://ethereum-sepolia-rpc.publicnode.com",
  blockExplorer: "https://sepolia.etherscan.io",
  contracts: {
    HealerAuth: "",
    ConsentManager: "",
    MedicalAuditRegistry: "",
    BreakGlassEmergency: ""
  },
  consentManagerAbi: [
    "function grantConsent(address practitioner,string recordCategory,uint8 accessLevel,uint256 durationSeconds,string encryptedKey)",
    "function revokeConsent(address practitioner,string recordCategory)",
    "function hasActiveConsent(address patient,address practitioner,string recordCategory) view returns (bool,uint8,string)",
    "event ConsentGranted(address indexed patient,address indexed practitioner,string recordCategory,uint8 accessLevel,uint256 validUntil,uint256 timestamp)",
    "event ConsentRevoked(address indexed patient,address indexed practitioner,string recordCategory,uint256 timestamp)"
  ]
};
