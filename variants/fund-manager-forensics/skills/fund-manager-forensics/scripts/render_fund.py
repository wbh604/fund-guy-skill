"""Offline reader: all identities, metrics, judgments and citations come from the case."""
import json
import re
from html import escape
from pathlib import Path
from urllib.parse import urlsplit

SKILL = Path(__file__).resolve().parents[1]


def e(value):
    return escape(str(value if value is not None else "—"), quote=True)


def lis(values):
    return "<ul>" + "".join(f"<li>{e(x)}</li>" for x in values) + "</ul>"


def money(n):
    if not isinstance(n, (int, float)):
        return "未估算"
    return f"{n/1e8:+.2f} 亿" if abs(n) >= 1e8 else f"{n/1e4:+,.1f} 万"


def render(r, stock_ohlc=None):
    f, m, v, ledger = r["fund"], r["meta"], r["verdict"], r["trade_ledger"]
    deep = m["analysis_mode"] == "deep"
    def section(title, body):
        return f"<section><h2>{e(title)}</h2>{body}</section>"
    def bars(items):
        result = []
        for stock in items:
            weight = stock.get("weight_pct")
            if not isinstance(weight, (int, float)) or not 0 <= weight <= 100:
                continue
            result.append(f'<div class="bar"><span>{e(stock["name"])}</span><meter min="0" max="100" value="{weight}"></meter><b>{weight:.2f}%</b></div>')
        return "".join(result)
    mode = "深度报告" if deep else "快报 · 未经深度 Agent 取证"
    sources = {s["id"]:s for s in r["sources"]}
    def cites(refs):
        refs = refs if isinstance(refs, list) else [refs or ""]
        ids = dict.fromkeys(re.findall(r"\b[A-D]\d{2,}\b", " ".join(refs)))
        return " · ".join(f'<a href="#source-{e(k)}">{e(sources[k]["title"])}</a>' for k in ids if k in sources)
    head = f'<header><small>基金经理照妖镜　/　{mode}</small><h1>{e(r["people"]["manager"])}</h1><p>{e(f["short_name"])}　{e(f["code"])}　{e(f["share_class"])}</p><p>研究截至 {e(m["as_of"])}　｜　持仓截至 {e(m["evidence_cutoff"])}</p></header>'
    body = section("研究判断",f'<strong class="stamp">{e(v["label"])}</strong><h3>{e(v["sentence"])}</h3>{lis(v["reasons"])}<p>{cites(v.get("evidence_refs") or v.get("evidence_ref"))}</p>')
    body += section("机构怎么看",e(v["institutional_view"])+"<h3>什么变化会改判</h3>"+lis(v["flip_conditions"]))
    body += section("谁在管理",lis([f'{x["name"]} · {x["start_date"]} 至 {x.get("end_date") or "研究日"}' for x in f["managers"]]))
    philosophy = r["people"]["fields"].get("investment_philosophy", {})
    if philosophy.get("conclusion"):
        body += section("经理相信什么",e(philosophy["conclusion"])+"　"+cites(philosophy.get("evidence_ref")))
    if deep:
        rarity = r["manager_rarity"]
        body += section("经理卡",f'<strong class="stamp">{e(rarity["card_rarity"])}</strong><h3>{e(rarity["punchline"])}</h3>{e(rarity["scarcity_reason"])}<p>反证：{e(rarity["counterevidence"])}</p>')
        ind = r["independent_decision"]
        body += section("独立决策", "".join(f'<h3>{title}</h3><p>{e(ind[k]["conclusion"])}</p>' for k,title in [("thinking","敢不敢和同事买得不一样"),("alpha","不一样的时候赚了钱吗")])+lis(ind.get("missing_data", [])))
    if f.get("latest_top_holdings"):
        body += section("季末重仓 · 占基金净值", bars(f["latest_top_holdings"]))
    scope = r["meta"]["coverage"]["holding_periods"]
    body += section("持仓复盘", f'本次任职从 {e(m["holding_window_start"])} 开始；收录 {scope} 期。共管期的仓位和盈亏属于团队。榜单只比较有披露的区间。')
    stocks = []
    for group,title in [("winners","估算盈利最多"),("losers","估算亏损最多"),("manager_approved","经理本人点名"),("manager_approved_candidates","描述对应的候选")]:
        lines = []
        for entry in ledger.get(group, []):
            item = entry.get("trade_record") or entry
            lines.append(f'<button type="button" data-stock="{len(stocks)}">{e(item.get("name"))}　{e(money(item.get("estimated_pnl")))}</button>')
            stocks.append(item)
        fallback = ledger.get("manager_approved_conclusion") if group=="manager_approved" else None
        body += section(title,"".join(lines) or e(fallback or "本案没有足够的披露记录。"))
    if stocks:
        body += section("周K与持仓变化",'<h3 id="stock-name"></h3><div id="chart"></div><p>标记为报告期末附近的公开持股变化，成交日未知。</p>')
    if deep:
        names = dict(re.findall(r"^\| ([MP]\d\d) \| ([^|]+?) \|", (SKILL/"references/module-contract.md").read_text(encoding="utf8"),re.M))
        for key,title in [("people_reviews","经理的24项调查"),("module_reviews","基金的45项调查")]:
            rows = []
            for k, item in sorted(r["agent_panel"][key].items()):
                rows.append(f'<details><summary>{e(names.get(k,"调查项目"))} · {e(item["conclusion"])}</summary><p>{e(item["status"])}　{cites(item["evidence_refs"])}</p></details>')
            body += section(title,"".join(rows))
    if r.get("gaps"):
        body += section("还缺什么",lis(r["gaps"]))
    refs = []
    for k,s in sources.items():
        url = s.get("url_or_path") or s.get("url") or ""
        link = f'<a href="{e(url)}" rel="noreferrer">{e(s["title"])}</a>' if urlsplit(url).scheme=="https" and urlsplit(url).hostname else e(s["title"])
        refs.append(f'<p id="source-{e(k)}">{link}　{e(s.get("published_at",""))}　{e(s.get("page_or_paragraph",""))}</p>')
    body += section("原始资料","".join(refs))
    js = ""
    if stocks:
        series = (stock_ohlc or {}).get("series", {})
        packed = json.dumps([stocks,{"series":{str(i.get("code")):series[str(i["code"])] for i in stocks if str(i.get("code")) in series}}],ensure_ascii=True,allow_nan=False).replace("<","\\u003c")
        assets = SKILL / "assets"
        js = "<script>"+(assets/"report-chart.js").read_text(encoding="utf8")+"</script><script>"+(assets/"human-language.js").read_text(encoding="utf8")+"</script>"
        js += '<script type="application/json" id="stock-data">'+packed+'</script><script>const [stocks,ohlc]=JSON.parse(document.getElementById("stock-data").textContent);function show(n){const item=stocks[n];document.getElementById("stock-name").textContent=item.name;FMFReportChart.buildCandlestickSvg({container:document.getElementById("chart"),item,stockOhlc:ohlc,human:FMFHumanLanguage});}document.querySelectorAll("[data-stock]").forEach(b=>b.onclick=()=>{show(+b.dataset.stock);document.getElementById("stock-name").scrollIntoView({block:"center"});});show(0);</script>'
    style = """*{box-sizing:border-box}body{margin:0;background:#f5f2e9;color:#252620;font:16px/1.65 system-ui,sans-serif}main{max-width:860px;margin:auto;padding:24px}header{border-top:8px solid #243c32;border-bottom:1px solid;padding:24px 0}h1{font:800 clamp(44px,8vw,76px)/1.05 serif;margin:18px 0}h2{font:700 24px/1.25 serif}section{padding:16px 0;border-bottom:1px solid #bbb8a9}.stamp{color:#86392b;border:2px solid;padding:4px 12px;display:inline-block;font-weight:850}meter{width:100%;accent-color:#46664d}.bar{display:grid;grid-template-columns:6em 1fr 5em;align-items:center;gap:12px}.bar b{text-align:right}a{color:#295a48}button,summary{cursor:pointer}button{margin:4px;padding:7px 10px;border:1px solid #aca99c;color:inherit;background:white}details{padding:.5em 0}#chart svg{width:100%}.candle-body.is-up,.event-buy circle{fill:#b74439}.candle-body.is-down,.event-sell circle{fill:#248067}.candle-wick.is-up{stroke:#b74439}.candle-wick.is-down{stroke:#248067}.chart-grid{stroke:#c8c7bf}.event-stem{stroke:#777}.event-mark{fill:white}#chart text{font:12px sans-serif}footer{padding:24px 0;color:#54544e}"""
    return f'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><link rel="icon" href="data:,"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(f["short_name"])} · {mode}</title><style>{style}</style><main>{head}{body}<footer>历史研究记录，不是个性化投资建议。</footer></main>{js}</html>'
