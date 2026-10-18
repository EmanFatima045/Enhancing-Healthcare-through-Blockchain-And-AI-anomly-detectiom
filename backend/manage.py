"""Administrative CLI for creating the first trusted local administrator."""
import argparse
import getpass
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.app.core.database import SessionLocal, initialize_database
from backend.app.core.security import hash_password
from backend.app.models import User
from backend.app.services.outbox import process_jobs

def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create-admin")
    create.add_argument("--email", required=True)
    create.add_argument("--name", required=True)
    sub.add_parser("process-outbox")
    args = parser.parse_args()
    initialize_database()
    if args.command == "process-outbox":
        with SessionLocal() as db: print(process_jobs(db))
        return
    password = os.getenv("HEALER_BOOTSTRAP_PASSWORD") or getpass.getpass("Initial admin password: ")
    if len(password) < 10: raise SystemExit("Password must contain at least 10 characters")
    with SessionLocal() as db:
        email = args.email.strip().lower()
        if db.get(User, email): raise SystemExit("Account already exists")
        db.add(User(email=email, name=args.name.strip(), password_hash=hash_password(password),
                    role="HospitalAdmin", is_verified=True, is_active=True))
        db.commit()
    print(f"Created verified HospitalAdmin: {email}")

if __name__ == "__main__": main()
