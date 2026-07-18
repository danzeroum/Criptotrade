"""Create (or reset) an admin user from the shell (D3 bootstrap path).

Usage:
    python -m scripts.create_admin --email owner@example.com
    python -m scripts.create_admin --email owner@example.com --force-reset

Prompts for the password (hidden). Never an open-signup path: requires shell
access to the deployment. Applies pending migrations first so it works on a
fresh volume.
"""
from __future__ import annotations

import argparse
import getpass
import sys

from src.auth.store import UserStore
from src.core.db import init_db


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or reset an admin user.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default="Admin")
    parser.add_argument(
        "--force-reset", action="store_true",
        help="Reset the password if the user already exists.",
    )
    args = parser.parse_args()

    init_db()
    store = UserStore()
    existing = store.get_by_email(args.email)

    if existing and not args.force_reset:
        print(f"User {args.email} already exists (use --force-reset to rotate the password).")
        return 1

    password = getpass.getpass("Password: ")
    if len(password) < 8:
        print("Password must have at least 8 characters.")
        return 1
    if getpass.getpass("Confirm password: ") != password:
        print("Passwords do not match.")
        return 1

    if existing:
        store.set_password(existing["id"], password)
        print(f"Password reset for {args.email}.")
    else:
        store.create(args.email, password, name=args.name, role="admin")
        print(f"Admin user {args.email} created.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
