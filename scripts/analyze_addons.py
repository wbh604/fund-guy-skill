#!/usr/bin/env python3
"""附加对照卡:年底冲排名 / 一车多牌 / 开门批次命运 / 持有人换手。
另:按本品生成 K 线 fund 事件,造神九项用公告/任期/持仓筛(三级证据制)。

全部不计入行为总分。假信号先剔除,拿不到的数字写未获取。
用法: .venv/bin/python scripts/analyze_addons.py 163417
"""
import json, os, re, sys
from collections import defaultdict
from datetime import date as D, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fund_meta import require_code, style_bench
CODE = require_code()
DIR = os.path.join(ROOT, ".cache", f"fund_{CODE}")
HDIR = os.path.join(DIR, "house")
load = lambda n: json.load(open(os.path.join(DIR, n + ".json")))


def date_plus(d, days):
    y, mo, dd = map(int, d.split("-"))
    return str(D(y, mo, dd) + timedelta(days=days))


def at(series, d):
    prev = None
    for dd, v in series:
        if dd > d:
            break
        prev = v
    return prev


def at_or_next(series, d):
    v = at(series, d)
    if v is not None:
        return v
    for dd, x in series:
        if dd >= d:
            return x
    return None


def pctile(series, d, years=3):
    v = at(series, d)
    if v is None:
        return None
    start = date_plus(d, -365 * years)
    window = [x for dd, x in series if start <= dd <= d]
    if len(window) < 60:
        return None
    return round(sum(1 for x in window if x <= v) / len(window) * 100)


def fwd_ret(series, d, days=365):
    a = at_or_next(series, d)
    b = at(series, date_plus(d, days))
    last = series[-1][0] if series else ""
    pending = date_plus(d, days) > last
    if not a or not b:
        return None, True
    return round((b / a - 1) * 100, 1), pending


def zone_of(csi_pct, g_pct):
    vals = [p for p in (csi_pct, g_pct) if p is not None]
    if not vals:
        return "unknown"
    hi = any(p >= 80 for p in vals)
    lo = any(p <= 20 for p in vals)
    if hi and lo:
        return "mixed"
    if hi:
        return "high"
    if all(p <= 20 for p in vals) or (lo and not hi):
        return "low"
    return "mid"


def qkey(s):
    m = re.match(r"(\d{4})年(\d)季度", s)
    return f"{m.group(1)}Q{m.group(2)}" if m else None


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def load_nav():
    nav = load("nav")
    kd = [k for k in nav[0] if "日期" in k][0]
    kv = [k for k in nav[0] if "净值" in k and "日期" not in k][0]
    return [(r[kd][:10], r[kv]) for r in nav if r.get(kv)]


def load_idx(name):
    return [(r["date"][:10], r["close"]) for r in load(name)]


def load_holdings():
    hold = []
    for f in sorted(os.listdir(DIR)):
        if f.startswith("hold_2") and f.endswith(".json"):
            hold += json.load(open(os.path.join(DIR, f)))
    by_q = defaultdict(list)
    for r in hold:
        q = qkey(r["季度"])
        if not q:
            continue
        by_q[q].append({
            "code": r["股票代码"], "name": r["股票名称"],
            "w": r["占净值比例"] or 0,
        })
    return by_q


# ---------- 1. 年底冲排名 ----------
def yearend_chase(by_q, nav):
    """Q4 vs 非Q4:前十大集中度 / 单票上限 / 换血率 / 仓位(仅全持仓期) / 当季收益。
    假信号:Q1/Q3 只有前十大,禁止拿持股只数比;成立首年当建仓年剔除。
    """
    qs = sorted(by_q)
    if len(qs) < 8:
        return {"flagged": False, "reason": "季度不足,未鉴定", "metrics": None}

    first_year = qs[0][:4]
    t10_q4, t10_o, mx_q4, mx_o, ch_q4, ch_o, eq_q4, eq_q2 = [], [], [], [], [], [], [], []
    q_rows = []
    for q in qs:
        rows = sorted(by_q[q], key=lambda x: -x["w"])
        n = int(q[-1])
        # 中报/年报尚未出全的季度不进样本
        if n in (2, 4) and len(rows) < 40:
            continue
        y = q[:4]
        if y == first_year:
            continue  # 建仓年
        top = rows[:10]
        t10 = round(sum(x["w"] for x in top), 1)
        mx = round(top[0]["w"], 1) if top else None
        topset = {x["code"] for x in top}
        prev = f"{y}Q{n-1}" if n > 1 else f"{int(y)-1}Q4"
        prev_top = {x["code"] for x in sorted(by_q.get(prev, []), key=lambda x: -x["w"])[:10]}
        churn = round(1 - len(topset & prev_top) / 10, 2) if prev_top and len(prev_top) >= 8 else None
        full = n in (2, 4) and len(rows) >= 40
        eq = round(sum(x["w"] for x in rows), 1) if full else None
        is_q4 = n == 4
        q_rows.append({"q": q, "top10": t10, "max_w": mx, "churn": churn, "equity": eq, "n": len(rows)})
        (t10_q4 if is_q4 else t10_o).append(t10)
        if mx is not None:
            (mx_q4 if is_q4 else mx_o).append(mx)
        if churn is not None:
            (ch_q4 if is_q4 else ch_o).append(churn)
        if eq is not None:
            (eq_q4 if is_q4 else eq_q2).append(eq)

    ends = {"1": "03-31", "2": "06-30", "3": "09-30", "4": "12-31"}
    q4_ret, o_ret = [], []
    for q in qs:
        y, n = q[:4], int(q[-1])
        if y == first_year:
            continue
        d0 = f"{y}-{ends[str(n)]}"
        d_s = f"{int(y)-1}-12-31" if n == 1 else f"{y}-{ends[str(n-1)]}"
        a, b = at(nav, d_s), at(nav, d0)
        if a and b:
            r = round((b / a - 1) * 100, 1)
            (q4_ret if n == 4 else o_ret).append(r)
            for row in q_rows:
                if row["q"] == q:
                    row["ret"] = r

    m = {
        "top10_q4": round(mean(t10_q4), 1) if t10_q4 else None,
        "top10_other": round(mean(t10_o), 1) if t10_o else None,
        "max_q4": round(mean(mx_q4), 1) if mx_q4 else None,
        "max_other": round(mean(mx_o), 1) if mx_o else None,
        "churn_q4": round(mean(ch_q4), 2) if ch_q4 else None,
        "churn_other": round(mean(ch_o), 2) if ch_o else None,
        "equity_q4": round(mean(eq_q4), 1) if eq_q4 else None,
        "equity_q2": round(mean(eq_q2), 1) if eq_q2 else None,
        "ret_q4": round(mean(q4_ret), 1) if q4_ret else None,
        "ret_other": round(mean(o_ret), 1) if o_ret else None,
        "n_q4": len(t10_q4), "n_other": len(t10_o),
        "skip_year": first_year,
    }

    flags = []
    if m["top10_q4"] is not None and m["top10_other"] is not None and m["top10_q4"] - m["top10_other"] >= 4:
        flags.append("前十大集中度Q4更高")
    if m["max_q4"] is not None and m["max_other"] is not None and m["max_q4"] - m["max_other"] >= 1.5:
        flags.append("单票上限Q4更高")
    if m["churn_q4"] is not None and m["churn_other"] is not None and m["churn_q4"] - m["churn_other"] >= 0.12:
        flags.append("前十大换血率Q4更高")
    if m["equity_q4"] is not None and m["equity_q2"] is not None and m["equity_q4"] - m["equity_q2"] >= 5:
        flags.append("股票仓位Q4高于中报")
    if m["ret_q4"] is not None and m["ret_other"] is not None and m["ret_q4"] - m["ret_other"] >= 6:
        flags.append("Q4收益显著高于其他季")

    flagged = len(flags) >= 2
    if flagged:
        verdict = f"Q4 有 {len(flags)} 项异常({('、'.join(flags))}),存在年底冲排名嫌疑"
        evidence = "inference"
        tone = "warn"
    elif flags:
        verdict = f"只有 1 项偏高({flags[0]}),构不成模式,不记红旗"
        evidence = "clue"
        tone = "ok"
    else:
        verdict = (f"成立首年 {first_year} 已剔除。Q4 前十大 {m['top10_q4']}% vs 其他季 {m['top10_other']}%,"
                   f"换血率 {m['churn_q4']} vs {m['churn_other']},"
                   f"当季收益 {m['ret_q4']}% vs {m['ret_other']}%。没有年底加码赌名次的模式")
        evidence = "fact"
        tone = "ok"

    return {
        "flagged": flagged, "flags": flags, "metrics": m, "quarters": q_rows,
        "verdict": verdict, "evidence": evidence, "tone": tone,
        "scoring": "对照卡,不计入行为总分",
    }


# ---------- 2. 一车多牌 ----------
def load_fund_hold(code):
    by_q = defaultdict(list)
    if not os.path.isdir(HDIR):
        return by_q
    for f in os.listdir(HDIR):
        m = re.match(rf"hold_{re.escape(code)}_(\d{{4}})\.json", f)
        if not m:
            continue
        for r in json.load(open(os.path.join(HDIR, f))):
            q = qkey(r["季度"])
            if q:
                by_q[q].append({
                    "code": r["股票代码"], "name": r["股票名称"],
                    "w": r["占净值比例"] or 0,
                })
    return by_q


def latest_full(by_q):
    for q in sorted(by_q, reverse=True):
        if len(by_q[q]) >= 40:
            return q
    for q in sorted(by_q, reverse=True):
        if len(by_q[q]) >= 8:
            return q
    return None


def overlap_pair(a_rows, b_rows):
    a = {x["code"]: x for x in sorted(a_rows, key=lambda x: -x["w"])[:10]}
    b = {x["code"]: x for x in sorted(b_rows, key=lambda x: -x["w"])[:10]}
    shared = set(a) & set(b)
    names = [a[c]["name"] for c in sorted(shared, key=lambda c: -min(a[c]["w"], b[c]["w"]))]
    overlap_w = round(sum(min(a[c]["w"], b[c]["w"]) for c in shared), 1)
    his_on_shared = round(sum(a[c]["w"] for c in shared), 1)
    return {
        "n_shared": len(shared),
        "overlap_w": overlap_w,
        "his_w_shared": his_on_shared,
        "shared_names": names[:6],
    }


def clones(by_q):
    path = os.path.join(HDIR, "funds.json")
    if not os.path.exists(path):
        return {"available": False, "reason": "名下产品清单未获取"}
    funds = json.load(open(path))
    others = [f for f in funds if f.get("self") and f["code"] != CODE]
    if not others:
        return {"available": False, "reason": "公开资料未找到他名下其他主动权益产品"}

    q0 = latest_full(by_q)
    pairs = []
    missing = []
    for f in others:
        ob = load_fund_hold(f["code"])
        q = q0 if q0 in ob else latest_full(ob)
        if not q or q not in by_q:
            missing.append({"code": f["code"], "name": f.get("name"), "reason": "持仓未获取"})
            continue
        ov = overlap_pair(by_q[q], ob[q])
        ov.update({"code": f["code"], "name": f.get("name"), "q": q,
                   "managers": f.get("managers")})
        pairs.append(ov)

    if not pairs:
        return {"available": False, "reason": "名下其他产品持仓未获取", "missing": missing,
                "n_products": 1 + len(others)}

    hi = max(pairs, key=lambda x: (x["n_shared"], x["overlap_w"]))
    cloneish = [p for p in pairs if p["n_shared"] >= 6 or p["his_w_shared"] >= 35]
    if cloneish:
        verdict = (f"名下 {1+len(others)} 只产品里,与「{hi['name']}」最新 {hi['q']} 前十大撞 {hi['n_shared']}/10,"
                   f"重合权重 {hi['overlap_w']}%(他在这些票上 {hi['his_w_shared']}%)。"
                   f"{'本质上是一辆车换了车牌' if hi['n_shared']>=7 else '高度同构,不完全是两套打法'}")
        tone = "warn"
        evidence = "fact"
    else:
        verdict = (f"名下另有 {len(others)} 只。跟最像的「{hi['name']}」只撞 {hi['n_shared']}/10,"
                   f"重合权重 {hi['overlap_w']}%。还没到一车多牌")
        tone = "ok"
        evidence = "fact"
    return {
        "available": True, "n_products": 1 + len(others), "pairs": pairs,
        "missing": missing, "cloneish": len(cloneish),
        "verdict": verdict, "tone": tone, "evidence": evidence,
        "scoring": "对照卡,不计入行为总分",
    }


# ---------- 3. 开门批次 + 持有人换手 ----------
def parse_pct(s):
    try:
        return float(str(s).replace("%", ""))
    except (TypeError, ValueError):
        return None


def holder_flow(nav, csi, growth):
    try:
        raw = load("holders2")
    except Exception:
        return {"available": False, "reason": "持有人结构未获取"}
    rows = []
    prev = None
    lockup_share = None
    # 份额几乎不变的最长前缀 = 锁定期
    shares = []
    for h in sorted(raw, key=lambda x: x["date"]):
        try:
            shares.append((h["date"][:10], float(h["total_share_yi"])))
        except (TypeError, ValueError):
            continue
    if shares:
        lockup_share = shares[0][1]
        lockup_until = shares[0][0]
        for d, s in shares:
            if abs(s - lockup_share) / lockup_share < 0.02:
                lockup_until = d
            else:
                break
    else:
        lockup_until = None

    for h in sorted(raw, key=lambda x: x["date"]):
        d = h["date"][:10]
        inst, retail = parse_pct(h.get("inst")), parse_pct(h.get("retail"))
        try:
            share = float(h["total_share_yi"])
        except (TypeError, ValueError):
            continue
        csi_p, g_p = pctile(csi, d), pctile(growth, d)
        zone = zone_of(csi_p, g_p)
        f_fwd, pend = fwd_ret(nav, d)
        rec = {
            "date": d, "inst": inst, "retail": retail, "share_yi": share,
            "csi_pct": csi_p, "growth_pct": g_p, "zone": zone,
            "fwd_fund": f_fwd, "fwd_pending": pend,
            "d_inst": round(inst - prev["inst"], 2) if prev and inst is not None and prev.get("inst") is not None else None,
            "d_share": round(share - prev["share_yi"], 2) if prev else None,
            "lockup": bool(lockup_until and d <= lockup_until),
        }
        tags = []
        if rec["lockup"]:
            tags.append("锁定期·份额不动,机构占比变化是场内换手")
        elif rec["d_share"] is not None and lockup_share and rec["d_share"] < -lockup_share * 0.3:
            tags.append("解锁后份额急缩,散户到期赎回,不是山顶新进")
        elif zone == "high" and rec.get("d_share") and rec["d_share"] > 5:
            if rec.get("d_inst") is not None and rec["d_inst"] < 0:
                tags.append("高位净申购且机构占比下降 → 散户山顶进(较强推断)")
            else:
                tags.append("高位净申购(较强推断)")
        elif zone == "high" and rec.get("d_inst") is not None and rec["d_inst"] < -2:
            tags.append("高位机构占比下降 → 机构在走(较强推断)")
        elif zone == "low" and rec.get("d_share") and rec["d_share"] < 0:
            tags.append("低位份额还在缩 → 有人在底部赎回")
        rec["tags"] = tags
        rows.append(rec)
        prev = rec

    # 一句话:机构是不是高位走、散户是不是山顶进
    high_inst_out = sum(1 for r in rows if r["zone"] == "high" and (r.get("d_inst") or 0) < -2 and not r.get("lockup"))
    high_in = sum(1 for r in rows if any("高位净申购" in t for t in r["tags"]))
    if high_in:
        verdict = f"有 {high_in} 期在市场高位出现净申购 —— 散户山顶进的时间线对得上(较强推断)"
        tone = "warn"
    elif high_inst_out:
        verdict = f"有 {high_inst_out} 期在高位机构占比下滑。份额变化拆不开申购赎回,记较强推断,不写成机构抛售"
        tone = "warn"
    else:
        verdict = "没有稳定的「机构高位走、散户山顶进」模式。锁定期的机构占比上升是场内换手,不能当成申购进来的机构"
        tone = "ok"
    return {
        "available": True, "lockup_until": lockup_until, "rows": rows,
        "verdict": verdict, "tone": tone, "evidence": "inference" if (high_in or high_inst_out) else "fact",
        "scoring": "对照卡,不计入行为总分",
    }


def cohorts(nav, holder):
    """开门之后 1~2 期份额变了多少。净缩 ≠ 没人申购,只是拆不开,不能写成开门收钱。"""
    A = load("analysis")
    events = ((A.get("ability") or {}).get("gates") or {}).get("events") or []
    opens = [e for e in events if e["kind"] in ("open", "open_unlock")]
    hrows = (holder or {}).get("rows") or []
    out = []
    for e in opens:
        d = e["date"]
        before = [h for h in hrows if h["date"] <= d]
        after = [h for h in hrows if h["date"] > d]
        b, a1 = (before[-1] if before else None), (after[0] if after else None)
        a2 = after[1] if len(after) > 1 else None
        rec = {
            "date": d, "kind": e["kind"], "zone": e.get("zone"),
            "title": e.get("title"), "fwd_fund": e.get("fwd_fund"),
            "fwd_csi": e.get("fwd_csi"), "in_sample": e.get("in_sample"),
        }
        if b and a1:
            chg = round(a1["share_yi"] / b["share_yi"] - 1, 3) if b["share_yi"] else None
            rec["share_before"] = b["share_yi"]
            rec["share_after"] = a1["share_yi"]
            rec["share_after_date"] = a1["date"]
            rec["net_chg"] = chg
            rec["share_after2"] = a2["share_yi"] if a2 else None
            rec["share_after2_date"] = a2["date"] if a2 else None
            if e["kind"] == "open_unlock" and chg is not None and chg < -0.2:
                rec["label"] = "unlock_redeem"
                rec["note"] = (f"封闭期满后份额 {b['share_yi']:.0f}→{a1['share_yi']:.0f} 亿份(净 {chg:.0%})。"
                               f"这是到期赎回,不是开门接进来的钱。当天买进的人 12 个月本基金 {e.get('fwd_fund')}% ,"
                               f"但走掉的人没拿到这截")
            elif chg is not None and chg > 0.05:
                rec["label"] = "inflow"
                rec["note"] = (f"打开后到 {a1['date'][:7]} 净份额 +{chg:.0%}。"
                               f"这批净申购之后 12 个月本基金 {e.get('fwd_fund')}%")
            elif chg is not None and chg < -0.05:
                rec["label"] = "net_out"
                rec["note"] = (f"打开后到 {a1['date'][:7]} 净份额 {chg:.0%}。"
                               f"申购赎回拆不开,不能写成开门收钱;当天买进的人 12 个月本基金 {e.get('fwd_fund')}%")
            else:
                rec["label"] = "flat"
                rec["note"] = "打开后净份额几乎没动,没有「一批新钱」可验"
        else:
            rec["label"] = "missing"
            rec["note"] = "开门前后份额未获取"
        out.append(rec)

    # 解锁后规模翻倍的滞后批次(2020H2-2021H1 这类)
    if hrows:
        unlocked = [h for h in hrows if not h.get("lockup")]
        if len(unlocked) >= 3:
            trough = unlocked[0]
            later = [h for h in unlocked if h["date"] > trough["date"]][:4]
            if later:
                peak = max(later, key=lambda x: x["share_yi"])
                if peak["share_yi"] > trough["share_yi"] * 1.15:
                    f_fwd, pend = fwd_ret(nav, peak["date"])
                    out.append({
                        "date": trough["date"], "kind": "rebuild",
                        "label": "rebuild",
                        "share_before": trough["share_yi"],
                        "share_after": peak["share_yi"],
                        "share_after_date": peak["date"],
                        "net_chg": round(peak["share_yi"] / trough["share_yi"] - 1, 3),
                        "fwd_fund": f_fwd, "fwd_pending": pend,
                        "note": (f"解锁低点 {trough['date'][:7]} {trough['share_yi']:.0f} 亿份 "
                                 f"→ {peak['date'][:7]} {peak['share_yi']:.0f} 亿份。"
                                 f"这截后进的钱,从 {peak['date'][:7]} 起算 12 个月本基金 "
                                 f"{'未到期' if pend else (str(f_fwd)+'%')}。"
                                 f"跟闸门当天那一笔不是同一批人"),
                    })

    n_in = sum(1 for x in out if x.get("label") == "inflow")
    n_out = sum(1 for x in out if x.get("label") in ("net_out", "unlock_redeem"))
    hurt_rebuild = [x for x in out if x.get("label") == "rebuild"
                    and x.get("fwd_fund") is not None and x["fwd_fund"] < -10]
    if hurt_rebuild:
        verdict = ("打开闸门当时净份额在缩,不是当场收钱;"
                   "解锁之后规模从低点爬回去的那批钱,12 个月本基金为负")
        tone = "warn"
    elif n_in and any(x.get("fwd_fund") is not None and x["fwd_fund"] < -15 and x.get("label") == "inflow" for x in out):
        verdict = "有净申购批次,随后 12 个月基金大跌 —— 这批新钱挨了打"
        tone = "warn"
    elif n_out and not n_in:
        verdict = "打开闸门之后净份额在缩,没有「开门收钱」的份额证据。闸门当天买入的 12 个月仍按买卖点口径验"
        tone = "ok"
    else:
        verdict = "开门批次能对上份额变化的不多;能对上的已按 12 个月验尸,拆不开申购赎回的不编"
        tone = "ok"
    return {
        "events": out, "verdict": verdict, "tone": tone,
        "scoring": "对照卡,不计入行为总分",
    }


def main():
    apath = os.path.join(DIR, "analysis.json")
    if not os.path.exists(apath):
        print("analysis.json 不存在,先跑 analyze_fund.py")
        sys.exit(1)
    by_q = load_holdings()
    nav = load_nav()
    csi = load_idx("csi300")
    style_file, style_name = style_bench(DIR)
    try:
        growth = load_idx(style_file)
    except Exception:
        try:
            growth = load_idx("idx_growth")
        except Exception:
            growth = []
        style_name = "成长"

    ye = yearend_chase(by_q, nav)
    cl = clones(by_q)
    hf = holder_flow(nav, csi, growth)
    if isinstance(hf, dict):
        hf["style_name"] = style_name
    co = cohorts(nav, hf)

    A = load("analysis")
    ab = A.setdefault("ability", {})
    ab["yearend"] = ye
    ab["clones"] = cl
    ab["holder_flow"] = hf
    ab["cohorts"] = co
    json.dump(A, open(apath, "w"), ensure_ascii=False)

    print("年底冲排名:", "红旗" if ye.get("flagged") else ye.get("tone"), ye.get("verdict", "")[:80])
    print("一车多牌:", cl.get("verdict", cl.get("reason", ""))[:80])
    print("持有人换手:", hf.get("verdict", hf.get("reason", ""))[:80])
    print("开门批次:", co.get("verdict", "")[:80])
    for e in co.get("events") or []:
        print(f"  {e.get('date')} {e.get('label')} {e.get('note','')[:70]}")

    write_events(A)
    god = god_checks(A)
    ab["god"] = god
    json.dump(A, open(apath, "w"), ensure_ascii=False)
    print("造神:", f"{god.get('n_pass')}通过 / {god.get('n_flag')}留意 / {god.get('n_miss')}未查证")
    for it in god.get("items") or []:
        print(f"  {it['status']:4} {it['name']} —— {it['text'][:72]}")


# ---------- 4. K 线情景:本品 fund 事件(不编行业/宏观新闻) ----------
GATE_TITLE = {
    "close_launch": "提前结束募集",
    "close_limit": "限额/暂停大额申购",
    "open": "恢复/打开申购",
    "open_unlock": "封闭期满开放日常申购",
}


def _q_date(q):
    m = re.match(r"(?:20)?(\d{2})Q(\d)", str(q or ""))
    if not m:
        return None
    y, n = 2000 + int(m.group(1)), int(m.group(2))
    if n < 1 or n > 4:
        return None
    return f"{y}-{['03-31', '06-30', '09-30', '12-31'][n - 1]}"


def _ev(date, title, hint):
    return {"date": date, "title": title, "kind": "fund", "source_hint": hint, "auto": True}


def build_fund_events(A):
    evs, seen = [], set()

    def add(date, title, hint):
        if not date or date in ("至今", "—") or len(str(date)) < 10:
            return
        key = (date[:10], title)
        if key in seen:
            return
        seen.add(key)
        evs.append(_ev(date[:10], title, hint))

    meta = A.get("meta") or {}
    nm = A.get("nav_metrics") or {}
    fname = meta.get("基金名称") or meta.get("基金全称") or CODE
    found = (meta.get("成立时间") or "")[:10]
    if found:
        add(found, f"{fname}成立", "basic.json 成立时间")
    scale = A.get("scale") or []
    if scale:
        first, peak = scale[0], max(scale, key=lambda x: x.get("yi") or 0)
        fd = _q_date(first.get("q"))
        if fd and first.get("yi") is not None:
            add(fd, f"首个披露季规模约 {first['yi']} 亿", "持仓市值/权重反推,非募集公告")
        pd = _q_date(peak.get("q"))
        if pd and peak is not first and (peak.get("yi") or 0) > (first.get("yi") or 0):
            add(pd, f"估算规模见顶约 {peak['yi']} 亿", "持仓市值/权重反推")
    if nm.get("dd_from") and nm.get("max_dd") is not None:
        add(nm["dd_from"], f"净值最大回撤起于峰值({nm['max_dd']}%)", "cumnav 回撤")
    if nm.get("dd_to") and nm.get("dd_to") != nm.get("dd_from"):
        add(nm["dd_to"], f"净值最大回撤探底 {nm.get('max_dd')}%", "cumnav 回撤")
    if nm.get("uw_to") and nm["uw_to"] not in ("至今", "", None) and nm.get("underwater_days"):
        add(nm["uw_to"], f"最长水下结束(共 {nm['underwater_days']} 天)", "cumnav 水下")
    regimes = A.get("managers") or []
    for i, r in enumerate(regimes):
        st = (r.get("start") or "")[:10]
        if not st:
            continue
        if i == len(regimes) - 1 and found:
            try:
                if abs((D(*map(int, st.split("-"))) - D(*map(int, found.split("-")))).days) <= 14:
                    continue
            except Exception:
                pass
        mgrs = r.get("managers") or ""
        add(st, f"经理变更: {mgrs}", "managers.json")
    try:
        raw = load("gates")
    except Exception:
        raw = {}
    for e in raw.get("events") or []:
        kind = e.get("kind")
        if kind not in GATE_TITLE:
            continue
        t = GATE_TITLE[kind]
        if kind == "close_limit" and e.get("limit_yuan"):
            t = f"暂停接受 {int(e['limit_yuan']) // 10000} 万元以上申购"
        elif kind == "open" and e.get("limit_yuan"):
            t = f"恢复接受 {int(e['limit_yuan']) // 10000} 万元以上申购"
        add(e.get("date"), t, "gates.json JJGG")
    evs.sort(key=lambda x: x["date"])
    return evs


def merge_events(auto, old, A):
    hold_codes = {str(s.get("code") or "") for s in (A.get("replay") or {}).get("stocks") or []}
    hold_codes.discard("")
    fo = ((A.get("meta") or {}).get("成立时间") or "")[:10] or "1900-01-01"
    extras = []
    for e in old or []:
        if e.get("kind") == "fund" or e.get("auto"):
            continue
        d = (e.get("date") or "")[:10]
        if d and d < fo:
            continue
        codes = [str(c) for c in (e.get("codes") or [])]
        if e.get("kind") in ("industry", "company") and codes and hold_codes:
            if not (set(codes) & hold_codes):
                continue
        extras.append(e)
    seen = {(x.get("date"), x.get("title")) for x in auto}
    out = list(auto)
    for e in extras:
        key = (e.get("date"), e.get("title"))
        if key in seen:
            continue
        out.append(e)
        seen.add(key)
    out.sort(key=lambda x: x.get("date") or "")
    return out


def write_events(A):
    path = os.path.join(DIR, "events.json")
    old = []
    if os.path.exists(path):
        try:
            old = json.load(open(path))
        except Exception:
            old = []
    auto = build_fund_events(A)
    merged = merge_events(auto, old, A)
    json.dump(merged, open(path, "w"), ensure_ascii=False, indent=2)
    n_fund = sum(1 for e in merged if e.get("kind") == "fund")
    print(f"情景事件: 本品 {n_fund} 条 + 保留行业/宏观 {len(merged) - n_fund} 条 → {path}")


# ---------- 5. 造神九项(本品数据筛,动机最多较强推断) ----------
GROWTH_IND = ("半导体", "电子", "通信", "通讯", "计算机", "光伏", "电池", "光学", "软件")
VALUE_IND = ("银行", "保险", "非银", "煤炭", "钢铁", "石油", "公用事业")
CONSUME_IND = ("食品", "饮料", "白酒", "家电", "零售", "免税", "美容", "纺织")
MED_IND = ("医药", "医疗", "生物", "创新药")


def _item(key, name, status, text, level=None):
    return {"key": key, "name": name, "status": status, "level": level, "text": text}


def _parse_day(s):
    if not s or s in ("至今", "—"):
        return D.today()
    y, mo, d = map(int, s[:10].split("-"))
    return D(y, mo, d)


def _lead_tenure(A):
    from collections import Counter
    regimes = A.get("managers") or []
    meta = A.get("meta") or {}
    c = Counter()
    for r in regimes:
        for n in str(r.get("managers") or "").split():
            c[n] += 1
    current = str((regimes[0].get("managers") if regimes else "") or "").split()
    if current:
        lead = max(current, key=lambda n: (c[n], -current.index(n)))
    elif c:
        lead = c.most_common(1)[0][0]
    else:
        lead = (meta.get("基金经理") or "未获取").split()[0]
    first, n_with = None, 0
    for r in regimes:
        if lead not in str(r.get("managers") or "").split():
            continue
        n_with += 1
        st = r.get("start") or ""
        if first is None or st < first:
            first = st
    found = (meta.get("成立时间") or "")[:10]
    lead_always = bool(regimes) and n_with == len(regimes)
    from_inc = bool(first and found and abs((_parse_day(first) - _parse_day(found)).days) <= 14)
    return lead, regimes, lead_always, from_inc, first, n_with


def _ann_flags():
    try:
        from fetch_gates import ensure_ann_flags
        return ensure_ann_flags() or {}
    except Exception as e:
        print("ann_flags skip:", e)
        gpath = os.path.join(DIR, "gates.json")
        if os.path.exists(gpath):
            return (json.load(open(gpath)).get("ann_flags")) or {}
        return {}


def _top_industries(A):
    w = defaultdict(float)
    for s in (A.get("replay") or {}).get("stocks") or []:
        if not s.get("cur_w"):
            continue
        t = (s.get("industry") or s.get("board") or "").strip() or "未分类"
        w[t] += float(s["cur_w"])
    return sorted(w.items(), key=lambda kv: -kv[1])


def _ind_hit(name, keys):
    return any(k in (name or "") for k in keys)


def _pp(v):
    if v is None:
        return "—"
    return f"{v:+.1f}%" if isinstance(v, (int, float)) else str(v)


def god_checks(A):
    ab = A.get("ability") or {}
    meta = A.get("meta") or {}
    nm = A.get("nav_metrics") or {}
    lead, regimes, lead_always, from_inc, first, n_with = _lead_tenure(A)
    flags = _ann_flags()
    items = []

    n_reg = len(regimes)
    extra_hire = []
    lo = nm.get("uw_from") or nm.get("dd_from") or ""
    hi = nm.get("uw_to") or nm.get("dd_to") or ""
    if hi == "至今":
        hi = "9999-12-31"
    prev_names = set()
    for r in sorted(regimes, key=lambda x: x.get("start") or ""):
        names = [n for n in str(r.get("managers") or "").split() if n]
        st = (r.get("start") or "")[:10]
        if lo and hi and st and lo <= st <= hi:
            for n in names:
                if n != lead and n not in prev_names:
                    extra_hire.append((st, n))
        prev_names |= set(names)
    if lead_always:
        txt = f"{n_reg} 次变更他都在任,从未离任"
        if extra_hire:
            st, n = extra_hire[0]
            txt += (f"。线索:{st[:7]} 水下/回撤期出现 {n}"
                    "(公告时间线=已确认事实,甩锅动机未确认;接任者从业年限未获取)")
        items.append(_item("dump", "甩锅跑路", "pass", txt,
                           "已确认事实" if not extra_hire else "线索"))
    else:
        items.append(_item(
            "dump", "甩锅跑路", "flag",
            f"他不是全程在任(最早 {(first or '未获取')[:7]}),现任任期不能包装前任",
            "已确认事实"))

    if from_inc:
        items.append(_item("peach", "摘桃子", "pass",
                           "基金自成立即由他管,无接盘他人业绩", "已确认事实"))
    elif first:
        items.append(_item("peach", "摘桃子", "flag",
                           f"他 {first[:10]} 才上台,成立以来业绩不能全记在他头上",
                           "已确认事实"))
    else:
        items.append(_item("peach", "摘桃子", "miss", "任期起点未获取"))

    self_funds, tiny = [], []
    fp = os.path.join(HDIR, "funds.json")
    if os.path.exists(fp):
        for f in json.load(open(fp)):
            if f.get("self"):
                self_funds.append(f)
                if f.get("aum") is not None and float(f.get("aum") or 0) < 0.5 \
                        and f.get("code") != CODE:
                    tiny.append(f)
    term = flags.get("terminate") or []
    if term:
        t0 = term[0]
        items.append(_item(
            "body", "藏尸体", "flag",
            f"JJGG 标题命中清盘/终止 {len(term)} 条,如 {t0.get('date','')[:10]} "
            f"{(t0.get('title') or '')[:36]}(标题=已确认事实,是否从履历抹掉未交叉备案)",
            "线索"))
    elif not self_funds:
        items.append(_item("body", "藏尸体", "miss",
                           "名下产品清单未获取,清盘未交叉中基协备案"))
    else:
        extra = f";名下另有迷你产品 {len(tiny)} 只(规模<0.5亿,只作线索)" if tiny else ""
        items.append(_item(
            "body", "藏尸体", "pass",
            f"公开名下 {len(self_funds)} 只,JJGG 未检出清盘/终止{extra}"
            "。未交叉中基协备案,不能写成不存在", "线索"))

    strat = str(meta.get("投资策略") or "") + str(meta.get("投资目标") or "") \
        + str(meta.get("基金类型") or "")
    tops = [t for t, _ in _top_industries(A) if t != "未分类"]
    top1 = tops[0] if tops else ""
    narrow, face = None, False
    if re.search(r"医药|医疗|健康产业", strat) and top1 and not _ind_hit(top1, MED_IND):
        narrow, face = "医药", True
    elif re.search(r"消费", strat) and not re.search(r"灵活配置", strat) \
            and top1 and not _ind_hit(top1, CONSUME_IND):
        narrow, face = "消费", True
    elif re.search(r"价值|蓝筹|高股息|红利", strat) and not re.search(r"灵活配置|成长", strat) \
            and top1 and _ind_hit(top1, GROWTH_IND):
        narrow, face = "价值", True
    elif re.search(r"成长|科技创新|新兴产业", strat) and not re.search(r"灵活配置", strat) \
            and top1 and _ind_hit(top1, VALUE_IND):
        narrow, face = "成长", True
    if face:
        items.append(_item(
            "persona", "人设造假", "flag",
            f"资料写偏{narrow},最新牌面最大行业是 {top1}。季报原文未读,记线索不是动机",
            "线索"))
    elif not strat.strip():
        items.append(_item("persona", "人设造假", "miss", "投资策略未获取,季报原文未读"))
    else:
        items.append(_item(
            "persona", "人设造假", "pass",
            "策略表述宽或未与牌面直接打脸;季报原文/路演未逐段核对,不从别的基金抄",
            "线索"))

    bm = flags.get("benchmark") or []
    if bm:
        t0 = bm[0]
        items.append(_item(
            "ruler", "偷换尺子", "flag",
            f"公开公告标题命中基准相关 {len(bm)} 条,如 {t0.get('date','')[:10]} "
            f"{(t0.get('title') or '')[:36]}。是否悄悄改要对照招募书全文", "线索"))
    elif flags:
        items.append(_item(
            "ruler", "偷换尺子", "pass",
            "公开公告标题未检出业绩比较基准变更(未逐页对照招募书全文,不写成不存在)",
            "线索"))
    else:
        items.append(_item("ruler", "偷换尺子", "miss",
                           "公告标题未扫描,基准是否中途改过未查"))

    gates = ab.get("gates") or {}
    gev = gates.get("events") or []
    launch = gates.get("launch_close") or next(
        (e for e in gev if e.get("kind") == "close_launch"), None)
    open_hi = next((e for e in gev if e.get("in_sample") and e.get("quadrant") == "high_open"), None)
    style_nm = gates.get("style_name") or "风格"
    if not gates:
        items.append(_item("hype", "高位圈钱", "miss", "闸门时间轴未跑,未鉴定"))
    elif launch or open_hi:
        bits = []
        if launch:
            bits.append(
                f"{launch['date'][:7]} 提前结束募集,随后 12 个月沪深300 "
                f"{_pp(launch.get('fwd_csi'))}、本基金 {_pp(launch.get('fwd_fund'))}")
        if open_hi:
            bits.append(
                f"{open_hi['date'][:7]} {style_nm}指数 {open_hi.get('growth_pct')}% 分位打开申购,"
                f"随后 12 个月本基金 {_pp(open_hi.get('fwd_fund'))}")
        items.append(_item(
            "hype", "高位圈钱", "flag",
            "。".join(bits) + "。公告时间线=已确认事实,圈钱动机=较强推断;公司发行他是代言人",
            "较强推断"))
    else:
        items.append(_item(
            "hype", "高位圈钱", "pass",
            "公开闸门未检出高位提前结束募集,也没有进样本的高位开门", "线索"))

    ye = ab.get("yearend") or {}
    ym = ye.get("metrics") or {}
    if not ym:
        items.append(_item("yearend", "年底冲排名", "miss", "未检测"))
    elif ye.get("flagged"):
        items.append(_item("yearend", "年底冲排名", "flag",
                           ye.get("verdict") or "Q4 显著高于其他季", "线索"))
    else:
        items.append(_item(
            "yearend", "年底冲排名", "pass",
            f"Q4 前十大 {ym.get('top10_q4')}% 不高于其他季 {ym.get('top10_other')}%,"
            f"换血率 {ym.get('churn_q4')} vs {ym.get('churn_other')}", "已确认事实"))

    co_ps = []
    for r in regimes:
        ns = [n for n in str(r.get("managers") or "").split() if n]
        if len(ns) >= 2:
            co_ps.append(((r.get("start") or "")[:10], " ".join(ns)))
    if not regimes:
        items.append(_item("hitch", "蹭业绩", "miss", "任期记录未获取"))
    elif co_ps:
        st, who = min(co_ps, key=lambda x: x[0] or "9999")
        items.append(_item(
            "hitch", "蹭业绩", "flag",
            f"多段共管(如 {st[:7]} {who}),共管期收益不能当个人战绩。"
            "是否被宣传成个人未查传播材料,记较强推断", "较强推断"))
    elif lead_always:
        items.append(_item("hitch", "蹭业绩", "pass",
                           "公开任期均为独管,未检出挂名共管", "已确认事实"))
    else:
        items.append(_item("hitch", "蹭业绩", "flag",
                           "他不是全程独管,成立以来业绩不能全记在他头上", "已确认事实"))

    internal = (gates.get("internal_holders") or [])
    int_txt = "员工持有比例未获取"
    if internal:
        a, b = internal[0], internal[-1]
        if a is not b:
            int_txt = (f"员工持有 {a.get('internal')}({(a.get('date') or '')[:7]}) → "
                       f"{b.get('internal')}({(b.get('date') or '')[:7]})")
        else:
            int_txt = f"员工持有 {a.get('internal')}"
    items.append(_item(
        "conflict", "利益冲突", "miss",
        f"定期报告关联交易/亲属任职未获取;{int_txt}(员工≠经理自购)。记未发现,不写成不存在"))

    n_pass = sum(1 for x in items if x["status"] == "pass")
    n_flag = sum(1 for x in items if x["status"] == "flag")
    n_miss = sum(1 for x in items if x["status"] == "miss")
    return {
        "items": items,
        "n_pass": n_pass, "n_flag": n_flag, "n_miss": n_miss,
        "note": "娱乐标题可以狠,证据正文必须克制。未交叉的数据源不能写成不存在。",
    }


if __name__ == "__main__":
    main()
