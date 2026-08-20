# 開発・再ビルド手順

## 必要なもの

- Python 3.11 以上
- `numpy` `pandas` `scikit-learn` `umap-learn` `matplotlib` `shapely`

```bash
pip install numpy pandas scikit-learn umap-learn matplotlib shapely
```

Node.js は不要です（アプリは素の HTML/CSS/JS で、ビルドツールを使いません）。

## ビルドの流れ

```
data/sakenowa/*.json ──┐
                       ├─→ analysis/build_sakenowa_dataset.py ─→ app/data_sakenowa.json ─┐
data/sake_dataset/  ───┴─→ analysis/build_specs_dataset.py    ─→ app/data_specs.json   ─┤
                                                                                        │
data/details/*.json ──┐                                                                 │
data/brewery_*.json  ─┼─→ analysis/build_enrich.py ─→ 上記2つに位置・地域・商品情報を付与 ─┤
data/localgovjp/    ──┤                                                                 │
data/land/          ──┘                                        app/japan_outline.json ──┤
                                                                                        │
app/template.html ──────────────→ app/build_app.py ────────────────────→ app/sake_map.html
```

`build_enrich.py` が使う蔵元公式 URL は `data/brewery_urls.json`（Code for SAKE 由来の派生ファイル）
です。原データ `data/SAKEOpenData/` が手元にある場合はそちらへフォールバックします。

### 全部やり直す

```bash
bash scripts/fetch_sakenowa.sh          # さけのわAPIから最新データを取得
python3 analysis/build_sakenowa_dataset.py
python3 analysis/build_specs_dataset.py
python3 analysis/build_enrich.py
python3 app/build_app.py                # → app/sake_map.html
```

### 見た目・機能だけ直す（いちばん多いケース）

`app/template.html` を編集して、次を実行するだけです。

```bash
python3 app/build_app.py
```

`build_app.py` は `template.html` の中のプレースホルダ（`__DATA_SAKENOWA__`, `__DATA_SPECS__`, `__REGION_ORDER__`, `__JAPAN_OUTLINE__`）を JSON で置換して単一 HTML を書き出すだけの、19 行のスクリプトです。

> **`app/sake_map.html` を直接編集しないでください。** 次のビルドで上書きされます。編集するのは常に `app/template.html` です。

### 商品情報を追加・修正する

1. 調査結果を `/tmp/nresult<N>.json` に、県の対応表を `/tmp/nchunk_prefs.json`（`{"1": "佐賀県"}` 形式）に置く
2. `python3 analysis/merge_details.py 1 2 3` で `data/details/<都道府県>.json` にマージ
   - 既存エントリは (商品数, 価格数) が多い方を優先します
   - 価格レンジ 200〜60,000 円の外は `null` にされます
   - 商品の重複は自動で除去されます
3. 商品を取得できた蔵を `data/gap_breweries_todo.json` から除外
4. `python3 analysis/build_enrich.py && python3 app/build_app.py` で再ビルド

入力 JSON の形式は `analysis/merge_details.py` の docstring と `data/details/*.json` の既存エントリを参照してください。

### 県内地域の区分を変える

`data/region_schemes.json` を編集して再ビルドします。市区町村名 → 地域名のマッピングです。

## アプリのデータ構造

`app/data_sakenowa.json` は `{ meta, points }` の形です。

```jsonc
{
  "meta": {
    "features": ["f1", "f2", ...],       // 味わい6軸のキー
    "feature_labels": ["華やか", ...],
    "clusters": [{ "name": "芳醇・華やか・ジューシー系" }, ...],
    "n_with_flavor": 1354,
    "retrieved": "2026-08-14"
  },
  "points": [{
    "id": 968,                            // さけのわの brandId
    "brand": "七田",
    "brewer": "天山酒造",
    "pref": "佐賀県",
    "muni": "小城市",
    "reg": "東部（佐賀平野）",             // 県内地域
    "x": 3.21, "y": 4.05,                 // UMAP座標
    "z": [...],                           // 標準化した特徴量（類似計算に使う）
    "raw": { "f1": 0.25, ... },           // 生のフレーバー値
    "rank": 66,                           // 人気ランキング順位（Top100のみ）
    "tags": ["ガス", "旨味", ...],
    "cl": 5,                              // 味タイプのクラスタ番号
    "geo": [33.28, 130.20],               // 蔵元の緯度経度
    "url": "https://tenzan.co.jp/",
    "rice": ["山田錦", "雄町"],
    "intro": "...",                        // 機械生成の紹介文
    "detail": {                            // 蔵元公式サイト由来
      "brewery_summary": "...",
      "blurb": "...",
      "products": [{
        "name": "七田 純米大吟醸", "spec": "純米大吟醸", "volume": "720ml",
        "price": 3960, "price_note": "税込",
        "source": "https://tenzan.co.jp/product/...", "seasonal": false
      }],
      "sources": ["https://..."]
    }
  }]
}
```

**重要**: `detail` の結合キーは **(都道府県, 銘柄名) の複合キー**です（`analysis/build_enrich.py` の `_details[(pref, brand)]`）。銘柄名だけをキーにすると、県をまたぐ同名銘柄（道灌＝兵庫/滋賀 など）が衝突します。件数の検証スクリプトを書くときも必ず複合キーで行ってください。

```python
import json
pts = {(p['pref'], p['brand']) for p in json.load(open('app/data_sakenowa.json'))['points']}
# data/details/<県>.json の各キーが pts に含まれるか確認する
```

## アプリ内の主要な関数

`app/template.html` の JavaScript は 1 ファイルにまとまっています。フレームワークは使っていません。

| 関数 | 役割 |
|---|---|
| `initForDataset()` | データセット切替時の初期化。**すべての描画の起点** |
| `buildMap()` / `restyleDots()` / `sizeDots()` | SVG の点の生成・色付け・サイズ調整 |
| `select(id)` / `renderSel()` | 銘柄選択と右パネルの描画 |
| `similar(sel, n)` | 類似銘柄の計算（`z` 配列のユークリッド距離） |
| `renderMemo(p)` / `setNote(p, r, t)` | メモと★評価 |
| `saveLocal()` / `loadLocal()` | localStorage への自動保存・復元 |
| `pbKey(p)` | `"都道府県␟銘柄"` のキー生成。飲んだ酒・お気に入り・メモで共通 |
| `normalizeKeySet(arr)` | 旧形式（銘柄名のみ）を複合キーへ移行 |

### つまずきやすい点

- **`refreshAfterDrunkChange()` は `initForDataset()` より後に呼ぶこと。** 内部で `restyleDots()` を呼ぶため、マップ生成前だと `sizeDots` が null 参照で落ちます
- ユーザーデータの localStorage キーは `sakeFlavorMap.v1`（キー名は固定。保存内容の形式バージョンは payload の `v` で管理しており現在は 2）。形式を変えるときは `loadLocal()` に移行処理を足してください
- 同名銘柄の判定は `isAmbiguousBrand()`。両データセットを横断して「銘柄名 → 県の集合」を作っています

## 動作確認

Playwright でヘッドレス検証できます。

```bash
npm install playwright
node -e "
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const page = await b.newPage();
  const errs = [];
  page.on('pageerror', e => errs.push(e.message));
  await page.goto('file://' + process.cwd() + '/app/sake_map.html');
  await page.waitForTimeout(1500);
  console.log('dots:', await page.evaluate(() => document.querySelectorAll('#mapsvg circle').length));
  console.log('errors:', errs.length ? errs : 'none');
  await b.close();
})();
"
```

JS の構文チェックだけなら次で足ります。

```bash
node -e "
const s = require('fs').readFileSync('app/sake_map.html','utf8');
const m = s.match(/<script>([\s\S]*)<\/script>\s*<\/body>/);
new Function(m[1]); console.log('JS syntax OK');
"
```
