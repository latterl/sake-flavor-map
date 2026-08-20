#!/usr/bin/env python3
"""Code for SAKE 酒蔵オープンデータの原本に含まれる連絡先情報を数える監査スクリプト。

docs/DATA_SOURCES.md に載せている件数の根拠。原本を手元に置いている場合のみ実行できる。
    git clone https://github.com/Code-for-SAKE/SAKEOpenData data/SAKEOpenData
    python3 scripts/audit_pii.py

「フリーメール」の判定は下記 FREE_DOMAINS との完全一致。
部分一致（例 "ocn" で *.ocn.ne.jp を拾う）にすると ISP 提供のドメインまで数えてしまい
過大になるため、必ず完全一致で数えること。
"""
import json
from collections import Counter
from pathlib import Path

# 個人が無償で取得できるメールサービスのドメイン（完全一致で判定する）
FREE_DOMAINS = {
    "gmail.com", "yahoo.co.jp", "ybb.ne.jp", "hotmail.com", "hotmail.co.jp",
    "outlook.com", "outlook.jp", "icloud.com", "me.com", "live.jp", "msn.com",
    "aol.com", "docomo.ne.jp", "ezweb.ne.jp", "softbank.ne.jp", "i.softbank.jp",
    "nifty.com", "nifty.ne.jp", "ocn.ne.jp", "so-net.ne.jp", "biglobe.ne.jp",
    "plala.or.jp", "infoseek.jp", "excite.co.jp", "goo.jp",
    "zoho.com", "gmx.com", "protonmail.com", "proton.me",
}

ROOT = Path(__file__).resolve().parent.parent
src = ROOT / "data/SAKEOpenData/json/breweries.json"
if not src.exists():
    raise SystemExit(f"原本が見つかりません: {src}\n"
                     "git clone https://github.com/Code-for-SAKE/SAKEOpenData data/SAKEOpenData")

rows = json.load(open(src, encoding="utf-8"))
def n(key):
    return sum(1 for b in rows if str(b.get(key, "")).strip())

mails = [str(b.get("email", "")).strip().lower() for b in rows if str(b.get("email", "")).strip()]
free = [m for m in mails if m.rsplit("@", 1)[-1] in FREE_DOMAINS]

print(f"レコード数         : {len(rows)}")
print(f"email             : {n('email')}")
print(f"tel               : {n('tel')}")
print(f"住所               : {n('住所')}")
print(f"フリーメール(完全一致): {len(free)}")
print("  内訳:", Counter(m.rsplit('@', 1)[-1] for m in free).most_common())
