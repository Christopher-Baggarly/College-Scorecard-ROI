"""
End-to-End Demo: College Scorecard ROI Analysis Pipeline

Runs the full pipeline against the synthetic sample institution:
1. Load config
2. Try cache first; if miss, run targeted extraction on the raw federal CSV
3. Cache the extraction result
4. Calculate ROI metrics
5. Generate the executive PDF report
6. Print summary to console

Usage:
    python examples/run_analysis.py
"""

import os
import sys
import json


def main():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(repo_root)

    # Allow imports from src/
    sys.path.insert(0, os.path.join(repo_root, "src"))

    from extractor import grep_rows
    from cache import ExtractionCache
    from roi import calculate_roi
    from report import generate_report

    # ----- 1. Load config -----
    config_path = os.path.join(repo_root, "config", "analysis_config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    inst = config["institution"]
    extraction_cfg = config["extraction"]
    cache_cfg = config["cache"]

    print("=" * 70)
    print(f"College Scorecard ROI Analysis — {inst['name']}")
    print("=" * 70)

    # ----- 2. Cache check + extraction -----
    cache = ExtractionCache(
        cache_path=cache_cfg["cache_path"],
        ttl_days=cache_cfg["ttl_days"],
        force_refresh=cache_cfg["force_refresh"],
    )

    match_value = extraction_cfg["match_value"]
    extracted = cache.get(match_value)

    if extracted is None:
        print(f"\n[1/4] Cache miss for {match_value}. Running targeted extraction...")
        raw_path = os.path.join(repo_root, config["data_source"]["raw_csv_path"])
        if not os.path.exists(raw_path):
            print(f"\nERROR: Raw data file not found at:\n  {raw_path}")
            print("\nTo run this demo:")
            print("  1. Download the College Scorecard Institution-Level CSV from:")
            print("     https://collegescorecard.ed.gov/data/")
            print(f"  2. Place it at: {raw_path}")
            print(f"  3. Update config['extraction']['match_value'] to a real UNITID.")
            print("\n(Skipping to report generation with synthetic metrics instead.)")
            # Synthetic metrics for demo when raw file is absent
            extracted = {
                "INSTNM": inst["name"],
                "CONTROL": inst["control"],
                "PREDDEG": inst["predominant_degree"],
                "NPT4_PRIV": "28500",
                "DEBT_MDN": "12500",
                "EARN_MDN_HI_1YR": "38500",
                "EARN_MDN_HI_2YR": "42000",
                "EARN_MDN_HI_3YR": "46800",
            }
        else:
            extracted = grep_rows(
                filepath=raw_path,
                match_field=extraction_cfg["match_field"],
                match_value=match_value,
                fields_to_extract=extraction_cfg["fields_to_extract"],
                encoding=config["data_source"]["encoding"],
                delimiter=config["data_source"]["delimiter"],
            )
            if extracted is None:
                print(f"  [WARN] No match for UNITID {match_value} in {raw_path}")
                return 1
            print(f"  [OK] Extracted {len(extracted)} fields for {extracted.get('INSTNM', match_value)}")

        cache.set(match_value, extracted)
        cache.save()
        print(f"  [OK] Cached to {cache_cfg['cache_path']}")
    else:
        print(f"\n[1/4] Cache hit for {match_value}. Skipping extraction.")

    # ----- 3. Calculate ROI -----
    print("\n[2/4] Calculating ROI metrics...")
    metrics = calculate_roi(extracted, config)
    print(f"  Net Price: ${metrics.get('net_price') or 0:,.0f}")
    print(f"  Median Debt: ${metrics.get('median_debt_at_graduation') or 0:,.0f}")
    print(f"  Year-1 Earnings: ${metrics.get('earnings_1yr_post_entry') or 0:,.0f}")
    print(f"  Year-3 Earnings: ${metrics.get('earnings_3yr_post_entry') or 0:,.0f}")
    print(f"  CAGR: {metrics.get('cagr_pct') or 0:.2f}%")
    print(f"  Payback: {metrics.get('payback_period_years') or 'N/A'} years")
    print(f"  10-Year ROI Multiple: {metrics.get('roi_multiple_10yr') or 0:.2f}x")

    # ----- 4. Generate PDF -----
    print("\n[3/4] Generating executive PDF report...")
    output_path = generate_report(metrics, extracted, config)

    # ----- 5. Done -----
    print(f"\n[4/4] Complete.")
    print(f"\nReport saved to: {output_path}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())