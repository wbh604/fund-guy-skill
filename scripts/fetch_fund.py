#!/usr/bin/env python3
"""抓取一只基金跑通 skill 流程所需的全部真实数据,缓存到 .cache/fund_<code>/。

用法: .venv/bin/python scripts/fetch_fund.py 163417
已缓存的文件跳过,不重复请求(尊重限速)。
"""
import json, os, re, sys, time
import warnings
warnings.filterwarnings("ignore")

import akshare as ak
import requests

CODE = sys.argv[1] if len(sys.argv) > 1 else "163417"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, ".cache", f"fund_{CODE}")
os.makedirs(DIR, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}


def cached(name, fn):
    path = os.path.join(DIR, name + ".json")
    if os.path.exists(path):
        print(f"  [skip] {name}")
        return json.load(open(path))
    data = fn()
    json.dump(data, open(path, "w"), ensure_ascii=False)
    print(f"  [ok]   {name}")
    time.sleep(1.2)
    return data


def df_records(df):
    return json.loads(df.to_json(orient="records", force_ascii=False, date_format="iso"))


# ---------- 1. 基本信息 ----------
basic = cached("basic", lambda: df_records(ak.fund_individual_basic_info_xq(symbol=CODE)))

# ---------- 2. 净值走势 ----------
nav = cached("nav", lambda: df_records(ak.fund_open_fund_info_em(symbol=CODE, indicator="单位净值走势")))
cumnav = cached("cumnav", lambda: df_records(ak.fund_open_fund_info_em(symbol=CODE, indicator="累计净值走势")))

# ---------- 3. 业绩与排名 ----------
achieve = cached("achieve", lambda: df_records(ak.fund_individual_achievement_xq(symbol=CODE)))

# ---------- 4. 历任经理(东财 f10) ----------
def fetch_managers():
    r = requests.get(f"http://fundf10.eastmoney.com/jjjl_{CODE}.html", timeout=15, headers=UA)
    rows = re.findall(r"<tr>(.*?)</tr>", r.text, re.S)
    out = []
    for row in rows:
        cells = [re.sub(r"<[^>]+>", "", c).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len(cells) == 5 and re.match(r"\d{4}-\d{2}-\d{2}", cells[0]):
            out.append({"start": cells[0], "end": cells[1], "managers": cells[2],
                        "days": cells[3], "ret": cells[4]})
    return out
managers = cached("managers", fetch_managers)

# ---------- 5. 规模:由持有人结构的总份额 × 净值推算,不单独抓 ----------

# ---------- 6. 持有人结构(东财 f10) ----------
def fetch_holders():
    r = requests.get(f"http://fundf10.eastmoney.com/cyrjg_{CODE}.html", timeout=15, headers=UA)
    rows = re.findall(r"<tr>(.*?)</tr>", r.text, re.S)
    out = []
    for row in rows:
        cells = [re.sub(r"<[^>]+>", "", c).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len(cells) >= 5 and re.match(r"\d{4}", cells[0]):
            out.append({"date": cells[0], "inst": cells[1], "retail": cells[2],
                        "internal": cells[3], "total_share": cells[4]})
    return out
holders = cached("holders", fetch_holders)

# ---------- 7. 逐年季度持仓 ----------
y0 = int(basic[3]["value"][:4]) if "成立" in basic[3]["item"] else 2018
import datetime
for year in range(y0, datetime.date.today().year + 1):
    cached(f"hold_{year}", lambda y=year: df_records(ak.fund_portfolio_hold_em(symbol=CODE, date=str(y))))

# ---------- 8. 沪深300 指数(对照) ----------
def fetch_csi300():
    df = ak.stock_zh_index_daily(symbol="sh000300")
    df["date"] = df["date"].astype(str)
    df = df[df["date"] >= "2017-06-01"]
    return df_records(df[["date", "close"]])
csi300 = cached("csi300", fetch_csi300)

print("\n全部完成 →", DIR)
