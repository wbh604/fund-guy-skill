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

series = []
for q in QS:
    house = defaultdict(float)
    nf = len(peers_hold[q])
    for fc, hp in peers_hold[q].items():
        for c, w in hp.items():
            house[c] += w / nf
    tw = tgt[q]
    stocks_union = set(tw) | set(house)
    div = 0.5 * sum(abs(tw.get(c, 0) - house.get(c, 0)) for c in stocks_union)
    tot = 0.5 * (sum(tw.values()) + sum(house.values()))
    div_pct = round(div / tot * 100, 1) if tot else None
    # 同门平均两两分歧(他是不是最独的)
    fcs = list(peers_hold[q])[:20]
    pair = []
    for i in range(len(fcs)):
        for j in range(i + 1, min(i + 4, len(fcs))):  # 采样,够用
            a, b = peers_hold[q][fcs[i]], peers_hold[q][fcs[j]]
            u = set(a) | set(b)
            d = 0.5 * sum(abs(a.get(c, 0) - b.get(c, 0)) for c in u)
            t = 0.5 * (sum(a.values()) + sum(b.values()))
            if t:
                pair.append(d / t * 100)
    peer_avg = round(sum(pair) / len(pair), 1) if pair else None
    # 公司共识重仓(他持有/不持有,含他的权重)
    top_house = sorted(house.items(), key=lambda kv: -kv[1])[:5]
    # 他"独"在哪:权重差最大的两侧
    diffs = {c: tw.get(c, 0) - house.get(c, 0) for c in stocks_union}
    only_his = sorted(((c, d) for c, d in diffs.items() if d > 0.5), key=lambda kv: -kv[1])[:4]
    not_his = sorted(((c, d) for c, d in diffs.items() if d < -0.3), key=lambda kv: kv[1])[:4]
    series.append({
        "q": q[2:], "n_funds": nf, "divergence": div_pct, "peer_avg_div": peer_avg,
        "house_top": [{"name": names.get(c, c), "w": round(w, 2),
                       "his_w": round(tw.get(c, 0), 2), "he_holds": c in tw}
                      for c, w in top_house],
        "only_his": [{"name": names.get(c, c), "his_w": round(tgt[q].get(c, 0), 2),
                      "house_w": round(tgt[q].get(c, 0) - d, 2)} for c, d in only_his],
        "not_his": [{"name": names.get(c, c), "house_w": round(-d + tgt[q].get(c, 0), 2),
                     "his_w": round(tgt[q].get(c, 0), 2)} for c, d in not_his],
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

out = {
    "series": series,
    "latest": series[-1] if series else None,
    "avg_divergence": round(sum(s["divergence"] for s in series) / len(series), 1),
    "contrarian": {"low_div_fwd6": lo_ex, "high_div_fwd6": hi_ex, "n": len(valid)},
}
json.dump(out, open(os.path.join(DIR, "house_analysis.json"), "w"), ensure_ascii=False)

print(f"季度数: {len(series)},同门样本 {series[-1]['n_funds'] if series else 0} 只")
print(f"平均分歧度: {out['avg_divergence']}%  最新: {series[-1]['divergence']}% (同门平均 {series[-1]['peer_avg_div']}%)")
print(f"逆共识: 高分歧季度后6M超额 {hi_ex}% vs 低分歧 {lo_ex}% (n={len(valid)})")
print("最新公司共识重仓:", [(x['name'], x['w'], '他也持有' if x['he_holds'] else '他不碰') for x in series[-1]['house_top']])
