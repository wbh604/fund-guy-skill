"""全市场今年收益 TOP10 主动基金 vs 目标经理当前持仓的同步度。

口径:
- 排行来自东财开放式基金排行(今年来),剔除指数/ETF/联接/QDII/FOF 等非主动选股产品
- 同一基金多个份额(A/C/E)只留今年来最高的一个
- 同步度 = 对方最新前十大里,与他当前前十大同名的只数 / 10
"""
import json
import os
import re
import sys
import time

import akshare as ak

CODE = sys.argv[1] if len(sys.argv) > 1 else "163417"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, ".cache", f"fund_{CODE}")

my = json.load(open(os.path.join(DIR, "analysis.json")))
my_names = {s["name"] for s in my["replay"]["stocks"] if s.get("cur_w")}
print(f"他的当前前十大: {sorted(my_names)}")

rank = ak.fund_open_fund_rank_em(symbol="全部")
rank = rank.dropna(subset=["今年来"])
BAD = re.compile(r"指数|ETF|联接|QDII|FOF|LOF联接|增强|沪深300|中证|标普|纳斯达克|恒生")
rank = rank[~rank["基金简称"].str.contains(BAD)]
rank = rank[rank["基金简称"].str.contains("混合|股票")]
rank = rank.sort_values("今年来", ascending=False)

# 去重份额:去掉尾缀 A/B/C/E/D 后的名字相同视为同一只
seen, top = set(), []
for _, r in rank.iterrows():
    base = re.sub(r"[ABCDE]$", "", r["基金简称"])
    if base in seen:
        continue
    seen.add(base)
    top.append(r)
    if len(top) >= 10:
        break

out = []
for r in top:
    code, name, ytd = r["基金代码"], r["基金简称"], float(r["今年来"])
    shared, latest_q = [], ""
    try:
        h = ak.fund_portfolio_hold_em(symbol=code, date="2026")
        if h is not None and len(h):
            latest_q = sorted(h["季度"].unique())[-1]
            top10 = h[h["季度"] == latest_q].nsmallest(10, "序号")
            shared = [n for n in top10["股票名称"] if n in my_names]
    except Exception as e:
        print(f"  {name} 持仓抓取失败: {e}")
    out.append({"code": code, "name": name, "ytd": ytd,
                "n_shared": len(shared), "shared": shared, "q": latest_q})
    print(f"  {name}({code}) 今年 +{ytd}% 撞 {len(shared)}/10: {shared}")
    time.sleep(1.5)

json.dump({"asof": str(rank.iloc[0]["日期"]) if len(rank) else "", "funds": out},
          open(os.path.join(DIR, "top_funds.json"), "w"), ensure_ascii=False)
print(f"→ {DIR}/top_funds.json")
