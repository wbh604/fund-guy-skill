#!/usr/bin/env python3
"""抓取基金重仓股的周K(前复权),缓存到 .cache/fund_<code>/kline/。

选股规则:峰值仓位 >= 3.5%,按(峰值仓位 × 持有期数)取前 16。
"""
import json, os, re, sys, time
import warnings
warnings.filterwarnings("ignore")

import akshare as ak

CODE = sys.argv[1] if len(sys.argv) > 1 else "163417"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, ".cache", f"fund_{CODE}")
KDIR = os.path.join(DIR, "kline")
os.makedirs(KDIR, exist_ok=True)

from collections import defaultdict
hold = []
for f in sorted(os.listdir(DIR)):
    if f.startswith("hold_"):
        hold += json.load(open(os.path.join(DIR, f)))

def qkey(s):
    m = re.match(r"(\d{4})年(\d)季度", s)
    return f"{m.group(1)}Q{m.group(2)}"

by_stock = defaultdict(dict)
names = {}
for r in hold:
    w = r["占净值比例"] or 0
    by_stock[r["股票代码"]][qkey(r["季度"])] = w
    names[r["股票代码"]] = r["股票名称"]

cands = []
for code, qmap in by_stock.items():
    peak = max(qmap.values())
    if peak >= 3.5:
        cands.append((peak * len(qmap), code, peak, len(qmap)))
cands.sort(reverse=True)
picks = cands[:16]

# 最新一期前十大必须全覆盖(当前持仓实况)
latest_q = max(q for qmap in by_stock.values() for q in qmap)
cur = sorted(((by_stock[c][latest_q], c) for c in by_stock if latest_q in by_stock[c]),
             reverse=True)[:10]
have = {c for _, c, _, _ in picks}
for w, c in cur:
    if c not in have:
        picks.append((0, c, w, len(by_stock[c])))
print(f"选中 {len(picks)} 只:")
for score, code, peak, n in picks:
    print(f"  {names[code]:<10}{code:<8}峰值{peak:.1f}% × {n}期")

import baostock as bs
bs.login()


def bs_code(code):
    if code.startswith(("60", "68")):
        return "sh." + code
    return "sz." + code


def fetch_a(code):
    """baostock 周K,前复权"""
    rs = bs.query_history_k_data_plus(
        bs_code(code), "date,open,high,low,close",
        start_date="2017-11-01", end_date="2026-12-31",
        frequency="w", adjustflag="2")
    rows = []
    while rs.next():
        d, o, h, l, c = rs.get_row_data()
        if o and c:
            rows.append([d, round(float(o), 2), round(float(h), 2),
                         round(float(l), 2), round(float(c), 2)])
    return rows


def fetch_hk(code):
    """新浪日K → 周K(ISO周)"""
    df = ak.stock_hk_daily(symbol=code, adjust="qfq")
    df["date"] = df["date"].astype(str)
    df = df[df["date"] >= "2017-11-01"]
    from datetime import date as D
    weeks, order = {}, []
    for _, r in df.iterrows():
        y, m, d = map(int, r["date"].split("-"))
        iso = D(y, m, d).isocalendar()
        key = (iso[0], iso[1])
        if key not in weeks:
            weeks[key] = [r["date"], r["open"], r["high"], r["low"], r["close"]]
            order.append(key)
        else:
            w = weeks[key]
            w[0] = r["date"]
            w[2] = max(w[2], r["high"])
            w[3] = min(w[3], r["low"])
            w[4] = r["close"]
    return [[w[0], round(float(w[1]), 2), round(float(w[2]), 2),
             round(float(w[3]), 2), round(float(w[4]), 2)] for w in (weeks[k] for k in order)]


for _, code, _, _ in picks:
    path = os.path.join(KDIR, f"{code}.json")
    if os.path.exists(path):
        print(f"  [skip] {names[code]}")
        continue
    try:
        rows = fetch_hk(code) if len(code) == 5 else fetch_a(code)
        assert rows, "empty"
        json.dump(rows, open(path, "w"))
        print(f"  [ok]   {names[code]} {len(rows)}根")
    except Exception as e:
        print(f"  [FAIL] {names[code]}: {str(e)[:100]}")
    time.sleep(1.2)

bs.logout()
print("done")
