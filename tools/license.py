#!/usr/bin/env python3
"""License keys for Jobadabra (Stage 1), signed by the owner with Ed25519.

  tools/license.py init                                    one time: make the signing key (Keychain only), print the public key
  tools/license.py mint --name "Ana" --kind friend [--until 2027-01-01]
  tools/license.py list                                    who got which key (no keys shown)
  tools/license.py show <id or name>                       print a key again (the same key: signatures are deterministic)
  tools/license.py revoke <id>                             writes data/revocations.json (signed) for the app to fetch later
  tools/license.py verify <key>
  tools/license.py sync                                    Notion 🔑 Licenses: every key, status, and when its app was last seen

Key format: JP1.<base64url payload>.<base64url signature>, payload {id, name, kind: founder|friend|pass, until?}.
The private key lives ONLY in the macOS Keychain (jobadabra.license.signing_key): never in git, Notion or logs.
data/licenses.json keeps what was minted (id, name, kind, until, date), never a key or the private key.
"""
import argparse
import base64
import datetime
import json
import secrets
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

ACCOUNT, SERVICE = "jobadabra", "jobadabra.license.signing_key"
# Why (2 Nov 2026, Gitar on lab #68): the rename moves the signing key's Keychain name; a Mac that has not run tools/keychain-copy-to-jobadabra.sh in the public repo
# still holds the key under the old name, and `init` would mint a second key that no license verifies against. Not a fallback: init only refuses.
OLD_SIGNING_ITEM = ("job-pilotto", "job-pilotto.license.signing_key")
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


def old_signing_key_exists() -> bool:
    return subprocess.run(["security", "find-generic-password", "-a", OLD_SIGNING_ITEM[0], "-s", OLD_SIGNING_ITEM[1]], capture_output=True).returncode == 0


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
        raise ValueError("Not a Jobadabra license key")
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


def show(key: Ed25519PrivateKey, who: str) -> list[tuple[dict, str]]:
    """The keys already minted for an id or a name (case-insensitive): re-signed, so identical to the originals."""
    found = [item for item in load(LEDGER, []) if who == item['id'] or who.lower() in item['name'].lower()]
    return [(item, sign_payload(key, {k: item[k] for k in ('id', 'name', 'kind', 'until') if k in item})) for item in found]


# ---- Notion 🔑 Licenses (Project Hub → Users & Launch): one row per key, never the key itself ----
# Written with the Job Pilotto Brain connection (Keychain jobadabra.notion.brain_token); "Last seen" comes from the
# apps' daily health lines (the website's /api/signals, key jobadabra.site.stats_key), which carry only the id.
SIGNALS = "https://www.jobadabra.top/api/signals?days=30"


def keychain(service: str) -> str:
    return subprocess.run(["security", "find-generic-password", "-s", service, "-w"], capture_output=True, text=True, check=True).stdout.strip()


def http(url: str, method: str = "GET", body: dict | None = None, headers: dict | None = None) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, method=method,
                                 headers={"Content-Type": "application/json", "User-Agent": "jobadabra-license", **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read() or b"{}")


def notion_api(path: str, method: str = "GET", body: dict | None = None) -> dict:
    return http(f"https://api.notion.com/v1/{path}", method, body,
                {"Authorization": f"Bearer {keychain('jobadabra.notion.brain_token')}", "Notion-Version": "2022-06-28"})


def seen_by_id() -> dict:
    try:
        return http(SIGNALS, headers={"Authorization": f"Bearer {keychain('jobadabra.site.stats_key')}"}).get("licenses", {})
    except (urllib.error.URLError, subprocess.CalledProcessError, OSError) as error:
        print(f"(Last seen not updated: {error})", file=sys.stderr)
        return {}


def row_properties(item: dict, revoked: set, seen: dict) -> dict:
    text = lambda value: {"rich_text": [{"type": "text", "text": {"content": value}}] if value else []}
    date = lambda value: {"date": {"start": value[:10]} if value else None}
    props = {"Name": {"title": [{"type": "text", "text": {"content": item["name"]}}]}, "License id": text(item["id"]),
             "Kind": {"select": {"name": item["kind"]}}, "Status": {"select": {"name": "Revoked" if item["id"] in revoked else "Active"}},
             "Minted": date(item.get("minted")), "Until": date(item.get("until"))}
    if item["id"] in seen:  # only set when the app reported it; never erase an older "Last seen"
        props["Last seen"] = date(seen[item["id"]].get("lastSeen"))
        props["Version"] = text(seen[item["id"]].get("version", ""))
    return props


def sync(notion=notion_api, seen: dict | None = None) -> int:
    """Every minted key -> one row in Notion 🔑 Licenses (matched by License id). Returns how many rows were written."""
    database = load("notion.json", {}).get("licenses_database")
    if not database:
        raise SystemExit("data/notion.json has no licenses_database")
    revoked = set(load(REVOCATIONS, {}).get("revoked", []))
    seen = seen_by_id() if seen is None else seen
    written = 0
    for item in load(LEDGER, []):
        found = notion(f"databases/{database}/query", "POST",
                       {"filter": {"property": "License id", "rich_text": {"equals": item["id"]}}, "page_size": 1}).get("results", [])
        props = row_properties(item, revoked, seen)
        if found:
            notion(f"pages/{found[0]['id']}", "PATCH", {"properties": props})
        else:
            notion("pages", "POST", {"parent": {"database_id": database}, "properties": props})
        written += 1
    return written


def try_sync() -> None:
    try:
        print(f"Notion 🔑 Licenses: {sync()} rows up to date")
    except Exception as error:  # the key is minted either way; syncing can be re-run with `sync`
        print(f"(Notion not updated: {error}. Run: tools/license.py sync)", file=sys.stderr)


def install_line(key: str) -> str:
    return f"curl -fsSL https://www.jobadabra.top/install | bash -s {key}"


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
    sub.add_parser("sync")
    w = sub.add_parser("show")
    w.add_argument("who", help="a license id or (part of) a name")
    r = sub.add_parser("revoke")
    r.add_argument("id")
    v = sub.add_parser("verify")
    v.add_argument("key")
    args = parser.parse_args(argv)

    if args.command == "init":
        if keychain_get():
            sys.exit(f"A signing key already exists ({SERVICE}). Not replacing it: every key minted so far would stop verifying.")
        if old_signing_key_exists():
            sys.exit(f"The signing key is still under its old Keychain name. Copy it first (tools/keychain-copy-to-jobadabra.sh --go in the jobadabra repo); init would make a second key and every key minted so far would stop verifying.")
        seed = Ed25519PrivateKey.generate()
        keychain_set(b64(seed.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())))
        print(f"Signing key stored in the Keychain as {SERVICE}.\nPublic key (goes into desktop/lib/license.js): {public_b64(seed)}")
    elif args.command == "mint":
        try:
            key = mint(private_key(), args.name, args.kind, args.until)
        except ValueError as error:
            sys.exit(str(error))
        print(key)
        print(f"\nSend this (Mac, one line: installs, unlocks, $1 free AI):\n{install_line(key)}")
        try_sync()
    elif args.command == "show":
        found = show(private_key(), args.who)
        if not found:
            raise SystemExit(f"No license for {args.who!r}: see tools/license.py list")
        for item, text in found:
            print(f"{item['name']} ({item['kind']}, id {item['id']}):\n{text}\nInstall line: {install_line(text)}\n")
    elif args.command == "sync":
        print(f"Notion 🔑 Licenses: {sync()} rows up to date")
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
        try_sync()
    elif args.command == "verify":
        try:
            print(json.dumps(verify(args.key, public_b64(private_key())), ensure_ascii=False))
        except ValueError as error:
            sys.exit(str(error))


if __name__ == "__main__":
    main()
