"""
ROI Analysis Engine for College Scorecard Data

Translates raw federal data into investment metrics:
- Net price (cost of attendance minus grant aid)
- Median debt at graduation
- Median earnings trajectory (1, 2, 3 years post-entry)
- Payback period (when cumulative earnings exceed net price)
- CAGR (compound annual growth rate on earnings)
- ROI multiple (lifetime earnings ratio vs net price)
- Benchmark delta vs national + regional median earnings
"""

import math
from typing import Dict, Any, Optional


def _to_float(v: Any) -> Optional[float]:
    """Convert College Scorecard string values to float; None if missing."""
    if v is None:
        return None
    try:
        return float(str(v).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def _classify_institution(row: Dict[str, Any], control: str) -> Optional[float]:
    """Pick the correct net price column based on public/private control."""
    control_lower = (control or "").lower()
    if "public" in control_lower:
        return _to_float(row.get("NPT4_PUB"))
    return _to_float(row.get("NPT4_PRIV"))


def calculate_roi(
    extracted_row: Dict[str, Any],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Main ROI calculation. Input: a single institution's extracted row
    plus the ROI assumptions from analysis_config.json. Output: a dict
    of calculated metrics ready for the PDF report.
    """
    roi_cfg = config["roi"]

    control = extracted_row.get("CONTROL") or config["institution"].get("control", "")
    net_price = _classify_institution(extracted_row, control)
    median_debt = _to_float(extracted_row.get("DEBT_MDN"))

    earn_1yr = _to_float(extracted_row.get("EARN_MDN_HI_1YR"))
    earn_2yr = _to_float(extracted_row.get("EARN_MDN_HI_2YR"))
    earn_3yr = _to_float(extracted_row.get("EARN_MDN_HI_3YR"))

    earnings_trajectory = [e for e in [earn_1yr, earn_2yr, earn_3yr] if e is not None]

    # CAGR on earnings (years 1 -> 3 if available)
    cagr = None
    if len(earnings_trajectory) >= 2:
        start = earnings_trajectory[0]
        end = earnings_trajectory[-1]
        years = len(earnings_trajectory) - 1
        if start > 0 and end > 0 and years > 0:
            cagr = ((end / start) ** (1.0 / years)) - 1

    # Payback period: how many years of earnings to clear net price
    payback_years = None
    if net_price and earnings_trajectory:
        annual_earn = earnings_trajectory[-1]
        if annual_earn > 0:
            payback_years = round(net_price / annual_earn, 1)

    # 10-year projection with CAGR applied to median 1-year earnings
    projection_10yr = None
    if earn_1yr and cagr is not None:
        projection_10yr = earn_1yr * ((1 + cagr) ** 10)
    elif earn_1yr:
        # Fall back to flat projection if CAGR unavailable
        projection_10yr = earn_1yr * 10

    # ROI multiple: cumulative earnings over horizon vs net price
    roi_multiple = None
    if net_price and earnings_trajectory and projection_10yr:
        cumulative_10yr = sum(earnings_trajectory) + (
            projection_10yr - earnings_trajectory[-1]
        )
        roi_multiple = round(cumulative_10yr / net_price, 2)

    # Monthly loan payment (Standard 10-Year plan)
    monthly_loan_payment = None
    if median_debt and roi_cfg.get("loan_interest_rate_annual"):
        r = roi_cfg["loan_interest_rate_annual"] / 12.0
        n = roi_cfg.get("loan_repayment_term_years", 10) * 12
        if r > 0:
            monthly_loan_payment = median_debt * (
                (r * ((1 + r) ** n)) / (((1 + r) ** n) - 1)
            )

    # Benchmark deltas vs national and regional median earnings
    national_median = roi_cfg.get("national_median_earnings_1yr", 35000)
    regional_median = roi_cfg.get("regional_median_earnings_1yr", 32000)

    delta_vs_national = None
    delta_vs_regional = None
    if earn_1yr:
        delta_vs_national = earn_1yr - national_median
        delta_vs_regional = earn_1yr - regional_median

    return {
        "net_price": net_price,
        "median_debt_at_graduation": median_debt,
        "earnings_1yr_post_entry": earn_1yr,
        "earnings_2yr_post_entry": earn_2yr,
        "earnings_3yr_post_entry": earn_3yr,
        "earnings_cagr_3yr": cagr,
        "cagr_pct": round(cagr * 100, 2) if cagr is not None else None,
        "payback_period_years": payback_years,
        "projection_10yr_earnings": projection_10yr,
        "roi_multiple_10yr": roi_multiple,
        "monthly_loan_payment_10yr_std": monthly_loan_payment,
        "delta_vs_national_median_1yr": delta_vs_national,
        "delta_vs_regional_median_1yr": delta_vs_regional,
    }