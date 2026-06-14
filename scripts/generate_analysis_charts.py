"""Generate charts for the Shanzhai-NEV analysis."""
import os
os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
from pathlib import Path

CHARTS_DIR = Path(__file__).resolve().parent.parent / "charts"
CHARTS_DIR.mkdir(exist_ok=True)

plt.rcParams.update({
    "font.family": "Heiti TC",
    "font.size": 12,
    "axes.titlesize": 14,
    "axes.labelsize": 12,
    "axes.unicode_minus": False,
})

# ── Chart 1: Profit Rate Comparison ──
fig, ax = plt.subplots(figsize=(10, 5))

# Shanzhai profit rates from documented sources
shanzhai_years = ["2006", "2007", "2008"]
shanzhai_profits = [15, 8, 3]  # estimated from "hundreds yuan → tens → single digits"
shanzhai_desc = ["人人赚钱", ">50% 赚钱", "<33% 赚钱"]

# NEV profit rates
nev_years = ["2024", "2025", "2026Q1"]
nev_profits = [4.3, 3.5, 2.9]

x1 = np.arange(len(shanzhai_years))
x2 = np.arange(len(nev_years))

bars1 = ax.bar(x1 - 0.2, shanzhai_profits, 0.35, color="#d97706", alpha=0.85, label="山寨手机 (2006-2008)")
bars2 = ax.bar(x2 + 0.2, nev_profits, 0.35, color="#1e40af", alpha=0.85, label="新能源车 (2024-2026)")

for bar, desc in zip(bars1, shanzhai_desc):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3, desc,
            ha="center", fontsize=10, color="#92400e")
for bar in bars2:
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3, f"{bar.get_height()}%",
            ha="center", fontsize=10, color="#1e40af")

ax.set_xticks(list(x1 - 0.2) + list(x2 + 0.2))
ax.set_xticklabels(shanzhai_years + nev_years)
ax.set_ylabel("行业利润率 (%)")
ax.set_title("行业利润率对比：山寨手机 vs 新能源车")
ax.legend(frameon=False)
ax.set_ylim(0, 20)
ax.grid(axis="y", alpha=0.2)
plt.tight_layout()
fig.savefig(CHARTS_DIR / "profit-comparison.png", dpi=150, bbox_inches="tight")
plt.close()
print("Chart 1 saved: profit-comparison.png")

# ── Chart 2: Market Concentration ──
fig, ax = plt.subplots(figsize=(10, 5))

industries = ["中国新能源车\n(2026)", "中国空调\n(2023)", "全球智能手机\n(2024)", "美国汽车\n(1950s)", "韩国汽车\n(2000s)"]
concentration = [27.3, 85, 71, 94, 92]
colors = ["#dc2626", "#059669", "#059669", "#059669", "#059669"]

bars = ax.barh(industries, concentration, color=colors, height=0.6)
for bar, val in zip(bars, concentration):
    ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height()/2, f"{val}%",
            va="center", fontweight="bold")

ax.set_xlabel("TOP5 市场份额 (%)")
ax.set_title("行业集中度对比")
ax.axvline(x=60, color="gray", linestyle="--", alpha=0.3, label="成熟行业通常 >60%")
ax.legend(frameon=False)
ax.set_xlim(0, 110)
ax.grid(axis="x", alpha=0.2)
plt.tight_layout()
fig.savefig(CHARTS_DIR / "concentration.png", dpi=150, bbox_inches="tight")
plt.close()
print("Chart 2 saved: concentration.png")

# ── Chart 3: Supplier Concentration ──
fig, ax = plt.subplots(figsize=(10, 5))

# Data from our SCEM
suppliers = ["宁德时代\n(电池)", "博世\n(底盘/制动)", "华为\n(智驾)", "弗迪电池\n(电池)", "地平线\n(芯片)", "联发科(MTK)\n(山寨机时代)"]
brands_served = [13, 8, 6, 5, 4, 4000]
colors2 = ["#1e40af"]*5 + ["#d97706"]

bars = ax.barh(suppliers, brands_served, color=colors2, height=0.6)
for bar, val in zip(bars, brands_served):
    label = f"{val} 品牌" if val < 100 else f"~{val} 厂商"
    ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2, label, va="center")

ax.set_xlabel("服务品牌/厂商数量")
ax.set_title("供应链集中度：谁在为行业「造铲子」")
ax.set_xlim(0, 20)
ax.grid(axis="x", alpha=0.2)
plt.tight_layout()
fig.savefig(CHARTS_DIR / "supplier-concentration.png", dpi=150, bbox_inches="tight")
plt.close()
print("Chart 3 saved: supplier-concentration.png")

# ── Chart 4: Financial Health Matrix ──
fig, ax = plt.subplots(figsize=(10, 6))

brands = ["比亚迪", "理想", "问界", "特斯拉", "长安", "一汽", "广汽", "小鹏", "蔚来"]
profits = [41, 11, 8, 30, 4, 0, -7, -15, -157]
margins = [18.8, 19.0, 26.2, 17.3, 14.1, 5.3, -0.9, 17.9, 11.1]
debts = [70.9, 52.2, 65.9, 39.6, 57.1, 67.5, 51.7, 69.5, 89.2]

colors3 = [(0.9, 0.1, 0.1) if p < 0 else (0.1, 0.6, 0.1) for p in profits]

scatter = ax.scatter(margins, profits, s=[d*3 for d in debts], c=colors3, alpha=0.7, edgecolors="white", linewidth=1)

for i, b in enumerate(brands):
    offset = 5 if b not in ["蔚来", "广汽"] else -12
    ax.annotate(b, (margins[i], profits[i]),
                textcoords="offset points", xytext=(0, offset),
                fontsize=11, ha="center")

ax.axhline(y=0, color="gray", linestyle="--", alpha=0.3)
ax.set_xlabel("毛利润率 (%)")
ax.set_ylabel("净利润 (亿)")
ax.set_title("财务健康矩阵：盈利 vs 亏损\n（气泡大小 = 负债率）")
ax.grid(alpha=0.2)
plt.tight_layout()
fig.savefig(CHARTS_DIR / "financial-matrix.png", dpi=150, bbox_inches="tight")
plt.close()
print("Chart 4 saved: financial-matrix.png")
