"""
LegalShield AI 2026 — Testes Unitários do Projeto B (Enterprise)
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

ENTERPRISE_PATH = str(Path(__file__).parent.parent / "projeto_b_enterprise")
if ENTERPRISE_PATH not in sys.path:
    sys.path.insert(0, ENTERPRISE_PATH)


class TestSteganography(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def test_encrypt_decrypt(self):
        from app.core.steganography import _encrypt_fingerprint, _decrypt_fingerprint
        enc = _encrypt_fingerprint("secret")
        self.assertEqual(_decrypt_fingerprint(enc), "secret")

    def test_zwc(self):
        from app.core.steganography import _encode_zwc, _decode_zwc
        self.assertEqual(_decode_zwc(_encode_zwc("abc123")), "abc123")

    def test_5_of_5(self):
        from app.core.steganography import FingerprintData, inject_all_fingerprints, extract_all_fingerprints
        fp = FingerprintData(fingerprint_id="T_2026", customer_name="Teste",
                            contract_id="CT", sale_date="2026-05-04")
        self.assertEqual(sum(inject_all_fingerprints(fp, self.temp_dir).values()), 5)
        r = extract_all_fingerprints(self.temp_dir)
        self.assertEqual(r.confidence, "5/5")
        self.assertEqual(r.confirmed_fingerprint, "T_2026")

    def test_resilience_3_of_5(self):
        from app.core.steganography import FingerprintData, inject_all_fingerprints, extract_all_fingerprints
        fp = FingerprintData(fingerprint_id="RES", customer_name="R",
                            contract_id="C", sale_date="2026-05-04")
        inject_all_fingerprints(fp, self.temp_dir)
        for f in ["data/legalshield.db", "config/settings.yml"]:
            p = os.path.join(self.temp_dir, f)
            if os.path.exists(p): os.remove(p)
        r = extract_all_fingerprints(self.temp_dir)
        self.assertEqual(r.confirmed_fingerprint, "RES")
        self.assertGreaterEqual(sum(1 for x in r.results if x.found), 3)


class TestLicenseManager(unittest.TestCase):
    def test_hardware_id(self):
        from app.core.license_manager import get_hardware_id
        h = get_hardware_id()
        self.assertEqual(h, get_hardware_id())
        self.assertEqual(len(h), 64)

    def test_rsa_keys(self):
        from app.core.license_manager import generate_rsa_keypair
        priv, pub = generate_rsa_keypair()
        self.assertIn(b"PRIVATE KEY", priv)
        self.assertIn(b"PUBLIC KEY", pub)

    def test_license_valid(self):
        from datetime import datetime, timedelta, timezone
        from app.core.license_manager import LicenseInfo, generate_rsa_keypair, create_license, validate_license, get_hardware_id
        priv, pub = generate_rsa_keypair()
        info = LicenseInfo(customer_id="T", customer_name="Teste", hardware_id=get_hardware_id(),
                          issued_at=datetime.now(timezone.utc).isoformat(),
                          expires_at=(datetime.now(timezone.utc) + timedelta(days=365)).isoformat())
        s = validate_license(create_license(info, priv), pub)
        self.assertTrue(s.is_valid)
        self.assertTrue(s.hardware_match)

    def test_tampered(self):
        from datetime import datetime, timedelta, timezone
        from app.core.license_manager import LicenseInfo, generate_rsa_keypair, create_license, validate_license, get_hardware_id
        priv, pub = generate_rsa_keypair()
        info = LicenseInfo(customer_id="T", customer_name="T", hardware_id=get_hardware_id(),
                          issued_at=datetime.now(timezone.utc).isoformat(),
                          expires_at=(datetime.now(timezone.utc) + timedelta(days=30)).isoformat())
        s = validate_license(create_license(info, priv)[:-5] + "XXXXX", pub)
        self.assertFalse(s.is_valid)

    def test_expired(self):
        from datetime import datetime, timedelta, timezone
        from app.core.license_manager import LicenseInfo, generate_rsa_keypair, create_license, validate_license, get_hardware_id
        priv, pub = generate_rsa_keypair()
        info = LicenseInfo(customer_id="T", customer_name="T", hardware_id=get_hardware_id(),
                          issued_at=(datetime.now(timezone.utc) - timedelta(days=400)).isoformat(),
                          expires_at=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat())
        s = validate_license(create_license(info, priv), pub)
        self.assertFalse(s.is_valid)


if __name__ == "__main__":
    unittest.main(verbosity=2)
