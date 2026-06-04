#!/usr/bin/env python3
"""
LegalShield AI 2026 — Watermark Extractor (Forense)
Script para extrair marca d'água digital de software Enterprise vazado.

Uso:
    python extract_watermark.py --source /caminho/para/software/vazado
    python extract_watermark.py --source ./leaked_software --registry ./watermark_registry.db
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# Adicionar diretório pai ao path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.steganography import (
    ForensicReport,
    extract_all_fingerprints,
)


def lookup_registry(
    fingerprint_id: str,
    registry_path: str = "watermark_registry.db",
) -> dict | None:
    """Busca informações do comprador original no registro."""
    try:
        conn = sqlite3.connect(registry_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM watermark_registry WHERE fingerprint_id = ?",
            (fingerprint_id,),
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "id": row[0],
                "fingerprint_id": row[1],
                "customer_name": row[2],
                "contract_id": row[3],
                "sale_date": row[4],
                "build_path": row[5],
                "created_at": row[6],
            }
    except Exception:
        pass
    return None


def generate_forensic_text_report(
    report: ForensicReport,
    registry_info: dict | None = None,
) -> str:
    """Gera relatório forense em texto para uso legal."""
    lines = []
    lines.append("=" * 70)
    lines.append("  RELATÓRIO FORENSE — LEGALSHIELD AI ENTERPRISE")
    lines.append("  EXTRAÇÃO DE MARCA D'ÁGUA DIGITAL")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  Data do escaneamento: {report.scan_date}")
    lines.append(f"  Diretório analisado:  {report.source_path}")
    lines.append("")
    lines.append("-" * 70)
    lines.append("  RESULTADOS POR LOCAL DE ESTEGANOGRAFIA:")
    lines.append("-" * 70)
    lines.append("")

    for i, result in enumerate(report.results, 1):
        status = "✓ ENCONTRADO" if result.found else "✗ NÃO ENCONTRADO"
        lines.append(f"  [{i}/5] {result.location}")
        lines.append(f"         Status: {status}")
        if result.found:
            lines.append(f"         Fingerprint: {result.fingerprint_id}")
        if result.error:
            lines.append(f"         Observação: {result.error}")
        lines.append("")

    lines.append("-" * 70)
    lines.append("  CONCLUSÃO:")
    lines.append("-" * 70)
    lines.append("")

    if report.confirmed_fingerprint:
        lines.append(f"  Confiança: {report.confidence}")
        lines.append(f"  Fingerprint confirmado: {report.confirmed_fingerprint}")
        lines.append("")

        if report.customer_name:
            lines.append(f"  COMPRADOR ORIGINAL IDENTIFICADO:")
            lines.append(f"    Nome:     {report.customer_name}")
        if report.contract_id:
            lines.append(f"    Contrato: {report.contract_id}")

        if registry_info:
            lines.append(f"    Data da venda: {registry_info.get('sale_date', 'N/A')}")
            lines.append("")
            lines.append("  ⚖️  Este relatório pode ser usado como PROVA TÉCNICA")
            lines.append("      em ação judicial por quebra de contrato e pirataria.")
    else:
        lines.append("  Nenhuma marca d'água encontrada.")
        lines.append("  Possibilidades:")
        lines.append("    - Software não é uma cópia do LegalShield Enterprise")
        lines.append("    - Todas as marcas foram removidas pelo infrator")
        lines.append("    - Versão anterior ao sistema de marcação")

    lines.append("")
    lines.append("=" * 70)
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Extrator Forense de Marca d'Água — LegalShield AI Enterprise",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--source",
        required=True,
        help="Diretório raiz do software vazado a analisar",
    )
    parser.add_argument(
        "--registry",
        default="./watermark_registry.db",
        help="Caminho do banco de registro de vendas",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Arquivo de saída para o relatório (default: stdout + arquivo automático)",
    )

    args = parser.parse_args()

    print()
    print("🔍 LEGALSHIELD AI — EXTRATOR FORENSE DE MARCA D'ÁGUA")
    print()
    print(f"  Analisando: {args.source}")
    print("  Escaneando 5 locais de esteganografia...")
    print()

    # 1. Executar extração forense
    report = extract_all_fingerprints(args.source)

    # 2. Exibir resultados na tela
    for i, result in enumerate(report.results, 1):
        if result.found:
            print(f"  [{i}/5] {result.location}: ✓ ENCONTRADO → {result.fingerprint_id}")
        else:
            reason = result.error or "Não encontrado"
            print(f"  [{i}/5] {result.location}: ✗ {reason}")

    print()

    # 3. Buscar no registro
    registry_info = None
    if report.confirmed_fingerprint:
        registry_info = lookup_registry(report.confirmed_fingerprint, args.registry)

        found_count = sum(1 for r in report.results if r.found)
        total = len(report.results)

        print(f"  RESULTADO: {found_count}/{total} marcas confirmam →", end=" ")
        print(f"Comprador Original: {report.customer_name or 'DESCONHECIDO'}")

        if registry_info:
            print(f"  Contrato: {registry_info['contract_id']}")
            print(f"  Data da venda: {registry_info['sale_date']}")
    else:
        print("  RESULTADO: Nenhuma marca d'água identificada.")

    # 4. Salvar relatório
    text_report = generate_forensic_text_report(report, registry_info)

    output_path = args.output or f"forensic_report_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.txt"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text_report)

    print()
    print(f"  → Relatório forense salvo em: {output_path}")
    print()


if __name__ == "__main__":
    main()
