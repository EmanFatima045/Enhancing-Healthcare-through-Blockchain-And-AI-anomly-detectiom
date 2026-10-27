"""Runtime configuration with fail-closed production defaults."""

import os
from pathlib import Path


class Settings:
    PROJECT_NAME = "HealerPlus"
    VERSION = "2.1.0"
    API_V1_STR = "/api/v1"
    ENVIRONMENT = os.getenv("HEALER_ENV", "development").lower()
    TESTING = ENVIRONMENT == "test"
    DEMO_MODE = os.getenv("HEALER_DEMO_MODE", "false").lower() == "true"

    _default_db = Path(__file__).resolve().parents[2] / "data" / "healerplus.db"
    DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{_default_db.as_posix()}")
    SECRET_KEY = os.getenv("HEALER_SECRET_KEY", "")
    JWT_ALGORITHM = "HS256"
    JWT_ISSUER = os.getenv("HEALER_JWT_ISSUER", "healerplus-api")
    JWT_AUDIENCE = os.getenv("HEALER_JWT_AUDIENCE", "healerplus-web")
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("HEALER_TOKEN_MINUTES", "60"))
    OUTBOX_POLL_SECONDS = float(os.getenv("HEALER_OUTBOX_POLL_SECONDS", "5"))

    TRUST_PROXY_HEADERS = os.getenv("HEALER_TRUST_PROXY_HEADERS", "false").lower() == "true"
    TRUSTED_PROXIES = {v.strip() for v in os.getenv("HEALER_TRUSTED_PROXIES", "127.0.0.1,::1").split(",") if v.strip()}
    CORS_ORIGINS = [v.strip() for v in os.getenv("HEALER_CORS_ORIGINS", "http://127.0.0.1:3000,http://localhost:3000").split(",") if v.strip()]
    _default_trusted_hosts = "127.0.0.1,localhost,testserver" if TESTING else "127.0.0.1,localhost"
    TRUSTED_HOSTS = [v.strip() for v in os.getenv("HEALER_TRUSTED_HOSTS", _default_trusted_hosts).split(",") if v.strip()]

    RPC_URL = os.getenv("ETH_RPC_URL", "").strip()
    CHAIN_ID = int(os.getenv("CHAIN_ID", "31337"))
    APP_DOMAIN = os.getenv("HEALER_APP_DOMAIN", "127.0.0.1:3000").strip().lower()
    WALLET_CHALLENGE_MINUTES = int(os.getenv("HEALER_WALLET_CHALLENGE_MINUTES", "5"))
    CHAIN_CONFIRMATIONS = int(os.getenv("HEALER_CHAIN_CONFIRMATIONS", "1"))
    SERVICE_SIGNER_PRIVATE_KEY = os.getenv("HEALER_SERVICE_SIGNER_PRIVATE_KEY", "").strip()
    STAFF_ADMIN_PRIVATE_KEY = os.getenv("HEALER_STAFF_ADMIN_PRIVATE_KEY", "").strip()
    SERVICE_SIGNER_SCOPES = {v.strip() for v in os.getenv("HEALER_SERVICE_SIGNER_SCOPES", "").split(",") if v.strip()}
    MODEL_ARTIFACT_DIR = os.getenv("HEALER_MODEL_ARTIFACT_DIR", str(Path(__file__).resolve().parents[1] / "ml" / "artifacts"))
    NOTIFICATION_SINK = os.getenv("HEALER_NOTIFICATION_SINK", "local").lower()
    SMTP_HOST = os.getenv("HEALER_SMTP_HOST", "").strip()
    SMTP_PORT = int(os.getenv("HEALER_SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("HEALER_SMTP_USERNAME", "").strip()
    SMTP_PASSWORD = os.getenv("HEALER_SMTP_PASSWORD", "")
    SMTP_FROM = os.getenv("HEALER_SMTP_FROM", "").strip()
    CARE_TEAM_EMAIL = os.getenv("HEALER_CARE_TEAM_EMAIL", "").strip().lower()
    SMTP_STARTTLS = os.getenv("HEALER_SMTP_STARTTLS", "true").lower() == "true"
    AUTH_ADDRESS = os.getenv("HEALER_AUTH_CONTRACT_ADDRESS", "").strip()
    CONSENT_ADDRESS = os.getenv("CONSENT_MANAGER_CONTRACT_ADDRESS", "").strip()
    AUDIT_ADDRESS = os.getenv("MEDICAL_AUDIT_CONTRACT_ADDRESS", "").strip()
    BREAK_GLASS_ADDRESS = os.getenv("BREAK_GLASS_CONTRACT_ADDRESS", "").strip()
    EMERGENCY_ESCROW_EMAIL = os.getenv("HEALER_EMERGENCY_ESCROW_EMAIL", "").strip().lower()
    EMERGENCY_ESCROW_PRIVATE_KEY_PATH = os.getenv("HEALER_EMERGENCY_ESCROW_PRIVATE_KEY_PATH", "").strip()
    CIPHERTEXT_STORAGE = os.getenv("HEALER_CIPHERTEXT_STORAGE", "local").lower()
    KUBO_API_URL = os.getenv("KUBO_API_URL", "").rstrip("/")
    PINATA_JWT = os.getenv("PINATA_JWT", "")

    def validate(self) -> None:
        if not self.TESTING and len(self.SECRET_KEY) < 32:
            raise RuntimeError("HEALER_SECRET_KEY must be configured with at least 32 characters")
        if self.WALLET_CHALLENGE_MINUTES < 1 or self.WALLET_CHALLENGE_MINUTES > 15:
            raise RuntimeError("HEALER_WALLET_CHALLENGE_MINUTES must be between 1 and 15")
        if self.OUTBOX_POLL_SECONDS < 1 or self.OUTBOX_POLL_SECONDS > 300:
            raise RuntimeError("HEALER_OUTBOX_POLL_SECONDS must be between 1 and 300")
        if not self.TRUSTED_HOSTS:
            raise RuntimeError("HEALER_TRUSTED_HOSTS must contain at least one host")
        if self.NOTIFICATION_SINK not in {"local", "smtp"}:
            raise RuntimeError("HEALER_NOTIFICATION_SINK must be local or smtp")
        if self.NOTIFICATION_SINK == "smtp" and not all((self.SMTP_HOST, self.SMTP_FROM, self.CARE_TEAM_EMAIL)):
            raise RuntimeError("SMTP notification sink requires host, sender, and care-team email")
        if self.NOTIFICATION_SINK == "smtp" and self.SMTP_STARTTLS and not all((self.SMTP_USERNAME, self.SMTP_PASSWORD)):
            raise RuntimeError("STARTTLS SMTP notification sink requires username and password")


settings = Settings()
