"""tools/license.py: minting, verifying and revoking, with a throwaway key and a temporary data folder (never the Keychain).
Run: python3 -m unittest discover -s tests"""
import datetime
import sys
import tempfile
import json
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import license as lic  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402


class LicenseTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.saved = lic.DATA
        lic.DATA = Path(self.folder.name)
        self.addCleanup(lambda: setattr(lic, "DATA", self.saved))
        self.key = Ed25519PrivateKey.generate()
        self.public = lic.public_b64(self.key)

    def test_minted_key_verifies_and_carries_its_payload(self):
        key = lic.mint(self.key, "Ana", "friend", "2027-01-01", today=datetime.date(2026, 9, 30))
        self.assertTrue(key.startswith("JP1.") and key.count(".") == 2)
        payload = lic.verify(key, self.public)
        self.assertEqual((payload["name"], payload["kind"], payload["until"]), ("Ana", "friend", "2027-01-01"))
        self.assertEqual(len(payload["id"]), 8)

    def test_a_tampered_or_foreign_key_is_rejected(self):
        key = lic.mint(self.key, "Ana", "friend")
        head, _, sig = key.split(".")
        forged = ".".join([head, lic.b64(b'{"id":"x","name":"Eve","kind":"founder"}'), sig])
        for bad, public in ((forged, self.public), (key, lic.public_b64(Ed25519PrivateKey.generate())), ("JP1.abc", self.public), ("nonsense", self.public)):
            with self.assertRaises(ValueError):
                lic.verify(bad, public)

    def test_bad_input_is_refused_and_nothing_is_recorded(self):
        for args in (("Ana", "boss"), ("  ", "friend"), ("Ana", "friend", "soon")):
            with self.assertRaises(ValueError):
                lic.mint(self.key, *args)
        self.assertEqual(lic.load(lic.LEDGER, []), [])

    def test_ledger_lists_what_was_minted_without_the_key(self):
        key = lic.mint(self.key, "Ana", "founder")
        ledger = lic.load(lic.LEDGER, [])
        self.assertEqual([item["name"] for item in ledger], ["Ana"])
        self.assertNotIn(key, str(ledger))

    def test_show_gives_back_the_exact_same_key_by_id_or_name(self):
        key = lic.mint(self.key, "Ana Popescu", "founder", until="2027-01-01")
        item = lic.load(lic.LEDGER, [])[0]
        self.assertEqual(lic.show(self.key, item["id"])[0][1], key)
        self.assertEqual(lic.show(self.key, "ana")[0][1], key)
        self.assertEqual(lic.show(self.key, "nobody"), [])

    def test_revoke_signs_a_list_and_rejects_unknown_ids(self):
        payload = lic.verify(lic.mint(self.key, "Ana", "friend"), self.public)
        signed = lic.revoke(self.key, payload["id"], today=datetime.date(2026, 10, 1))
        self.assertEqual(lic.verify(signed, self.public, prefix="JP1R"), {"revoked": [payload["id"]], "issued": "2026-10-01"})
        with self.assertRaises(ValueError):
            lic.revoke(self.key, "nope")


if __name__ == "__main__":
    unittest.main()


class SyncTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.saved = lic.DATA
        lic.DATA = Path(self.folder.name)
        self.addCleanup(lambda: setattr(lic, "DATA", self.saved))
        lic.save("notion.json", {"licenses_database": "db"})
        self.key = Ed25519PrivateKey.generate()

    def test_each_key_becomes_one_row_updated_in_place_never_with_the_key(self):
        key = lic.mint(self.key, "Ana", "founder")
        item = lic.load(lic.LEDGER, [])[0]
        rows, calls = {}, []
        def notion(path, method="GET", body=None):
            calls.append((path, method, body))
            if path.endswith("/query"):
                wanted = body["filter"]["rich_text"]["equals"]
                return {"results": [{"id": rows[wanted]}] if wanted in rows else []}
            if path == "pages":
                rows[item["id"]] = "page-1"
            return {}
        seen = {item["id"]: {"lastSeen": "2026-09-30T08:00:00Z", "version": "0.4.0-alpha.75"}}
        self.assertEqual(lic.sync(notion, seen), 1)
        self.assertEqual(lic.sync(notion, {}), 1)
        created = [c for c in calls if c[0] == "pages"][0][2]["properties"]
        self.assertEqual(created["Status"]["select"]["name"], "Active")
        self.assertEqual(created["Last seen"]["date"]["start"], "2026-09-30")
        updated = [c for c in calls if c[0] == "pages/page-1"][0][2]["properties"]
        self.assertNotIn("Last seen", updated)  # no report since: the old date stays
        self.assertNotIn(key.split(".")[2], json.dumps(calls))
