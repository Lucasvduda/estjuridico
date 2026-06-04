"""
LegalShield AI 2026 — Testes de Integração SaaS
"""

import base64
import os
import sys
import unittest
from pathlib import Path

SAAS_PATH = str(Path(__file__).parent.parent / "projeto_a_saas")
if SAAS_PATH not in sys.path:
    sys.path.insert(0, SAAS_PATH)

os.environ.setdefault("ENCRYPTION_MASTER_KEY", base64.b64encode(os.urandom(32)).decode())
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-integration")


class TestTenantIsolation(unittest.TestCase):
    """Dados de um tenant não são acessíveis por outro."""

    def test_encryption_isolation(self):
        from app.core.encryption import encrypt_file, decrypt_file, EncryptionError
        data = b"Dados sigilosos."
        enc = encrypt_file(data, "tenant-a")
        self.assertEqual(decrypt_file(enc, "tenant-a"), data)
        with self.assertRaises(EncryptionError):
            decrypt_file(enc, "tenant-b")


class TestJWTFlow(unittest.TestCase):
    """Fluxo completo de tokens JWT."""

    def test_access_and_refresh(self):
        from app.core.security import create_access_token, create_refresh_token, decode_token
        access = create_access_token("u1", "t1", "admin")
        refresh = create_refresh_token("u1", "t1", "admin")
        self.assertEqual(decode_token(access).type, "access")
        self.assertEqual(decode_token(refresh).type, "refresh")
        self.assertIsNone(decode_token(access + "x"))


class TestPasswordSecurity(unittest.TestCase):
    """Testes de hashing de senhas."""

    def test_hash_and_verify(self):
        from app.core.security import hash_password, verify_password
        h = hash_password("M1nhaSenha!")
        self.assertTrue(verify_password("M1nhaSenha!", h))
        self.assertFalse(verify_password("outra", h))
        # Salt aleatório → hashes diferentes
        self.assertNotEqual(h, hash_password("M1nhaSenha!"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
