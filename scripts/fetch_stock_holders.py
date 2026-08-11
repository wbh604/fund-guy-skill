#!/usr/bin/env python3
"""抓当前持仓(A股)的十大流通股东,识别特殊持仓者(国家队/社保/养老金/险资/北向)。

用法: .venv/bin/python scripts/fetch_stock_holders.py 163417
输出: .cache/fund_<code>/stock_holders.json
"""
import json, os, re, sys, time
import warnings
warnings.filterwarnings("ignore")

import akshare as ak

CODE = sys.argv[1] if len(sys.argv) > 1 else "163417"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, ".cache", f"fund_{CODE}")

# 最新一期前十大持仓
hold = []
for f in sorted(os.listdir(DIR)):
    if f.startswith("hold_2"):
        hold += json.load(open(os.path.join(DIR, f)))

def qkey(s):
    m = re.match(r"(\d{4})年(\d)季度", s)
    return f"{m.group(1)}Q{m.group(2)}"

latest = max(qkey(r["季度"]) for r in hold)
cur = [(r["股票代码"], r["股票名称"]) for r in hold if qkey(r["季度"]) == latest]

def em_symbol(code):
    if len(code) == 5:
        return None  # 港股无此口径
    return ("sh" if code.startswith(("60", "68")) else "sz") + code

RULES = [
    ("国家队", r"中央汇金|中国证券金融|证金公司|梧桐树|外汇管理局"),
    ("社保",   r"全国社保基金|社保基金.{0,4}组合"),
    ("养老金", r"基本养老保险基金"),
    ("险资",   r"人寿保险|财产保险|平安保险|太平洋保险|保险股份|养老保险股份|保险集团"),
    ("北向外资", r"香港中央结算"),
    ("QFII/外资", r"摩根|瑞银|高盛|淡马锡|挪威中央银行|新加坡政府|科威特|阿布达比"),
]

def classify(name):
    for typ, pat in RULES:
        if re.search(pat, name):
            return typ
    return None

out = {}
for code, name in cur:
    sym = em_symbol(code)
    if not sym:
        out[code] = {"name": name, "special": None, "note": "港股无此口径"}
        continue
    got = None
    for date in ("20260630", "20260331", "20251231"):
        try:
            df = ak.stock_gdfx_free_top_10_em(symbol=sym, date=date)
            if len(df):
                got = (date, df)
                break
        except Exception:
            pass
        time.sleep(0.8)
    if not got:
        out[code] = {"name": name, "special": None, "note": "未获取"}
        continue
    date, df = got
    specials = []
    for _, r in df.iterrows():
        typ = classify(str(r["股东名称"]))
        if typ:
            specials.append({
                "type": typ, "holder": str(r["股东名称"]),
                "pct": float(r["占总流通股本持股比例"] or 0),
                "chg": str(r["增减"]),
            })
    out[code] = {"name": name, "period": date, "special": specials}
    print(f"  {name:<8} {date}: {[(s['type'], round(s['pct'],2), s['chg']) for s in specials] or '无特殊持仓者'}")
    time.sleep(1.0)

json.dump(out, open(os.path.join(DIR, "stock_holders.json"), "w"), ensure_ascii=False)
print("done →", os.path.join(DIR, "stock_holders.json"))
