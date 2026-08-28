# College Scorecard ROI Analytics Engine

### The Business Problem
Career-college leadership teams need a defensible answer to one recurring question: does our degree deliver positive lifetime ROI for our graduates? Today, that answer is usually assembled by hand — pulling federal data points from different sources, running a spreadsheet, eyeballing the result, and presenting a number with no auditable methodology behind it. Worse, the federal College Scorecard dataset is 100MB+ of wide-format CSV with thousands of columns, and most analysis attempts load the whole file into a dataframe — a non-starter for any environment without substantial RAM. This engine solves both problems: it ingests the federal file with constant memory, runs CAGR-based ROI modeling, and produces a publication-quality executive PDF that a CFO can hand to a board.

### The Architecture & Logic
This is a three-stage pipeline built around targeted extraction, read-through caching, and reportlab publication.

- **Memory-efficient extraction.** The `extractor.py` module scans the raw federal CSV one line at a time, parses only the columns required for the analysis, and short-circuits as soon as the target institution's row is found. Memory ceiling is one row (~5KB), regardless of dataset size. The module also exposes a batch variant (`grep_rows_multi`) for scanning multiple institutions in a single pass.

- **Read-through JSON cache.** The `cache.py` module wraps extraction results in a TTL-controlled JSON layer with atomic write semantics. Repeated runs against the same source file skip the scan entirely. Cache invalidation is configurable (`ttl_days`, `force_refresh`).

- **ROI calculation engine.** The `roi.py` module translates raw federal fields into business metrics: net price, median debt, payback period, three-year earnings CAGR, ten-year ROI multiple, and benchmark deltas against national and regional medians. All projection assumptions are configurable (`analysis_config.json`).

- **Publication-quality reporting.** The `report.py` module generates three embedded matplotlib charts (net price vs earnings, projected trajectory with CAGR curve, benchmark comparison) and lays them into a multi-page ReportLab PDF with executive summary, payback commentary, and methodology appendix.

### Standards Coverage
- **34 CFR Part 668** — federal student aid disclosure framework referenced for any loan-payment modeling included in ROI outputs
- **Higher Education Act Title IV** — institutional reporting context
- **College Scorecard data dictionary** — field name mapping (NPT4_PRIV, DEBT_MDN, EARN_MDN_HI_*) consistent with the official Department of Education documentation

### Sample Output
A pre-generated synthetic report is included in `samples/Sample_Career_College_ROI_Report.pdf`. The synthetic case study is a private for-profit Associate's-degree-granting institution in Georgia with net price $28,500, median debt $12,500, year-1 earnings $38,500, year-3 earnings $46,800, three-year CAGR 10.3%, and a 10-year ROI multiple of 9.4x. The report includes three embedded charts and an executive metrics table suitable for board-level presentation.

### Tech Stack
- **Python 3.10+** — runtime
- **Pandas / NumPy** — supporting data manipulation
- **Matplotlib (Agg backend)** — headless chart rendering for embedded publication
- **ReportLab** — multi-page PDF report assembly with executive formatting
- **JSON** — config and cache storage (no external database dependency)

### Repository Layout

 ├── README.md ├── requirements.txt ├── config/ │ └── analysis_config.json # Institution identity, field map, ROI assumptions, report branding ├── src/ │ ├── init.py │ ├── extractor.py # Targeted row extraction (constant memory) │ ├── cache.py # JSON read-through cache with atomic write │ ├── roi.py # CAGR, payback, ROI multiple calculation │ └── report.py # ReportLab + matplotlib executive PDF ├── data/ │ ├── raw/ # College Scorecard CSV (user-supplied; not in repo) │ └── cache/ # Extraction cache (gitignored) ├── examples/ │ └── run_analysis.py # End-to-end demo with synthetic case study └── samples/ └── Sample_Career_College_ROI_Report.pdf


### Quick Start
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. (Optional) Download the College Scorecard Institution-Level CSV
#    from https://collegescorecard.ed.gov/data/ and place it at
#    data/raw/College_Scorecard_Raw_Data/MERGED2019_20_PP.csv
#    Skip this step to run the demo against the synthetic case study.

# 3. Run the end-to-end demo
python examples/run_analysis.py

# 4. The PDF report lands at:
#    ./output/ROI_Reports/Sample_Career_College_ROI_Report.pdf




**** What This Engine Does Not Do****

This engine automates ROI calculation and executive report generation against a single institution. It does not:

Replace official institutional research methodology

Generate compliance filings (IPEDS, NSLDS, EADA)

Provide per-program granularity beyond what the federal source file offers

Run live web scraping — the College Scorecard file must be downloaded manually

The architectural decision was to automate the high-volume calculation and report-assembly work, and leave the institutional research judgment calls to humans.

**Author**

Built by Christopher Baggarly — Operations Architect with hands-on responsibility for institutional analytics, federal compliance reporting, and executive dashboard pipelines in higher education operations. Engineered to solve a recurring pain point (manual ROI benchmarking taking days, with no auditable methodology) while producing publication-grade output that survives board-level scrutiny.
