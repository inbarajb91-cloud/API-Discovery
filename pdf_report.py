"""PDF report generation for API Discovery Agent using ReportLab."""

import os
import tempfile
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)


def create_report(report_data: dict) -> str:
    """Create a PDF report and return the file path."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", prefix="api_discovery_")
    filepath = tmp.name
    tmp.close()

    doc = SimpleDocTemplate(
        filepath, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=20 * mm, bottomMargin=20 * mm,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    styles.add(ParagraphStyle(
        name="ReportTitle",
        parent=styles["Title"],
        fontSize=22,
        spaceAfter=6,
        textColor=colors.HexColor("#1a1a2e"),
    ))
    styles.add(ParagraphStyle(
        name="SectionHeader",
        parent=styles["Heading2"],
        fontSize=14,
        spaceBefore=16,
        spaceAfter=8,
        textColor=colors.HexColor("#16213e"),
        borderWidth=1,
        borderColor=colors.HexColor("#e2e8f0"),
        borderPadding=(0, 0, 4, 0),
    ))
    styles.add(ParagraphStyle(
        name="VerdictPass",
        parent=styles["Normal"],
        fontSize=16,
        textColor=colors.HexColor("#16a34a"),
        fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        name="VerdictPartial",
        parent=styles["Normal"],
        fontSize=16,
        textColor=colors.HexColor("#ca8a04"),
        fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        name="VerdictFail",
        parent=styles["Normal"],
        fontSize=16,
        textColor=colors.HexColor("#dc2626"),
        fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        name="BodyText2",
        parent=styles["Normal"],
        fontSize=10,
        spaceAfter=4,
        leading=14,
    ))

    elements = []

    # --- Title ---
    title = report_data.get("title", "API Discovery Report")
    elements.append(Paragraph(title, styles["ReportTitle"]))
    elements.append(Paragraph(
        f"Generated on {datetime.now().strftime('%B %d, %Y at %H:%M')}",
        styles["BodyText2"]
    ))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e2e8f0")))
    elements.append(Spacer(1, 12))

    # --- Executive Summary ---
    elements.append(Paragraph("Executive Summary", styles["SectionHeader"]))

    use_case = report_data.get("use_case", "N/A")
    target = report_data.get("target_system", "N/A")
    verdict = report_data.get("verdict", "N/A")
    confidence = report_data.get("confidence_score", 0)

    verdict_style = {
        "ACHIEVABLE": "VerdictPass",
        "PARTIALLY_ACHIEVABLE": "VerdictPartial",
        "NOT_ACHIEVABLE": "VerdictFail",
    }.get(verdict, "Normal")

    verdict_label = {
        "ACHIEVABLE": "ACHIEVABLE",
        "PARTIALLY_ACHIEVABLE": "PARTIALLY ACHIEVABLE",
        "NOT_ACHIEVABLE": "NOT ACHIEVABLE",
    }.get(verdict, verdict)

    summary_data = [
        ["Target System:", target],
        ["Use Case:", use_case],
        ["Verdict:", ""],  # verdict handled separately
        ["Confidence:", f"{int(confidence * 100)}%"],
    ]
    summary_table = Table(summary_data, colWidths=[120, 380])
    summary_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(f"Verdict: {verdict_label}", styles[verdict_style]))
    elements.append(Spacer(1, 12))

    # --- Endpoints Discovered ---
    endpoints = report_data.get("endpoints", [])
    if endpoints:
        elements.append(Paragraph("Endpoints Discovered", styles["SectionHeader"]))

        ep_header = ["Method", "Path", "Description", "Test Result", "Maps To"]
        ep_rows = [ep_header]
        for ep in endpoints:
            ep_rows.append([
                ep.get("method", ""),
                ep.get("path", ""),
                ep.get("description", "")[:50],
                ep.get("test_status", "N/A"),
                ep.get("maps_to", ""),
            ])

        ep_table = Table(ep_rows, colWidths=[50, 120, 140, 70, 120])
        ep_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ]))
        elements.append(ep_table)
        elements.append(Spacer(1, 12))

    # --- Capability Mapping ---
    cap_mapping = report_data.get("capability_mapping", [])
    if cap_mapping:
        elements.append(Paragraph("Capability Mapping", styles["SectionHeader"]))

        for cap in cap_mapping:
            capability = cap.get("capability", "")
            endpoint = cap.get("endpoint", "N/A")
            status = cap.get("status", "UNKNOWN")
            available = cap.get("available_fields", [])
            missing = cap.get("missing_fields", [])

            status_color = {"VERIFIED": "#16a34a", "PARTIAL": "#ca8a04", "MISSING": "#dc2626"}.get(status, "#6b7280")

            block = []
            block.append(Paragraph(
                f'<font color="{status_color}"><b>[{status}]</b></font> {capability}',
                styles["BodyText2"]
            ))
            block.append(Paragraph(f"&nbsp;&nbsp;&nbsp;Endpoint: <b>{endpoint}</b>", styles["BodyText2"]))
            if available:
                block.append(Paragraph(
                    f"&nbsp;&nbsp;&nbsp;Available fields: {', '.join(available[:10])}",
                    styles["BodyText2"]
                ))
            if missing:
                block.append(Paragraph(
                    f'&nbsp;&nbsp;&nbsp;<font color="#dc2626">Missing fields: {", ".join(missing)}</font>',
                    styles["BodyText2"]
                ))
            elements.append(KeepTogether(block))
            elements.append(Spacer(1, 4))

        elements.append(Spacer(1, 8))

    # --- Gaps ---
    gaps = report_data.get("gaps", [])
    if gaps:
        elements.append(Paragraph("Identified Gaps", styles["SectionHeader"]))
        for gap in gaps:
            elements.append(Paragraph(f'<font color="#dc2626">\u2022</font> {gap}', styles["BodyText2"]))
        elements.append(Spacer(1, 8))

    # --- Recommendations ---
    recommendations = report_data.get("recommendations", [])
    if recommendations:
        elements.append(Paragraph("Recommendations", styles["SectionHeader"]))
        for rec in recommendations:
            elements.append(Paragraph(f"\u2022 {rec}", styles["BodyText2"]))
        elements.append(Spacer(1, 8))

    # --- Footer ---
    elements.append(Spacer(1, 20))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e2e8f0")))
    elements.append(Paragraph(
        "Generated by API Discovery Agent | Powered by Claude AI",
        ParagraphStyle(
            name="Footer", parent=styles["Normal"],
            fontSize=8, textColor=colors.HexColor("#94a3b8"),
            alignment=1,
        )
    ))

    doc.build(elements)
    return filepath
