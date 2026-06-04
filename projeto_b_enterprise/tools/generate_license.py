#!/usr/bin/env python3
"""
LegalShield AI 2026 — License Key Generator
Script para gerar chaves de licença vinculadas ao hardware do cliente.

Uso:
    # Gerar par de chaves RSA (apenas uma vez)
    python generate_license.py --init-keys

    # Gerar licença para um cliente
    python generate_license.py --customer "Empresa ABC" --hardware-id "abc123..." --days 365

    # Validar uma licença
    python generate_license.py --validate --license-file license.key
"""

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.license_manager import (
    LicenseInfo,
    create_license,
    generate_rsa_keypair,
    get_hardware_id,
    validate_license,
)


def cmd_init_keys(args):
    """Gera par de chaves RSA."""
    print("\n🔑 Gerando par de chaves RSA-4096...\n")

    private_pem, public_pem = generate_rsa_keypair()

    priv_path = args.output_dir + "/private_key.pem"
    pub_path = args.output_dir + "/public_key.pem"

    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    with open(priv_path, "wb") as f:
        f.write(private_pem)
    with open(pub_path, "wb") as f:
        f.write(public_pem)

    print(f"  ✓ Chave privada: {priv_path}")
    print(f"  ✓ Chave pública: {pub_path}")
    print()
    print("  ⚠️  GUARDE A CHAVE PRIVADA EM LOCAL SEGURO!")
    print("      A chave pública será embutida no software do cliente.")
    print()


def cmd_generate(args):
    """Gera licença para cliente."""
    print(f"\n📄 Gerando licença para: {args.customer}\n")

    # Carregar chave privada
    try:
        with open(args.private_key, "rb") as f:
            private_pem = f.read()
    except FileNotFoundError:
        print(f"  ✗ Chave privada não encontrada: {args.private_key}")
        print("    Execute --init-keys primeiro.")
        sys.exit(1)

    # Hardware ID
    hw_id = args.hardware_id
    if not hw_id:
        print("  ⚠️  Sem --hardware-id, usando hardware ID desta máquina")
        hw_id = get_hardware_id()

    # Calcular expiração
    expires = datetime.now(timezone.utc) + timedelta(days=args.days)

    license_info = LicenseInfo(
        customer_id=args.customer.replace(" ", "_").upper(),
        customer_name=args.customer,
        hardware_id=hw_id,
        issued_at=datetime.now(timezone.utc).isoformat(),
        expires_at=expires.isoformat(),
    )

    license_str = create_license(license_info, private_pem)

    # Salvar
    output_file = args.output or f"license_{license_info.customer_id}.key"
    with open(output_file, "w") as f:
        f.write(license_str)

    print(f"  Cliente:      {args.customer}")
    print(f"  Hardware ID:  {hw_id[:32]}...")
    print(f"  Expira em:    {expires.strftime('%d/%m/%Y')}")
    print(f"  Validade:     {args.days} dias")
    print(f"  ✓ Licença salva: {output_file}")
    print()


def cmd_validate(args):
    """Valida uma licença."""
    print(f"\n🔍 Validando licença: {args.license_file}\n")

    try:
        with open(args.license_file, "r") as f:
            license_str = f.read().strip()
    except FileNotFoundError:
        print(f"  ✗ Arquivo não encontrado: {args.license_file}")
        sys.exit(1)

    # Carregar chave pública
    pub_key = None
    if args.public_key:
        try:
            with open(args.public_key, "rb") as f:
                pub_key = f.read()
        except FileNotFoundError:
            print(f"  ⚠️  Chave pública não encontrada: {args.public_key}")

    status = validate_license(license_str, pub_key)

    icon = "✓" if status.is_valid else "✗"
    print(f"  [{icon}] {status.message}")
    if status.customer_name:
        print(f"  Cliente: {status.customer_name}")
    if status.expires_at:
        print(f"  Expira:  {status.expires_at}")
    print(f"  Hardware match: {'Sim' if status.hardware_match else 'Não'}")
    print()


def cmd_hwid(args):
    """Mostra Hardware ID da máquina atual."""
    hw_id = get_hardware_id()
    print(f"\n  Hardware ID desta máquina:")
    print(f"  {hw_id}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Gerador de Licenças — LegalShield AI Enterprise",
    )
    subparsers = parser.add_subparsers(dest="command", help="Comando")

    # init-keys
    p_init = subparsers.add_parser("init-keys", help="Gerar par de chaves RSA")
    p_init.add_argument("--output-dir", default="./keys", help="Diretório de saída")

    # generate
    p_gen = subparsers.add_parser("generate", help="Gerar licença")
    p_gen.add_argument("--customer", required=True, help="Nome do cliente")
    p_gen.add_argument("--hardware-id", default=None, help="Hardware ID do servidor do cliente")
    p_gen.add_argument("--days", type=int, default=365, help="Validade em dias")
    p_gen.add_argument("--private-key", default="./keys/private_key.pem", help="Caminho da chave privada")
    p_gen.add_argument("--output", default=None, help="Arquivo de saída da licença")

    # validate
    p_val = subparsers.add_parser("validate", help="Validar licença")
    p_val.add_argument("--license-file", required=True, help="Arquivo da licença")
    p_val.add_argument("--public-key", default="./keys/public_key.pem", help="Chave pública")

    # hwid
    subparsers.add_parser("hwid", help="Mostrar Hardware ID desta máquina")

    args = parser.parse_args()

    if args.command == "init-keys":
        cmd_init_keys(args)
    elif args.command == "generate":
        cmd_generate(args)
    elif args.command == "validate":
        cmd_validate(args)
    elif args.command == "hwid":
        cmd_hwid(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
