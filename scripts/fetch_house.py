#!/usr/bin/env python3
"""补齐证据缺口的数据:持有人结构、风格指数、兴证全球全部权益基金持仓(House Consensus)。

用法: .venv/bin/python scripts/fetch_house.py 163417
"""
import json, os, re, sys, time
import warnings
warnings.filterwarnings("ignore")

import akshare as ak
import requests

CODE = sys.argv[1] if len(sys.argv) > 1 else "163417"
COMPANY = "兴证全球"
SELF_MANAGER = "谢治宇"          # House 必须排除目标经理自己的产品(硬规则)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, ".cache", f"fund_{CODE}")
HDIR = os.path.join(DIR, "house")
os.makedirs(HDIR, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0", "Referer": "http://fundf10.eastmoney.com/"}


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
for sym, name in [("sh000905", "csi500"), ("sh000852", "csi1000"),
                  ("sz399370", "growth"), ("sz399371", "value")]:
    def f(sym=sym):
        df = ak.stock_zh_index_daily(symbol=sym)
        df["date"] = df["date"].astype(str)
        df = df[df["date"] >= "2017-06-01"]
        return json.loads(df[["date", "close"]].to_json(orient="records", force_ascii=False))
    cached(os.path.join(DIR, f"idx_{name}.json"), f)
    print(f"[2] 指数 {name} ok")

# ---------- 3. 兴证全球权益基金清单 ----------
def fetch_company_funds():
    mgr = ak.fund_manager_em()
    co = mgr[mgr["所属公司"].str.contains(COMPANY, na=False)]
    fund_mgrs = {}
    for _, r in co.iterrows():
        fund_mgrs.setdefault(str(r["现任基金代码"]), []).append(r["姓名"])
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
                    "self": SELF_MANAGER in mgrs})
    return out

funds = cached(os.path.join(HDIR, "funds.json"), fetch_company_funds)
peers = [f for f in funds if not f["self"] and f["code"] != CODE]
print(f"[3] 兴证全球权益基金 {len(funds)} 只,排除{SELF_MANAGER}自管后 {len(peers)} 只")

# ---------- 4. 同门基金逐年持仓(近5年) ----------
ok, fail = 0, 0
for f in peers:
    for year in range(2021, 2027):
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

# ---------- 5. 全市场公募持股横截面(半年度,巨潮) ----------
periods = [f"{y}{md}" for y in range(2021, 2026) for md in ("0630", "1231")]
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
