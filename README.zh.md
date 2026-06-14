# 🚗 China Auto Trends · 中国汽车趋势追踪

**用代码和数据追踪中国汽车行业，而非人云亦云。**

[![Weekly Scrape](https://github.com/CHANGEME/china-auto-trends/actions/workflows/scrape-weekly.yml/badge.svg)](https://github.com/CHANGEME/china-auto-trends/actions/workflows/scrape-weekly.yml)
[![License: CC BY 4.0](https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![Data Updated](https://img.shields.io/badge/data-weekly-brightgreen)]()

---

## 为什么需要这个仓库

2026年的中国新能源汽车市场：

- 每 **12.9 小时**上市一款新车
- 销量 **TOP10 全部是新能源**，燃油车首次跌出前十
- **100+ 品牌**混战，行业利润率仅 2.9%
- 智驾算法工程师**供需比 0.38**，顶薪 200 万+

媒体在写故事，券商在卖报告，但没有人在做一件事：**用可复现的代码管线，持续追踪一手数据，并从一个懂技术的人的角度给出分析。** 这个仓库补这个缺。

---

## 仓库结构

```
china-auto-trends/
├── data/                   # 结构化 CSV（月度快照）
│   ├── sales/              #   车型销量排行
│   └── brands/             #   品牌/厂商销量排行
├── charts/                 # 自动生成的月报 + JSON 摘要
├── analysis/               # 深度分析文章（中英双语）
├── scripts/
│   ├── scrape_sales.py     # 核心爬虫（xl.16888.com）
│   └── generate_charts.py  # 报表与统计生成
├── .github/workflows/      # 每周自动抓取
└── README.md
```

---

## 快速开始

```bash
git clone https://github.com/CHANGEME/china-auto-trends.git
cd china-auto-trends

pip install -r requirements.txt

# 抓取最新销量数据
python scripts/scrape_sales.py

# 生成月报
python scripts/generate_charts.py
```

**使用代理**（国内环境）：

```bash
export HTTPS_PROXY=http://127.0.0.1:7890
python scripts/scrape_sales.py
```

---

## 核心指标

| 指标 | 当前值 (2026-05) | 趋势 |
|------|-----------------|------|
| TOP50 新能源占比 | ~85% | ↑ |
| 比亚迪品牌份额 | 10.84% | → |
| 月新车上市数 | ~55 | ↑ |
| 行业利润率 | 2.9% | ↓ |
| 新能源渗透率 | ~62% | ↑ |

---

## 深度分析

- [山寨机 → 新能源车：历史的押韵与分歧](analysis/shanzhai-to-nev.md)

---

## 路线图

- [x] 自动化销量抓取（每周 GitHub Actions）
- [x] 自动生成月报
- [ ] 历史数据回填（2020-2025）
- [ ] 新能源/燃油车细分类
- [ ] 新车上市追踪（工信部数据）
- [ ] 智驾功能矩阵
- [ ] 出口价格监控
- [ ] 交互式 Dashboard（GitHub Pages）

---

## 目标读者

- **行业分析师** — 用结构化数据替代 PDF 报告
- **投资者** — 在共识形成前追踪份额变化
- **CS/工程师** — 理解软件岗位会流向哪里
- **国内购车者** — 判断哪些品牌5年后还会活着

---

## License

代码: MIT · 数据与分析: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)

**作者:** 浙江大学计算机直博生，从技术视角追踪汽车行业。

---

⭐ **Star 这个仓库**，让更多人发现这些数据。
