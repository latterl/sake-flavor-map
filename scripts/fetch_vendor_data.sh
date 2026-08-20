#!/usr/bin/env bash
# 外部データセットのうち、リポジトリに含めていないファイルを再取得する。
# 通常のビルドには不要（build_enrich.py が使うのは japan.topojson と localgovjp.json のみ）。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "== localgovjp (CC0) =="
mkdir -p "$ROOT/data/localgovjp"
curl -sSL https://code4fukui.github.io/localgovjp/localgovjp.json \
     -o "$ROOT/data/localgovjp/localgovjp.json"

echo "== 地球地図日本（国土地理院）由来の日本地図 TopoJSON =="
echo "   dataofjapan/land リポジトリから取得します"
mkdir -p "$ROOT/data/land"
curl -sSL https://raw.githubusercontent.com/dataofjapan/land/master/japan.topojson \
     -o "$ROOT/data/land/japan.topojson"

echo "done."
