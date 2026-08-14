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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fund_meta import require_code
CODE = require_code()
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

# ---------- 6b. 费率(东财 F10 基金费率页,拿不到就空着) ----------
def fetch_fees():
    r = requests.get(f"http://fundf10.eastmoney.com/jjfl_{CODE}.html", timeout=15, headers=UA)
    r.raise_for_status()
    text = re.sub(r"<[^>]+>", " ", r.text).replace("&nbsp;", " ")
    text = re.sub(r"\s+", " ", text)
    def grab(label):
        m = re.search(rf"{label}\s*([0-9.]+%)", text)
        return m.group(1) if m else None
    return {
        "mgmt": grab("管理费率"),
        "custodian": grab("托管费率"),
        "sales": grab("销售服务费率"),
        "source": "eastmoney jjfl",
        "url": f"http://fundf10.eastmoney.com/jjfl_{CODE}.html",
    }
fees = cached("fees", fetch_fees)
print(f"  费率 管理 {fees.get('mgmt') or '未获取'} / 托管 {fees.get('custodian') or '未获取'}")

# ---------- 7. 逐年季度持仓 ----------
import datetime
_bmap = {r["item"]: r["value"] for r in basic} if basic and isinstance(basic[0], dict) else {}
_found = str(_bmap.get("成立时间") or "")
y0 = int(_found[:4]) if _found[:4].isdigit() else datetime.date.today().year - 5
for year in range(y0, datetime.date.today().year + 1):
    cached(f"hold_{year}", lambda y=year: df_records(ak.fund_portfolio_hold_em(symbol=CODE, date=str(y))))

# ---------- 8. 沪深300 指数(对照) ----------
def fetch_csi300():
    df = ak.stock_zh_index_daily(symbol="sh000300")
    df["date"] = df["date"].astype(str)
    df = df[df["date"] >= f"{max(y0 - 1, 2005)}-01-01"]
    return df_records(df[["date", "close"]])
csi300 = cached("csi300", fetch_csi300)

print("\n全部完成 →", DIR)
