#!/usr/bin/env python3
"""
パターン2（独立データ版）: sake_dataset (yoichi1484/sake_dataset, MIT, 2020-03-12版)
から商品単位の味スペック特徴量を作り、UMAP/PCAで2次元化して
アプリ用JSON (app/data_specs.json) と検証用CSVを出力する。

特徴量（5次元, z-score標準化）:
  - 日本酒度 (sake_meter_value.mean)
  - 酸度 (titratable_acidity.mean)
  - アミノ酸度 (amino_acid_content.mean)
  - アルコール度数 (alcohol_rate.mean)
  - 精米歩合 (rice_polishing_rate)
甘辛度 (dgree_of_sweetness/dryness) は日本酒度・酸度から導出される派生値のため
特徴量から除外し、表示用のみに保持する。

出典: https://github.com/yoichi1484/sake_dataset
"""
import json, re, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data/sake_dataset/json/sake_dataset_v1.json"
TANGO = ROOT / "data/tango_breweries.json"
OUT_JSON = ROOT / "app/data_specs.json"
OUT_CSV = ROOT / "analysis/specs_features.csv"

FEATURES = ["smv", "acidity", "amino", "alcohol", "polish"]
FEATURE_LABELS = {"smv": "日本酒度", "acidity": "酸度", "amino": "アミノ酸度",
                  "alcohol": "アルコール度数", "polish": "精米歩合"}

def fnum(x):
    """'11.00' → 11.0, '' → nan. dict{mean,...} は mean を使う"""
    if isinstance(x, dict):
        x = x.get("mean", "")
    if x is None:
        return np.nan
    s = str(x).strip().replace("％", "").replace("%", "")
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group()) if m else np.nan

def main():
    raw = json.load(open(SRC))
    date = raw.get("YYYY-MM-DD", "unknown")
    ds = raw["dataset"]
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from region_assign import assign_region

    rows = []
    for r in ds:
        pref = (r.get("prefecture") or "").strip()
        muni, reg = assign_region(pref, (r.get("city") or "").strip())
        rows.append({
            "brand": (r.get("brand") or "").strip(),
            "name": (r.get("name") or "").strip(),
            "brewer": (r.get("brewer") or "").strip(),
            "pref": pref,
            "city": muni or (r.get("city") or "").strip(),
            "reg": reg,
            "cls": (r.get("sake_class") or "").strip(),
            "rice_list": [x for x in (r.get("rice") or []) if x],
            "smv": fnum(r.get("sake_meter_value")),
            "acidity": fnum(r.get("titratable_acidity")),
            "amino": fnum(r.get("amino_acid_content")),
            "alcohol": fnum(r.get("alcohol_rate")),
            "polish": fnum(r.get("rice_polishing_rate")),
            "sweetness": fnum(r.get("dgree_of_sweetness/dryness")),
        })
    df = pd.DataFrame(rows)
    n0 = len(df)

    # 有名銘柄フラグ: さけのわランキングTop100と銘柄名の完全一致で付与
    # （さけのわ rankings.json / brands.json が data/sakenowa/ にある場合のみ）
    famous_by_name = {}
    sakenowa_dir = ROOT / "data/sakenowa"
    if (sakenowa_dir / "rankings.json").exists():
        rk = json.load(open(sakenowa_dir / "rankings.json"))
        snw_brands = {b["id"]: b["name"]
                      for b in json.load(open(sakenowa_dir / "brands.json"))["brands"]}
        for r in rk["overall"]:
            nm = snw_brands.get(r["brandId"])
            if nm:
                famous_by_name[nm] = r["rank"]
    df["rank"] = df.brand.map(famous_by_name)

    # 物理的にあり得ない値を欠損化（データ品質ガード）
    df.loc[(df.alcohol < 5) | (df.alcohol > 25), "alcohol"] = np.nan
    df.loc[(df.polish < 1) | (df.polish > 100), "polish"] = np.nan
    df.loc[(df.smv < -100) | (df.smv > 30), "smv"] = np.nan
    df.loc[(df.acidity <= 0) | (df.acidity > 6), "acidity"] = np.nan
    df.loc[(df.amino <= 0) | (df.amino > 6), "amino"] = np.nan

    # 5特徴のうち3つ以上欠損している商品は除外、残りは中央値補完
    miss = df[FEATURES].isna().sum(axis=1)
    df = df[miss <= 2].reset_index(drop=True)
    n_drop = n0 - len(df)
    medians = df[FEATURES].median()
    imputed_mask = df[FEATURES].isna()
    df[FEATURES] = df[FEATURES].fillna(medians)

    # z-score 標準化
    mu, sd = df[FEATURES].mean(), df[FEATURES].std(ddof=0)
    Z = ((df[FEATURES] - mu) / sd).to_numpy()

    # PCA（参照用）と UMAP（マップ座標）
    from sklearn.decomposition import PCA
    pca = PCA(n_components=2, random_state=42)
    P = pca.fit_transform(Z)

    import umap
    reducer = umap.UMAP(n_neighbors=15, min_dist=0.15, metric="euclidean",
                        random_state=42)
    U = reducer.fit_transform(Z)

    df["umap_x"], df["umap_y"] = U[:, 0], U[:, 1]
    df["pca_x"], df["pca_y"] = P[:, 0], P[:, 1]
    df["tango"] = df.reg == "丹後"
    df["n_imputed"] = imputed_mask.sum(axis=1).astype(int)

    # アプリ用JSON
    points = []
    for i, r in df.iterrows():
        points.append({
            "id": int(i),
            "brand": r.brand, "name": r["name"], "brewer": r.brewer,
            "pref": r.pref, "city": r.city,
            "reg": r.reg if isinstance(r.reg, str) else None, "cls": r.cls,
            "rice": list(r.rice_list)[:3],
            "x": round(float(r.umap_x), 4), "y": round(float(r.umap_y), 4),
            "z": [round(float(v), 4) for v in Z[i]],          # 標準化特徴量（類似度計算用）
            "raw": {f: (None if pd.isna(v) else round(float(v), 2))
                    for f, v in zip(FEATURES + ["sweetness"],
                                    list(df.loc[i, FEATURES]) + [r.sweetness])},
            "imp": int(r.n_imputed),
            "rank": (int(r["rank"]) if pd.notna(r["rank"]) else None),
            "tango": bool(r.tango),
        })
    out = {
        "meta": {
            "source": "sake_dataset v1 (https://github.com/yoichi1484/sake_dataset, MIT License)",
            "source_date": date,
            "built_with": "UMAP(n_neighbors=15, min_dist=0.15, seed=42) on z-scored specs",
            "features": FEATURES,
            "feature_labels": FEATURE_LABELS,
            "n_total_source": n0, "n_used": len(df), "n_dropped": n_drop,
            "feature_means": {f: round(float(mu[f]), 4) for f in FEATURES},
            "feature_stds": {f: round(float(sd[f]), 4) for f in FEATURES},
            "pca_explained_var": [round(float(v), 4) for v in pca.explained_variance_ratio_],
        },
        "points": points,
    }
    OUT_JSON.parent.mkdir(exist_ok=True)
    json.dump(out, open(OUT_JSON, "w"), ensure_ascii=False)
    df.to_csv(OUT_CSV, index=False)
    print(f"source={n0} used={len(df)} dropped={n_drop}")
    print(f"imputed cells: {int(imputed_mask.values.sum())}")
    print(f"tango products: {int(df.tango.sum())} from {sorted(df[df.tango].brewer.unique())}")
    print(f"PCA explained variance: {pca.explained_variance_ratio_}")
    print(f"wrote {OUT_JSON} ({OUT_JSON.stat().st_size//1024} KB)")

if __name__ == "__main__":
    main()
