#!/usr/bin/env python3
"""全市场反查:哪些主动基金也重仓他的当前持仓(东财数据中心,A股口径)。

用法: .venv/bin/python scripts/fetch_market_similar.py 163417
输出: .cache/fund_<code>/market_similar.json
"""
import json, os, re, sys, time
from collections import defaultdict

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fund_meta import require_code, report_dates
CODE = require_code()
DIR = os.path.join(ROOT, ".cache", f"fund_{CODE}")

UA = {"User-Agent": "Mozilla/5.0"}
API = "https://datacenter-web.eastmoney.com/api/data/v1/get"

PASSIVE = re.compile(r"ETF|指数|联接|沪深300|中证|上证|创业板(?!.*精选)|增强|量化|双利|债")

def _company_pat():
    bp = os.path.join(DIR, "basic.json")
    tokens = []
    if os.path.exists(bp):
        rows = json.load(open(bp))
        b = {r["item"]: r["value"] for r in rows} if rows and isinstance(rows[0], dict) and "item" in rows[0] else {}
        raw = b.get("基金公司") or ""
        short = re.sub(r"(基金管理有限公司|基金有限公司|股份有限公司|有限公司)$", "", raw)
        if short:
            tokens.append(short)
        if "兴证全球" in raw or "兴全" in raw:
            tokens += ["兴全", "兴证全球"]
    tokens = [t for t in dict.fromkeys(tokens) if t]
    if not tokens:
        return re.compile(r"(?!)")  # 匹配不到任何公司
    return re.compile("|".join(re.escape(t) for t in tokens))

SELF_CO = _company_pat()

# 当前持仓(A股)
hold = []
for f in sorted(os.listdir(DIR)):
    if f.startswith("hold_2"):
        hold += json.load(open(os.path.join(DIR, f)))
qk = lambda s: re.match(r"(\d{4})年(\d)季度", s) and re.sub(r"(\d{4})年(\d)季度.*", r"\1Q\2", s)
latest = max(qk(r["季度"]) for r in hold)
cur = [(r["股票代码"], r["股票名称"], r["占净值比例"] or 0)
       for r in hold if qk(r["季度"]) == latest and len(r["股票代码"]) == 6]
cur.sort(key=lambda x: -x[2])
print(f"反查 {latest} 的 {len(cur)} 只 A 股持仓")

REPORT_DATES = report_dates(DIR, n=3)
print(f"反查报告日 {REPORT_DATES}")
fund_hits = defaultdict(lambda: {"stocks": [], "cap": 0.0})

for code, name, w in cur:
    got = False
    for rd in REPORT_DATES:
        params = {
            "reportName": "RPT_MAINDATA_MAIN_POSITIONDETAILS",
            "columns": "HOLDER_NAME,HOLD_MARKET_CAP",
            "filter": f'(SECURITY_CODE="{code}")(REPORT_DATE=\'{rd}\')(ORG_TYPE_CODE="1")',
            "pageSize": 800, "pageNumber": 1,
            "sortColumns": "HOLD_MARKET_CAP", "sortTypes": "-1",
        }
        try:
            j = requests.get(API, params=params, headers=UA, timeout=20).json()
            rows = (j.get("result") or {}).get("data") or []
        except Exception:
            rows = []
        if rows:
            n_active = 0
            for r in rows:
                fn = r["HOLDER_NAME"] or ""
                if PASSIVE.search(fn) or SELF_CO.search(fn):
                    continue
                fund_hits[fn]["stocks"].append(name)
                fund_hits[fn]["cap"] += (r["HOLD_MARKET_CAP"] or 0) / 1e8
                n_active += 1
            print(f"  {name:<8}{rd}: 持有主动基金 {n_active} 只")
            got = True
            break
        time.sleep(0.8)
    if not got:
        print(f"  {name:<8}未获取")
    time.sleep(1.0)

ranked = [{"fund": fn, "n": len(set(v["stocks"])), "stocks": sorted(set(v["stocks"])),
           "cap_yi": round(v["cap"], 1)}
          for fn, v in fund_hits.items() if len(set(v["stocks"])) >= 3]
ranked.sort(key=lambda x: (-x["n"], -x["cap_yi"]))
out = {"period": REPORT_DATES[0], "latest_q": latest,
       "n_stocks_checked": len(cur), "funds": ranked[:12]}
json.dump(out, open(os.path.join(DIR, "market_similar.json"), "w"), ensure_ascii=False)
print(f"\n撞车 ≥3 只的全市场主动基金: {len(ranked)}")
for x in ranked[:12]:
    print(f"  {x['fund']:<28} {x['n']}/{len(cur)} 只  {x['cap_yi']:>7.1f}亿  {x['stocks']}")
