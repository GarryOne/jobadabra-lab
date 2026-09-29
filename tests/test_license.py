"""tools/license.py: minting, verifying and revoking, with a throwaway key and a temporary data folder (never the Keychain).
Run: python3 -m unittest discover -s tests"""
import datetime
import sys
import tempfile
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

    def test_revoke_signs_a_list_and_rejects_unknown_ids(self):
        payload = lic.verify(lic.mint(self.key, "Ana", "friend"), self.public)
        signed = lic.revoke(self.key, payload["id"], today=datetime.date(2026, 10, 1))
        self.assertEqual(lic.verify(signed, self.public, prefix="JP1R"), {"revoked": [payload["id"]], "issued": "2026-10-01"})
        with self.assertRaises(ValueError):
            lic.revoke(self.key, "nope")


if __name__ == "__main__":
    unittest.main()
