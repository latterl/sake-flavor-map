#!/usr/bin/env python3
"""
パターン1（さけのわデータ版）: さけのわデータプロジェクトのAPI JSONから
銘柄単位のフレーバー6軸特徴量を作り、UMAP/PCAで2次元化して
アプリ用JSON (app/data_sakenowa.json) と検証用CSVを出力する。

6軸: f1=華やか, f2=芳醇, f3=重厚, f4=穏やか, f5=ドライ, f6=軽快
（さけのわデータプロジェクト https://muro.sakenowa.com/sakenowa-data/ ）

データ利用条件: 「データ提供:さけのわ(https://sakenowa.com)」のクレジット表記が必要。
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data/sakenowa"
TANGO = ROOT / "data/tango_breweries.json"
OUT_JSON = ROOT / "app/data_sakenowa.json"
OUT_CSV = ROOT / "analysis/sakenowa_features.csv"

AXES = ["f1", "f2", "f3", "f4", "f5", "f6"]
AXIS_LABELS = {"f1": "華やか", "f2": "芳醇", "f3": "重厚",
               "f4": "穏やか", "f5": "ドライ", "f6": "軽快"}

def load(name, key):
    return json.load(open(SRC / f"{name}.json"))[key]

def main():
    areas = {a["id"]: a["name"] for a in load("areas", "areas")}
    brands = {b["id"]: b for b in load("brands", "brands")}
    brewers = {b["id"]: b for b in load("breweries", "breweries")}
    charts = load("flavor-charts", "flavorCharts")
    tags = {t["id"]: t["tag"] for t in load("flavor-tags", "tags")}
    btags = {t["brandId"]: t["tagIds"] for t in load("brand-flavor-tags", "flavorTags")}
    rankings = json.load(open(SRC / "rankings.json"))
    rank_month = rankings["yearMonth"]
    overall_rank = {r["brandId"]: r["rank"] for r in rankings["overall"]}

    # 蔵元所在地（市区町村）→ 県内地域の割り当て
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from region_assign import assign_region
    locs = json.load(open(ROOT / "data/brewery_locations.json"))

    rows = []
    for c in charts:
        bid = c["brandId"]
        b = brands.get(bid)
        if b is None:
            continue
        bw = brewers.get(b["breweryId"], {})
        pref = areas.get(bw.get("areaId"), "その他")
        loc = locs.get(str(b["breweryId"]))
        muni, reg = assign_region(pref, loc["muni"]) if loc else (None, None)
        rows.append({
            "id": bid, "brand": b["name"],
            "brewer": bw.get("name", ""), "breweryId": b["breweryId"],
            "pref": pref, "muni": muni, "reg": reg,
            "areaId": bw.get("areaId"),
            **{a: float(c[a]) for a in AXES},
            "rank": overall_rank.get(bid),
            "tango": reg == "丹後",
            "tagIds": btags.get(bid, [])[:8],
        })
    df = pd.DataFrame(rows)
    n = len(df)

    # z-score 標準化（6軸のスケール差を吸収）
    mu, sd = df[AXES].mean(), df[AXES].std(ddof=0)
    Z = ((df[AXES] - mu) / sd).to_numpy()

    from sklearn.decomposition import PCA
    pca = PCA(n_components=2, random_state=42)
    P = pca.fit_transform(Z)

    import umap
    reducer = umap.UMAP(n_neighbors=15, min_dist=0.15, metric="euclidean",
                        random_state=42)
    U = reducer.fit_transform(Z)

    df["umap_x"], df["umap_y"] = U[:, 0], U[:, 1]
    df["pca_x"], df["pca_y"] = P[:, 0], P[:, 1]

    points = []
    for i, r in df.iterrows():
        points.append({
            "id": int(r.id), "brand": r.brand, "brewer": r.brewer,
            "pref": r.pref,
            "muni": r.muni if isinstance(r.muni, str) else None,
            "reg": r.reg if isinstance(r.reg, str) else None,
            "x": round(float(r.umap_x), 4), "y": round(float(r.umap_y), 4),
            "z": [round(float(v), 4) for v in Z[i]],
            "raw": {a: round(float(r[a]), 4) for a in AXES},
            "rank": (int(r["rank"]) if pd.notna(r["rank"]) else None),
            "tango": bool(r.tango),
            "tags": [tags[t] for t in r.tagIds if t in tags],
        })
    out = {
        "meta": {
            "source": "さけのわデータ (https://sakenowa.com) — データ提供:さけのわ",
            "api": "https://muro.sakenowa.com/sakenowa-data/api",
            "retrieved": "2026-08-14",
            "ranking_month": rank_month,
            "features": AXES, "feature_labels": AXIS_LABELS,
            "n_brands_total": len(brands), "n_with_flavor": n,
            "feature_means": {a: round(float(mu[a]), 4) for a in AXES},
            "feature_stds": {a: round(float(sd[a]), 4) for a in AXES},
            "pca_explained_var": [round(float(v), 4) for v in pca.explained_variance_ratio_],
            "n_located": int(df.muni.notna().sum()),
            "location_sources": "Code for SAKE SAKEOpenData (MIT) / sake_dataset (MIT) / 個別Web確認",
        },
        "points": points,
    }
    OUT_JSON.parent.mkdir(exist_ok=True)
    json.dump(out, open(OUT_JSON, "w"), ensure_ascii=False)
    df.drop(columns=["tagIds"]).to_csv(OUT_CSV, index=False)

    print(f"brands with flavor chart: {n} / {len(brands)}")
    print(f"brands with region: {int(df.reg.notna().sum())} / {n}")
    print(f"tango brands on map: {int(df.tango.sum())}")
    print(f"famous (top100) on map: {int(df['rank'].notna().sum())}")
    print(f"PCA explained variance: {pca.explained_variance_ratio_}")
    print(f"axis ranges: min={df[AXES].min().round(3).to_dict()} max={df[AXES].max().round(3).to_dict()}")
    print(f"wrote {OUT_JSON} ({OUT_JSON.stat().st_size//1024} KB)")

if __name__ == "__main__":
    main()
