#!/usr/bin/env python3
"""把 lightweight-charts 库和买卖复盘数据注入 prototype-v2.html(单文件自包含)。

先运行 scripts/build_replay_data.py 生成 .cache/replay.json。
"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")

replay = open(os.path.join(ROOT, ".cache", "replay.json")).read()
lib = open(os.path.join(ASSETS, "vendor", "lightweight-charts.js")).read()

tpl_path = os.path.join(ASSETS, "prototype-v2.template.html")
out_path = os.path.join(ASSETS, "prototype-v2.html")
html = open(tpl_path).read()
assert "/*__LWCHARTS__*/" in html and "/*__RPDATA__*/" in html, "placeholders missing"
html = html.replace("/*__LWCHARTS__*/", lib.replace("</script>", "<\\/script>"))
html = html.replace("/*__RPDATA__*/{}", replay)
open(out_path, "w").write(html)

n = len(json.loads(replay)["stocks"])
print(f"injected: lib={len(lib)//1024}KB, replay={len(replay)//1024}KB ({n} stocks), total={len(html)//1024}KB")
