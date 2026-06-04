#!/usr/bin/env python3
"""
LegalShield AI 2026 - Seed de Dados Demo (SaaS)
Popula o banco com dados de exemplo para testar os paineis.
"""

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Fix encoding no Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent.resolve()
os.chdir(ROOT)

env_file = ROOT / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


async def seed():
    from app.database import engine, Base, async_session_factory
    from app.models import Tenant, User, Contract, Analysis, SystemSettings

    # Criar tabelas
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[OK] Tabelas criadas")

    async with async_session_factory() as db:
        from sqlalchemy import select, func
        result = await db.execute(select(func.count()).select_from(Tenant))
        count = result.scalar()
        if count > 0:
            print(f"[!!] Banco ja tem {count} tenant(s). Pulando seed.")
            return

        # === 1. TENANTS ===
        tid1 = str(uuid.uuid4())
        tid2 = str(uuid.uuid4())
        tid3 = str(uuid.uuid4())

        tenants = [
            Tenant(id=tid1, name="Silva & Associados Advogados", slug="silva-advogados",
                   email="contato@silva-advogados.com.br", subscription_plan="pro",
                   subscription_status="active", max_analyses_per_month=200, max_users=10,
                   theme_primary_color="#6C5CE7", theme_accent_color="#00D2D3",
                   theme_sidebar_color="#1A1A2E", theme_bg_color="#0F0F23"),
            Tenant(id=tid2, name="Oliveira Juridico", slug="oliveira-juridico",
                   email="admin@oliveira-juridico.com", subscription_plan="basic",
                   subscription_status="active", max_analyses_per_month=50, max_users=3,
                   theme_primary_color="#0984E3", theme_accent_color="#74B9FF",
                   theme_sidebar_color="#1B2838", theme_bg_color="#0D1B2A"),
            Tenant(id=tid3, name="Costa & Lima Assessoria", slug="costa-lima",
                   email="contato@costalima.adv.br", subscription_plan="enterprise",
                   subscription_status="active", max_analyses_per_month=500, max_users=25,
                   theme_primary_color="#D4A76A", theme_accent_color="#F0E68C",
                   theme_sidebar_color="#1A1A1A", theme_bg_color="#121212"),
        ]
        for t in tenants:
            db.add(t)
        print(f"[OK] {len(tenants)} tenants criados")

        # === 2. USERS ===
        import bcrypt as _bcrypt

        def hash_pw(pw):
            return _bcrypt.hashpw(pw.encode(), _bcrypt.gensalt()).decode()

        uid_admin = str(uuid.uuid4())
        uid_adv = str(uuid.uuid4())

        superadmin = User(id=uid_admin, tenant_id=tid1, email="dev@legalshield.ai",
                          full_name="Dev Admin", password_hash=hash_pw("@Lucasvd10"),
                          role="superadmin", is_active=True)
        advogado = User(id=uid_adv, tenant_id=tid1, email="joao@silva-advogados.com.br",
                        full_name="Joao Silva", password_hash=hash_pw("Joao@12345"),
                        role="admin", is_active=True)
        db.add(superadmin)
        db.add(advogado)
        await db.flush()  # Flush users antes de criar contracts (FK)
        print("[OK] 2 usuarios criados")

        # === 3. CONTRACTS ===
        now = datetime.now(timezone.utc)
        contract_data = [
            ("Contrato de Prestacao de Servicos - TechServ.pdf", "pdf", 245000),
            ("Contrato de Locacao Comercial - Sala 302.pdf", "pdf", 180000),
            ("Acordo de Confidencialidade - NDA.docx", "docx", 95000),
            ("Contrato SaaS - CloudProvider.pdf", "pdf", 320000),
            ("Termo de Parceria Empresarial.pdf", "pdf", 150000),
            ("Contrato Trabalhista - Gerente TI.docx", "docx", 210000),
        ]

        contract_ids = []
        for i, (name, ftype, size) in enumerate(contract_data):
            cid = str(uuid.uuid4())
            contract_ids.append(cid)
            c = Contract(
                id=cid,
                tenant_id=tid1,
                uploaded_by=uid_adv,
                original_filename=name,
                stored_filename=f"{cid}.{ftype}",
                file_type=ftype,
                file_size_bytes=size,
                sha256_hash=f"demo_hash_{i:04d}",
                encrypted_path=f"/uploads/demo/{cid}.{ftype}",
                status="analyzed" if i < 4 else "uploaded",
                created_at=now - timedelta(days=i * 3),
            )
            db.add(c)
        print(f"[OK] {len(contract_data)} contratos criados")

        # === 4. ANALYSES ===
        modes = ["defensive", "offensive", "audit", "shield"]
        for i in range(4):
            analysis = Analysis(
                id=str(uuid.uuid4()),
                tenant_id=tid1,
                contract_id=contract_ids[i],
                requested_by=uid_adv,
                analysis_mode=modes[i],
                status="completed",
                resumo_executivo=f"Analise {modes[i]} do contrato {contract_data[i][0]}. Identificados {3+i} pontos de atencao.",
                score_risco=30 + i * 15,
                total_achados=3 + i,
                model_used="openai/gpt-4o",
                tokens_used=2500 + i * 800,
                cost_usd=0.05 + i * 0.02,
                latency_seconds=3.5 + i * 0.8,
                created_at=now - timedelta(days=i * 2),
            )
            db.add(analysis)
        print("[OK] 4 analises criadas")

        # === 5. SYSTEM SETTINGS ===
        settings = [
            ("llm_primary_model", "openai/gpt-4o"),
            ("llm_fallback_model", "anthropic/claude-3-5-sonnet-20241022"),
            ("llm_temperature", "0.3"),
            ("llm_max_tokens", "4096"),
        ]
        for key, value in settings:
            db.add(SystemSettings(key=key, value=value))
        print("[OK] Configuracoes de LLM definidas")

        await db.commit()

    print()
    print("=" * 55)
    print("  SEED CONCLUIDO!")
    print("=" * 55)
    print()
    print("  Contas de teste:")
    print("  -------------------------------------------------")
    print("  Dev/Admin:  dev@legalshield.ai      / @Lucasvd10")
    print("  Advogado:   joao@silva-advogados.com.br / Joao@12345")
    print()
    print("  O Dev/Admin tem acesso a TODOS os paineis admin.")
    print("  O Advogado ve apenas Dashboard, Contratos, Analises.")
    print()
    print("  Para iniciar o servidor:")
    print("  python run_server.py --local")
    print()


if __name__ == "__main__":
    asyncio.run(seed())
