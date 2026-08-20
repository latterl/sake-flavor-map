#!/usr/bin/env python3
"""template.html にデータJSONを埋め込み、単一ファイルの sake_map.html を生成する。"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
tpl = (HERE / "template.html").read_text(encoding="utf-8")
snw = (HERE / "data_sakenowa.json").read_text(encoding="utf-8")
spc = (HERE / "data_specs.json").read_text(encoding="utf-8")
schemes = json.load(open(HERE.parent / "data/region_schemes.json"))
region_order = {p: list(v.keys()) for p, v in schemes.items() if not p.startswith("_")}
outline = (HERE / "japan_outline.json").read_text(encoding="utf-8")
out = (tpl.replace("__DATA_SAKENOWA__", snw)
          .replace("__DATA_SPECS__", spc)
          .replace("__REGION_ORDER__", json.dumps(region_order, ensure_ascii=False))
          .replace("__JAPAN_OUTLINE__", outline))
dst = HERE / "sake_map.html"
dst.write_text(out, encoding="utf-8")
print(f"wrote {dst} ({dst.stat().st_size/1024:.0f} KB)")
