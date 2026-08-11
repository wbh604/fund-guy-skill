#!/usr/bin/env python3
"""把 lightweight-charts 库和 baostock 真实周K数据注入 prototype-v2.html(单文件自包含)。"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
CACHE = os.path.join(ROOT, ".cache")

STOCKS = [
    ("sh.601012", "2019-03-01_2022-06-30"),
    ("sz.002129", "2020-09-01_2022-06-30"),
    ("sz.300750", "2020-04-01_2022-09-30"),
    ("sz.002027", "2021-01-01_2022-02-28"),
]

portfolio = json.load(open(os.path.join(CACHE, "holdings", "portfolio.json")))
points_by_code = {s["code"]: s["points"] for s in portfolio["stocks"]}

kdata = {}
for code, span in STOCKS:
    rows = json.load(open(os.path.join(CACHE, "kline", f"{code}_{span}.json")))
    candles = [[r["date"], round(r["o"], 2), round(r["h"], 2), round(r["l"], 2), round(r["c"], 2)] for r in rows]
    dates = [c[0] for c in candles]
    dset = set(dates)

    def snap(d):
        if d in dset:
            return d
        earlier = [x for x in dates if x < d]
        return earlier[-1] if earlier else dates[0]

    pts = [{"date": snap(p["date"]), "act": p["act"]} for p in points_by_code.get(code, [])]
    kdata[code] = {"candles": candles, "points": pts}

lib = open(os.path.join(ASSETS, "vendor", "lightweight-charts.js")).read()

tpl_path = os.path.join(ASSETS, "prototype-v2.template.html")
out_path = os.path.join(ASSETS, "prototype-v2.html")
html = open(tpl_path).read()
assert "/*__LWCHARTS__*/" in html and "/*__KDATA__*/" in html, "placeholders missing"
html = html.replace("/*__LWCHARTS__*/", lib.replace("</script>", "<\\/script>"))
html = html.replace("/*__KDATA__*/{}", json.dumps(kdata, ensure_ascii=False, separators=(",", ":")))
open(out_path, "w").write(html)
print(f"injected: lib={len(lib)//1024}KB, kdata={len(json.dumps(kdata))//1024}KB, total={len(html)//1024}KB")
for code, d in kdata.items():
    print(f"  {code}: {len(d['candles'])} candles, {len(d['points'])} B/S points "
          f"({', '.join(p['date'] + '/' + p['act'] for p in d['points'])})")
