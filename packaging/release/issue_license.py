"""Issues, renews and revokes MidiBakery licenses in the license service's D1 database (services/updates).
Until a merchant of record's webhook does it, you run this by hand after a sale:

    uv run python packaging/release/issue_license.py issue --name "Ada Lovelace" --email ada@example.com [--seats 2] [--months 12]
    uv run python packaging/release/issue_license.py renew MB-XXXX-XXXX-XXXX-XXXX [--months 12]
    uv run python packaging/release/issue_license.py revoke MB-XXXX-XXXX-XXXX-XXXX

It runs `npx wrangler d1 execute midibakery --remote` in services/updates (your wrangler login);
--dry-run only prints the SQL. The key itself is printed once and stored only as its SHA-256.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import secrets
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"  # no 0/O, 1/I: keys get typed off emails


def new_key() -> str:
    groups = ["".join(secrets.choice(ALPHABET) for _ in range(4)) for _ in range(4)]
    return "MB-" + "-".join(groups)


def key_hash(key: str) -> str:
    return hashlib.sha256(key.strip().upper().encode()).hexdigest()


def quote(text: str) -> str:
    return "'" + str(text).replace("'", "''") + "'"


def add_months(date: datetime.date, months: int) -> datetime.date:
    month = date.month - 1 + months
    year, month = date.year + month // 12, month % 12 + 1
    return date.replace(year=year, month=month, day=min(date.day, 28))


def issue_sql(key: str, name: str, email: str, seats: int, months: int, source: str) -> str:
    today = datetime.date.today()
    license_id = f"L-{today:%Y}-{secrets.token_hex(3).upper()}"
    return ("INSERT INTO licenses (key_hash, id, name, email, seats, updates_until, created, source) VALUES ("
            f"{quote(key_hash(key))}, {quote(license_id)}, {quote(name)}, {quote(email)}, {int(seats)}, "
            f"{quote(add_months(today, months).isoformat())}, {quote(today.isoformat())}, {quote(source)});")


def renew_sql(key: str, months: int) -> str:
    # from the later of today and the current end: renewing early loses nothing
    return (f"UPDATE licenses SET updates_until = date(max(updates_until, date('now')), '+{int(months)} months') "
            f"WHERE key_hash = {quote(key_hash(key))};")


def revoke_sql(key: str) -> str:
    return f"UPDATE licenses SET revoked = 1 WHERE key_hash = {quote(key_hash(key))};"


def execute(sql: str, dry_run: bool) -> None:
    if dry_run:
        print(sql)
        return
    subprocess.run(["npx", "--yes", "wrangler@4.147.0", "d1", "execute", "midibakery", "--remote", "--command", sql],
                   cwd=ROOT / "services" / "updates", check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("issue")
    p.add_argument("--name", required=True)
    p.add_argument("--email", default="")
    p.add_argument("--seats", type=int, default=2)
    p.add_argument("--months", type=int, default=12, help="updates included")
    p.add_argument("--source", default="", help="order id")
    p = sub.add_parser("renew")
    p.add_argument("key")
    p.add_argument("--months", type=int, default=12)
    p = sub.add_parser("revoke")
    p.add_argument("key")
    args = parser.parse_args(argv)

    if args.command == "issue":
        key = new_key()
        execute(issue_sql(key, args.name, args.email, args.seats, args.months, args.source), args.dry_run)
        print(f"license key for {args.name}: {key}")
    elif args.command == "renew":
        execute(renew_sql(args.key, args.months), args.dry_run)
        print("renewed; the app picks it up within a week (or: midibakery license activate <key>)")
    else:
        execute(revoke_sql(args.key), args.dry_run)
        print("revoked; installs stop working with it at their next weekly check")
    return 0


if __name__ == "__main__":
    sys.exit(main())
