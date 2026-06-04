"""
LegalShield AI 2026 — Report Generator
Geração de relatórios PDF profissionais a partir dos resultados de análise.
"""

import io
import logging
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)

from .analysis_engine import AnalysisResult
from .prompt_templates import MODE_DESCRIPTIONS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cores do tema
# ---------------------------------------------------------------------------
BRAND_DARK = colors.HexColor("#0F172A")
BRAND_PRIMARY = colors.HexColor("#3B82F6")
BRAND_DANGER = colors.HexColor("#EF4444")
BRAND_WARNING = colors.HexColor("#F59E0B")
BRAND_SUCCESS = colors.HexColor("#10B981")
BRAND_INFO = colors.HexColor("#6366F1")
BRAND_LIGHT_BG = colors.HexColor("#F8FAFC")
BRAND_BORDER = colors.HexColor("#E2E8F0")

SEVERITY_COLORS = {
    "CRÍTICO": BRAND_DANGER,
    "ALTO": colors.HexColor("#F97316"),
    "MÉDIO": BRAND_WARNING,
    "BAIXO": BRAND_SUCCESS,
}


def _get_styles() -> dict:
    """Retorna estilos customizados para o relatório."""
    base = getSampleStyleSheet()
    styles = {}

    styles["Title"] = ParagraphStyle(
        "CustomTitle",
        parent=base["Title"],
        fontSize=24,
        textColor=BRAND_DARK,
        spaceAfter=6 * mm,
        alignment=TA_CENTER,
    )
    styles["Subtitle"] = ParagraphStyle(
        "CustomSubtitle",
        parent=base["Normal"],
        fontSize=12,
        textColor=colors.HexColor("#64748B"),
        alignment=TA_CENTER,
        spaceAfter=10 * mm,
    )
    styles["Heading"] = ParagraphStyle(
        "CustomHeading",
        parent=base["Heading1"],
        fontSize=16,
        textColor=BRAND_PRIMARY,
        spaceBefore=8 * mm,
        spaceAfter=4 * mm,
    )
    styles["SubHeading"] = ParagraphStyle(
        "CustomSubHeading",
        parent=base["Heading2"],
        fontSize=13,
        textColor=BRAND_DARK,
        spaceBefore=5 * mm,
        spaceAfter=3 * mm,
    )
    styles["Body"] = ParagraphStyle(
        "CustomBody",
        parent=base["Normal"],
        fontSize=10,
        textColor=BRAND_DARK,
        alignment=TA_JUSTIFY,
        spaceAfter=3 * mm,
        leading=14,
    )
    styles["Small"] = ParagraphStyle(
        "CustomSmall",
        parent=base["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#94A3B8"),
    )
    styles["Finding"] = ParagraphStyle(
        "CustomFinding",
        parent=base["Normal"],
        fontSize=10,
        textColor=BRAND_DARK,
        leftIndent=5 * mm,
        spaceAfter=2 * mm,
        leading=13,
    )
    return styles


def _header_footer(canvas, doc):
    """Desenha cabeçalho e rodapé em cada página."""
    canvas.saveState()

    # Header: linha azul
    canvas.setStrokeColor(BRAND_PRIMARY)
    canvas.setLineWidth(2)
    canvas.line(2 * cm, A4[1] - 1.5 * cm, A4[0] - 2 * cm, A4[1] - 1.5 * cm)

    canvas.setFont("Helvetica-Bold", 8)
    canvas.setFillColor(BRAND_PRIMARY)
    canvas.drawString(2 * cm, A4[1] - 1.3 * cm, "LEGALSHIELD AI 2026")

    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#94A3B8"))
    canvas.drawRightString(
        A4[0] - 2 * cm, A4[1] - 1.3 * cm, "CONFIDENCIAL"
    )

    # Footer
    canvas.setStrokeColor(BRAND_BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(2 * cm, 1.5 * cm, A4[0] - 2 * cm, 1.5 * cm)

    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#94A3B8"))
    canvas.drawString(2 * cm, 1 * cm, "Gerado automaticamente por LegalShield AI")
    canvas.drawRightString(
        A4[0] - 2 * cm,
        1 * cm,
        f"Página {canvas.getPageNumber()}",
    )

    canvas.restoreState()


def generate_pdf_report(result: AnalysisResult) -> bytes:
    """
    Gera relatório PDF profissional a partir de um AnalysisResult.

    Args:
        result: Resultado da análise jurídica.

    Returns:
        Bytes do PDF gerado.
    """
    buffer = io.BytesIO()
    styles = _get_styles()

    # Configurar documento
    doc = BaseDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    frame = Frame(
        doc.leftMargin,
        doc.bottomMargin,
        doc.width,
        doc.height,
        id="main",
    )
    template = PageTemplate(
        id="main",
        frames=frame,
        onPage=_header_footer,
    )
    doc.addPageTemplates([template])

    # Construir conteúdo
    elements = []

    # === CAPA ===
    elements.append(Spacer(1, 3 * cm))
    elements.append(Paragraph("RELATÓRIO DE ANÁLISE JURÍDICA", styles["Title"]))
    elements.append(
        Paragraph(
            result.mode_description or MODE_DESCRIPTIONS.get(result.mode, ""),
            styles["Subtitle"],
        )
    )
    elements.append(Spacer(1, 1 * cm))

    # Info do documento
    info_data = [
        ["Documento:", result.filename],
        ["Tipo:", result.file_type.upper()],
        ["Páginas:", str(result.page_count)],
        ["OCR:", "Sim" if result.ocr_used else "Não"],
        ["Data:", result.timestamp.strftime("%d/%m/%Y %H:%M UTC")],
        ["ID Análise:", result.analysis_id],
    ]
    info_table = Table(info_data, colWidths=[4 * cm, 10 * cm])
    info_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("TEXTCOLOR", (0, 0), (0, -1), BRAND_PRIMARY),
                ("TEXTCOLOR", (1, 0), (1, -1), BRAND_DARK),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    elements.append(info_table)
    elements.append(PageBreak())

    # === RESUMO EXECUTIVO ===
    elements.append(Paragraph("Resumo Executivo", styles["Heading"]))
    if result.resumo_executivo:
        elements.append(Paragraph(result.resumo_executivo, styles["Body"]))
    else:
        elements.append(
            Paragraph(
                "<i>Resumo não disponível no formato estruturado.</i>",
                styles["Body"],
            )
        )

    # Score de Risco
    elements.append(Spacer(1, 5 * mm))
    score_color = (
        BRAND_DANGER if result.score_risco >= 70
        else BRAND_WARNING if result.score_risco >= 40
        else BRAND_SUCCESS
    )
    score_text = f"Score de Risco: <font color='{score_color}'><b>{result.score_risco}/100</b></font>"
    elements.append(Paragraph(score_text, styles["SubHeading"]))

    # === ESTATÍSTICAS ===
    elements.append(Paragraph("Estatísticas", styles["Heading"]))
    stats = result.estatisticas
    stats_data = [
        ["Total", "Críticos", "Altos", "Médios", "Baixos"],
        [
            str(stats.total_achados),
            str(stats.criticos),
            str(stats.altos),
            str(stats.medios),
            str(stats.baixos),
        ],
    ]
    stats_table = Table(stats_data, colWidths=[3 * cm] * 5)
    stats_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BRAND_DARK),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, BRAND_BORDER),
                ("BACKGROUND", (1, 1), (1, 1), colors.HexColor("#FEE2E2")),
                ("BACKGROUND", (2, 1), (2, 1), colors.HexColor("#FEF3C7")),
                ("BACKGROUND", (3, 1), (3, 1), colors.HexColor("#FEF9C3")),
                ("BACKGROUND", (4, 1), (4, 1), colors.HexColor("#D1FAE5")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    elements.append(stats_table)

    # === ACHADOS DETALHADOS ===
    if result.achados:
        elements.append(PageBreak())
        elements.append(Paragraph("Achados Detalhados", styles["Heading"]))

        for achado in result.achados:
            sev_color = SEVERITY_COLORS.get(achado.severidade, BRAND_INFO)

            # Cabeçalho do achado
            header = (
                f"<font color='{sev_color}'>[{achado.severidade}]</font> "
                f"<b>{achado.titulo}</b>"
            )
            elements.append(Paragraph(header, styles["SubHeading"]))

            if achado.clausula:
                elements.append(
                    Paragraph(
                        f"<b>Cláusula:</b> {achado.clausula}",
                        styles["Finding"],
                    )
                )

            elements.append(
                Paragraph(
                    f"<b>Descrição:</b> {achado.descricao}",
                    styles["Finding"],
                )
            )

            if achado.fundamentacao_legal:
                elements.append(
                    Paragraph(
                        f"<b>Fundamentação Legal:</b> {achado.fundamentacao_legal}",
                        styles["Finding"],
                    )
                )

            if achado.recomendacao:
                elements.append(
                    Paragraph(
                        f"<b>Recomendação:</b> {achado.recomendacao}",
                        styles["Finding"],
                    )
                )

            if achado.impacto_financeiro:
                elements.append(
                    Paragraph(
                        f"<b>Impacto Financeiro:</b> {achado.impacto_financeiro}",
                        styles["Finding"],
                    )
                )

            elements.append(Spacer(1, 3 * mm))

    # === SEGURANÇA ===
    if result.injection_detected:
        elements.append(Paragraph("⚠️ Alertas de Segurança", styles["Heading"]))
        elements.append(
            Paragraph(
                "<b>ATENÇÃO:</b> Foram detectadas tentativas de injeção de prompt "
                "neste documento. O texto foi sanitizado antes da análise.",
                styles["Body"],
            )
        )
        for threat in result.threats_found:
            elements.append(
                Paragraph(f"• {threat}", styles["Finding"])
            )

    # === METADADOS ===
    elements.append(Spacer(1, 1 * cm))
    elements.append(
        Paragraph(
            f"<i>Hash SHA-256 do documento: {result.document_hash}</i>",
            styles["Small"],
        )
    )
    if result.token_usage:
        elements.append(
            Paragraph(
                f"<i>Tokens: {result.token_usage.total_tokens} | "
                f"Modelo: {result.token_usage.model_used} | "
                f"Custo: ${result.token_usage.cost_estimate_usd:.4f}</i>",
                styles["Small"],
            )
        )

    # Build PDF
    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    logger.info(
        "Relatório PDF gerado",
        extra={
            "analysis_id": result.analysis_id,
            "pdf_size_kb": len(pdf_bytes) // 1024,
        },
    )

    return pdf_bytes
