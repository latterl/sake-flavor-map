#!/usr/bin/env python3
"""全国展開の調査結果 (/tmp/nresultNNN.json) を data/details/<pref>.json にマージする"""
import json, re, glob, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
BAD=["接続","年齢認証","調査環境","確認できな","robots","SSL","文字化け","タイムアウト","価格未","取得不可","閲覧不可","アクセス不能","エンコード"]
def clean_text(t):
    if not t: return None
    parts=[s for s in re.split(r'(?<=。)', t) if s.strip()]
    return "".join(s for s in parts if not any(b in s for b in BAD)).strip() or None
def norm_products(prods):
    out=[]; seen=set()
    for p in (prods or []):
        if not p or not p.get('name'): continue
        k=(p['name'], p.get('volume'))
        if k in seen: continue
        seen.add(k)
        pr=p.get('price')
        try: pr=int(pr) if pr is not None else None
        except (ValueError,TypeError): pr=None
        if pr is not None and not (200<=pr<=60000): pr=None
        note=None
        if pr is not None:
            m=re.search(r'税込|税抜|税別', str(p.get('price_note') or ''))
            note=m.group(0) if m else None
        out.append({'name':str(p['name']).strip(),'spec':(p.get('spec') or '').strip() or None,
                    'volume':(p.get('volume') or '').strip() or None,'price':pr,'price_note':note,
                    'source':(p.get('source') or '').strip() or None,'seasonal':bool(p.get('seasonal'))})
    return out[:12]
def main(indices, prefix='n'):
    prefs=json.load(open(f'/tmp/{prefix}chunk_prefs.json'))
    changed={}
    for idx in indices:
        f=f'/tmp/{prefix}result{idx}.json'
        try:
            recs=json.load(open(f))
        except Exception as e:
            print(f"SKIP {f}: {e}"); continue
        pref=prefs[idx]
        path=ROOT/f'data/details/{pref}.json'
        d=json.load(open(path)) if path.exists() else {}
        for bw in recs:
            for br in bw.get('brands',[]):
                brand=(br.get('brand') or '').strip()
                if not brand: continue
                entry={'brewer':bw.get('brewer'),'official_url':bw.get('official_url'),
                       'brewery_summary':clean_text(bw.get('summary')),
                       'blurb':clean_text(br.get('blurb')),
                       'rice':(br.get('rice') or [])[:3],
                       'products':norm_products(br.get('products')),
                       'sources':(bw.get('sources') or [])[:5]}
                old=d.get(brand)
                if old and (len(old['products']),sum(1 for p in old['products'] if p['price'] is not None))>=(len(entry['products']),sum(1 for p in entry['products'] if p['price'] is not None)):
                    continue
                d[brand]=entry
        json.dump(d, open(path,'w'), ensure_ascii=False, indent=1)
        changed[pref]=len(d)
    for p,n in changed.items(): print(f"{p}: {n} brands")
    # 全体集計
    tot=pr=nb=0
    for f in sorted((ROOT/'data/details').glob('*.json')):
        d=json.load(open(f))
        nb+=len(d)
        tot+=sum(len(v['products']) for v in d.values())
        pr+=sum(1 for v in d.values() for x in v['products'] if x['price'] is not None)
    print(f"TOTAL: {nb} brands, {tot} products, {pr} priced")
if __name__=='__main__':
    main([a for a in sys.argv[1:] if not a.startswith('--')], prefix=('v' if '--v' in sys.argv else 'u' if '--u' in sys.argv else 'n'))
