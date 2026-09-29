#!/usr/bin/env python3
"""License keys for Job Pilotto (Stage 1), signed by the owner with Ed25519.

  tools/license.py init                                    one time: make the signing key (Keychain only), print the public key
  tools/license.py mint --name "Ana" --kind friend [--until 2027-01-01]
  tools/license.py list
  tools/license.py revoke <id>                             writes data/revocations.json (signed) for the app to fetch later
  tools/license.py verify <key>

Key format: JP1.<base64url payload>.<base64url signature>, payload {id, name, kind: founder|friend|pass, until?}.
The private key lives ONLY in the macOS Keychain (job-pilotto.license.signing_key): never in git, Notion or logs.
data/licenses.json keeps what was minted (id, name, kind, until, date), never a key or the private key.
"""
import argparse
import base64
import datetime
import json
import secrets
import subprocess
import sys
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

ACCOUNT, SERVICE = "job-pilotto", "job-pilotto.license.signing_key"
KINDS = ("founder", "friend", "pass")
DATA = Path(__file__).resolve().parent.parent / "data"
LEDGER, REVOCATIONS = "licenses.json", "revocations.json"


def b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def keychain_get() -> str | None:
    done = subprocess.run(["security", "find-generic-password", "-a", ACCOUNT, "-s", SERVICE, "-w"], capture_output=True, text=True)
    return done.stdout.strip() if done.returncode == 0 else None


def keychain_set(value: str) -> None:
    subprocess.run(["security", "add-generic-password", "-U", "-a", ACCOUNT, "-s", SERVICE, "-w", value], check=True, capture_output=True)


def private_key(seed: str | None = None) -> Ed25519PrivateKey:
    seed = seed or keychain_get()
    if not seed:
        sys.exit(f"No signing key in the Keychain ({SERVICE}). Run: tools/license.py init")
    return Ed25519PrivateKey.from_private_bytes(unb64(seed))


def public_b64(key: Ed25519PrivateKey) -> str:
    return b64(key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))


def sign_payload(key: Ed25519PrivateKey, payload: dict, prefix: str = "JP1") -> str:
    body = b64(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    return f"{prefix}.{body}.{b64(key.sign(body.encode()))}"


def verify(text: str, public: str, prefix: str = "JP1") -> dict:
    """The payload of a genuinely signed key; ValueError otherwise."""
    parts = text.strip().split(".")
    if len(parts) != 3 or parts[0] != prefix:
        raise ValueError("Not a Job Pilotto license key")
    try:
        Ed25519PublicKey.from_public_bytes(unb64(public)).verify(unb64(parts[2]), parts[1].encode())
        return json.loads(unb64(parts[1]))
    except (InvalidSignature, ValueError) as error:
        raise ValueError("The signature does not match") from error


def load(name: str, fallback):
    try:
        return json.loads((DATA / name).read_text())
    except FileNotFoundError:
        return fallback


def save(name: str, value) -> None:
    DATA.mkdir(exist_ok=True)
    (DATA / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def mint(key: Ed25519PrivateKey, name: str, kind: str, until: str | None = None, today: datetime.date | None = None) -> str:
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {', '.join(KINDS)}")
    if not name.strip():
        raise ValueError("a name is needed")
    if until:
        datetime.date.fromisoformat(until)
    ledger = load(LEDGER, [])
    payload = {"id": secrets.token_hex(4), "name": name.strip(), "kind": kind}
    if until:
        payload["until"] = until
    ledger.append({**payload, "minted": (today or datetime.date.today()).isoformat()})
    save(LEDGER, ledger)
    return sign_payload(key, payload)


def revoke(key: Ed25519PrivateKey, license_id: str, today: datetime.date | None = None) -> str:
    ledger = load(LEDGER, [])
    if not any(item["id"] == license_id for item in ledger):
        raise ValueError(f"No license with id {license_id} (tools/license.py list)")
    ids = sorted({*load(REVOCATIONS, {}).get("revoked", []), license_id})
    text = sign_payload(key, {"revoked": ids, "issued": (today or datetime.date.today()).isoformat()}, prefix="JP1R")
    save(REVOCATIONS, {"revoked": ids, "signed": text})
    return text


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    m = sub.add_parser("mint")
    m.add_argument("--name", required=True)
    m.add_argument("--kind", required=True, choices=KINDS)
    m.add_argument("--until", help="YYYY-MM-DD; omit for no end date")
    sub.add_parser("list")
    r = sub.add_parser("revoke")
    r.add_argument("id")
    v = sub.add_parser("verify")
    v.add_argument("key")
    args = parser.parse_args(argv)

    if args.command == "init":
        if keychain_get():
            sys.exit(f"A signing key already exists ({SERVICE}). Not replacing it: every key minted so far would stop verifying.")
        seed = Ed25519PrivateKey.generate()
        keychain_set(b64(seed.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())))
        print(f"Signing key stored in the Keychain as {SERVICE}.\nPublic key (goes into desktop/lib/license.js): {public_b64(seed)}")
    elif args.command == "mint":
        try:
            print(mint(private_key(), args.name, args.kind, args.until))
        except ValueError as error:
            sys.exit(str(error))
    elif args.command == "list":
        revoked = set(load(REVOCATIONS, {}).get("revoked", []))
        for item in load(LEDGER, []):
            print(f"{item['id']}  {item['kind']:<8} {item['name']:<24} until {item.get('until', '-'):<10} minted {item['minted']}{'  REVOKED' if item['id'] in revoked else ''}")
    elif args.command == "revoke":
        try:
            revoke(private_key(), args.id)
        except ValueError as error:
            sys.exit(str(error))
        print(f"Revoked {args.id}. Signed list: data/revocations.json")
    elif args.command == "verify":
        try:
            print(json.dumps(verify(args.key, public_b64(private_key())), ensure_ascii=False))
        except ValueError as error:
            sys.exit(str(error))


if __name__ == "__main__":
    main()
