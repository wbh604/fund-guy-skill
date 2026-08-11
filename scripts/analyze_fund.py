#!/usr/bin/env python3
"""基于抓取的真实数据计算 skill 指标,输出 .cache/fund_<code>/analysis.json。

买卖事件推断规则(诚实原则):
- Q2/Q4 为中报/年报全持仓,Q1/Q3 仅前十大
- 首次披露 = 买入;持股数环比 +25% = 加仓;-25% = 减仓
- 在全持仓期(Q2/Q4)消失 = 清仓(推断);仅在前十大期消失不算卖出,仓位延续
- 盈亏 = Σ 上期持股数 × 季度末价差(估算,标注口径)
"""
import json, os, re, sys
from collections import defaultdict

CODE = sys.argv[1] if len(sys.argv) > 1 else "163417"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, ".cache", f"fund_{CODE}")
KDIR = os.path.join(DIR, "kline")

load = lambda n: json.load(open(os.path.join(DIR, n + ".json")))

# ---------- 季度工具 ----------
def qkey(s):
    m = re.match(r"(\d{4})年(\d)季度", s)
    return f"{m.group(1)}Q{m.group(2)}"

def qend(q):
    y, n = q.split("Q")
    return f"{y}-{['03-31','06-30','09-30','12-31'][int(n)-1]}"

def qlabel(q):
    return q[2:]

ALL_Q = [f"{y}Q{n}" for y in range(2018, 2027) for n in range(1, 5)][:34]  # 2018Q1..2026Q2
FULL = {q for q in ALL_Q if q.endswith("2") or q.endswith("4")}

# ---------- 持仓 ----------
hold = []
for f in sorted(os.listdir(DIR)):
    if f.startswith("hold_"):
        hold += load(f[:-5] if f.endswith(".json") else f)

shares = defaultdict(dict)   # code -> q -> 万股
weights = defaultdict(dict)  # code -> q -> %
mv = defaultdict(dict)       # code -> q -> 万元
names = {}
for r in hold:
    q = qkey(r["季度"])
    c = r["股票代码"]
    names[c] = r["股票名称"]
    shares[c][q] = r["持股数"]
    weights[c][q] = r["占净值比例"] or 0
    mv[c][q] = r["持仓市值"]

# ---------- 周K ----------
klines = {}
for f in os.listdir(KDIR):
    klines[f[:-5]] = json.load(open(os.path.join(KDIR, f)))

def px(code, date):
    """date 当日或之前最近周收盘"""
    prev = None
    for row in klines[code]:
        if row[0] > date:
            break
        prev = row
    return prev[4] if prev else None

# ---------- 每只股票:事件 + 盈亏 ----------
stocks_out = []
for code in klines:
    ks = klines[code]
    events, pnl, sellfly = [], 0.0, 0.0
    pos = None       # 当前持股(万股)
    last_q = None    # 上一个计价季度
    for q in ALL_Q:
        d = qend(q)
        if q in shares[code]:
            sh = shares[code][q]
            p_now = px(code, d)
            if pos is None:
                events.append({"date": d, "act": "buy", "label": "买入", "q": qlabel(q)})
            else:
                if p_now and last_q:
                    p_prev = px(code, qend(last_q))
                    if p_prev:
                        pnl += pos * (p_now - p_prev)
                ratio = sh / pos if pos else 9
                if ratio >= 1.25:
                    events.append({"date": d, "act": "buy", "label": "加仓", "q": qlabel(q)})
                elif ratio <= 0.75:
                    events.append({"date": d, "act": "sell", "label": "减仓", "q": qlabel(q)})
                else:
                    events.append({"date": d, "act": "hold", "label": "持", "q": qlabel(q)})
            pos, last_q = sh, q
        else:
            if pos is not None and q in FULL:
                p_now, p_prev = px(code, d), px(code, qend(last_q))
                if p_now and p_prev:
                    pnl += pos * (p_now - p_prev)
                events.append({"date": d, "act": "sell", "label": "清仓", "q": qlabel(q)})
                # 卖飞:清仓后12个月最高收盘
                y, mo, dd = map(int, d.split("-"))
                end = f"{y+1}-{mo:02d}-{dd:02d}"
                future = [r[4] for r in ks if d < r[0] <= end]
                if future and p_now:
                    sellfly = max(sellfly, (max(future) - p_now) / p_now)
                pos, last_q = None, None
    if pos is not None:  # 仍持有,按最新价 mark
        p_now, p_prev = ks[-1][4], px(code, qend(last_q))
        if p_now and p_prev:
            pnl += pos * (p_now - p_prev)

    peak_w = max(weights[code].values())
    n_disc = len(shares[code])
    anchors = [e for e in events if e["act"] != "hold"]
    still = pos is not None
    amount_yi = round(pnl / 10000, 2)  # 万股×元=万元 → 亿
    stocks_out.append({
        "name": names[code], "code": code, "industry": "",
        "weight": peak_w, "skill": "", "skill_key": "",
        "verdict": f"{'仍在持仓' if still else '已退出'} · 披露 {n_disc} 期 · 买卖动作 {len(anchors)} 次(按季报持股数推断)",
        "rating": f"峰值仓位 {peak_w:.1f}% · {'持有中' if still else '完整闭环'}",
        "amount": amount_yi, "ret_pct": 0.0,
        "sellfly_pct": round(sellfly * 100, 1),
        "n_disclose": n_disc,
        "points": events,
        "kline": ks,
    })

stocks_out.sort(key=lambda s: -s["amount"])

# ---------- 基金层面 ----------
cumnav = load("cumnav")
key_v = [k for k in cumnav[0] if "净值" in k and "日期" not in k][0]
key_d = [k for k in cumnav[0] if "日期" in k][0]
navs = [(r[key_d][:10], r[key_v]) for r in cumnav if r[key_v]]

peak, dd_max, dd_start, dd_trough = navs[0][1], 0, None, None
peak_d = navs[0][0]
cur_uw_start, uw_longest, uw_span = None, 0, ("", "")
for d, v in navs:
    if v >= peak:
        if cur_uw_start:
            from datetime import date as D
            days = (D(*map(int, d.split("-"))) - D(*map(int, cur_uw_start.split("-")))).days
            if days > uw_longest:
                uw_longest, uw_span = days, (cur_uw_start, d)
            cur_uw_start = None
        peak, peak_d = v, d
    else:
        if cur_uw_start is None:
            cur_uw_start = peak_d
        dd = (peak - v) / peak
        if dd > dd_max:
            dd_max, dd_start, dd_trough = dd, peak_d, d
# 未修复的水下段
if cur_uw_start:
    from datetime import date as D
    days = (D(*map(int, navs[-1][0].split("-"))) - D(*map(int, cur_uw_start.split("-")))).days
    if days > uw_longest:
        uw_longest, uw_span = days, (cur_uw_start, "至今")

# 规模估算(每季度 Σ市值/Σ比例)
scale = []
for q in ALL_Q:
    tot_mv = sum(mv[c].get(q, 0) or 0 for c in mv if q in mv[c])
    tot_w = sum(weights[c].get(q, 0) or 0 for c in weights if q in weights[c])
    if tot_w > 5:
        scale.append({"q": qlabel(q), "yi": round(tot_mv / tot_w * 100 / 10000, 1)})

# 年度收益 vs 沪深300
achieve = load("achieve")
annual = [r for r in achieve if r["业绩类型"] == "年度业绩" and r["周期"] not in ("成立以来", "今年以来")]
csi = load("csi300")
csi_by_year = defaultdict(list)
for r in csi:
    csi_by_year[r["date"][:4]].append(r["close"])
years_out = []
for r in sorted(annual, key=lambda x: x["周期"]):
    y = r["周期"]
    closes = csi_by_year.get(y)
    prev = csi_by_year.get(str(int(y) - 1))
    idx_ret = round((closes[-1] / prev[-1] - 1) * 100, 1) if closes and prev else None
    years_out.append({"year": y, "fund": round(r["本产品区间收益"], 1), "csi300": idx_ret,
                      "dd": r["本产品最大回撒"], "rank": r["周期收益同类排名"],
                      "win": idx_ret is not None and r["本产品区间收益"] > idx_ret})

managers = load("managers")
basic = {r["item"]: r["value"] for r in load("basic")}

out = {
    "meta": basic,
    "managers": managers,
    "years": years_out,
    "nav_metrics": {
        "total_ret": round((navs[-1][1] / navs[0][1] - 1) * 100, 1),
        "since": navs[0][0], "until": navs[-1][0],
        "max_dd": round(dd_max * 100, 1), "dd_from": dd_start, "dd_to": dd_trough,
        "underwater_days": uw_longest, "uw_from": uw_span[0], "uw_to": uw_span[1],
    },
    "scale": scale,
    "replay": {"aum": None, "stocks": stocks_out},
}
json.dump(out, open(os.path.join(DIR, "analysis.json"), "w"), ensure_ascii=False)

print(f"净值:{out['nav_metrics']['since']} → {out['nav_metrics']['until']}  累计 +{out['nav_metrics']['total_ret']}%")
print(f"最大回撤:{out['nav_metrics']['max_dd']}%  ({dd_start} → {dd_trough})")
print(f"最长水下:{uw_longest} 天  ({uw_span[0]} → {uw_span[1]})")
print(f"规模估算:{scale[-1]['q']} ≈ {scale[-1]['yi']} 亿" if scale else "规模估算失败")
print("\n年度: ", " ".join(f"{y['year']}:{y['fund']:+.0f}%{'√' if y['win'] else '×'}" for y in years_out))
print("\n买卖复盘(按估算盈亏排序):")
for s in stocks_out:
    print(f"  {s['name']:<8} {s['amount']:+8.2f}亿  披露{s['n_disclose']:>2}期  "
          f"动作{len([p for p in s['points'] if p['act']!='hold']):>2}次  卖飞{s['sellfly_pct']:5.1f}%")
