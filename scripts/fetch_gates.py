#!/usr/bin/env python3
"""抓取申购闸门公告:暂停/恢复申购、限额、提前结束募集、公司自购。

东财 JJGG type=0 全量公告。标题分类只做候选,假闸门(假期双边暂停等)在本脚本剔除,
同门是否同一天限购在本脚本对照;市场分位和 12 个月验尸交给 analyze_gates.py。

用法: .venv/bin/python scripts/fetch_gates.py 163417
"""
import json, os, re, sys, time
from datetime import datetime, timedelta

import requests

CODE = sys.argv[1] if len(sys.argv) > 1 else "163417"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, ".cache", f"fund_{CODE}")
os.makedirs(DIR, exist_ok=True)
UA = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://fundf10.eastmoney.com/",
}
SRC = "https://api.fund.eastmoney.com/f10/JJGG"

# 同门对照:挑成立较早的主动权益,排除目标经理自己的产品
PEER_N = 6


def get_jjgg(code, page, size=50, typ=0):
    url = f"{SRC}?fundcode={code}&pageIndex={page}&pageSize={size}&type={typ}"
    r = requests.get(url, headers=UA, timeout=20)
    r.raise_for_status()
    return r.json()


def fetch_all_announcements(code):
    rows, page = [], 1
    while page <= 40:
        js = get_jjgg(code, page)
        data = js.get("Data") or []
        if not data:
            break
        rows.extend(data)
        total = js.get("TotalCount") or 0
        print(f"  JJGG {code} p{page}: +{len(data)} / {total}")
        if len(rows) >= total:
            break
        page += 1
        time.sleep(0.35)
    return rows


def parse_limit_yuan(title):
    """从标题抽出限额(元)。只认「X万元以上」这种关门口径。"""
    m = re.search(r"([一二两三四五六七八九十百\d]+)万元以上", title)
    if not m:
        return None
    raw = m.group(1)
    cn = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
          "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    if raw.isdigit():
        n = int(raw)
    elif raw in cn:
        n = cn[raw]
    else:
        return None
    return n * 10000


def classify(title):
    """标题分类。返回 (kind, extra) 或 ('skip', reason)。

    kind:
      close_launch  提前结束募集
      close_limit   限额/暂停大额/暂停接受 X 元以上
      open          恢复申购/取消限购
      open_unlock   封闭期满开放日常申购(合同动作,非裁量)
      self_buy      固有资金/自购
      operational   假期/港股通/双边暂停(假闸门)
      skip          无关
    """
    t = title or ""

    if any(k in t for k in ("费率优惠", "估值方法", "招募说明书", "基金合同",
                            "托管协议", "季度报告", "年度报告", "半年度",
                            "上市交易", "销售机构", "网上交易系统暂停",
                            "客服热线", "掌柜钱包", "现金宝", "投顾",
                            "非公开发行", "高级管理人员", "基金经理",
                            "增聘", "离任", "分红", "拆分",
                            "渠道暂停", "网银", "直连渠道", "暂停服务")):
        return "skip", "noise"

    if "自购" in t or "固有资金" in t:
        who = "company" if ("旗下" in t or "固有资金" in t) else "unknown"
        return "self_buy", who

    if "提前结束募集" in t:
        return "close_launch", None

    if "单笔最低" in t:
        return "skip", "min_amount"

    # 恢复/取消限购 = 开门
    if any(k in t for k in ("恢复接受", "恢复申购", "取消限制", "取消限购",
                            "取消大额", "打开申购")):
        return "open", parse_limit_yuan(t)

    if "开放日常申购" in t:
        return "open_unlock", None

    # 真限购:暂停接受 X 元以上 / 暂停大额 / 限制申购金额
    if re.search(r"暂停接受.{0,12}以上申购", t) or "暂停大额" in t \
            or "限制大额申购" in t or "限制申购金额" in t:
        return "close_limit", parse_limit_yuan(t)

    # 假闸门:非港股通交易日、或申购+赎回一起停(节假日/结算)
    if "非港股通" in t:
        return "operational", "hk_connect"
    if ("暂停申购" in t and "赎回" in t) or ("暂停申购" in t and "转换" in t and "赎回" in t):
        return "operational", "holiday_both"
    if "暂停申购" in t and "赎回" not in t:
        return "close_limit", parse_limit_yuan(t)

    return "skip", "other"


def rec_of(row, kind, extra):
    title = row.get("TITLE") or ""
    return {
        "date": (row.get("PUBLISHDATE") or "")[:10],
        "title": title,
        "id": row.get("ID"),
        "kind": kind,
        "extra": extra,
        "limit_yuan": extra if isinstance(extra, int) else parse_limit_yuan(title),
        "house_hint": bool(re.search(r"旗下部分|旗下权益|旗下公募|旗下基金", title)),
    }


def pick_peers():
    path = os.path.join(DIR, "house", "funds.json")
    if not os.path.exists(path):
        return []
    funds = json.load(open(path))
    out = []
    for f in funds:
        if f.get("self"):
            continue
        t = f.get("type") or ""
        if any(k in t for k in ("债券", "指数", "联接", "偏债")):
            continue
        if not any(k in t for k in ("偏股", "灵活", "股票")):
            continue
        # 老代码更可能覆盖 2018-2021 闸门窗口
        if not (str(f["code"]).startswith("163") or str(f["code"]).startswith("340")):
            continue
        out.append({"code": f["code"], "name": f["name"], "managers": f.get("managers")})
    return out[:PEER_N]


def peer_hits(peers, event_dates):
    """同门在闸门日 ±2 天是否也出现限购标题。全公司同一天限购 = 假信号。"""
    if not peers or not event_dates:
        return {}
    want = set()
    for d in event_dates:
        dt = datetime.strptime(d, "%Y-%m-%d")
        for k in range(-2, 3):
            want.add((dt + timedelta(days=k)).strftime("%Y-%m-%d"))

    result = {}
    for p in peers:
        cache = os.path.join(DIR, "house", f"gates_peer_{p['code']}.json")
        if os.path.exists(cache):
            rows = json.load(open(cache))
        else:
            try:
                rows = fetch_all_announcements(p["code"])
            except Exception as e:
                print(f"  peer {p['code']} fail: {e}")
                rows = []
            json.dump(rows, open(cache, "w"), ensure_ascii=False)
            time.sleep(0.4)
        hits = []
        for row in rows:
            d = (row.get("PUBLISHDATE") or "")[:10]
            if d not in want:
                continue
            kind, extra = classify(row.get("TITLE") or "")
            if kind in ("close_limit", "close_launch", "open"):
                hits.append(rec_of(row, kind, extra))
        result[p["code"]] = {"name": p["name"], "managers": p.get("managers"), "hits": hits}
        print(f"  peer {p['code']} {p['name']}: {len(hits)} 闸门命中")
    return result


def main():
    out_path = os.path.join(DIR, "gates.json")
    if os.path.exists(out_path):
        print(f"[skip] gates.json 已存在")
        return

    print(f"[1] 全量公告 {CODE}")
    rows = fetch_all_announcements(CODE)

    operational, events, self_buy, skipped = [], [], [], 0
    for row in rows:
        kind, extra = classify(row.get("TITLE") or "")
        if kind == "skip":
            skipped += 1
            continue
        rec = rec_of(row, kind, extra)
        if kind == "operational":
            operational.append(rec)
        elif kind == "self_buy":
            self_buy.append(rec)
        else:
            events.append(rec)

    events.sort(key=lambda x: x["date"])
    self_buy.sort(key=lambda x: x["date"])

    print(f"[2] 分类: 闸门候选 {len(events)} · 假闸门(假期等) {len(operational)} · "
          f"自购 {len(self_buy)} · 跳过 {skipped} / 公告 {len(rows)}")

    peers = pick_peers()
    print(f"[3] 同门对照 {len(peers)} 只")
    gate_dates = [e["date"] for e in events if e["kind"] in ("close_limit", "close_launch", "open")]
    peer_map = peer_hits(peers, gate_dates)

    # 标每条事件:同门是否同日也限购
    for e in events:
        same = []
        dt = datetime.strptime(e["date"], "%Y-%m-%d")
        window = {(dt + timedelta(days=k)).strftime("%Y-%m-%d") for k in range(-2, 3)}
        for code, info in peer_map.items():
            for h in info["hits"]:
                if h["date"] in window and h["kind"] == e["kind"]:
                    same.append({"code": code, "name": info["name"], "date": h["date"],
                                 "title": h["title"]})
        e["peer_same_kind"] = same
        e["house_wide"] = bool(e["house_hint"] or same)

    out = {
        "code": CODE,
        "source": SRC + "?type=0",
        "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "n_all": len(rows),
        "n_skipped": skipped,
        "events": events,
        "operational": [{"date": x["date"], "title": x["title"], "extra": x["extra"]}
                        for x in operational],
        "self_buy": self_buy,
        "peers_checked": [{"code": p["code"], "name": p["name"]} for p in peers],
        "note": "经理个人自购无独立公告接口;公司固有资金自购有公告。"
                "员工持有比例见 holders2.json,不等于经理自购。",
    }
    json.dump(out, open(out_path, "w"), ensure_ascii=False, indent=2)
    print(f"→ {out_path}")
    for e in events:
        print(f"  {e['date']}  {e['kind']:<14}  house={e['house_wide']}  {e['title'][:42]}")


if __name__ == "__main__":
    main()
