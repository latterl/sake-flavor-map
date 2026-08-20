#!/usr/bin/env python3
"""Code for SAKE 酒蔵オープンデータ (MIT) から蔵元公式URLだけを抽出し、
data/brewery_urls.json を作り直す。

元データ (data/SAKEOpenData/json/breweries.json) にはメールアドレス607件・
電話番号1,204件・住所1,205件が含まれるため、公開リポジトリではその原本を配布せず、
ビルドに必要な「都道府県・蔵元名・URL」だけを持つこの派生ファイルを配布している。

元データの取得:
    git clone https://github.com/Code-for-SAKE/SAKEOpenData data/SAKEOpenData
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
src = json.load(open(ROOT / "data/SAKEOpenData/json/breweries.json", encoding="utf-8"))

rows = sorted(
    ({"pref": b.get("都道府県", ""), "brewer": b.get("蔵元", ""), "url": (b.get("url") or "").strip()}
     for b in src if (b.get("url") or "").strip().startswith("http")),
    key=lambda r: (r["pref"], r["brewer"]),
)
payload = {
    "_note": "Code for SAKE 酒蔵オープンデータ (MIT) から蔵元公式URLのみを抽出した派生ファイル。"
             "メールアドレス・電話番号・住所は意図的に含めていない。"
             "元データ: https://github.com/Code-for-SAKE/SAKEOpenData",
    "_license": "MIT License (Code for SAKE). THIRD_PARTY_NOTICES.txt を参照",
    "_derived": "諏訪酒造の url は旧ドメイン失効のため https://suwaizumi.jp/ に更新済み",
    "breweries": rows,
}
dst = ROOT / "data/brewery_urls.json"
json.dump(payload, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"wrote {dst} ({len(rows)} breweries)")
