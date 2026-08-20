#!/usr/bin/env python3
"""app/data_sakenowa.json / data_specs.json への付加情報の追加:
- 味タイプ自動分類 (k-means, seed=42) とデータ由来のクラスタ命名
- データ由来の紹介文（タグ・味軸・人気順位・所在地から機械的に生成）
- 蔵の位置座標（localgovjp CC0 の市区町村代表点）
- 蔵元公式サイトURL（Code for SAKE / 京都詳細調査）
- 京都府の銘柄詳細（公式情報由来の紹介・商品・公式価格・酒米、出典付き）
- 日本の海岸線アウトライン (data/land/japan.topojson, 出典: 地球地図日本(国土地理院)) の簡略化
実行順: build_sakenowa_dataset.py → build_specs_dataset.py → 本スクリプト → build_app.py
"""
import json, re, unicodedata
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SEED = 42

# ---------- 共通ユーティリティ ----------
def norm_name(s):
    s = unicodedata.normalize("NFKC", s or "")
    for w in ["株式会社", "有限会社", "合名会社", "合資会社", "合同会社", "(株)", "(有)",
              "(名)", "(資)", "酒造場", "醸造場", "酒造", "醸造", "酒舗", "本店", "商店",
              "本家", "酒類", "酒造店", "醸造元", "酒造元", "酒店"]:
        s = s.replace(w, "")
    return s.replace(" ", "").replace("　", "")

# ---------- 位置座標 (localgovjp, CC0) ----------
lg = json.load(open(ROOT / "data/localgovjp/localgovjp.json"))
geo_lookup = {}
for r in lg:
    city = r["city"].replace(" ", "")
    geo_lookup[(r["pref"], city)] = (round(float(r["lat"]), 4), round(float(r["lng"]), 4))

# 平成の大合併等で現存しない自治体 → 現在の自治体
MERGED = {"下都賀郡岩舟町": "栃木市"}

def muni_coord(pref, muni):
    if not muni:
        return None
    m = unicodedata.normalize("NFKC", muni).replace(" ", "")
    m = MERGED.get(m, m)
    if (pref, m) in geo_lookup:
        return geo_lookup[(pref, m)]
    # 郡を除いた町村名 / 区を除いた市名で再試行
    m2 = re.sub(r"^.+?郡", "", m)
    if (pref, m2) in geo_lookup:
        return geo_lookup[(pref, m2)]
    m3 = re.match(r"^(.+?市)", m)
    if m3 and (pref, m3.group(1)) in geo_lookup:
        return geo_lookup[(pref, m3.group(1))]
    return None

# ---------- 蔵元公式URL (Code for SAKE 由来の派生ファイル) ----------
# data/brewery_urls.json は SAKEOpenData から「都道府県・蔵元名・URL」だけを抽出したもの。
# 元データにはメールアドレス・電話番号・住所が含まれるため、公開リポジトリでは配布しない。
# 元データから作り直す場合は scripts/make_brewery_urls.py を実行する。
url_lookup = {}
_uf = ROOT / "data/brewery_urls.json"
if _uf.exists():
    for b in json.load(open(_uf))["breweries"]:
        url_lookup[(b["pref"], norm_name(b["brewer"]))] = b["url"]
else:  # 元データが手元にある場合のフォールバック
    for b in json.load(open(ROOT / "data/SAKEOpenData/json/breweries.json")):
        u = (b.get("url") or "").strip()
        if u.startswith("http"):
            url_lookup[(b["都道府県"], norm_name(b["蔵元"]))] = u

# ---------- 都道府県別 詳細（公式情報調査） ----------
# data/details/<都道府県>.json （銘柄名 → 詳細）を (pref, brand) キーで統合
_details = {}
for f in sorted((ROOT / "data/details").glob("*.json")):
    pref = f.stem
    for brand, v in json.load(open(f)).items():
        _details[(pref, brand)] = v

class _DetailLookup:
    """既存コードの kyoto.get(brand) 互換のため pref を後付けできるラッパ"""
    def get_for(self, pref, brand):
        return _details.get((pref, brand))

kyoto = _DetailLookup()

AXES = ["f1", "f2", "f3", "f4", "f5", "f6"]
AXIS_JA = {"f1": "華やか", "f2": "芳醇", "f3": "重厚", "f4": "穏やか", "f5": "ドライ", "f6": "軽快"}
SPEC_AXES = ["smv", "acidity", "amino", "alcohol", "polish"]

def kmeans_clusters(Z, k):
    from sklearn.cluster import KMeans
    km = KMeans(n_clusters=k, random_state=SEED, n_init=10)
    return km.fit_predict(Z), km.cluster_centers_

# ---------- さけのわ側 ----------
def enrich_sakenowa():
    path = ROOT / "app/data_sakenowa.json"
    d = json.load(open(path))
    pts = d["points"]
    Z = np.array([p["z"] for p in pts])
    labels, centers = kmeans_clusters(Z, 7)

    # クラスタ命名: 中心の上位軸 + 特徴的タグ（リフト上位）
    n = len(pts)
    tag_total = {}
    for p in pts:
        for t in p["tags"]:
            tag_total[t] = tag_total.get(t, 0) + 1
    cluster_meta = []
    for c in range(7):
        idx = [i for i in range(n) if labels[i] == c]
        zc = centers[c]
        top_axes = [AXIS_JA[AXES[j]] for j in np.argsort(-zc)[:2] if zc[j] > 0.25]
        tag_c = {}
        for i in idx:
            for t in pts[i]["tags"]:
                tag_c[t] = tag_c.get(t, 0) + 1
        lifts = []
        for t, ccount in tag_c.items():
            if ccount >= max(5, 0.08 * len(idx)):
                lift = (ccount / len(idx)) / (tag_total[t] / n)
                lifts.append((lift, t))
        top_tags = [t for _, t in sorted(lifts, reverse=True)[:2]]
        parts = top_axes + [t for t in top_tags if t not in top_axes]
        name = "・".join(parts[:3]) if parts else "バランス"
        cluster_meta.append({
            "id": c, "name": name + "系", "n": len(idx),
            "center_z": [round(float(v), 3) for v in zc],
            "top_tags": top_tags,
        })
    for i, p in enumerate(pts):
        p["cl"] = int(labels[i])

    # 位置・URL・酒米(specsから銘柄名一致で補完)・紹介文
    spc = json.load(open(ROOT / "app/data_specs.json"))
    rice_by_brand = {}
    for q in spc["points"]:
        if q.get("rice"):
            rice_by_brand.setdefault((q["pref"], q["brand"]), [])
            for rv in q["rice"]:
                if rv not in rice_by_brand[(q["pref"], q["brand"])]:
                    rice_by_brand[(q["pref"], q["brand"])].append(rv)
    n_geo = n_url = 0
    for p in pts:
        coord = muni_coord(p["pref"], p.get("muni"))
        p["geo"] = list(coord) if coord else None
        n_geo += coord is not None
        url = url_lookup.get((p["pref"], norm_name(p["brewer"])))
        ky = kyoto.get_for(p["pref"], p["brand"])
        if ky and ky.get("official_url"):
            url = ky["official_url"]
        p["url"] = url
        n_url += url is not None
        rice = (ky.get("rice") if ky else None) or rice_by_brand.get((p["pref"], p["brand"]), [])
        p["rice"] = rice[:3]
        # 紹介文（データ由来・機械生成）
        cm = cluster_meta[p["cl"]]
        zmap = dict(zip(AXES, p["z"]))
        strong = [AXIS_JA[a] for a in AXES if zmap[a] > 0.5]
        strong = sorted(strong, key=lambda x: -zmap[[k for k, v in AXIS_JA.items() if v == x][0]])[:2]
        weak = [AXIS_JA[a] for a in AXES if zmap[a] < -0.8][:1]
        loc = p["pref"] + (("・" + p["reg"]) if p.get("reg") else "")
        s = f"{p['brewer']}（{loc}）の銘柄。"
        if strong:
            s += f"フレーバー値では「{'」「'.join(strong)}」が全国平均より強め"
            s += f"、「{weak[0]}」は控えめ。" if weak else "。"
        elif weak:
            s += f"フレーバー値では「{weak[0]}」が全国平均より控えめ。"
        else:
            s += "フレーバー値は全体に平均的なバランス。"
        if p["tags"]:
            s += f"よく付くタグは「{'」「'.join(p['tags'][:3])}」。"
        s += f"味タイプ分類では「{cm['name']}」（全{cm['n']}銘柄）。"
        if p.get("rank"):
            s += f"さけのわ人気ランキング{p['rank']}位（{str(d['meta']['ranking_month'])[:4]}年{str(d['meta']['ranking_month'])[4:]}月）。"
        p["intro"] = s
        # 京都詳細
        if ky:
            p["detail"] = {
                "brewery_summary": ky.get("brewery_summary"),
                "blurb": ky.get("blurb"),
                "products": ky.get("products", []),
                "sources": ky.get("sources", [])[:5],
            }
    d["meta"]["clusters"] = cluster_meta
    d["meta"]["n_geo"] = n_geo
    d["meta"]["n_url"] = n_url
    d["meta"]["geo_source"] = "localgovjp (CC0) 市区町村代表点"
    json.dump(d, open(path, "w"), ensure_ascii=False)
    print(f"sakenowa: clusters={[(c['name'], c['n']) for c in cluster_meta]}")
    print(f"sakenowa: geo {n_geo}/{len(pts)}, url {n_url}/{len(pts)}, kyoto details {sum(1 for p in pts if 'detail' in p)}")

# ---------- specs側 ----------
def enrich_specs():
    path = ROOT / "app/data_specs.json"
    d = json.load(open(path))
    pts = d["points"]
    Z = np.array([p["z"] for p in pts])
    labels, centers = kmeans_clusters(Z, 6)
    DESC = {
        "smv": ("辛口", "甘口"), "acidity": ("酸しっかり", "酸ひかえめ"),
        "amino": ("旨味濃厚", "淡麗"), "alcohol": ("高アルコール", "低アルコール"),
        "polish": ("低精白", "高精白（吟醸系）"),
    }
    cluster_meta = []
    for c in range(6):
        idx = [i for i in range(len(pts)) if labels[i] == c]
        zc = centers[c]
        parts = []
        for j in np.argsort(-np.abs(zc))[:2]:
            a = SPEC_AXES[j]
            if abs(zc[j]) < 0.3:
                continue
            parts.append(DESC[a][0] if zc[j] > 0 else DESC[a][1])
        name = "・".join(parts) if parts else "標準的"
        cluster_meta.append({"id": c, "name": name + "型", "n": len(idx),
                             "center_z": [round(float(v), 3) for v in zc]})
    for i, p in enumerate(pts):
        p["cl"] = int(labels[i])
        coord = muni_coord(p["pref"], p.get("city"))
        p["geo"] = list(coord) if coord else None
        url = url_lookup.get((p["pref"], norm_name(p["brewer"])))
        ky = kyoto.get_for(p["pref"], p["brand"])
        if ky and ky.get("official_url"):
            url = ky["official_url"]
        p["url"] = url
        # 紹介文（スペック由来）
        r = p["raw"]
        cm = cluster_meta[p["cl"]]
        loc = p["pref"] + (("・" + p["reg"]) if p.get("reg") else "")
        s = f"{p['brewer']}（{loc}）の商品"
        s += f"（{p['cls']}）。" if p.get("cls") else "。"
        specs_txt = []
        if r.get("smv") is not None:
            specs_txt.append(f"日本酒度{r['smv']:+g}")
        if r.get("acidity") is not None:
            specs_txt.append(f"酸度{r['acidity']:g}")
        if r.get("alcohol") is not None:
            specs_txt.append(f"アルコール{r['alcohol']:g}度")
        if r.get("polish") is not None:
            specs_txt.append(f"精米歩合{r['polish']:.0f}%")
        if specs_txt:
            s += "、".join(specs_txt) + "。"
        if p.get("rice"):
            s += f"使用米は{'・'.join(p['rice'])}。"
        s += f"スペック分類では「{cm['name']}」（全{cm['n']}商品）。"
        if p.get("imp"):
            s += f"※{p['imp']}項目は欠損のため中央値補完。"
        p["intro"] = s
        if ky:
            p["detail"] = {
                "brewery_summary": ky.get("brewery_summary"),
                "blurb": ky.get("blurb"),
                "products": ky.get("products", []),
                "sources": ky.get("sources", [])[:5],
            }
    d["meta"]["clusters"] = cluster_meta
    json.dump(d, open(path, "w"), ensure_ascii=False)
    print(f"specs: clusters={[(c['name'], c['n']) for c in cluster_meta]}")
    print(f"specs: geo {sum(1 for p in pts if p['geo'])}/{len(pts)}, url {sum(1 for p in pts if p['url'])}")

# ---------- 日本アウトライン ----------
def build_outline():
    """japan.topojson → 簡略化した経緯度ポリライン集合 (app/japan_outline.json)"""
    import shapely.geometry as sg
    topo = json.load(open(ROOT / "data/land/japan.topojson"))
    obj = list(topo["objects"].values())[0]
    scale = topo["transform"]["scale"]; trans = topo["transform"]["translate"]
    arcs = []
    for arc in topo["arcs"]:
        x = y = 0; pts = []
        for dx, dy in arc:
            x += dx; y += dy
            pts.append((x * scale[0] + trans[0], y * scale[1] + trans[1]))
        arcs.append(pts)
    def ring_coords(arc_idxs):
        out = []
        for ai in arc_idxs:
            seg = arcs[ai] if ai >= 0 else arcs[~ai][::-1]
            out.extend(seg if not out else seg[1:])
        return out
    polys = []
    for geom in obj["geometries"]:
        gs = geom["arcs"] if geom["type"] == "MultiPolygon" else [geom["arcs"]]
        for poly in gs:
            ring = ring_coords(poly[0])  # 外環のみ
            if len(ring) < 4:
                continue
            p = sg.Polygon(ring)
            if not p.is_valid:
                p = p.buffer(0)  # 自己交差等を修復（Multiになる場合あり）
            parts = list(p.geoms) if p.geom_type == "MultiPolygon" else [p]
            for part in parts:
                if part.area < 0.002:  # ごく小さい島は省略
                    continue
                simp = part.simplify(0.012, preserve_topology=True)
                coords = [[round(x, 3), round(y, 3)] for x, y in simp.exterior.coords]
                if len(coords) >= 5:
                    polys.append(coords)
    out = {"source": "地球地図日本（国土地理院） https://www.gsi.go.jp/kankyochiri/gm_jpn.html を簡略化",
           "polys": polys}
    op = ROOT / "app/japan_outline.json"
    json.dump(out, open(op, "w"), ensure_ascii=False)
    print(f"outline: {len(polys)} polygons, {op.stat().st_size // 1024} KB")

if __name__ == "__main__":
    enrich_sakenowa()
    enrich_specs()
    build_outline()
