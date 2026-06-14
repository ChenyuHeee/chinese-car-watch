# Contributing to Chinese Car Watch

Thanks for your interest! This project tracks China's auto industry through open data and code.

## Ways to contribute

### Add a data source

The most impactful contribution is adding new scrapers. Good candidates:

- **MIIT new car filings** — every new model must be registered before production. This gives a 3-6 month leading indicator of launches.
- **Used car prices** — depreciating NEV values are a key signal.
- **Insurance registration data** — more accurate than manufacturer-reported sales.
- **Export port data** — track China's auto export surge.

To add a scraper:

1. Create `scripts/scrape_<source>.py` following the pattern in `scrape_sales.py`
2. Add configuration to `PAGES` or a new registry
3. Update `.github/workflows/scrape-weekly.yml` to run it

### Improve NEV classification

The current heuristic (keyword matching in `generate_charts.py`) is crude. A better approach might:

- Maintain a curated list of NEV-only nameplates
- Parse MIIT filings for powertrain type
- Use the 16888 EV page as ground truth

### Translate analysis

All analysis articles live in `analysis/`. We aim for bilingual (zh + en) versions. If you can translate an article, open a PR.

### Fix data quality issues

Sales data can have gaps (missing months, misclassified models). If you spot errors, open an issue with:

- The file path (e.g. `data/sales/2026/202605_style.csv`)
- The specific row(s) with issues
- What you think the correct value should be and why

## Setup

```bash
pip install -r requirements.txt
python scripts/scrape_sales.py
python scripts/generate_charts.py
```

## Guidelines

- Scrapers must include reasonable delays between requests (0.5s+).
- Don't commit `.env` files or credentials.
- Analysis articles should be grounded in the repo's own data where possible.
- PRs should include a brief explanation of what changed and why.

## License

By contributing, you agree that your contributions (code) will be licensed under MIT, and data/analysis under CC BY 4.0.
