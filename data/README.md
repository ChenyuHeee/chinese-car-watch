# Data Schema / 数据格式

## Directory structure

```
data/
├── sales/{YYYY}/           # Model-level sales ranking
│   └── {YYYYMM}_style.csv  #   All models (NEV + ICE)
│   └── {YYYYMM}_ev.csv     #   EV-only ranking
├── brands/{YYYY}/          # Brand & manufacturer ranking
│   └── {YYYYMM}_brand.csv  #   Brand-level
│   └── {YYYYMM}_factory.csv #  Manufacturer-level
└── models/                 # (planned) New car launch tracker
```

## CSV format: sales ranking

`{YYYYMM}_style.csv` — Model-level sales

| Column | Type | Description |
|--------|------|-------------|
| `rank` | int | Sales ranking position |
| `name` | string | Model name (Chinese/English) |
| `sales` | int | Monthly sales units |
| `price_range` | string | MSRP range in 万元 (e.g. "6.48-9.48万") |
| `month` | string | Reporting month (YYYYMM) |
| `type` | string | Page type (`style`, `ev`, `brand`, `factory`) |
| `scraped_at` | ISO datetime | When data was collected |

`{YYYYMM}_ev.csv` — Same schema, EV-only ranking.

## CSV format: brand ranking

`{YYYYMM}_brand.csv`

| Column | Type | Description |
|--------|------|-------------|
| `rank` | int | Brand ranking position |
| `name` | string | Brand name |
| `sales` | int | Monthly brand sales |
| `price_range` | string | Market share (e.g. "10.84%") |
| `month` | string | Reporting month (YYYYMM) |
| `type` | string | `brand` or `factory` |
| `scraped_at` | ISO datetime | When data was collected |

## JSON summary format

`charts/summary-{YYYYMM}.json`

```json
{
  "month": "202605",
  "generated_at": "2026-06-14T...",
  "model_stats": {
    "total_rows": 50,
    "total_sales": 673773,
    "nev_sales": 448729,
    "nev_pct": 66.6,
    "ice_sales": 225044,
    "top10": [{"rank": "1", "name": "星愿", "sales": "38751"}, ...],
    "top_brands": [["比亚迪", 164971], ...]
  },
  "ev_stats": { ... },
  "brand_stats": { ... }
}
```

## Caveats / 注意事项

- Data excludes imported vehicles (per source: xl.16888.com)
- Sales numbers are manufacturer-reported, not insurance registrations
- NEV classification uses heuristics (see `generate_charts.py`) — not 100% accurate
- Monthly data is scraped weekly; the CSV always contains the latest snapshot for that month
