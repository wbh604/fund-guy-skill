#!/usr/bin/env python3
"""闸门事件 × 市场分位 × 12 个月验尸,写入 analysis.json['ability']['gates']。

分位:近 3 年,≥80% 高位,<20% 低位。对照沪深300 + 他的风格指数(成长β选成长,否则选价值)。
假信号剔除:全公司同日限购 / 触 10% 双十线 / 熊市+份额急缩保命。
「良心」不进行为总分,本模块是对照卡。

用法: .venv/bin/python scripts/analyze_gates.py 163417
"""
import json, os, re, sys
from datetime import date as D, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fund_meta import require_code, style_bench
CODE = require_code()
DIR = os.path.join(ROOT, ".cache", f"fund_{CODE}")
load = lambda n: json.load(open(os.path.join(DIR, n + ".json")))


def date_plus(d, days):
    y, mo, dd = map(int, d.split("-"))
    return str(D(y, mo, dd) + timedelta(days=days))


def series_map(rows):
    return {r["date"][:10]: r["close"] for r in rows}


def at(series, d):
    """d 当日或之前最近收盘。series: [(date, value), ...] 已按日期升序。"""
    prev = None
    for dd, v in series:
        if dd > d:
            break
        prev = v
    return prev


def at_or_next(series, d):
    """闸门日可能早于基金净值首日(成立前结束募集),用之后第一个点。"""
    v = at(series, d)
    if v is not None:
        return v
    for dd, x in series:
        if dd >= d:
            return x
    return None


def pctile(series, d, years=3):
    """d 当日点位在过去 years 年里的分位 0-100。不足 60 个交易日返回 None。"""
    v = at(series, d)
    if v is None:
        return None
    start = date_plus(d, -365 * years)
    window = [x for dd, x in series if start <= dd <= d]
    if len(window) < 60:
        return None
    n = sum(1 for x in window if x <= v)
    return round(n / len(window) * 100)


def fwd_ret(series, d, days=365, start="at"):
    a = at_or_next(series, d) if start == "next" else at(series, d)
    b = at(series, date_plus(d, days))
    last = series[-1][0] if series else ""
    pending = date_plus(d, days) > last
    if not a or not b:
        return None, True
    return round((b / a - 1) * 100, 1), pending


def zone_of(csi_pct, g_pct):
    """双指数分位 → high/low/mid/mixed。成长基金以风格为主,沪深300 作第二把尺子。"""
    vals = [p for p in (csi_pct, g_pct) if p is not None]
    if not vals:
        return "unknown"
    hi = any(p >= 80 for p in vals)
    lo = any(p <= 20 for p in vals)
    if hi and lo:
        return "mixed"
    if hi:
        return "high"
    if all(p <= 20 for p in vals):
        return "low"
    if lo and not hi:
        return "low"
    return "mid"


def q_of(d):
    y, m = int(d[:4]), int(d[5:7])
    return f"{y}Q{(m - 1) // 3 + 1}"


def max_weight_near(d, weights_by_q):
    q = q_of(d)
    y, n = q.split("Q")
    n = int(n)
    cands = [q]
    if n > 1:
        cands.append(f"{y}Q{n - 1}")
    else:
        cands.append(f"{int(y) - 1}Q4")
    best = None
    for cq in cands:
        w = weights_by_q.get(cq)
        if w is not None:
            best = w if best is None else max(best, w)
    return best


def share_shrink(d, holders):
    """闸门日前最近两期份额是否急缩(>12%)。"""
    prior = [h for h in holders if h["date"][:10] <= d]
    if len(prior) < 2:
        return None
    a, b = prior[-2], prior[-1]
    try:
        sa, sb = float(a["total_share_yi"]), float(b["total_share_yi"])
    except (TypeError, ValueError):
        return None
    if sa <= 0:
        return None
    return round(1 - sb / sa, 3)


def load_nav_series():
    nav = load("nav")
    kd = [k for k in nav[0] if "日期" in k][0]
    kv = [k for k in nav[0] if "净值" in k and "日期" not in k][0]
    return [(r[kd][:10], r[kv]) for r in nav if r.get(kv)]


def load_weights():
    """每季最大个股权重,用来抓触 10% 双十线被迫限购。"""
    hold = []
    for f in sorted(os.listdir(DIR)):
        if f.startswith("hold_") and f.endswith(".json"):
            hold += json.load(open(os.path.join(DIR, f)))
    by_q = {}
    for r in hold:
        m = re.match(r"(\d{4})年(\d)季度", r.get("季度") or "")
        if not m:
            continue
        q = f"{m.group(1)}Q{m.group(2)}"
        w = r.get("占净值比例") or 0
        by_q[q] = max(by_q.get(q, 0), w)
    return by_q


def quadrant(kind, zone):
    closing = kind in ("close_limit", "close_launch")
    opening = kind in ("open", "open_unlock")
    if zone == "high" and closing:
        return "high_close"
    if zone == "high" and opening:
        return "high_open"
    if zone == "low" and closing:
        return "low_close"
    if zone == "low" and opening:
        return "low_open"
    return "mid"


def fake_reason(e, zone, max_w, shrink):
    if e.get("house_wide"):
        return "house_wide"
    if max_w is not None and max_w >= 9.3 and e["kind"] in ("close_limit", "close_launch"):
        return "cap_10"
    if zone == "low" and shrink is not None and shrink > 0.12 and e["kind"] == "close_limit":
        return "bear_protect"
    return None


def in_sample(e, fake, kind):
    if fake:
        return False
    if kind == "open_unlock":
        return False  # 封闭期满按合同开放,不是裁量开门
    return kind in ("close_limit", "close_launch", "open")


def note_of(e, fake, zone, qdr):
    kind = e["kind"]
    if kind == "open_unlock":
        return "封闭期满按合同开放日常申购,不是经理裁量开门"
    if kind == "close_launch" and zone == "high":
        return "高位募满即关:闸关上了,但钱已经收完,不是拦人未进"
    if fake == "house_wide":
        return "同门同日也限购,更像公司风控,不是他个人的良心"
    if fake == "cap_10":
        return "当时重仓已逼近 10% 双十线,限购可能是被迫的,不是决策"
    if fake == "bear_protect":
        return "熊市且份额在急缩,限购更像保命/清盘线,不一定是良心"
    if qdr == "high_close":
        return "高位关门:时间线重合是事实,「拦人接盘」是较强推断"
    if qdr == "high_open":
        return "高位开门:时间线重合是事实,「开门收钱」是较强推断"
    if qdr == "low_open":
        return "低位开门:便宜时接钱,对持有人友好(较强推断)"
    if qdr == "low_close":
        return "低位关门:可能流动性/合规,不一定坏"
    return "中位动作,不进良心四象限"


def analyze():
    gpath = os.path.join(DIR, "gates.json")
    apath = os.path.join(DIR, "analysis.json")
    if not os.path.exists(gpath):
        print("gates.json 未获取,跳过")
        if os.path.exists(apath):
            A = load("analysis")
            A.setdefault("ability", {})["gates"] = None
            json.dump(A, open(apath, "w"), ensure_ascii=False)
        return

    raw = load("gates")
    csi = [(r["date"][:10], r["close"]) for r in load("csi300")]
    style_file, style_name = style_bench(DIR)
    try:
        style = [(r["date"][:10], r["close"]) for r in load(style_file)]
    except Exception:
        style = [(r["date"][:10], r["close"]) for r in load("idx_growth")]
        style_name = "成长"
    nav = load_nav_series()
    weights_by_q = load_weights()
    try:
        holders = load("holders2")
        holders = sorted(holders, key=lambda h: h["date"])
    except Exception:
        holders = []

    events = []
    for e in raw.get("events") or []:
        d = e["date"]
        csi_pct = pctile(csi, d)
        g_pct = pctile(style, d)
        zone = zone_of(csi_pct, g_pct)
        csi_fwd, csi_pend = fwd_ret(csi, d)
        g_fwd, g_pend = fwd_ret(style, d)
        f_fwd, f_pend = fwd_ret(nav, d, start="next") if nav else (None, True)
        max_w = max_weight_near(d, weights_by_q)
        shrink = share_shrink(d, holders)
        qdr = quadrant(e["kind"], zone)
        fake = fake_reason(e, zone, max_w, shrink)
        sample = in_sample(e, fake, e["kind"])
        events.append({
            "date": d,
            "kind": e["kind"],
            "title": e["title"],
            "id": e.get("id"),
            "limit_yuan": e.get("limit_yuan"),
            "house_wide": bool(e.get("house_wide")),
            "peer_n": len(e.get("peer_same_kind") or []),
            "csi_pct": csi_pct,
            "growth_pct": g_pct,
            "zone": zone,
            "quadrant": qdr,
            "fwd_csi": csi_fwd,
            "fwd_growth": g_fwd,
            "fwd_fund": f_fwd,
            "fwd_pending": bool(csi_pend or g_pend or f_pend),
            "max_weight": round(max_w, 2) if max_w is not None else None,
            "share_shrink": shrink,
            "fake": fake,
            "in_sample": sample,
            "evidence": "fact",  # 公告+时间线是事实;动机另说
            "note": note_of(e, fake, zone, qdr),
        })

    sample = [x for x in events if x["in_sample"]]

    def cluster(xs, days=21):
        """同方向 21 天内连发(2万→1万)算一回,避免高关次数虚高。"""
        out = []
        for x in xs:
            if out and x["kind"] == out[-1]["kind"] and x["quadrant"] == out[-1]["quadrant"]:
                d0 = D(*map(int, out[-1]["date"].split("-")))
                d1 = D(*map(int, x["date"].split("-")))
                if (d1 - d0).days <= days:
                    continue
            out.append(x)
        return out

    episodes = cluster(sample)
    counts = {
        "high_close": sum(1 for x in episodes if x["quadrant"] == "high_close"),
        "high_open": sum(1 for x in episodes if x["quadrant"] == "high_open"),
        "low_close": sum(1 for x in episodes if x["quadrant"] == "low_close"),
        "low_open": sum(1 for x in episodes if x["quadrant"] == "low_open"),
        "n_sample": len(sample),
        "n_episodes": len(episodes),
        "n_events": len(events),
        "n_operational": len(raw.get("operational") or []),
        "n_fake": sum(1 for x in events if x["fake"]),
    }

    # 自购:经理个人未获取;公司固有资金有公告就叠上去(不假装是他本人)
    self_buy = []
    for s in raw.get("self_buy") or []:
        d = s["date"]
        self_buy.append({
            "date": d,
            "title": s["title"],
            "who": s.get("extra") or "unknown",
            "csi_pct": pctile(csi, d),
            "growth_pct": pctile(style, d),
            "zone": zone_of(pctile(csi, d), pctile(style, d)),
            "fwd_csi": fwd_ret(csi, d)[0],
            "evidence": "clue",  # 旗下权益类未必含本基金
            "note": "公司固有资金自购旗下权益类,公告未确认是否含本基金",
        })

    internal = []
    for h in holders:
        try:
            internal.append({
                "date": h["date"][:10],
                "internal": h.get("internal"),
                "share_yi": float(h["total_share_yi"]),
            })
        except (TypeError, ValueError):
            pass

    launch = next((x for x in events if x["kind"] == "close_launch"), None)

    out = {
        "source": raw.get("source"),
        "fetched_at": raw.get("fetched_at"),
        "counts": counts,
        "events": events,
        "self_buy_company": self_buy,
        "self_buy_manager": "未获取",
        "internal_holders": internal[:1] + internal[-1:] if len(internal) > 1 else internal,
        "peers_checked": raw.get("peers_checked") or [],
        "style_name": style_name,
        "style_file": style_file,
        "scoring": "对照卡,不计入行为总分。时间线是已确认事实,良心/圈钱动机最多较强推断。",
        "launch_close": launch,
    }

    A = load("analysis")
    A.setdefault("ability", {})["gates"] = out
    json.dump(A, open(apath, "w"), ensure_ascii=False)
    print(f"闸门 {counts['n_events']} 条候选 / 进样本 {counts['n_sample']} / "
          f"假信号 {counts['n_fake']} / 假期剔除 {counts['n_operational']}")
    print(f"四象限 高关{counts['high_close']} 高开{counts['high_open']} "
          f"低关{counts['low_close']} 低开{counts['low_open']}")
    for x in events:
        flag = "样本" if x["in_sample"] else (x["fake"] or "排除")
        print(f"  {x['date']}  {x['kind']:<12} {x['zone']:<6} "
              f"沪深{x['csi_pct']}% {style_name}{x['growth_pct']}%  "
              f"12m沪深{x['fwd_csi']}% 基金{x['fwd_fund']}%  [{flag}]")


if __name__ == "__main__":
    analyze()
