#!/usr/bin/env python3
"""从 kline-interactive.html 提取全部股票数据,降采样为周K,估算盈亏,输出 .cache/replay.json。"""
import json, re, os
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FUND_AUM = 12.5  # 亿,模拟基金规模

src = open(os.path.join(ROOT, "assets", "kline-interactive.html")).read()
m = re.search(r"const DATA\s*=\s*(\{.*?\});\n", src, re.S)
data = json.loads(m.group(1))


def to_weekly(kline):
    """日K → 周K(ISO周),o=首日开 h=max l=min c=末日收"""
    weeks = {}
    order = []
    for k in kline:
        y, mo, dd = map(int, k["t"].split("-"))
        iso = date(y, mo, dd).isocalendar()
        key = (iso[0], iso[1])
        if key not in weeks:
            weeks[key] = {"t": k["t"], "o": k["o"], "h": k["h"], "l": k["l"], "c": k["c"]}
            order.append(key)
        else:
            w = weeks[key]
            w["h"] = max(w["h"], k["h"])
            w["l"] = min(w["l"], k["l"])
            w["c"] = k["c"]
            w["t"] = k["t"]  # 周内最后一个交易日
    return [weeks[k] for k in order]


def close_on(kline, d):
    """d 当日或之前最近收盘价"""
    prev = None
    for k in kline:
        if k["t"] > d:
            break
        prev = k
    return (prev or kline[0])["c"], (prev or kline[0])["t"]


def quarter(d):
    y, mo = d.split("-")[:2]
    return f"{y[2:]}Q{(int(mo) - 1) // 3 + 1}"


FULL_EXIT = ("全清", "卖出", "割肉", "止损", "清仓")


def synth_holds(anchors, kline):
    """锚点之间按季度末合成「持」披露点;未清仓则延续到K线末尾(每半年一个)。"""
    from datetime import date as D
    first = anchors[0]["date"]
    last = anchors[-1]["date"]
    fully_exited = anchors[-1]["act"] == "sell" and any(w in anchors[-1]["label"] for w in FULL_EXIT)
    end = last if fully_exited else kline[-1]["t"]

    qends = []
    y0, y1 = int(first[:4]), int(end[:4])
    for y in range(y0, y1 + 1):
        for md in ("03-31", "06-30", "09-30", "12-31"):
            d = f"{y}-{md}"
            if first < d < end:
                qends.append(d)

    # 锚点之后仍持有的时段降频为半年(中报/年报),避免标记过密
    holds = []
    for d in qends:
        if d > last and int(d[5:7]) not in (6, 12):
            continue
        near_anchor = any(abs((D(*map(int, d.split("-"))) - D(*map(int, a["date"].split("-")))).days) < 45
                          for a in anchors)
        if near_anchor:
            continue
        snap_c, snap_d = close_on(kline, d)
        holds.append({"date": snap_d, "act": "hold", "label": "持", "q": quarter(snap_d)})
    return holds


stocks = []
for s in data["stocks"]:
    kline = s["kline"]
    weekly = to_weekly(kline)
    last_c = kline[-1]["c"]

    # 简易持仓模拟:buy +1 手,sell 按标签清一半或全部,期末按最后收盘 mark
    units, cost, realized = 0.0, 0.0, 0.0
    sellfly = 0.0  # 卖飞幅度:卖出价到期末最大涨幅
    pts = []
    for p in s["points"]:
        c, snap = close_on(kline, p["date"])
        pts.append({"date": snap, "act": p["act"], "label": p["label"], "q": quarter(snap)})
        if p["act"] == "buy":
            units += 1
            cost += c
        elif p["act"] == "sell" and units > 0:
            frac = 0.5 if ("一半" in p["label"] or "50" in p["label"] or "减" in p["label"]) else 1.0
            sold = units * frac
            avg = cost / units
            realized += sold * (c - avg)
            cost -= sold * avg
            units -= sold
            # 卖飞 = 卖出后 12 个月内最高收盘 vs 卖价
            y, mo, dd = map(int, snap.split("-"))
            end = f"{y + 1:04d}-{mo:02d}-{dd:02d}"
            future = [k["c"] for k in kline if snap < k["t"] <= end]
            if future:
                sellfly = max(sellfly, (max(future) - c) / c)
    unreal = units * (last_c - (cost / units if units else 0)) if units else 0
    invested = sum(close_on(kline, p["date"])[0] for p in s["points"] if p["act"] == "buy")
    ret = (realized + unreal) / invested if invested else 0
    amount = round(s["weight"] / 100 * FUND_AUM * ret, 2)

    # 合成季度「持」披露点,按时间与锚点合并
    pts = sorted(pts + synth_holds(pts, kline), key=lambda p: p["date"])

    stocks.append({
        "name": s["name"], "code": s["code"], "industry": s["industry"],
        "weight": s["weight"], "skill": s["skill"], "skill_key": s["skill_key"],
        "verdict": s["verdict"], "rating": s["rating"],
        "amount": amount, "ret_pct": round(ret * 100, 1),
        "sellfly_pct": round(sellfly * 100, 1),
        "n_disclose": len(pts),
        "points": pts,
        "kline": [[w["t"], round(w["o"], 2), round(w["h"], 2), round(w["l"], 2), round(w["c"], 2)] for w in weekly],
    })

out = {"aum": FUND_AUM, "stocks": stocks}
os.makedirs(os.path.join(ROOT, ".cache"), exist_ok=True)
path = os.path.join(ROOT, ".cache", "replay.json")
json.dump(out, open(path, "w"), ensure_ascii=False, separators=(",", ":"))
size = os.path.getsize(path) // 1024
print(f"replay.json: {size}KB, {len(stocks)} stocks")
for s in sorted(stocks, key=lambda x: -x["amount"]):
    print(f"  {s['name']:<8} {s['amount']:+7.2f}亿  ret {s['ret_pct']:+6.1f}%  卖飞 {s['sellfly_pct']:5.1f}%  {len(s['kline'])}周K")
