"""
Executive ROI Report Generator

Produces a publication-quality PDF report from calculated ROI metrics
plus the original extracted federal data. Embeds three matplotlib
charts as PNG buffers and lays them into a ReportLab document.

Charts:
1. Net Price vs Median Earnings — bar chart comparing investment
   to early-career earnings
2. Earnings Trajectory — line chart of 1/2/3-year post-entry earnings
   with projected 10-year CAGR curve
3. Benchmark Comparison — bar chart showing institution vs national
   and regional median earnings
"""

import io
import os
from typing import Dict, Any

import matplotlib
matplotlib.use("Agg")  # Headless rendering — no display required
import matplotlib.pyplot as plt
import numpy as np

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table,
    TableStyle, Image, PageBreak,
)


def _chart_net_price_vs_earnings(metrics: Dict[str, Any], primary_hex: str) -> bytes:
    """Chart 1: Net price vs 1/2/3-year median earnings."""
    fig, ax = plt.subplots(figsize=(7, 3.5), dpi=150)

    labels = ["Net Price\n(4-Year)", "Median Earnings\nYear 1", "Year 2", "Year 3"]
    values = [
        metrics.get("net_price") or 0,
        metrics.get("earnings_1yr_post_entry") or 0,
        metrics.get("earnings_2yr_post_entry") or 0,
        metrics.get("earnings_3yr_post_entry") or 0,
    ]
    colors_list = [primary_hex, "#27AE60", "#52BE80", "#7DCEA0"]

    bars = ax.bar(labels, values, color=colors_list, edgecolor="white", linewidth=1.2)
    ax.set_ylabel("USD ($)", fontsize=9)
    ax.set_title("Net Price vs Median Earnings Trajectory",
                 fontsize=11, fontweight="bold", color=primary_hex)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda x, p: f"${x:,.0f}")
    )

    for bar, v in zip(bars, values):
        if v > 0:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(values) * 0.01,
                    f"${v:,.0f}", ha="center", va="bottom", fontsize=8, fontweight="bold")

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _chart_earnings_projection(metrics: Dict[str, Any], primary_hex: str) -> bytes:
    """Chart 2: 1/2/3-year actual + 10-year CAGR projection."""
    fig, ax = plt.subplots(figsize=(7, 3.5), dpi=150)

    actual_years = [1, 2, 3]
    actual_values = [
        metrics.get("earnings_1yr_post_entry"),
        metrics.get("earnings_2yr_post_entry"),
        metrics.get("earnings_3yr_post_entry"),
    ]
    actual_clean = [v if v is not None else None for v in actual_values]

    cagr = metrics.get("earnings_cagr_3yr")
    base_earn = metrics.get("earnings_3yr_post_entry") or metrics.get("earnings_1yr_post_entry")

    proj_years = list(range(4, 11))
    proj_values = []
    if base_earn and cagr:
        for y in proj_years:
            proj_values.append(base_earn * ((1 + cagr) ** (y - 3)))
    else:
        proj_values = [base_earn] * len(proj_years) if base_earn else []

    all_years = actual_years + proj_years
    all_values_actual = actual_clean + [None] * len(proj_years)
    all_values_proj = [None] * len(actual_years) + proj_values

    ax.plot([y for y, v in zip(all_years, all_values_actual) if v is not None],
            [v for v in all_values_actual if v is not None],
            marker="o", linewidth=2, color=primary_hex, label="Actual (Federal Data)")

    if proj_values:
        ax.plot([y for y, v in zip(all_years, all_values_proj) if v is not None],
                [v for v in all_values_proj if v is not None],
                marker="s", linewidth=2, linestyle="--",
                color="#F39C12", label=f"Projected (CAGR {metrics.get('cagr_pct', 0):.2f}%)")

    ax.set_xlabel("Years Post-Entry", fontsize=9)
    ax.set_ylabel("Median Annual Earnings ($)", fontsize=9)
    ax.set_title("Earnings Trajectory: Actual + 10-Year CAGR Projection",
                 fontsize=11, fontweight="bold", color=primary_hex)
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(linestyle="--", alpha=0.4)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"${x:,.0f}"))
    ax.set_xticks(range(1, 11))

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _chart_benchmark_comparison(
    metrics: Dict[str, Any], config: Dict[str, Any], primary_hex: str
) -> bytes:
    """Chart 3: Institution 1-year median vs national + regional benchmark."""
    fig, ax = plt.subplots(figsize=(7, 3), dpi=150)

    earn_1yr = metrics.get("earnings_1yr_post_entry") or 0
    national = config["roi"].get("national_median_earnings_1yr", 35000)
    regional = config["roi"].get("regional_median_earnings_1yr", 32000)

    labels = ["Institution\n(Year 1)", "Regional\nMedian", "National\nMedian"]
    values = [earn_1yr, regional, national]
    bar_colors = [primary_hex, "#85C1E9", "#A9DFBF"]

    bars = ax.barh(labels, values, color=bar_colors, edgecolor="white", linewidth=1.2)
    ax.set_xlabel("USD ($)", fontsize=9)
    ax.set_title("Year-1 Earnings: Institution vs National & Regional Benchmarks",
                 fontsize=11, fontweight="bold", color=primary_hex)
    ax.grid(axis="x", linestyle="--", alpha=0.4)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"${x:,.0f}"))

    for bar, v in zip(bars, values):
        ax.text(bar.get_width() + max(values) * 0.01, bar.get_y() + bar.get_height() / 2,
                f"${v:,.0f}", va="center", fontsize=8, fontweight="bold")

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _fmt_dollar(v, prefix="$", na="N/A"):
    if v is None:
        return na
    return f"{prefix}{v:,.0f}"


def _fmt_pct(v, decimals=2, na="N/A"):
    if v is None:
        return na
    return f"{v:.{decimals}f}%"


def _fmt_ratio(v, na="N/A"):
    if v is None:
        return na
    return f"{v:.2f}x"


def generate_report(
    metrics: Dict[str, Any],
    extracted_row: Dict[str, Any],
    config: Dict[str, Any],
) -> str:
    """
    Build the executive ROI PDF. Returns the output file path.

    Layout:
        Page 1: Title block + executive summary metrics table
        Page 2: Net Price vs Earnings chart + Payback & ROI summary
        Page 3: Earnings Trajectory chart + Benchmark comparison chart
    """
    inst = config["institution"]
    report_cfg = config["report"]
    primary = report_cfg["primary_brand_color_hex"]
    accent = report_cfg["accent_color_hex"]

    primary_color = colors.HexColor(primary)
    accent_color = colors.HexColor(accent)
    dark = colors.HexColor("#333333")
    light_bg = colors.HexColor("#F4F6F9")

    os.makedirs(report_cfg["output_path"], exist_ok=True)
    filename = report_cfg["filename_template"].format(
        institution_name=inst["name"].replace(" ", "_").replace(",", "")
    )
    output_path = os.path.join(report_cfg["output_path"], filename)

    doc = SimpleDocTemplate(
        output_path, pagesize=letter,
        leftMargin=54, rightMargin=54, topMargin=54, bottomMargin=54,
    )
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle(
        "Title", fontName="Helvetica-Bold", fontSize=20, leading=24,
        textColor=colors.white, alignment=1, spaceAfter=4,
    )
    sub_style = ParagraphStyle(
        "Sub", fontName="Helvetica-Bold", fontSize=12, leading=15,
        textColor=accent_color, alignment=1, spaceAfter=6,
    )
    section_style = ParagraphStyle(
        "Section", fontName="Helvetica-Bold", fontSize=14, leading=18,
        textColor=primary_color, spaceBefore=12, spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "Body", fontName="Helvetica", fontSize=10, leading=14,
        textColor=dark,
    )
    th_style = ParagraphStyle(
        "TH", fontName="Helvetica-Bold", fontSize=9.5, leading=12,
        textColor=colors.white, alignment=1,
    )
    td_style = ParagraphStyle(
        "TD", fontName="Helvetica", fontSize=9.5, leading=12,
        textColor=dark, alignment=1,
    )
    td_left = ParagraphStyle(
        "TDLeft", fontName="Helvetica", fontSize=9.5, leading=12,
        textColor=dark, alignment=0,
    )
    note_style = ParagraphStyle(
        "Note", fontName="Helvetica-Oblique", fontSize=8.5, leading=11,
        textColor=colors.HexColor("#555555"),
    )

    # ---------------- PAGE 1: COVER + EXECUTIVE METRICS ----------------

    header_table = Table(
        [[
            Paragraph("ROI ANALYSIS REPORT", title_style),
        ], [
            Paragraph(
                f"{inst['name']} ({inst.get('state', '')}) &bull; "
                f"{inst.get('control', '')} &bull; {inst.get('predominant_degree', '')}",
                sub_style,
            ),
        ]],
        colWidths=[500],
    )
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), primary_color),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 14))

    story.append(Paragraph("Executive Summary", section_style))
    story.append(Paragraph(
        f"This report benchmarks <b>{inst['name']}</b> against national and regional "
        f"medians using U.S. Department of Education College Scorecard data. It calculates "
        f"the institution's return on investment based on net price, median debt at "
        f"graduation, and post-entry earnings trajectory. All financial metrics are "
        f"derived from the federal source file; benchmarks and projection assumptions "
        f"are documented in the methodology appendix.",
        body_style,
    ))
    story.append(Spacer(1, 10))

    # Executive metrics table
    metrics_table = Table(
        [[
            Paragraph("Metric", th_style),
            Paragraph("Value", th_style),
            Paragraph("Benchmark", th_style),
        ], [
            Paragraph("<b>Net Price (4-Year)</b>", td_left),
            Paragraph(_fmt_dollar(metrics.get("net_price")), td_style),
            Paragraph("—", td_style),
        ], [
            Paragraph("<b>Median Debt at Graduation</b>", td_left),
            Paragraph(_fmt_dollar(metrics.get("median_debt_at_graduation")), td_style),
            Paragraph("—", td_style),
        ], [
            Paragraph("<b>Year-1 Median Earnings</b>", td_left),
            Paragraph(_fmt_dollar(metrics.get("earnings_1yr_post_entry")), td_style),
            Paragraph(_fmt_dollar(config["roi"].get("national_median_earnings_1yr")), td_style),
        ], [
            Paragraph("<b>Year-3 Median Earnings</b>", td_left),
            Paragraph(_fmt_dollar(metrics.get("earnings_3yr_post_entry")), td_style),
            Paragraph("—", td_style),
        ], [
            Paragraph("<b>Earnings CAGR (Yr 1 → Yr 3)</b>", td_left),
            Paragraph(_fmt_pct(metrics.get("cagr_pct")), td_style),
            Paragraph("—", td_style),
        ], [
            Paragraph("<b>Payback Period</b>", td_left),
            Paragraph(
                f"{metrics['payback_period_years']:.1f} yrs" if metrics.get("payback_period_years") else "N/A",
                td_style,
            ),
            Paragraph("—", td_style),
        ], [
            Paragraph("<b>10-Year ROI Multiple</b>", td_left),
            Paragraph(_fmt_ratio(metrics.get("roi_multiple_10yr")), td_style),
            Paragraph("—", td_style),
        ], [
            Paragraph("<b>Monthly Loan Payment (Std 10-Yr)</b>", td_left),
            Paragraph(
                _fmt_dollar(metrics.get("monthly_loan_payment_10yr_std")),
                td_style,
            ),
            Paragraph("—", td_style),
        ]],
        colWidths=[230, 140, 130],
    )
    metrics_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), primary_color),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9D9D9")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, light_bg]),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(metrics_table)
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "<i>Source: U.S. Department of Education College Scorecard, "
        "Institution-Level data file. " + config["data_source"].get("scorecard_year", "") + " vintage. "
        "Benchmark values are configurable in <code>analysis_config.json</code>.</i>",
        note_style,
    ))

    # ---------------- PAGE 2: NET PRICE VS EARNINGS CHART ----------------

    story.append(PageBreak())
    story.append(Paragraph("Net Price vs Median Earnings", section_style))
    story.append(Paragraph(
        "The chart below compares the institution's four-year net price (the total "
        "cost of attendance after grant aid) against the median earnings its former "
        "students report at one, two, and three years post-entry. If the year-three "
        "earnings bar exceeds the net price bar, the institution is delivering positive "
        "first-decade ROI on average.",
        body_style,
    ))
    story.append(Spacer(1, 8))

    chart1_bytes = _chart_net_price_vs_earnings(metrics, primary)
    chart1_img = Image(io.BytesIO(chart1_bytes), width=6.5 * inch, height=3.25 * inch)
    story.append(chart1_img)
    story.append(Spacer(1, 10))

    # Payback commentary box
    payback = metrics.get("payback_period_years")
    roi_mult = metrics.get("roi_multiple_10yr")
    if payback is not None and payback <= 5:
        payback_text = (
            f"<b>Strong Payback Profile:</b> At current earnings trajectory, graduates "
            f"recoup the full four-year net price within <b>{payback:.1f} years</b> of "
            f"entry-level employment. The 10-year ROI multiple is "
            f"<b>{_fmt_ratio(roi_mult)}</b>, indicating substantial lifetime earnings "
            f"return relative to educational investment."
        )
        box_bg = colors.HexColor("#E2F0D9")
        box_line = colors.HexColor("#385723")
    elif payback is not None and payback <= 10:
        payback_text = (
            f"<b>Moderate Payback Profile:</b> Graduates recoup net price within "
            f"<b>{payback:.1f} years</b>. The 10-year ROI multiple is "
            f"<b>{_fmt_ratio(roi_mult)}</b>. ROI is positive but margins are tighter "
            f"than the strong-profile case; financial aid packaging and career "
            f"placement support can materially improve outcomes."
        )
        box_bg = colors.HexColor("#FFF2CC")
        box_line = colors.HexColor("#D6B656")
    else:
        payback_text = (
            f"<b>Extended Payback Profile:</b> At current trajectory, payback "
            f"extends beyond 10 years ({payback:.1f} yrs projected). The 10-year ROI "
            f"multiple is <b>{_fmt_ratio(roi_mult)}</b>. This institution's ROI "
            f"depends heavily on continued earnings growth and aggressive loan "
            f"repayment strategy. Income-driven repayment plans (RAP, IBR) should "
            f"be prioritized in exit counseling."
        )
        box_bg = colors.HexColor("#FCE4D6")
        box_line = colors.HexColor("#C65911")

    payback_table = Table([[Paragraph(payback_text, body_style)]], colWidths=[500])
    payback_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), box_bg),
        ("BOX", (0, 0), (-1, -1), 1.2, box_line),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(payback_table)

    # ---------------- PAGE 3: TRAJECTORY + BENCHMARK ----------------

    story.append(PageBreak())
    story.append(Paragraph("Earnings Trajectory & Benchmark Comparison", section_style))

    if report_cfg.get("include_charts", True):
        chart2_bytes = _chart_earnings_projection(metrics, primary)
        chart2_img = Image(io.BytesIO(chart2_bytes), width=6.5 * inch, height=3.25 * inch)
        story.append(chart2_img)
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            f"The solid line shows actual median earnings reported by graduates at "
            f"years one, two, and three post-entry. The dashed line projects earnings "
            f"through year ten using the institution's actual three-year CAGR of "
            f"<b>{_fmt_pct(metrics.get('cagr_pct'))}</b>. A higher CAGR indicates "
            f"stronger early-career wage growth and improves long-term ROI materially.",
            body_style,
        ))
        story.append(Spacer(1, 12))

    if report_cfg.get("include_national_benchmark", True):
        chart3_bytes = _chart_benchmark_comparison(metrics, config, primary)
        chart3_img = Image(io.BytesIO(chart3_bytes), width=6.5 * inch, height=2.5 * inch)
        story.append(chart3_img)
        story.append(Spacer(1, 6))

    delta_natl = metrics.get("delta_vs_national_median_1yr")
    delta_reg = metrics.get("delta_vs_regional_median_1yr")
    benchmark_text = (
        f"<b>Benchmark Position:</b> Year-one median earnings are "
        f"<b>{_fmt_dollar(delta_natl)}</b> vs the national median and "
        f"<b>{_fmt_dollar(delta_reg)}</b> vs the regional median. "
        + (
            "Outperforming both benchmarks." if (delta_natl or 0) > 0 and (delta_reg or 0) > 0
            else "Trailing one or both benchmarks; placement and earnings-growth "
                 "interventions are recommended."
        )
    )
    benchmark_table = Table([[Paragraph(benchmark_text, body_style)]], colWidths=[500])
    benchmark_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), light_bg),
        ("BOX", (0, 0), (-1, -1), 1, primary_color),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(benchmark_table)
    story.append(Spacer(1, 8))

    story.append(Paragraph("Methodology & Caveats", section_style))
    story.append(Paragraph(
        "<b>Data source.</b> Raw fields are extracted from the U.S. Department of "
        "Education College Scorecard Institution-Level data file. The "
        "<code>extractor.py</code> module uses targeted line-by-line scanning to "
        "extract a single institution's row without loading the full file into memory, "
        "making the engine suitable for memory-constrained environments.<br/><br/>"
        "<b>ROI calculation.</b> Net price is sourced from the <code>NPT4_PRIV</code> "
        "or <code>NPT4_PUB</code> field based on institutional control. Payback period "
        "is computed as net price divided by the highest available post-entry earnings "
        "(year three if present, else year one). The 10-year ROI multiple sums "
        "actual reported earnings (years 1-3) and projected earnings (years 4-10) "
        "using the institution's actual three-year CAGR.<br/><br/>"
        "<b>Caveats.</b> Median earnings include both completers and non-completers. "
        "Some fields are privacy-suppressed in the federal source. Benchmark "
        "medians are configurable and should be updated against the most recent "
        "Bureau of Labor Statistics or Census figures for institutional use.",
        body_style,
    ))

    doc.build(story)
    return output_path