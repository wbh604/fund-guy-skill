#!/usr/bin/env python3
"""House Consensus 与独立战争:目标基金 vs 同门权益基金的持仓分歧。

- House 组合 = 同门基金(排除目标经理自管)持仓等权平均(经理等权口径)
- 分歧度 = 0.5 × Σ|w_target - w_house|(主动份额式,按占净值权重)
- 逆共识验证:高分歧季度 vs 低分歧季度,随后6个月基金相对沪深300超额
输出 .cache/fund_<code>/house_analysis.json
"""
import json, os, re, sys
from collections import defaultdict

CODE = sys.argv[1] if len(sys.argv) > 1 else "163417"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, ".cache", f"fund_{CODE}")
HDIR = os.path.join(DIR, "house")

def qkey(s):
    m = re.match(r"(\d{4})年(\d)季度", s)
    return f"{m.group(1)}Q{m.group(2)}" if m else None

# 目标基金持仓
tgt = defaultdict(dict)
for f in sorted(os.listdir(DIR)):
    if f.startswith("hold_2"):
        for r in json.load(open(os.path.join(DIR, f))):
            q = qkey(r["季度"])
            if q and (r["占净值比例"] or 0) > 0:
                tgt[q][r["股票代码"]] = r["占净值比例"]

# 同门基金持仓: q -> fund -> {stock: w}
peers_hold = defaultdict(lambda: defaultdict(dict))
names = {}
for f in os.listdir(HDIR):
    m = re.match(r"hold_(\w+)_(\d{4})\.json", f)
    if not m:
        continue
    fc = m.group(1)
    for r in json.load(open(os.path.join(HDIR, f))):
        q = qkey(r["季度"])
        w = r["占净值比例"] or 0
        if q and w > 0:
            peers_hold[q][fc][r["股票代码"]] = w
            names[r["股票代码"]] = r["股票名称"]

QS = sorted(q for q in tgt if q >= "2021Q1" and q in peers_hold and len(peers_hold[q]) >= 8)

def norm100(port):
    tot = sum(port.values())
    return {c: w / tot * 100 for c, w in port.items()} if tot else {}

series = []
for q in QS:
    # 权益仓位过滤:披露权重合计 <8%(前十大期)视为偏债/迷你仓,剔出对照组
    active_funds = {fc: hp for fc, hp in peers_hold[q].items() if sum(hp.values()) >= 8}
    nf = len(active_funds)
    if nf < 8:
        continue
    # 每只基金先归一化到100,再等权平均 → 消除仓位水平差异
    house = defaultdict(float)
    for fc, hp in active_funds.items():
        for c, w in norm100(hp).items():
            house[c] += w / nf
    tw = norm100(tgt[q])
    stocks_union = set(tw) | set(house)
    div_pct = round(0.5 * sum(abs(tw.get(c, 0) - house.get(c, 0)) for c in stocks_union), 1)
    # 同门平均两两分歧(同样归一化口径)
    fcs = list(active_funds)[:20]
    pair = []
    for i in range(len(fcs)):
        for j in range(i + 1, min(i + 4, len(fcs))):
            a, b = norm100(active_funds[fcs[i]]), norm100(active_funds[fcs[j]])
            u = set(a) | set(b)
            pair.append(0.5 * sum(abs(a.get(c, 0) - b.get(c, 0)) for c in u))
    peer_avg = round(sum(pair) / len(pair), 1) if pair else None
    tw_raw_ref = tgt[q]
    # 公司共识重仓(他持有/不持有,含他的权重;归一化口径)
    top_house = sorted(house.items(), key=lambda kv: -kv[1])[:5]
    # 他"独"在哪:权重差最大的两侧(归一化口径)
    diffs = {c: tw.get(c, 0) - house.get(c, 0) for c in stocks_union}
    only_his = sorted(((c, d) for c, d in diffs.items() if d > 0.5), key=lambda kv: -kv[1])[:4]
    not_his = sorted(((c, d) for c, d in diffs.items() if d < -0.3), key=lambda kv: kv[1])[:4]
    series.append({
        "q": q[2:], "n_funds": nf, "divergence": div_pct, "peer_avg_div": peer_avg,
        "house_top": [{"name": names.get(c, c), "w": round(w, 2),
                       "his_w": round(tw.get(c, 0), 2), "he_holds": c in tw}
                      for c, w in top_house],
        "n_active": nf,
        "only_his": [{"name": names.get(c, c), "his_w": round(tw.get(c, 0), 2),
                      "house_w": round(tw.get(c, 0) - d, 2)} for c, d in only_his],
        "not_his": [{"name": names.get(c, c), "house_w": round(-d + tw.get(c, 0), 2),
                     "his_w": round(tw.get(c, 0), 2)} for c, d in not_his],
    })

# 逆共识验证:高/低分歧季度之后 6 个月的基金超额(vs 沪深300)
navr = json.load(open(os.path.join(DIR, "cumnav.json")))
kd = [k for k in navr[0] if "日期" in k][0]
kv = [k for k in navr[0] if "净值" in k and "日期" not in k][0]
nav = {r[kd][:10]: r[kv] for r in navr if r[kv]}
csi = {r["date"][:10]: r["close"] for r in json.load(open(os.path.join(DIR, "csi300.json")))}

def at(series_map, d):
    prev = None
    for k in sorted(series_map):
        if k > d:
            break
        prev = series_map[k]
    return prev

def qend(q):
    y = "20" + q[:2]
    return f"{y}-{['03-31','06-30','09-30','12-31'][int(q[-1])-1]}"

def fwd6(q):
    d0 = qend(q)
    from datetime import date as D, timedelta
    d1 = str(D(*map(int, d0.split("-"))) + timedelta(days=183))
    n0, n1, c0, c1 = at(nav, d0), at(nav, d1), at(csi, d0), at(csi, d1)
    if not all((n0, n1, c0, c1)) or d1 > max(nav):
        return None
    return (n1 / n0 - 1) - (c1 / c0 - 1)

valid = [s for s in series if s["divergence"] is not None and fwd6(s["q"]) is not None]
valid.sort(key=lambda s: s["divergence"])
half = len(valid) // 2
low, high = valid[:half], valid[half:]
lo_ex = round(sum(fwd6(s["q"]) for s in low) / len(low) * 100, 1) if low else None
hi_ex = round(sum(fwd6(s["q"]) for s in high) / len(high) * 100, 1) if high else None

# ---------- 全市场维度:他 vs 全市场公募共识 ----------
def market_analysis():
    files = sorted(f for f in os.listdir(HDIR) if f.startswith("market_"))
    if not files:
        return None
    ms = []
    for f in files:
        period = f[7:-5]                       # 20240630
        q = f"{period[:4]}Q{2 if period[4:6]=='06' else 4}"
        if q not in tgt:
            continue
        rows = json.load(open(os.path.join(HDIR, f)))
        tot = sum(r["持股总市值"] or 0 for r in rows)
        mkt_w = {r["股票代码"]: (r["持股总市值"] or 0) / tot * 100 for r in rows}
        mkt_names = {r["股票代码"]: r["股票简称"] for r in rows}
        # 双方归一化后算主动份额式分歧
        tw_raw = tgt[q]
        tsum = sum(tw_raw.values())
        tw_n = {c: w / tsum * 100 for c, w in tw_raw.items()}
        union = set(tw_n) | set(mkt_w)
        div = round(0.5 * sum(abs(tw_n.get(c, 0) - mkt_w.get(c, 0)) for c in union), 1)
        # 全市场抱团 TOP5 他跟不跟 + 他的组合有多少在拥挤区(TOP50)
        top5 = sorted(mkt_w.items(), key=lambda kv: -kv[1])[:5]
        top50 = {c for c, _ in sorted(mkt_w.items(), key=lambda kv: -kv[1])[:50]}
        crowd_w = round(sum(w for c, w in tw_raw.items() if c in top50), 1)
        ms.append({
            "q": q[2:], "divergence": div, "crowd_weight": crowd_w,
            "mkt_top": [{"name": mkt_names.get(c, c), "w": round(w, 2),
                         "his_w": round(tw_raw.get(c, 0), 2), "he_holds": c in tw_raw}
                        for c, w in top5],
        })
    return ms

mkt_series = market_analysis()

# ---------- 持仓最像的同门基金(最新期,归一化重合度) ----------
funds_meta = {f["code"]: f for f in json.load(open(os.path.join(HDIR, "funds.json")))}

def similar_funds():
    if not QS:
        return []
    q = QS[-1]
    tw = norm100(tgt[q])
    out = []
    for fc, hp in peers_hold[q].items():
        if sum(hp.values()) < 8:
            continue
        fw = norm100(hp)
        shared = set(tw) & set(fw)
        overlap = round(sum(min(tw[c], fw[c]) for c in shared), 1)
        if overlap < 3:
            continue
        top_shared = sorted(shared, key=lambda c: -min(tw[c], fw[c]))[:3]
        meta = funds_meta.get(fc, {})
        out.append({
            "code": fc, "name": meta.get("name", fc),
            "managers": " ".join(meta.get("managers", [])[:2]),
            "overlap": overlap,
            "shared": [names.get(c, c) for c in top_shared],
        })
    out.sort(key=lambda x: -x["overlap"])
    return out[:8]

sim = similar_funds()

out = {
    "series": series,
    "latest": series[-1] if series else None,
    "avg_divergence": round(sum(s["divergence"] for s in series) / len(series), 1),
    "contrarian": {"low_div_fwd6": lo_ex, "high_div_fwd6": hi_ex, "n": len(valid)},
    "market": {"series": mkt_series, "latest": mkt_series[-1] if mkt_series else None,
               "avg": round(sum(m["divergence"] for m in mkt_series) / len(mkt_series), 1)
               } if mkt_series else None,
    "similar_funds": sim,
}
json.dump(out, open(os.path.join(DIR, "house_analysis.json"), "w"), ensure_ascii=False)

print(f"季度数: {len(series)},同门样本 {series[-1]['n_funds'] if series else 0} 只")
print(f"平均分歧度: {out['avg_divergence']}%  最新: {series[-1]['divergence']}% (同门平均 {series[-1]['peer_avg_div']}%)")
print(f"逆共识: 高分歧季度后6M超额 {hi_ex}% vs 低分歧 {lo_ex}% (n={len(valid)})")
print("最新公司共识重仓:", [(x['name'], x['w'], '他也持有' if x['he_holds'] else '他不碰') for x in series[-1]['house_top']])
