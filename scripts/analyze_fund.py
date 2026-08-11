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

# ---------- 基金份额估算(判定被动减仓用) ----------
# 每季度规模 ≈ Σ持仓市值/Σ占比;份额 ≈ 规模/单位净值
nav_unit_rows = load("nav")
_k_d = [k for k in nav_unit_rows[0] if "日期" in k][0]
_k_v = [k for k in nav_unit_rows[0] if "净值" in k and "日期" not in k][0]
nav_unit = [(r[_k_d][:10], r[_k_v]) for r in nav_unit_rows if r[_k_v]]

def unit_nav_at(d):
    prev = None
    for dd, v in nav_unit:
        if dd > d:
            break
        prev = v
    return prev

fund_shares = {}  # q -> 估算总份额(亿份)
for q in ALL_Q:
    tot_mv = sum(mv[c].get(q, 0) or 0 for c in mv if q in mv[c])
    tot_w = sum(weights[c].get(q, 0) or 0 for c in weights if q in weights[c])
    u = unit_nav_at(qend(q))
    if tot_w > 5 and u:
        fund_shares[q] = (tot_mv / tot_w * 100 / 10000) / u

# ---------- 每只股票:事件 + 盈亏 + 成本/卖出线 ----------
stocks_out = []
for code in klines:
    ks = klines[code]
    events, pnl, sellfly = [], 0.0, 0.0
    pos = None       # 当前持股(万股)
    last_q = None    # 上一个计价季度
    cost_sh, cost_amt = 0.0, 0.0   # 累计买入股数/金额(全部买入动作加权)
    exits = []                      # 清仓价(卖出线)
    for q in ALL_Q:
        d = qend(q)
        if q in shares[code]:
            sh = shares[code][q]
            p_now = px(code, d)
            if pos is None:
                events.append({"date": d, "act": "buy", "label": "买入", "q": qlabel(q)})
                if p_now:
                    cost_sh += sh
                    cost_amt += sh * p_now
            else:
                if p_now and last_q:
                    p_prev = px(code, qend(last_q))
                    if p_prev:
                        pnl += pos * (p_now - p_prev)
                ratio = sh / pos if pos else 9
                if ratio >= 1.25:
                    events.append({"date": d, "act": "buy", "label": "加仓", "q": qlabel(q)})
                    if p_now:
                        cost_sh += sh - pos
                        cost_amt += (sh - pos) * p_now
                elif ratio <= 0.75:
                    # 被动减仓判定:①上季逼近10%双十红线 ②基金份额同期大幅缩水(赎回)
                    w_prev = weights[code].get(last_q, 0) or 0
                    f_now, f_prev = fund_shares.get(q), fund_shares.get(last_q)
                    fund_shrink = (1 - f_now / f_prev) if (f_now and f_prev) else 0
                    stock_cut = 1 - ratio
                    if w_prev >= 9.3:
                        events.append({"date": d, "act": "sell", "label": "被动减·触线",
                                       "q": qlabel(q), "passive": "cap"})
                    elif fund_shrink > 0.12 and stock_cut <= fund_shrink + 0.20:
                        events.append({"date": d, "act": "sell", "label": "被动减·赎回",
                                       "q": qlabel(q), "passive": "redeem"})
                    else:
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
                if p_now:
                    exits.append(round(p_now, 2))
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
    avg_cost = round(cost_amt / cost_sh, 2) if cost_sh else None

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
        "cost": avg_cost,
        "exits": exits[:3],
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

# ---------- 机构视角:风险调整指标(基于累计净值日收益 vs 沪深300) ----------
import math

csi_close = {r["date"][:10]: r["close"] for r in csi}
nav_map = dict(navs)
common = sorted(set(nav_map) & set(csi_close))
rf_ann = 0.02

rets_f, rets_i = [], []
for a, b in zip(common, common[1:]):
    if nav_map[a] and csi_close[a]:
        rets_f.append(nav_map[b] / nav_map[a] - 1)
        rets_i.append(csi_close[b] / csi_close[a] - 1)

n = len(rets_f)
mean = lambda xs: sum(xs) / len(xs)
def std(xs):
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))

from datetime import date as _D
cal_days = (_D(*map(int, common[-1].split("-"))) - _D(*map(int, common[0].split("-")))).days
ann_f = (nav_map[common[-1]] / nav_map[common[0]]) ** (365.25 / cal_days) - 1
ann_i = (csi_close[common[-1]] / csi_close[common[0]]) ** (365.25 / cal_days) - 1
vol_f = std(rets_f) * math.sqrt(250)
downside = [r for r in rets_f if r < 0]
dvol = std(downside) * math.sqrt(250) if len(downside) > 2 else vol_f
sharpe = (ann_f - rf_ann) / vol_f
sortino = (ann_f - rf_ann) / dvol
calmar = ann_f / (dd_max) if dd_max else 0

mf, mi = mean(rets_f), mean(rets_i)
cov = sum((a - mf) * (b - mi) for a, b in zip(rets_f, rets_i)) / (n - 1)
var_i = std(rets_i) ** 2
beta = cov / var_i
alpha_ann = ann_f - (rf_ann + beta * (ann_i - rf_ann))
diff = [a - b for a, b in zip(rets_f, rets_i)]
te = std(diff) * math.sqrt(250)
ir = (ann_f - ann_i) / te if te else 0
corr = cov / (std(rets_f) * std(rets_i))
r2 = corr ** 2

# 月度胜率 + 上/下行捕获
month_last = {}
for d in common:
    month_last[d[:7]] = d
months = sorted(month_last.values())
mret_f, mret_i = [], []
for a, b in zip(months, months[1:]):
    mret_f.append(nav_map[b] / nav_map[a] - 1)
    mret_i.append(csi_close[b] / csi_close[a] - 1)
mwin = sum(1 for a, b in zip(mret_f, mret_i) if a > b) / len(mret_f)
up_i = [(a, b) for a, b in zip(mret_f, mret_i) if b > 0]
dn_i = [(a, b) for a, b in zip(mret_f, mret_i) if b < 0]
up_cap = mean([a for a, _ in up_i]) / mean([b for _, b in up_i]) * 100
dn_cap = mean([a for a, _ in dn_i]) / mean([b for _, b in dn_i]) * 100

# 持仓集中度:每季度前十大权重合计
conc = []
for q in ALL_Q:
    ws = sorted((weights[c][q] for c in weights if q in weights[c] and weights[c][q]), reverse=True)
    if ws:
        conc.append({"q": qlabel(q), "top10": round(sum(ws[:10]), 1)})
# 最近一期真正的全持仓(中报/年报,持股数>=30 才算已发布)
latest_full, n_stocks_latest = None, None
for q in reversed(ALL_Q):
    if q in FULL:
        cnt = sum(1 for c in shares if q in shares[c])
        if cnt >= 30:
            latest_full, n_stocks_latest = q, cnt
            break

pro = {
    "ann_ret": round(ann_f * 100, 1), "ann_idx": round(ann_i * 100, 1),
    "vol": round(vol_f * 100, 1),
    "sharpe": round(sharpe, 2), "sortino": round(sortino, 2), "calmar": round(calmar, 2),
    "beta": round(beta, 2), "alpha": round(alpha_ann * 100, 1),
    "te": round(te * 100, 1), "ir": round(ir, 2), "r2": round(r2, 2),
    "mwin": round(mwin * 100), "n_months": len(mret_f),
    "up_cap": round(up_cap), "dn_cap": round(dn_cap),
    "top10_avg": round(mean([c["top10"] for c in conc]), 1),
    "top10_latest": conc[-1]["top10"] if conc else None,
    "n_stocks": n_stocks_latest, "n_stocks_period": qlabel(latest_full) if latest_full else "",
}

# ---------- 择时能力:买卖点验尸 ----------
def date_plus(d, days):
    from datetime import date as D, timedelta
    y, mo, dd = map(int, d.split("-"))
    return str(D(y, mo, dd) + timedelta(days=days))

def csi_at(d):
    prev = None
    for r in csi:
        if r["date"][:10] > d:
            break
        prev = r["close"]
    return prev

buy_calls, sell_calls = [], []
n_passive = {"cap": 0, "redeem": 0}
for st in stocks_out:
    code = st["code"]
    for p in st["points"]:
        if p["act"] == "hold":
            continue
        if p.get("passive"):
            n_passive[p["passive"]] += 1
            continue  # 被动减仓不是决策,不进验尸
        d = p["date"]
        p0 = px(code, d)
        d1 = date_plus(d, 365)
        p1 = px(code, d1)
        if not p0 or not p1 or d1 > klines[code][-1][0]:
            continue
        fwd = p1 / p0 - 1
        i0, i1 = csi_at(d), csi_at(d1)
        excess = fwd - (i1 / i0 - 1) if i0 and i1 else None
        rec = {"name": st["name"], "label": p["label"], "q": p["q"],
               "fwd": round(fwd * 100, 1),
               "excess": round(excess * 100, 1) if excess is not None else None}
        if p["act"] == "buy":
            buy_calls.append(rec)
        else:
            sell_calls.append(rec)

buy_wins = [c for c in buy_calls if c["excess"] is not None and c["excess"] > 0]
sell_dodge = [c for c in sell_calls if c["fwd"] < 0]
timing = {
    "n_buy": len(buy_calls),
    "buy_win_rate": round(len(buy_wins) / len(buy_calls) * 100) if buy_calls else None,
    "buy_avg_excess": round(mean([c["excess"] for c in buy_calls if c["excess"] is not None]), 1),
    "best_buy": max(buy_calls, key=lambda c: c["excess"] or -999),
    "worst_buy": min(buy_calls, key=lambda c: c["excess"] or 999),
    "n_sell": len(sell_calls),
    "dodge_rate": round(len(sell_dodge) / len(sell_calls) * 100) if sell_calls else None,
    "sell_avg_fwd": round(mean([c["fwd"] for c in sell_calls]), 1),
    "best_sell": min(sell_calls, key=lambda c: c["fwd"]),
    "worst_sell": max(sell_calls, key=lambda c: c["fwd"]),
}

# TM 择时回归: r_f - rf = a + b(r_m - rf) + g(r_m - rf)^2
rf_d = rf_ann / 250
X1 = [r - rf_d for r in rets_i]
X2 = [x * x for x in X1]
Y = [r - rf_d for r in rets_f]
mx1, mx2, my = mean(X1), mean(X2), mean(Y)
s11 = sum((a - mx1) ** 2 for a in X1)
s22 = sum((a - mx2) ** 2 for a in X2)
s12 = sum((a - mx1) * (b - mx2) for a, b in zip(X1, X2))
s1y = sum((a - mx1) * (b - my) for a, b in zip(X1, Y))
s2y = sum((a - mx2) * (b - my) for a, b in zip(X2, Y))
det = s11 * s22 - s12 * s12
tm_b = (s1y * s22 - s2y * s12) / det
tm_g = (s2y * s11 - s1y * s12) / det
tm_a = my - tm_b * mx1 - tm_g * mx2
resid = [y - (tm_a + tm_b * a + tm_g * b) for y, a, b in zip(Y, X1, X2)]
sse = sum(r * r for r in resid) / (n - 3)
se_g = math.sqrt(sse * s11 / det)
tm_t = tm_g / se_g if se_g else 0

# 仓位择时:全持仓期股票仓位变化 vs 随后6个月沪深300
pos_pts = []
for q in ALL_Q:
    if q in FULL:
        ws = sum(weights[c].get(q, 0) or 0 for c in weights if q in weights[c])
        if ws > 30:
            pos_pts.append((q, round(ws, 1)))
pos_timing = []
for (q0, w0), (q1, w1) in zip(pos_pts, pos_pts[1:]):
    d1 = qend(q1)
    d2 = date_plus(d1, 183)
    i1, i2 = csi_at(d1), csi_at(d2)
    if i1 and i2 and d2 <= csi[-1]["date"][:10]:
        pos_timing.append({"q": qlabel(q1), "dw": round(w1 - w0, 1),
                           "mkt6m": round((i2 / i1 - 1) * 100, 1)})
same_dir = sum(1 for p in pos_timing if (p["dw"] > 1 and p["mkt6m"] > 0) or (p["dw"] < -1 and p["mkt6m"] < 0))
moves = sum(1 for p in pos_timing if abs(p["dw"]) > 1)

# ---------- 控制能力 ----------
# 熊市年防守(基准为负的年份,他的超额)
bear_years = [y for y in years_out if y["csi300"] is not None and y["csi300"] < 0]
bear_defense = [{"year": y["year"], "fund": y["fund"], "idx": y["csi300"],
                 "excess": round(y["fund"] - y["csi300"], 1)} for y in bear_years]
# 大盘最差 10 个月的超额
ranked = sorted(zip(mret_f, mret_i), key=lambda ab: ab[1])[:10]
worst10_excess = round(mean([a - b for a, b in ranked]) * 100, 1)

# 浮亏时的处置:动作时价格低于当时加权成本 → 加仓(越跌越买) or 减仓(止损)
addl, cutl = 0, 0
for st in stocks_out:
    code = st["code"]
    c_sh, c_amt = 0.0, 0.0
    prev_sh = None
    for p in st["points"]:
        pnow = px(code, p["date"])
        if not pnow:
            continue
        if p["label"] == "买入":
            c_sh, c_amt = 1.0, pnow
        elif p["label"] == "加仓":
            if c_sh and pnow < c_amt / c_sh:
                addl += 1
            c_sh += 0.5
            c_amt += 0.5 * pnow
        elif p["act"] == "sell" and not p.get("passive"):
            if c_sh and pnow < c_amt / c_sh:
                cutl += 1

# ---------- 双轴评分(规则透明) ----------
timing_score = 0
if timing["buy_win_rate"] is not None:
    timing_score += timing["buy_win_rate"] * 0.4
if timing["dodge_rate"] is not None:
    timing_score += timing["dodge_rate"] * 0.4
timing_score += 10 if (tm_g > 0 and tm_t > 1.5) else (5 if tm_g > 0 else 0)
timing_score += 10 * (same_dir / moves) if moves else 5
timing_score = round(timing_score)

bear_avg = mean([b["excess"] for b in bear_defense]) if bear_defense else 0
control_score = 0
control_score += max(0, min(40, 20 + bear_avg * 2.5))       # 熊市年均超额 ±8pp → 0-40
control_score += max(0, min(30, 15 + worst10_excess * 7.5))  # 最差10月超额 ±2pp → 0-30
control_score += max(0, min(30, 16 + (100 - dn_cap) * 2))    # 下行捕获每低1点+2分
control_score = round(control_score)

# ---------- 抄作业指数:经理时钟 vs 披露时钟 ----------
# 季报(Q1/Q3)约在季末后 15 个工作日披露(+30 天),中报/年报(Q2/Q4)+60 天
def copy_trade():
    mgr_ex, copy_ex = [], []
    for st in stocks_out:
        code = st["code"]
        for p in st["points"]:
            if p["act"] != "buy" or p.get("passive"):
                continue
            d0 = p["date"]
            lag = 60 if p["q"].endswith(("2", "4")) else 30
            d_copy = date_plus(d0, lag)
            for start, sink in ((d0, mgr_ex), (d_copy, copy_ex)):
                p0, p1 = px(code, start), px(code, date_plus(start, 365))
                if not p0 or not p1 or date_plus(start, 365) > klines[code][-1][0]:
                    continue
                i0, i1 = csi_at(start), csi_at(date_plus(start, 365))
                if i0 and i1:
                    sink.append((p1 / p0 - 1) - (i1 / i0 - 1))
    return (round(mean(mgr_ex) * 100, 1) if mgr_ex else None,
            round(mean(copy_ex) * 100, 1) if copy_ex else None,
            len(mgr_ex))

copy_mgr, copy_follow, copy_n = copy_trade()

# ---------- Alpha 到手率:资金加权收益(基民) vs 时间加权收益(基金) ----------
# 季度申赎流 ≈ 规模变化 - 存量增值;IRR 解资金加权年化
def money_weighted():
    sq = [(x["q"], x["yi"]) for x in scale]
    if len(sq) < 8:
        return None
    def nav_at_q(q):
        y = "20" + q[:2]
        return unit_nav_at(f"{y}-{['03-31','06-30','09-30','12-31'][int(q[-1])-1]}")
    flows = [-sq[0][1]]
    for (q0, s0), (q1, s1) in zip(sq, sq[1:]):
        n0, n1 = nav_at_q(q0), nav_at_q(q1)
        if not n0 or not n1:
            flows.append(0)
            continue
        flows.append(-(s1 - s0 * (n1 / n0)))  # 申购为负现金流(投入)
    flows[-1] += sq[-1][1]  # 期末价值收回
    # 二分求季度 IRR
    def npv(r):
        return sum(f / (1 + r) ** i for i, f in enumerate(flows))
    lo, hi = -0.5, 0.5
    for _ in range(80):
        mid = (lo + hi) / 2
        if npv(mid) > 0:
            lo = mid
        else:
            hi = mid
    return round(((1 + (lo + hi) / 2) ** 4 - 1) * 100, 1)

mwr = money_weighted()
twr = round(ann_f * 100, 1)

# ---------- 机构资金画像(真实持有人结构) ----------
inst_series = []
try:
    for h in reversed(load("holders2")):
        inst_series.append({"date": h["date"][:7], "inst": float(h["inst"].replace("%", "")),
                            "share_yi": float(h["total_share_yi"])})
except Exception:
    pass

# ---------- 多因子运气拆解(月度收益回归风格因子) ----------
factor_out = None
try:
    idx = {}
    for nm in ("csi500", "csi1000", "growth", "value"):
        idx[nm] = {r["date"][:10]: r["close"] for r in load("idx_" + nm)}
    f_m, x_m = [], []
    for a, b in zip(months, months[1:]):
        ok_all = all(a in idx[nm] and b in idx[nm] for nm in idx) and a in csi_close and b in csi_close
        if not ok_all:
            # 用月末最近交易日对齐
            def at(series, d):
                prev = None
                for k in sorted(series):
                    if k > d:
                        break
                    prev = series[k]
                return prev
            r300 = csi_close[b] / csi_close[a] - 1
            rets = {nm: at(idx[nm], b) / at(idx[nm], a) - 1 for nm in idx}
        else:
            r300 = csi_close[b] / csi_close[a] - 1
            rets = {nm: idx[nm][b] / idx[nm][a] - 1 for nm in idx}
        f_m.append(nav_map[b] / nav_map[a] - 1)
        x_m.append([r300, rets["csi500"] - r300, rets["csi1000"] - rets["csi500"],
                    rets["growth"] - rets["value"]])
    # OLS: y = a + Xb (4因子)
    nn, kk = len(f_m), 4
    X = [[1.0] + row for row in x_m]
    XtX = [[sum(X[i][a] * X[i][b] for i in range(nn)) for b in range(kk + 1)] for a in range(kk + 1)]
    Xty = [sum(X[i][a] * f_m[i] for i in range(nn)) for a in range(kk + 1)]
    # 高斯消元
    M = [row[:] + [Xty[r]] for r, row in enumerate(XtX)]
    for col in range(kk + 1):
        piv = max(range(col, kk + 1), key=lambda r: abs(M[r][col]))
        M[col], M[piv] = M[piv], M[col]
        for r in range(kk + 1):
            if r != col and M[col][col]:
                f = M[r][col] / M[col][col]
                M[r] = [a - f * b for a, b in zip(M[r], M[col])]
    beta = [M[r][kk + 1] / M[r][r] for r in range(kk + 1)]
    yhat = [sum(b * x for b, x in zip(beta, X[i])) for i in range(nn)]
    ss_res = sum((y - h) ** 2 for y, h in zip(f_m, yhat))
    ss_tot = sum((y - mean(f_m)) ** 2 for y in f_m)
    factor_out = {
        "alpha_m": round(beta[0] * 100, 2), "alpha_ann": round(beta[0] * 12 * 100, 1),
        "b_mkt": round(beta[1], 2), "b_size5": round(beta[2], 2),
        "b_size10": round(beta[3], 2), "b_growth": round(beta[4], 2),
        "r2": round(1 - ss_res / ss_tot, 2), "n": nn,
    }
except Exception as e:
    print("factor skip:", e)

# 总分 = 择时35% + 控制35% + 超额质量30%(信息比率映射)
quality = min(100, round(ir * 100))
total_score = round(timing_score * 0.35 + control_score * 0.35 + quality * 0.30)

ability = {
    "timing": timing, "tm_gamma": round(tm_g, 2), "tm_t": round(tm_t, 1),
    "pos_timing": pos_timing, "pos_same_dir": same_dir, "pos_moves": moves,
    "bear_defense": bear_defense, "worst10_excess": worst10_excess,
    "loss_add": addl, "loss_cut": cutl,
    "passive_cap": n_passive["cap"], "passive_redeem": n_passive["redeem"],
    "copy_mgr": copy_mgr, "copy_follow": copy_follow, "copy_n": copy_n,
    "mwr": mwr, "twr": twr,
    "inst_series": inst_series,
    "factor": factor_out,
    "timing_score": timing_score, "control_score": control_score,
    "quality_score": quality, "total_score": total_score,
    "buy_calls": buy_calls, "sell_calls": sell_calls,
}

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
    "pro": pro,
    "ability": ability,
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
