"""Portable active-fund workflow. Python 3.10+, no third-party dependencies."""
from __future__ import annotations
import argparse
import json
import math
import os
import re
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

if __package__:
    from .case_io import build_case_from_cache
    from .validate_agent_analysis import validate_payload, check_refs
    from .render_fund import render
else:
    from case_io import build_case_from_cache
    from validate_agent_analysis import validate_payload, check_refs
    from render_fund import render

def merge_agent_review(report: dict, agent: dict) -> dict:
    """Merge only validated Agent judgments; keep case-owned trade evidence intact."""
    report["meta"]["agent_reviewed"] = True
    report["meta"]["analysis_mode"] = agent["analysis_mode"]
    report["meta"]["single_agent_fallback"] = agent.get("single_agent_fallback", False)
    report["meta"]["canonical_skill"] = "skills/fund-manager-forensics/SKILL.md"
    report["agent_panel"] = {
        "reviewers": agent["reviewers"],
        "conflicts": agent["conflicts"],
        "module_reviews": agent["module_reviews"],
        "people_reviews": agent["people_reviews"],
    }
    report["manager_rarity"] = agent["manager_rarity"]
    report["independent_decision"] = agent["independent_decision"]
    verdict = agent["verdict"]
    report["verdict"].update(
        {
            "buy_now": verdict["buy_now"],
            "label": verdict["label"],
            "institutional_view": verdict["institutional_view"],
            "sentence": verdict["sentence"],
            "reasons": verdict["reasons"],
            "flip_conditions": verdict["flip_conditions"],
            "evidence_ref": "/".join(verdict["evidence_refs"]),
        }
    )
    return report



def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, content):
    """Never leave a partial report on a failed refresh."""
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as f:
        tmp = Path(f.name)
        try:
            f.write(content)
            f.flush()
            f.close()
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)


def dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def case_path(root, code, slug=None, create=False):
    if not re.fullmatch(r"[0-9]{6}", code):
        raise ValueError("请输入六位份额代码，保留开头的零。")
    if slug and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", slug):
        raise ValueError("案例目录名无效。")
    base = root.resolve()
    direct = base / (slug or code)
    if direct.is_symlink():
        raise ValueError("案例目录不能是符号链接。")
    if not slug:
        matches = [p.parent for p in sorted(base.glob("*/case.json"))
                   if not p.parent.is_symlink() and read(p).get("fund", {}).get("code") == code]
        if len(matches) > 1:
            raise ValueError("同份额有多个研究截面，请用 --case 选择。")
        if matches:
            direct = matches[0]
    if (direct / "case.json").exists() and read(direct / "case.json")["fund"]["code"] != code:
        raise ValueError("请求的份额与案例不一致。")
    if not create and not (direct / "case.json").is_file():
        raise ValueError(f"尚无该份额底稿；先运行 {code} --init --as-of YYYY-MM-DD。")
    return direct


def init(folder, code, as_of):
    date.fromisoformat(as_of)
    if folder.exists():
        raise ValueError("目录已存在，拒绝覆盖原有研究。")
    folder.mkdir(parents=True)
    (folder / "raw").mkdir()
    manifest = {"schema_version":1, "fund":{"code":code, "short_name":"", "share_class":""},
                "as_of":as_of, "report_date":None, "management":"unverified", "subject":"",
                "managers":[], "identity_refs":[], "snapshot":{}, "top_holdings":[]}
    save(folder / "case.json", dump(manifest))
    save(folder / "raw/evidence-ledger.json", dump({"meta":{"fund_code":code,"evidence_cutoff":None,
         "retrieved_at":date.today().isoformat()}, "sources":[], "modules":{}, "people":{}, "family_background":{}}))
    base = {"fund_code":code,"as_of":as_of,"agent_reviewed":False}
    verdict = {"buy_now":None,"label":"","sentence":"","institutional_view":"","reasons":[],
               "flip_conditions":[],"evidence_refs":[]}
    save(folder/"quick_review.draft.json",dump({**base,"analysis_mode":"quick","subject":"","verdict":verdict,"gaps":[]}))
    review = {"reviewer":"","status":"未证明","conclusion":"","evidence_refs":[]}
    save(folder/"agent_analysis.draft.json",dump({**base,"schema_version":"1.0.0","analysis_mode":"deep",
         "reviewers":{role:{"reviewed":False} for role in ("people_investigator","alpha_forensic",
           "portfolio_detective","institutional_skeptic","chief_underwriter")},
         "single_agent_fallback":False,"manager_tenure":{"cut_complete":False,"current_manager":"","periods":[],"evidence_refs":[]},
         "manager_rarity":{},"independent_decision":{},"module_reviews":{f"M{i:02}":review for i in range(1,46)},
         "people_reviews":{f"P{i:02}":review for i in range(1,25)},"trade_reviews":{k:[] for k in ("winners","losers","manager_approved")},
         "conflicts":[],"verdict":verdict}))


def collect_nav(folder, code):
    end = read(folder / "case.json")["as_of"]
    url = "https://fund.eastmoney.com/pingzhongdata/" + code + ".js"
    with urlopen(Request(url, headers={"User-Agent":"Mozilla/5.0"}), timeout=25) as resp:
        data = resp.read(16_000_001)
    if len(data) > 16_000_000:
        raise ValueError("净值响应超出上限。")
    body = data.decode("utf-8-sig")
    found = re.search(r'\bfS_code\s*=\s*"([0-9]{6})"', body)
    if not found or found[1] != code:
        raise ValueError("净值供应方没有确认请求的份额。")
    start = re.search(r'\bData_netWorthTrend\s*=\s*',body)
    if not start:
        raise ValueError("未取得单位净值。")
    data, _ = json.JSONDecoder().raw_decode(body[start.end():])
    records = {}
    for row in data:
        day = datetime.fromtimestamp(row["x"]/1000, timezone(timedelta(hours=8))).date().isoformat()
        if day <= end:
            nav = float(row["y"])
            if not math.isfinite(nav) or nav <= 0 or day in records:
                raise ValueError("净值重复或无效，保留原缓存。")
            records[day] = {"date":day,"nav":nav}
    if not records:
        raise ValueError("截至研究日没有净值；保留原缓存。")
    save(folder / "raw/nav-series.json", dump({"fund_code":code,"source":url,"cutoff":end,
        "fetched_at":date.today().isoformat(),"records":[records[d] for d in sorted(records)]}))
    return len(records)


def verify_identity(m, ledger):
    f = m["fund"]
    if m.get("management") != "active":
        raise ValueError("尚未证实主动管理，不能出经理报告。")
    if not f.get("short_name") or not f.get("share_class"):
        raise ValueError("缺少份额全称或类别。")
    if not isinstance(m.get("report_date"),str):
        raise ValueError("先在 case.json 核对最新法定报告期。")
    end, period = date.fromisoformat(m["as_of"]), date.fromisoformat(m["report_date"])
    if period > end or ledger["meta"].get("evidence_cutoff") != m["report_date"] or ledger["meta"].get("fund_code") != f["code"]:
        raise ValueError("案例、报告期与证据账本不一致。")
    managers = m.get("managers", [])
    active = [entry["name"] for entry in managers if date.fromisoformat(entry["start_date"]) <= end and
              (not entry.get("end_date") or date.fromisoformat(entry["end_date"]) >= end)]
    if not m.get("subject") or m["subject"] not in active:
        raise ValueError("研究对象未出现在截至研究日的在任经理名单。")
    sources = {s["id"]:s for s in ledger["sources"]}
    if len(sources) != len(ledger["sources"]):
        raise ValueError("来源编号重复。")
    for s in sources.values():
        if s.get("fund_code", f["code"]) != f["code"] or not (s.get("title") and (s.get("url_or_path") or s.get("url"))):
            raise ValueError("来源缺少可追溯地址、标题，或引用了其他份额。")
        if s.get("published_at") and date.fromisoformat(s["published_at"]) > end:
            raise ValueError("来源发布日晚于研究日：" + s["title"])
    refs = m.get("identity_refs", [])
    if not refs or any(k not in sources or sources[k]["grade"] != "A" for k in refs):
        raise ValueError("产品身份、任期和报告期需要本案的法定来源。")


def collect_prices(folder, code):
    if __package__:
        from . import fetch_stock_ohlc as quotes
    else:
        import fetch_stock_ohlc as quotes
    manifest = read(folder/"case.json")
    verify_identity(manifest,read(folder/"raw/evidence-ledger.json"))
    r = build_case_from_cache(folder)
    targets = {x["code"]:x["name"] for key in ("winners","losers","manager_approved","manager_approved_candidates")
               for x in r["trade_ledger"][key] if x.get("code")}
    if not targets:
        raise ValueError("先提炼至少两期持仓，或录入有依据的点名股票。")
    def fetch(stock):
        try:
            batch = quotes.build_output({"trade_ledger":{"winners":[{"code":stock,"name":targets[stock]}]}})
            series = batch["series"][stock]
            series["rows"] = [i for i in series["rows"] if i["date"] <= manifest["as_of"]]
            if not series["rows"]:
                raise ValueError("研究日前无行情")
            return stock, series, None
        except (ValueError, quotes.BatchFetchError) as exc:
            return stock, None, str(exc)
    target = folder/"raw/stock-ohlc.json"
    old = read(target) if target.exists() else {}
    if old.get("fund_code",code) != code:
        raise ValueError("已有行情缓存与份额不符")
    rows, failures = {}, {}
    with ThreadPoolExecutor(max_workers=3) as workers:
        for stock, series, error in workers.map(fetch,targets):
            if error:
                failures[stock] = error
            else:
                rows[stock] = series
    save(folder/"raw/price-gaps.json",dump(failures))
    if not rows:
        raise ValueError("本次未取得可用周K，保留原缓存。详见 raw/price-gaps.json")
    cached = {k:v for k,v in old.get("series",{}).items() if k in targets and k not in rows}
    save(target,dump({"fund_code":code,"period":"weekly","fetched_at":date.today().isoformat(),
                      "as_of":manifest["as_of"],"series":{**cached,**rows}}))
    return len(rows), len(failures)


def build(folder, code, mode):
    m = read(folder / "case.json")
    ledger = read(folder / "raw/evidence-ledger.json")
    verify_identity(m, ledger)
    a = read(folder / ("agent_analysis.json" if mode == "deep" else "quick_review.json"))
    if (m["fund"]["code"], a.get("fund_code"), a.get("as_of")) != (code, code, m["as_of"]):
        raise ValueError("评审与本案的份额或研究日不一致。")
    if a.get("analysis_mode") != mode or a.get("agent_reviewed") is not True:
        raise ValueError("评审模式或确认标志不正确。")
    errors = check_refs(a, ledger)
    v = a.get("verdict", {})
    if mode == "deep":
        errors += validate_payload(a)
        if a.get("single_agent_fallback") and a.get("manager_rarity",{}).get("confidence") == "高":
            errors.append("单 Agent 评审不能给高置信度")
        if m["subject"] not in str((a.get("manager_tenure") or {}).get("current_manager", "")):
            errors.append("评审任期未对应本案经理")
    else:
        if a.get("subject") != m["subject"] or not isinstance(a.get("gaps"),list) or not a["gaps"] or not all(isinstance(g,str) and g.strip() for g in a["gaps"]):
            errors.append("快报须填写本案经理与证据缺口")
    if type(v.get("buy_now")) is not bool or v.get("label") != ("可以买" if v.get("buy_now") else "不能买"):
        errors.append("购买判断与标签不一致")
    for key in ("sentence","institutional_view"):
        if not isinstance(v.get(key), str) or not v[key].strip():
            errors.append(f"verdict.{key} 缺失")
    for key in ("reasons","flip_conditions","evidence_refs"):
        if not isinstance(v.get(key), list) or not all(isinstance(i,str) and i.strip() for i in v[key]) or len(v[key]) < (3 if key=="reasons" else 1):
            errors.append(f"verdict.{key} 不完整")
    if errors:
        raise ValueError("；".join(errors))
    report = build_case_from_cache(folder)
    if mode == "deep":
        if not all(report["trade_ledger"][k] for k in ("winners","losers")):
            raise ValueError("深度报告缺少现任期内可复核的盈利或亏损持仓。")
        merge_agent_review(report, a)
        report["manager_tenure"] = a["manager_tenure"]
    else:
        report["verdict"].update(v)
    report["meta"].update(as_of=m["as_of"],analysis_mode=mode,agent_reviewed=True)
    report["gaps"] = a.get("gaps", [])
    report["fund"]["management"] = m["management"]
    return report


def main(argv=None, default_root=None):
    parser = argparse.ArgumentParser(description="主动基金经理研究工作台")
    parser.add_argument("fund_code")
    parser.add_argument("--workspace", type=Path, default=default_root or Path.cwd() / "cases")
    parser.add_argument("--case")
    parser.add_argument("--as-of", help="新建案例的研究截止日")
    parser.add_argument("--init", action="store_true")
    parser.add_argument("--collect-nav", action="store_true")
    parser.add_argument("--collect-prices", action="store_true")
    parser.add_argument("--collect-holdings", action="store_true", help="获取待核验的历史前十大候选")
    parser.add_argument("--from-year", type=int, help="持仓起始年，默认取研究日前两个自然年")
    parser.add_argument("--mode", choices=["deep","quick"], default="deep")
    parser.add_argument("--output", type=Path, help="报告 JSON，HTML 同目录同名")
    parser.add_argument("--no-browser", action="store_true", help="兼容选项；便携入口默认不弹窗")
    args = parser.parse_args(argv)
    try:
        folder = case_path(args.workspace, args.fund_code, args.case, args.init)
        if args.init:
            init(folder,args.fund_code,args.as_of or date.today().isoformat())
            print(f"已建立独立研究目录：{folder}")
        if args.as_of and args.as_of != read(folder / "case.json")["as_of"]:
            raise ValueError("研究日期不一致；请新建另一截面。")
        if args.collect_nav:
            print(f"已按份额取得 {collect_nav(folder,args.fund_code)} 条单位净值")
        if args.collect_holdings:
            if __package__:
                from .holdings_provider import fetch_holdings_history
            else:
                from holdings_provider import fetch_holdings_history
            end = read(folder/"case.json")["as_of"]
            year = int(end[:4])
            first = args.from_year if args.from_year is not None else year-1
            if not 1990 <= first <= year or year-first > 30:
                raise ValueError("持仓年份范围无效。")
            candidate = fetch_holdings_history(args.fund_code,first,year)
            candidate["periods"] = [p for p in candidate["periods"] if p["report_date"] <= end]
            if not candidate["periods"]:
                raise ValueError("未取得持仓候选；请核对法定报告。")
            save(folder/"raw/holdings-provider.draft.json",dump(candidate))
            print(f"取得 {len(candidate['periods'])} 期持仓候选，尚未进入盈亏计算。")
        if args.collect_prices:
            ok, missing = collect_prices(folder,args.fund_code)
            print(f"已取得 {ok} 只股票的周K，{missing} 只待补。")
        if args.init or args.collect_nav or args.collect_prices or args.collect_holdings:
            return 0
        out = args.output or folder / ("report.json" if args.mode=="deep" else "quick.json")
        if (out.suffix.lower() != ".json" or out.name in {"case.json","agent_analysis.json","quick_review.json","quick_review.draft.json","agent_analysis.draft.json"}
            or out.resolve().is_relative_to((folder / "raw").resolve())
            or (out.resolve().is_relative_to(args.workspace.resolve()) and out.parent.resolve() != folder.resolve())
            or (args.mode == "quick" and out.name == "report.json")):
            raise ValueError("输出须为独立的报告 JSON 文件。")
        report = build(folder,args.fund_code,args.mode)
        ohlc = folder / "raw/stock-ohlc.json"
        prices = read(ohlc) if ohlc.exists() else {}
        for series in prices.get("series", {}).values():
            series["rows"] = [r for r in series["rows"] if r["date"] <= report["meta"]["as_of"]]
        html = render(report, prices)
        out.parent.mkdir(parents=True,exist_ok=True)
        save(out,dump(report)); save(out.with_suffix(".html"),html)
        print(f"{report['fund']['short_name']} | {report['verdict']['label']} | {out.with_suffix('.html')}")
        return 0
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RuntimeError) as exc:
        print(f"未生成报告：{exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
