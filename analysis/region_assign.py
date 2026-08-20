#!/usr/bin/env python3
"""市区町村 → 県内地域 の割り当てモジュール。
region_schemes.json（各県の確立した地方区分に基づく定義）を使う。
"""
import json, re, unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMES = {k: v for k, v in json.load(open(ROOT / "data/region_schemes.json")).items()
           if not k.startswith("_")}

# 表記ゆれ・旧表記・truncation の修正
FIXUPS = {
    "印旙郡酒々井町": "印旛郡酒々井町",
    "塩釜市": "塩竈市",
    "珠州市": "珠洲市",
    "茨城郡大洗町": "東茨城郡大洗町",
    "四日市": "四日市市",
    "十日町": "十日町市",
    "大町": "大町市",
    "東村": "東村山市",
    "田村": "田村市",
    "廿日市": "廿日市市",
    "設楽町": "北設楽郡設楽町",
    "愛荘町": "愛知郡愛荘町",
    "湯沢町": "南魚沼郡湯沢町",
    "佐波郡玉村": "佐波郡玉村町",
    "富谷町": "富谷市",
    "黒川郡富谷町": "富谷市",
    "東広島市西条": "東広島市",
    "姫路市網干区": "姫路市",
    "奥州市前沢区": "奥州市",
    "篠山市": "丹波篠山市",
}
# 区を市に集約する（京都市・神戸市は区が地域区分に必要なので残す）
KEEP_WARD_CITIES = ("京都市", "神戸市")

def normalize_muni(m):
    if not m:
        return None
    m = unicodedata.normalize("NFKC", str(m)).strip().replace(" ", "").replace("　", "")
    m = m.replace("ケ", "ヶ").replace("曾", "曽").replace("鯵", "鰺")
    m = FIXUPS.get(m, m)
    # 政令市等の区 → 市 に集約
    mm = re.match(r"^(.+?市)(.+区)$", m)
    if mm and not m.startswith(KEEP_WARD_CITIES):
        m = mm.group(1)
    m = FIXUPS.get(m, m)
    return m

# 逆引き辞書 pref -> muni -> region
_LOOKUP = {}
for pref, regions in SCHEMES.items():
    d = {}
    for reg, munis in regions.items():
        for mu in munis:
            d[mu] = reg
    _LOOKUP[pref] = d

def assign_region(pref, muni):
    """(正規化した市区町村, 地域名) を返す。未定義は (muni, None)。"""
    m = normalize_muni(muni)
    if m is None:
        return None, None
    reg = _LOOKUP.get(pref, {}).get(m)
    if reg is None and m.startswith(KEEP_WARD_CITIES):
        # 京都市・神戸市の区が定義漏れの場合は市単位で試す
        reg = _LOOKUP.get(pref, {}).get(m.split("市")[0] + "市")
    return m, reg

if __name__ == "__main__":
    # カバレッジ検証: データ中の全市区町村が地域に割り当たるか
    import collections
    fails = []
    # 1) さけのわ蔵元所在地
    locs = json.load(open(ROOT / "data/brewery_locations.json"))
    areas = {a["id"]: a["name"] for a in json.load(open(ROOT / "data/sakenowa/areas.json"))["areas"]}
    brewers = {b["id"]: b for b in json.load(open(ROOT / "data/sakenowa/breweries.json"))["breweries"]}
    for bid, v in locs.items():
        b = brewers[int(bid)]
        pref = areas.get(b["areaId"], "")
        m, reg = assign_region(pref, v["muni"])
        if reg is None:
            fails.append(("sakenowa", pref, v["muni"], m, b["name"]))
    # 2) specs の city
    sd = json.load(open(ROOT / "data/sake_dataset/json/sake_dataset_v1.json"))["dataset"]
    seen = set()
    for r in sd:
        pref, city = r.get("prefecture"), r.get("city")
        if not pref or not city or (pref, city) in seen:
            continue
        seen.add((pref, city))
        m, reg = assign_region(pref, city)
        if reg is None:
            fails.append(("specs", pref, city, m, r.get("brewer")))
    if fails:
        print(f"UNRESOLVED ({len(fails)}):")
        for f in fails:
            print(" ", f)
    else:
        print("all municipalities resolved ✓")
