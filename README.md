# 🚗 China Auto Trends

**The open-source toolkit for tracking China's automotive industry with data, not opinions.**

[![Weekly Scrape](https://github.com/ChenyuHeee/china-auto-trends/actions/workflows/scrape-weekly.yml/badge.svg)](https://github.com/ChenyuHeee/china-auto-trends/actions/workflows/scrape-weekly.yml)
[![License: CC BY 4.0](https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![Data Updated](https://img.shields.io/badge/data-weekly-brightgreen)]()

---

## Why this exists / 为什么有这个仓库

China's NEV (New Energy Vehicle) market is the most dynamic auto market in the world. In 2026, a new car launches every **12.9 hours**. The top 10 best-selling models are **100% NEV**. Over 100 brands are competing — and most will die within 3 years.

This is a CS-trained observer's attempt to track this industry with:

- **Automated data pipelines** — raw sales numbers, not media narratives
- **Code-first analysis** — reproducible, version-controlled, transparent
- **Tech-aware commentary** — understanding the difference between real AI and marketing slides

> 中国新能源汽车市场是全球最激烈的汽车战场。2026年，每12.9小时就有一款新车上市，销量前十全部是新能源，100+品牌混战——大部分将在3年内消失。这是一个CS背景的观察者，用代码和数据追踪这个行业的尝试。

---

## What's inside / 仓库里有什么

```
china-auto-trends/
├── data/                   # Structured CSVs (monthly snapshots)
│   ├── sales/              #   Model-level sales ranking
│   └── brands/             #   Brand & manufacturer ranking
├── charts/                 # Auto-generated reports & JSON summaries
├── analysis/               # Deep-dive articles (bilingual)
├── scripts/
│   ├── scrape_sales.py     # Core scraper for xl.16888.com
│   └── generate_charts.py  # Report & stats generator
├── .github/workflows/      # Weekly automated scraping
└── README.md
```

---

## Quick start / 快速开始

```bash
# 1. Clone
git clone https://github.com/ChenyuHeee/china-auto-trends.git
cd china-auto-trends

# 2. Install
pip install -r requirements.txt

# 3. Scrape latest data
python scripts/scrape_sales.py

# 4. Generate report
python scripts/generate_charts.py
```

**With proxy** (if you're in mainland China):

```bash
export HTTPS_PROXY=http://127.0.0.1:7890
python scripts/scrape_sales.py
```

---

## Data sources / 数据来源

| Source | What | Update |
|--------|------|--------|
| [xl.16888.com](https://xl.16888.com) | Monthly sales ranking (models, brands, factories) | Weekly scrape |
| (planned) MIIT filings | New car registrations, specs | TBD |
| (planned) CPCA | Industry-level aggregates | TBD |

Data excludes imported vehicles. All raw CSVs in `data/` are free to use under CC BY 4.0.

---

## Key metrics to watch / 核心观测指标

| Metric | Current (2026-05) | Trend |
|--------|-------------------|-------|
| NEV share of top-50 models | ~85% | ↑ |
| Top brand (BYD) market share | 10.84% | → |
| Monthly new car launches | ~55 | ↑ |
| Industry profit margin | 2.9% | ↓ |
| NEV penetration (total market) | ~62% | ↑ |

---

## Featured analysis / 深度分析

- [山寨机 → 新能源车：历史的押韵与分歧](analysis/shanzhai-to-nev.md) — *How the 2008-2010 shanzhai phone boom-and-bust foreshadows today's NEV market, and why the ending will be different.*

---

## Roadmap / 路线图

- [x] Automated sales scraping (weekly via GitHub Actions)
- [x] Auto-generated monthly reports
- [ ] Historical data backfill (2020-2025)
- [ ] NEV vs ICE segmentation by model
- [ ] New car launch tracker (MIIT filings)
- [ ] Intelligent driving feature matrix
- [ ] Export price monitoring
- [ ] Interactive dashboard (GitHub Pages)

---

## Who this is for / 目标读者

- **Industry analysts** — structured data instead of PDF reports
- **Investors** — track market share shifts before consensus moves
- **CS/engineers** — understand where the software jobs are heading
- **Car buyers in China** — know which brands will still exist in 5 years

---

## Contributing / 贡献

Pull requests welcome! Areas where help is especially valuable:

- Additional data sources (dealership data, used car prices, insurance registrations)
- Better NEV/ICE classification heuristics
- Visualization improvements
- English translations of analysis articles

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

---

## License / 许可

Code: MIT · Data & Analysis: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)

**Author:** A CS PhD student at Zhejiang University, tracking the auto industry from a technologist's lens.

---

⭐ **Star this repo** if you find it useful — it helps more people discover the data.
