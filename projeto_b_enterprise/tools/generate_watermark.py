#!/usr/bin/env python3
"""
LegalShield AI 2026 — Watermark Generator
Script para gerar marca d'água digital no momento da venda do Projeto B Enterprise.

Uso:
    python generate_watermark.py --customer "Empresa ABC" --contract "CONTRACT_2026_001"
    python generate_watermark.py --customer "Empresa XYZ" --contract "CONTRACT_2026_002" --build-path ./build_output
"""

import argparse
import hashlib
import json
import os
import random
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# Adicionar diretório pai ao path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.steganography import (
    FingerprintData,
    inject_all_fingerprints,
)


def generate_fingerprint_id(customer_name: str) -> str:
    """Gera ID de fingerprint único baseado no nome do cliente."""
    # Normalizar nome
    slug = customer_name.upper().strip()
    slug = slug.replace(" ", "_")
    slug = "".join(c for c in slug if c.isalnum() or c == "_")

    # Adicionar ano e número aleatório
    year = datetime.now().year
    rand_num = random.randint(10, 99)

    return f"{slug}_{year}_{rand_num}"


def save_to_registry(
    fingerprint_id: str,
    customer_name: str,
    contract_id: str,
    sale_date: str,
    build_path: str,
    registry_path: str = "watermark_registry.db",
):
    """Salva mapeamento fingerprint ↔ cliente no banco de registro."""
    conn = sqlite3.connect(registry_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS watermark_registry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fingerprint_id TEXT UNIQUE NOT NULL,
            customer_name TEXT NOT NULL,
            contract_id TEXT NOT NULL,
            sale_date TEXT NOT NULL,
            build_path TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        INSERT INTO watermark_registry
        (fingerprint_id, customer_name, contract_id, sale_date, build_path, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        fingerprint_id,
        customer_name,
        contract_id,
        sale_date,
        build_path,
        datetime.now(timezone.utc).isoformat(),
    ))

    conn.commit()
    conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Gerador de Marca d'Água Digital — LegalShield AI Enterprise",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python generate_watermark.py --customer "Empresa ABC" --contract "CONTRACT_2026_001"
  python generate_watermark.py --customer "Empresa XYZ" --contract "CT-002" --build-path ./builds/xyz
        """,
    )

    parser.add_argument(
        "--customer",
        required=True,
        help="Nome da empresa compradora",
    )
    parser.add_argument(
        "--contract",
        required=True,
        help="ID do contrato de venda",
    )
    parser.add_argument(
        "--build-path",
        default="./build_enterprise_output",
        help="Diretório de saída do build (default: ./build_enterprise_output)",
    )
    parser.add_argument(
        "--registry",
        default="./watermark_registry.db",
        help="Caminho do banco de registro de vendas (default: ./watermark_registry.db)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("  LEGALSHIELD AI — GERADOR DE MARCA D'ÁGUA DIGITAL")
    print("=" * 60)
    print()

    # 1. Gerar Fingerprint ID
    fingerprint_id = generate_fingerprint_id(args.customer)
    sale_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    fingerprint = FingerprintData(
        fingerprint_id=fingerprint_id,
        customer_name=args.customer,
        contract_id=args.contract,
        sale_date=sale_date,
    )

    print(f"  Cliente:        {args.customer}")
    print(f"  Contrato:       {args.contract}")
    print(f"  Fingerprint ID: {fingerprint_id}")
    print(f"  Data da venda:  {sale_date}")
    print(f"  Build path:     {args.build_path}")
    print()

    # 2. Criar diretórios necessários
    build_path = Path(args.build_path)
    for subdir in ["data", "config", "migrations", "static", "app/core"]:
        (build_path / subdir).mkdir(parents=True, exist_ok=True)

    # 3. Injetar fingerprints em todos os 5 locais
    print("  Injetando marcas d'água...")
    results = inject_all_fingerprints(fingerprint, str(build_path))

    location_names = {
        "sqlite": "BD SQLite (_sys_calibration)",
        "config_yaml": "Config YAML (zero-width chars)",
        "sql_comments": "Comentários SQL (migrations)",
        "exif_metadata": "Metadados EXIF de assets",
        "python_constants": "Constantes Python (.pyc)",
    }

    print()
    for key, success in results.items():
        status = "✓" if success else "✗"
        name = location_names.get(key, key)
        print(f"  [{status}] Injetado em: {name}")

    success_count = sum(1 for v in results.values() if v)
    print()
    print(f"  Resultado: {success_count}/5 locais injetados com sucesso")

    # 4. Salvar no registro
    try:
        save_to_registry(
            fingerprint_id=fingerprint_id,
            customer_name=args.customer,
            contract_id=args.contract,
            sale_date=sale_date,
            build_path=str(build_path),
            registry_path=args.registry,
        )
        print(f"  ✓ Registro salvo em: {args.registry}")
    except Exception as e:
        print(f"  ✗ Erro ao salvar registro: {e}")

    print()
    print("=" * 60)
    print(f"  MARCA D'ÁGUA GERADA COM SUCESSO: {fingerprint_id}")
    print("=" * 60)
    print()
    print("  IMPORTANTE: Guarde o banco 'watermark_registry.db'")
    print("  em local seguro. Ele é a prova da venda.")
    print()


if __name__ == "__main__":
    main()
