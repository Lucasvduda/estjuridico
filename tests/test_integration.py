"""
LegalShield AI 2026 — Testes de Integração Enterprise
"""

import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ENTERPRISE_PATH = str(Path(__file__).parent.parent / "projeto_b_enterprise")
if ENTERPRISE_PATH not in sys.path:
    sys.path.insert(0, ENTERPRISE_PATH)


class TestWatermarkFlow(unittest.TestCase):
    """Fluxo completo: gerar watermark → extrair → identificar comprador."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_full_flow(self):
        from app.core.steganography import FingerprintData, inject_all_fingerprints, extract_all_fingerprints
        fp = FingerprintData(fingerprint_id="INTEG_2026", customer_name="Cliente Integ",
                            contract_id="CT-INTEG", sale_date="2026-05-04")
        self.assertTrue(all(inject_all_fingerprints(fp, self.temp_dir).values()))
        r = extract_all_fingerprints(self.temp_dir)
        self.assertEqual(r.confidence, "5/5")
        self.assertEqual(r.confirmed_fingerprint, "INTEG_2026")

    def test_resilience(self):
        from app.core.steganography import FingerprintData, inject_all_fingerprints, extract_all_fingerprints
        fp = FingerprintData(fingerprint_id="RES", customer_name="R",
                            contract_id="C", sale_date="2026-05-04")
        inject_all_fingerprints(fp, self.temp_dir)
        for f in ["data/legalshield.db", "static/icon.png"]:
            p = os.path.join(self.temp_dir, f)
            if os.path.exists(p): os.remove(p)
        r = extract_all_fingerprints(self.temp_dir)
        self.assertEqual(r.confirmed_fingerprint, "RES")
        self.assertGreaterEqual(sum(1 for x in r.results if x.found), 3)


class TestLicenseLifecycle(unittest.TestCase):
    """Fluxo: gerar chaves → criar licença → validar → expirar."""

    def test_valid_then_expired(self):
        from app.core.license_manager import LicenseInfo, generate_rsa_keypair, create_license, validate_license, get_hardware_id
        priv, pub = generate_rsa_keypair()
        hw = get_hardware_id()

        # Válida
        info = LicenseInfo(customer_id="I", customer_name="Integ",
                          hardware_id=hw,
                          issued_at=datetime.now(timezone.utc).isoformat(),
                          expires_at=(datetime.now(timezone.utc) + timedelta(days=365)).isoformat())
        self.assertTrue(validate_license(create_license(info, priv), pub).is_valid)

        # Expirada
        exp_info = LicenseInfo(customer_id="E", customer_name="Exp",
                              hardware_id=hw,
                              issued_at=(datetime.now(timezone.utc) - timedelta(days=400)).isoformat(),
                              expires_at=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat())
        self.assertFalse(validate_license(create_license(exp_info, priv), pub).is_valid)

        # Hardware errado
        wrong = LicenseInfo(customer_id="W", customer_name="W",
                           hardware_id="0"*64,
                           issued_at=datetime.now(timezone.utc).isoformat(),
                           expires_at=(datetime.now(timezone.utc) + timedelta(days=365)).isoformat())
        s = validate_license(create_license(wrong, priv), pub)
        self.assertFalse(s.is_valid)
        self.assertFalse(s.hardware_match)


class TestDatabaseCRUD(unittest.TestCase):
    """CRUD SQLite Enterprise."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_contracts_crud(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE contracts (id TEXT PRIMARY KEY, filename TEXT, status TEXT)")
        conn.execute("INSERT INTO contracts VALUES ('c1', 'test.pdf', 'uploaded')")
        conn.commit()

        row = conn.execute("SELECT * FROM contracts WHERE id='c1'").fetchone()
        self.assertEqual(row["filename"], "test.pdf")

        conn.execute("UPDATE contracts SET status='analyzed' WHERE id='c1'")
        conn.commit()
        self.assertEqual(conn.execute("SELECT status FROM contracts WHERE id='c1'").fetchone()["status"], "analyzed")

        conn.execute("DELETE FROM contracts WHERE id='c1'")
        conn.commit()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM contracts").fetchone()[0], 0)
        conn.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
