#!/usr/bin/env python3
"""给本品重仓股打东财/港交所公开行业,禁止手写对照表。

A 股: F10 公司概况 sshy + 所属板块一级。
港股: 港股 F10 sshy,缺了再退东财行情 f127。
用法: .venv/bin/python scripts/fetch_stock_industry.py 163417
"""
import json
import os
import re
import sys
import time
from collections import defaultdict

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fund_meta import require_code
CODE = require_code()
DIR = os.path.join(ROOT, ".cache", f"fund_{CODE}")
GDIR = os.path.join(ROOT, ".cache", "stock_industry")
os.makedirs(DIR, exist_ok=True)
os.makedirs(GDIR, exist_ok=True)

S = requests.Session()
S.trust_env = False
S.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://emweb.securities.eastmoney.com/",
})

JUNK = ("板块", "金股", "市净", "市盈", "融资", "转融", "预盈", "预增", "龙虎",
        "破净", "破发", "连续", "涨停", "跌停", "次新", "新股")


def qkey(s):
    m = re.match(r"(\d{4})年(\d)季度", s or "")
    return f"{m.group(1)}Q{m.group(2)}" if m else None


def pick_codes():
    hold = []
    for f in sorted(os.listdir(DIR)):
        if f.startswith("hold_") and f.endswith(".json"):
            hold += json.load(open(os.path.join(DIR, f)))
    by_stock = defaultdict(dict)
    names = {}
    for r in hold:
        q = qkey(r.get("季度"))
        if not q:
            continue
        c = str(r["股票代码"])
        by_stock[c][q] = r["占净值比例"] or 0
        names[c] = r["股票名称"]
    cands = []
    for code, qmap in by_stock.items():
        peak = max(qmap.values()) if qmap else 0
        if peak >= 3.5:
            cands.append((peak * len(qmap), code))
    cands.sort(reverse=True)
    picks = [c for _, c in cands[:16]]
    if by_stock:
        latest = max(q for qmap in by_stock.values() for q in qmap)
        cur = sorted(((by_stock[c][latest], c) for c in by_stock if latest in by_stock[c]),
                     reverse=True)[:10]
        for _, c in cur:
            if c not in picks:
                picks.append(c)
    return picks, names


def em_a(code):
    if code.startswith(("60", "68", "90")):
        return "SH" + code
    if code.startswith(("00", "30", "20")):
        return "SZ" + code
    if len(code) == 6 and code.startswith(("8", "4", "92")):
        return "BJ" + code
    return None


def _ok(v):
    if v is None:
        return None
    s = str(v).strip()
    if s in ("", "-", "--", "None", "null"):
        return None
    return s


def _board_ok(name):
    n = _ok(name)
    if not n:
        return None
    if any(k in n for k in JUNK):
        return None
    return n


def fetch_a(code):
    em = em_a(code)
    if not em:
        return None
    r = S.get(
        "https://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/CompanySurveyAjax",
        params={"code": em}, timeout=15)
    r.raise_for_status()
    jb = (r.json() or {}).get("jbzl") or {}
    industry = _ok(jb.get("sshy"))
    board = None
    try:
        r2 = S.get(
            "https://emweb.securities.eastmoney.com/PC_HSF10/CoreConception/PageAjax",
            params={"code": em}, timeout=15)
        rows = (r2.json() or {}).get("ssbk") or []
        ranked = sorted(rows, key=lambda x: x.get("BOARD_RANK") or 99)
        for row in ranked:
            b = _board_ok(row.get("BOARD_NAME"))
            if b:
                board = b
                break
    except Exception:
        board = None
    if not industry and not board:
        return None
    return {
        "industry": industry or board or "",
        "board": board or industry or "",
        "source": "eastmoney hsf10",
    }


def fetch_hk(code):
    r = S.get(
        "https://emweb.securities.eastmoney.com/PC_HKF10/CompanyProfile/PageAjax",
        params={"code": code}, timeout=15)
    r.raise_for_status()
    gszl = (r.json() or {}).get("gszl") or {}
    industry = _ok(gszl.get("sshy"))
    if not industry:
        r2 = S.get(
            "https://push2.eastmoney.com/api/qt/stock/get",
            params={"invt": 2, "fltt": 2, "fields": "f127,f58",
                    "secid": f"116.{code}"}, timeout=15)
        raw = ((r2.json() or {}).get("data") or {}).get("f127")
        if isinstance(raw, str):
            industry = _ok(raw)
    if not industry:
        return None
    return {"industry": industry, "board": industry, "source": "eastmoney hkf10"}


def fetch_one(code):
    gp = os.path.join(GDIR, f"{code}.json")
    if os.path.exists(gp):
        return json.load(open(gp))
    try:
        data = fetch_hk(code) if len(code) == 5 else fetch_a(code)
    except Exception as e:
        print(f"  [FAIL] {code}: {str(e)[:80]}")
        data = None
    if data:
        json.dump(data, open(gp, "w"), ensure_ascii=False)
    time.sleep(0.35)
    return data


def main():
    if not os.path.isdir(DIR):
        print(f"没有 {DIR},先跑 fetch_fund.py")
        sys.exit(1)
    picks, names = pick_codes()
    out = {}
    for code in picks:
        data = fetch_one(code)
        if data:
            out[code] = data
            print(f"  [ok] {names.get(code, code):<10} {code}  {data.get('board') or ''} / {data.get('industry') or ''}")
        else:
            print(f"  [miss] {names.get(code, code)} {code}")
    json.dump(out, open(os.path.join(DIR, "industry.json"), "w"), ensure_ascii=False)
    print(f"行业 {len(out)}/{len(picks)} → {DIR}/industry.json")


if __name__ == "__main__":
    main()
