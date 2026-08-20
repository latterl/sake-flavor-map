#!/usr/bin/env python3
"""静的図の生成（研究・資料用）
fig1: さけのわ6軸マップ（丹後ハイライト＋銘柄ラベル）
fig2: 独立データ5軸マップ（丹後ハイライト）
fig3: PCA負荷量（どの軸がマップの方向を決めているか）
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

# 日本語フォント
for f in font_manager.findSystemFonts():
    if "NotoSansCJK" in f or "NotoSansJP" in f:
        font_manager.fontManager.addfont(f)
plt.rcParams["font.family"] = ["Noto Sans CJK JP", "sans-serif"]

C = dict(blue="#2a78d6", orange="#eb6834", aqua="#1baf7a",
         other="#c8c7c0", ink="#0b0b0b", sec="#52514e", muted="#898781",
         grid="#e1e0d9", surface="#fcfcfb")

ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / "analysis/figures"
FIG.mkdir(exist_ok=True)


def scatter_map(df, title, note, out, label_col=None):
    fig, ax = plt.subplots(figsize=(10, 7.2), dpi=150)
    fig.patch.set_facecolor(C["surface"]); ax.set_facecolor(C["surface"])
    other = df[~df.tango & df["rank"].isna()]
    famous = df[~df.tango & df["rank"].notna()]
    tango = df[df.tango]
    ax.scatter(other.umap_x, other.umap_y, s=9, c=C["other"], lw=0, alpha=0.8,
               label=f"その他（{len(other)}）")
    ax.scatter(famous.umap_x, famous.umap_y, s=16, c=C["orange"], lw=0.6,
               edgecolors=C["surface"], label=f"有名（人気Top100と一致, {len(famous)}）")
    ax.scatter(tango.umap_x, tango.umap_y, s=34, c=C["blue"], lw=0.8,
               edgecolors=C["surface"], label=f"丹後地域（{len(tango)}）", zorder=5)
    if label_col:
        # 簡易ラベル反発（y方向に最低間隔を確保）
        pts = tango[["umap_x", "umap_y", label_col]].values.tolist()
        pts.sort(key=lambda t: -t[1])
        placed = []
        for x, y, lb in pts:
            ty = y
            while any(abs(ty - py) < 0.55 and abs(x - px) < 2.6 for px, py in placed):
                ty -= 0.55
            placed.append((x, ty))
            ax.annotate(str(lb), (x, y), xytext=(x + 0.28, ty + 0.18),
                        fontsize=8.5, color=C["ink"],
                        arrowprops=dict(arrowstyle="-", lw=0.5, color=C["muted"])
                        if abs(ty - y) > 0.3 else None, zorder=6)
    ax.set_title(title, fontsize=12, color=C["ink"], loc="left")
    ax.text(0, -0.06, note, transform=ax.transAxes, fontsize=8, color=C["sec"])
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color(C["grid"])
    ax.legend(loc="upper right", fontsize=8.5, frameon=False, labelcolor=C["sec"])
    fig.tight_layout()
    fig.savefig(out, facecolor=C["surface"])
    plt.close(fig)
    print("wrote", out)


# fig1: さけのわ
df1 = pd.read_csv(ROOT / "analysis/sakenowa_features.csv")
scatter_map(
    df1,
    "全国の日本酒 味わいマップ（さけのわフレーバー6軸 → UMAP、銘柄単位 n=%d）" % len(df1),
    "データ提供:さけのわ (https://sakenowa.com)  6軸=華やか・芳醇・重厚・穏やか・ドライ・軽快（標準化後にUMAP射影）。軸自体に単位はない。",
    FIG / "fig1_sakenowa_umap.png", label_col="brand")

# fig2: 独立データ
df2 = pd.read_csv(ROOT / "analysis/specs_features.csv")
df2["label"] = df2.brand.fillna("")
scatter_map(
    df2,
    "全国の日本酒 スペックマップ（日本酒度など5軸 → UMAP、商品単位 n=%d）" % len(df2),
    "出典: sake_dataset v1 (github.com/yoichi1484/sake_dataset, MIT, 2020-03-12)。5軸=日本酒度・酸度・アミノ酸度・アルコール度数・精米歩合。",
    FIG / "fig2_specs_umap.png", label_col=None)

# fig3: PCA負荷量
from sklearn.decomposition import PCA
AX1 = ["f1", "f2", "f3", "f4", "f5", "f6"]
LB1 = ["華やか", "芳醇", "重厚", "穏やか", "ドライ", "軽快"]
Z1 = (df1[AX1] - df1[AX1].mean()) / df1[AX1].std(ddof=0)
p1 = PCA(2, random_state=42).fit(Z1)
AX2 = ["smv", "acidity", "amino", "alcohol", "polish"]
LB2 = ["日本酒度", "酸度", "アミノ酸度", "アルコール", "精米歩合"]
Z2 = (df2[AX2] - df2[AX2].mean()) / df2[AX2].std(ddof=0)
p2 = PCA(2, random_state=42).fit(Z2)

fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), dpi=150)
fig.patch.set_facecolor(C["surface"])
for ax, pca, labels, ttl in [
        (axes[0], p1, LB1, "さけのわ6軸のPCA負荷量"),
        (axes[1], p2, LB2, "スペック5軸のPCA負荷量")]:
    ax.set_facecolor(C["surface"])
    y = np.arange(len(labels))
    h = 0.34
    ax.barh(y + h/2 + 0.02, pca.components_[0], height=h, color=C["blue"],
            label="PC1（寄与率 %.0f%%）" % (100*pca.explained_variance_ratio_[0]))
    ax.barh(y - h/2 - 0.02, pca.components_[1], height=h, color=C["orange"],
            label="PC2（寄与率 %.0f%%）" % (100*pca.explained_variance_ratio_[1]))
    ax.axvline(0, color=C["grid"], lw=1)
    ax.set_yticks(y, labels, fontsize=9)
    ax.invert_yaxis()
    ax.set_title(ttl, fontsize=10.5, loc="left", color=C["ink"])
    ax.tick_params(colors=C["sec"], labelsize=8)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.legend(fontsize=8, frameon=False, labelcolor=C["sec"])
fig.tight_layout()
fig.savefig(FIG / "fig3_pca_loadings.png", facecolor=C["surface"])
print("wrote", FIG / "fig3_pca_loadings.png")
