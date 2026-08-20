#!/usr/bin/env bash
# さけのわデータプロジェクト API から全データを取得する
# 利用条件: 「データ提供:さけのわ (https://sakenowa.com)」のクレジット表記が必要
set -euo pipefail
DIR="$(dirname "$0")/../data/sakenowa"
mkdir -p "$DIR"
for ep in areas brands breweries rankings flavor-charts flavor-tags brand-flavor-tags; do
  echo "fetching $ep ..."
  curl -sS "https://muro.sakenowa.com/sakenowa-data/api/$ep" -o "$DIR/$ep.json"
done
ls -la "$DIR"
