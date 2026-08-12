"""抓取天天基金 pingzhongdata 单文件接口,解析关键变量落缓存。

一次请求可得:申购赎回/总份额、持有人结构、规模、经理(含照片+东财五维分)、
平台五维评价、同类排名走势、估算仓位序列。见 SKILL.md「一击必中接口」。
"""
import json
import os
import re
import sys
import urllib.request

CODE = sys.argv[1] if len(sys.argv) > 1 else "163417"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, ".cache", f"fund_{CODE}")
os.makedirs(DIR, exist_ok=True)

req = urllib.request.Request(
    f"https://fund.eastmoney.com/pingzhongdata/{CODE}.js",
    headers={"User-Agent": "Mozilla/5.0", "Referer": "https://fund.eastmoney.com/"})
raw = urllib.request.urlopen(req, timeout=15).read().decode("utf-8-sig", errors="ignore")


def grab(name):
    m = re.search(rf'var {name}\s*=\s*(\[.*?\]|\{{.*?\}}|"[^"]*")\s*;', raw, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


out = {k: grab(k) for k in [
    "Data_buySedemption",        # 每期申购/赎回/总份额(亿份)
    "Data_holderStructure",      # 机构/个人/内部持有比例
    "Data_fluctuationScale",     # 每期规模+环比
    "Data_currentFundManager",   # 经理:任期/总规模/星级/照片/东财五维
    "Data_performanceEvaluation",  # 平台五维评价(基金口径)
    "Data_rateInSimilarType",    # 同类排名走势
    "Data_fundSharesPositions",  # 估算股票仓位(derived,非披露值)
]}
json.dump(out, open(os.path.join(DIR, "pingzhongdata.json"), "w"), ensure_ascii=False)

bs = out["Data_buySedemption"]
print(f"申赎期数: {len(bs['categories'])}  {bs['categories'][0]} → {bs['categories'][-1]}")
for s in bs["series"]:
    print(f"  {s['name']}: 最近3期 {s['data'][-3:]}")
mgr = (out["Data_currentFundManager"] or [{}])[0]
print(f"经理: {mgr.get('name')} 东财五维均分 {mgr.get('power', {}).get('avr')}")
print(f"→ {DIR}/pingzhongdata.json")
