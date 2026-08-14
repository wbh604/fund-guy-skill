#!/usr/bin/env python3
"""补齐证据缺口的数据:持有人结构、风格指数、同门权益基金持仓(House Consensus)。

用法: .venv/bin/python scripts/fetch_house.py 163417
"""
import json, os, re, sys, time
import warnings
warnings.filterwarnings("ignore")

import akshare as ak
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fund_meta import require_code, house_years, index_start, market_periods

CODE = require_code()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, ".cache", f"fund_{CODE}")
HDIR = os.path.join(DIR, "house")
os.makedirs(HDIR, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0", "Referer": "http://fundf10.eastmoney.com/"}


def infer_company_and_lead():
    """从本品 basic/managers 推断公司简称和现任主经理,禁止写死谢治宇。"""
    company = lead = None
    bp = os.path.join(DIR, "basic.json")
    if os.path.exists(bp):
        rows = json.load(open(bp))
        b = {r["item"]: r["value"] for r in rows} if rows and isinstance(rows[0], dict) and "item" in rows[0] else {}
        raw = b.get("基金公司") or ""
        company = re.sub(r"(基金管理有限公司|基金有限公司|股份有限公司|有限公司)$", "", raw) or None
        lead = (b.get("基金经理") or "").split()[0] or None
    mp = os.path.join(DIR, "managers.json")
    if os.path.exists(mp):
        ms = json.load(open(mp))
        counts = {}
        for r in ms:
            for n in str(r.get("managers") or "").split():
                counts[n] = counts.get(n, 0) + 1
        cur = str((ms[0].get("managers") if ms else "") or "").split()
        if cur:
            lead = max(cur, key=lambda n: (counts.get(n, 0), -cur.index(n)))
    return company, lead


COMPANY, SELF_MANAGER = infer_company_and_lead()
if not COMPANY or not SELF_MANAGER:
    print(f"[3] 无法识别公司/现任经理(company={COMPANY} lead={SELF_MANAGER}),House 对照组跳过")
    COMPANY, SELF_MANAGER = COMPANY or "", SELF_MANAGER or ""


def cached(path, fn):
    if os.path.exists(path):
        return json.load(open(path))
    data = fn()
    json.dump(data, open(path, "w"), ensure_ascii=False)
    time.sleep(1.0)
    return data


# ---------- 1. 持有人结构(机构/个人占比 + 真实总份额) ----------
def fetch_holders():
    r = requests.get(f"http://fundf10.eastmoney.com/FundArchivesDatas.aspx?code={CODE}&type=cyrjg",
                     timeout=15, headers=UA)
    rows = re.findall(r"<tr>(.*?)</tr>", r.text, re.S)
    out = []
    for row in rows:
        cells = [re.sub(r"<[^>]+>", "", c).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len(cells) >= 5 and re.match(r"\d{4}-\d{2}-\d{2}", cells[0]):
            out.append({"date": cells[0], "inst": cells[1], "retail": cells[2],
                        "internal": cells[3], "total_share_yi": cells[4]})
    return out

holders = cached(os.path.join(DIR, "holders.json").replace("holders", "holders2"), fetch_holders)
print(f"[1] 持有人结构 {len(holders)} 期")

# ---------- 2. 风格指数(多因子拆解用) ----------
_IDX_START = index_start(DIR)
for sym, name in [("sh000905", "csi500"), ("sh000852", "csi1000"),
                  ("sz399370", "growth"), ("sz399371", "value")]:
    def f(sym=sym):
        df = ak.stock_zh_index_daily(symbol=sym)
        df["date"] = df["date"].astype(str)
        df = df[df["date"] >= _IDX_START]
        return json.loads(df[["date", "close"]].to_json(orient="records", force_ascii=False))
    cached(os.path.join(DIR, f"idx_{name}.json"), f)
    print(f"[2] 指数 {name} ok (from {_IDX_START})")

# ---------- 3. 同门权益基金清单 ----------
def fetch_company_funds():
    if not COMPANY:
        return []
    mgr = ak.fund_manager_em()
    co = mgr[mgr["所属公司"].str.contains(COMPANY, na=False)]
    fund_mgrs = {}
    aums = {}
    for _, r in co.iterrows():
        code = str(r["现任基金代码"])
        fund_mgrs.setdefault(code, []).append(r["姓名"])
        try:
            aums[code] = max(aums.get(code, 0.0), float(r["现任基金资产总规模"] or 0))
        except (TypeError, ValueError):
            pass
    names = ak.fund_name_em()
    types = dict(zip(names["基金代码"].astype(str), names["基金类型"]))
    fnames = dict(zip(names["基金代码"].astype(str), names["基金简称"]))
    out = []
    for code, mgrs in fund_mgrs.items():
        t = types.get(code, "")
        nm = fnames.get(code, "")
        if not any(k in t for k in ("混合", "股票")):
            continue
        if nm.endswith("C") or nm.endswith("E") or nm.endswith("H"):
            continue  # 去重份额类别
        out.append({"code": code, "name": nm, "type": t, "managers": mgrs,
                    "self": SELF_MANAGER in mgrs, "aum": round(aums.get(code, 0), 2)})
    return out

_funds_path = os.path.join(HDIR, "funds.json")
if os.path.exists(_funds_path):
    _old = json.load(open(_funds_path))
    if _old and "aum" not in _old[0]:
        os.remove(_funds_path)
funds = cached(_funds_path, fetch_company_funds)
peers = [f for f in funds if not f["self"] and f["code"] != CODE]
print(f"[3] {COMPANY or '公司未获取'}权益基金 {len(funds)} 只,排除{SELF_MANAGER or '现任'}自管后 {len(peers)} 只")

YEARS = house_years(DIR)
print(f"[3b] 同门持仓年份 {YEARS[0] if YEARS else '?'}–{YEARS[-1] if YEARS else '?'}")

# ---------- 4. 同门基金逐年持仓(本品有持仓的最近 5 年) ----------
ok, fail = 0, 0
for f in peers:
    for year in YEARS:
        path = os.path.join(HDIR, f"hold_{f['code']}_{year}.json")
        if os.path.exists(path):
            continue
        try:
            df = ak.fund_portfolio_hold_em(symbol=f["code"], date=str(year))
            json.dump(json.loads(df.to_json(orient="records", force_ascii=False)),
                      open(path, "w"), ensure_ascii=False)
            ok += 1
        except Exception:
            json.dump([], open(path, "w"))
            fail += 1
        time.sleep(0.9)
print(f"[4] 同门持仓抓取完成 ok={ok} fail={fail}")

# ---------- 4b. 目标经理名下其他产品(一车多牌) ----------
self_others = [f for f in funds if f.get("self") and f["code"] != CODE]
print(f"[4b] 名下其他产品 {len(self_others)} 只")
for f in self_others:
    for year in YEARS:
        path = os.path.join(HDIR, f"hold_{f['code']}_{year}.json")
        if os.path.exists(path):
            continue
        try:
            df = ak.fund_portfolio_hold_em(symbol=f["code"], date=str(year))
            json.dump(json.loads(df.to_json(orient="records", force_ascii=False)),
                      open(path, "w"), ensure_ascii=False)
            print(f"  clone {f['code']} {year} ok")
        except Exception as e:
            json.dump([], open(path, "w"))
            print(f"  clone {f['code']} {year} fail {str(e)[:60]}")
        time.sleep(0.9)

# ---------- 5. 全市场公募持股横截面(半年度,巨潮) ----------
periods = market_periods(DIR)
for p in periods:
    path = os.path.join(HDIR, f"market_{p}.json")
    if os.path.exists(path):
        continue
    try:
        df = ak.fund_report_stock_cninfo(date=p)
        slim = df[["股票代码", "股票简称", "基金覆盖家数", "持股总市值"]]
        json.dump(json.loads(slim.to_json(orient="records", force_ascii=False)),
                  open(path, "w"), ensure_ascii=False)
        print(f"[5] 全市场 {p} ok ({len(df)})")
    except Exception as e:
        print(f"[5] 全市场 {p} FAIL: {str(e)[:80]}")
    time.sleep(1.5)

print("ALL DONE")
