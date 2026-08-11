"""渲染真实K线买卖复盘页。

数据:baostock 周K(前复权),缓存到 .cache/kline/。
用法:python scripts/render_kline.py  → 产出 assets/kline-review.html
"""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache" / "kline"
OUT = ROOT / "assets" / "kline-review.html"

# 每只股票的案例:买入/加仓/卖出点(日期 → 动作)
CASES = {
    "隆基绿能": {
        "code": "sh.601012", "display": "601012",
        "win_start": "2019-03-01", "win_end": "2022-06-30",
        "points": [
            ("2019-07-01", "买入", "B"),
            ("2020-04-01", "加仓", "B"),
            ("2021-06-01", "卖一半", "S"),
        ],
        "verdict": "买点优秀,持有两年翻倍后减半仓 —— 卖得太早,卖完一年又涨42%",
        "skill": ("买对 · 卖飞了", "c"),
        "rating": "买入A · 持有A- · 卖出C(卖了又涨42%)",
    },
    "中环股份": {
        "code": "sz.002129", "display": "002129",
        "win_start": "2020-09-01", "win_end": "2022-06-30",
        "points": [
            ("2021-01-01", "买入", "B"),
            ("2022-02-01", "卖出", "S"),
        ],
        "verdict": "方向判断正确但买点太高,追高后回调22%,靠拿住回本小赚",
        "skill": ("判断对 · 买贵了", "c"),
        "rating": "买入C+(追高) · 持有A · 判断A-",
    },
    "宁德时代": {
        "code": "sz.300750", "display": "300750",
        "win_start": "2020-04-01", "win_end": "2022-09-30",
        "points": [
            ("2020-08-01", "买入", "B"),
            ("2021-01-01", "加仓", "B"),
            ("2021-08-01", "全清", "S"),
        ],
        "verdict": "翻倍后全部清仓,此后一年又涨78% —— 卖出能力70的铁证",
        "skill": ("最大短板 · 卖飞", "f"),
        "rating": "买入A · 卖出D(清仓后翻倍)",
    },
    "分众传媒": {
        "code": "sz.002027", "display": "002027",
        "win_start": "2021-01-01", "win_end": "2022-02-28",
        "points": [
            ("2021-04-01", "买入", "B"),
            ("2021-09-01", "止损", "S"),
        ],
        "verdict": "看错后两个季度内止损-12%,没死扛 —— 认错速度的最好一次",
        "skill": ("买错 · 割得干脆", "a"),
        "rating": "买入C(看错了) · 止损A+(没死扛)",
    },
}

SKILL_META = {
    "a": ("买错 · 割得干脆", "var(--ok)"),
    "c": ("判断对 · 买贵了", "var(--warn)"),
    "f": ("最大短板 · 卖飞", "var(--danger)"),
}


def load_kline(symbol, start, end):
    """拉取并缓存周K,格式 [{date, open, high, low, close}]"""
    key = f"{symbol}_{start}_{end}.json"
    cache_file = CACHE / key
    if cache_file.exists():
        return json.loads(cache_file.read_text())
    import baostock as bs
    bs.login()
    rs = bs.query_history_k_data_plus(
        symbol, "date,open,high,low,close",
        start_date=start.replace("-", ""), end_date=end.replace("-", ""),
        frequency="w", adjustflag="2",
    )
    rows = []
    while (rs.error_code == "0") & rs.next():
        d = rs.get_row_data()
        rows.append({"date": d[0], "o": float(d[1]), "h": float(d[2]),
                     "l": float(d[3]), "c": float(d[4])})
    bs.logout()
    CACHE.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(rows))
    return rows


def render_candles(rows, points, W=920, H=300, pad=8):
    """渲染蜡烛SVG。A股习惯:涨=红,跌=绿。B/S点标注。"""
    if not rows:
        return "<p style='color:var(--ghost)'>无数据</p>"
    lo = min(r["l"] for r in rows)
    hi = max(r["h"] for r in rows)
    rng = (hi - lo) or 1
    n = len(rows)
    cw = (W - 2 * pad) / n           # 每根蜡烛宽
    bw = max(2.0, cw * 0.62)         # 实体宽
    iw = cw * 0.12                   # 影线宽
    y = lambda v: pad + (hi - v) / rng * (H - 2 * pad)

    parts = []
    parts.append(f'<svg class="kline" viewBox="0 0 {W} {H+22}" xmlns="http://www.w3.org/2000/svg">')
    # 网格线
    for g in range(1, 5):
        gy = pad + g * (H - 2 * pad) / 5
        parts.append(f'<line class="gl-t" x1="0" y1="{gy:.1f}" x2="{W}" y2="{gy:.1f}"/>')
    # 蜡烛
    for i, r in enumerate(rows):
        x = pad + i * cw + (cw - bw) / 2
        xi = pad + i * cw + (cw - iw) / 2
        up = r["c"] >= r["o"]
        col = "#e0483e" if up else "#1e9e6e"   # 红涨绿跌(A股)
        yc, yo = y(r["c"]), y(r["o"])
        top, hgt = (yc, yo - yc) if up else (yo, yc - yo)
        hgt = max(1.0, hgt)
        # 影线
        parts.append(f'<line x1="{x+bw/2:.1f}" y1="{y(r["h"]):.1f}" x2="{x+bw/2:.1f}" y2="{y(r["l"]):.1f}" stroke="{col}" stroke-width="1"/>')
        # 实体
        parts.append(f'<rect x="{x:.1f}" y="{top:.1f}" width="{bw:.1f}" height="{hgt:.1f}" fill="{col}" rx="1"/>')
    # B/S 点
    for pdate, label, act in points:
        idx = None
        for i, r in enumerate(rows):
            if r["date"] >= pdate:
                idx = i
                break
        if idx is None:
            continue
        x = pad + idx * cw + cw / 2
        py = y(rows[idx]["l"]) + 8
        if act == "S":
            py = y(rows[idx]["h"]) - 8
            col, anchor = "#e0483e", "middle"
            parts.append(f'<circle class="dot dot-sell" cx="{x:.1f}" cy="{py:.1f}" r="7"/>')
            parts.append(f'<text class="tag-sell" x="{x:.1f}" y="{py-12:.1f}" text-anchor="middle">S {label}</text>')
        else:
            col, anchor = "#1e9e6e", "middle"
            parts.append(f'<circle class="dot dot-buy" cx="{x:.1f}" cy="{py:.1f}" r="7"/>')
            parts.append(f'<text class="tag-buy" x="{x:.1f}" y="{py+22:.1f}" text-anchor="middle">B {label}</text>')
    # 价格轴
    for v in (hi, (hi+lo)/2, lo):
        gy = y(v)
        parts.append(f'<text x="{W-4}" y="{gy-4:.1f}" text-anchor="end" font-size="10" fill="var(--ghost)">{v:.1f}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def build():
    blocks = []
    for name, case in CASES.items():
        rows = load_kline(case["code"], case["win_start"], case["win_end"])
        skill_key = case["skill"][1]
        skill_txt, skill_col = SKILL_META[skill_key]
        svg = render_candles(rows, case["points"])
        blocks.append(f'''
<div class="rstock">
  <div class="rstock-head">
    <span class="rstock-name">{name}</span>
    <span class="rstock-code">{case["display"]}</span>
    <span class="rstock-skill" style="color:{skill_col};border-color:{skill_col};background:{skill_col}1a">{skill_txt}</span>
  </div>
  <div class="rstock-verdict">{case["verdict"]}</div>
  <div class="rstock-chart">{svg}</div>
  <div class="rstock-foot"><span>案例评级: {case["rating"]}</span></div>
</div>''')
    html = f'''<!DOCTYPE html>
<html lang="zh-CN" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>买卖复盘 · 真实K线 · B/S 点标注</title>
<style>
:root{{--bg:#080a0d;--surface:#11151b;--raised:#171d25;--ink:#f2f5f8;--muted:#8b95a3;
  --ghost:#5a6472;--line:#1e242d;--line-hard:#2c343f;--ok:#34d399;--danger:#f87171;
  --warn:#fbbf24;--indep:#a78bfa;--radius:16px;--gap:20px}}
[data-theme="light"]{{--bg:#eef1f5;--surface:#fff;--raised:#f6f8fa;--ink:#0d1420;
  --muted:#4a5568;--ghost:#94a3b8;--line:#dfe5ec;--line-hard:#0d1420;--ok:#047857;
  --danger:#be123c;--warn:#b45309;--indep:#6d28d9}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--ink);font-family:Inter,'PingFang SC',system-ui,sans-serif;
  font-variant-numeric:tabular-nums;line-height:1.6;padding:30px 20px 100px}}
.wrap{{max-width:960px;margin:0 auto}}
h1{{font-size:26px;font-weight:900;letter-spacing:.05em}}
.sub{{font-size:13px;color:var(--muted);margin-top:8px}}
.theme-btn{{position:fixed;right:20px;top:20px;width:46px;height:46px;border-radius:50%;
  border:2px solid var(--line-hard);background:var(--surface);color:var(--ink);font-size:19px;cursor:pointer}}
.rstock{{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:22px;margin-top:20px}}
.rstock-head{{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:8px}}
.rstock-name{{font-size:19px;font-weight:900}}
.rstock-code{{font-size:12px;color:var(--ghost)}}
.rstock-skill{{font-size:11px;font-weight:800;padding:4px 10px;border-radius:20px;margin-left:auto}}
.rstock-verdict{{font-size:13.5px;color:var(--muted);margin-bottom:14px;line-height:1.7}}
.rstock-chart{{border:1px solid var(--line);border-radius:10px;padding:12px;background:var(--raised)}}
.rstock-foot{{font-size:12.5px;color:var(--muted);margin-top:12px}}
.kline{{display:block;width:100%;height:auto}}
.kline .gl-t{{stroke:var(--line);stroke-width:.5;stroke-dasharray:3 4}}
.kline .dot{{stroke:var(--bg);stroke-width:2}}
.kline .dot-buy{{fill:#1e9e6e}}
.kline .dot-sell{{fill:#e0483e}}
.kline .tag-buy{{fill:#1e9e6e;font-size:10px;font-weight:900;paint-order:stroke;stroke:var(--bg);stroke-width:3px}}
.kline .tag-sell{{fill:#e0483e;font-size:10px;font-weight:900;paint-order:stroke;stroke:var(--bg);stroke-width:3px}}
.legend{{display:flex;gap:20px;font-size:12px;color:var(--muted);margin-top:14px}}
.legend i{{display:inline-block;width:12px;height:12px;border-radius:2px;margin-right:6px;vertical-align:-1px}}
.legend .r{{background:#e0483e}}.legend .g{{background:#1e9e6e}}
.foot{{margin-top:40px;font-size:11px;color:var(--ghost);text-align:center;line-height:2}}
</style>
</head>
<body>
<div class="wrap">
  <h1>买卖复盘 · 真实 K 线</h1>
  <p class="sub">数据来源:baostock 周K(前复权)· A股配色:红涨绿跌 · 圆点 = B/S 买卖点</p>
  <div class="legend">
    <span><i class="r"></i>涨</span><span><i class="g"></i>跌</span>
    <span>● 买入/加仓</span><span>● 卖出/止损</span>
  </div>
  {''.join(blocks)}
  <p class="foot">全部为界面演示用模拟买卖点,叠加真实历史K线 · 非投资建议</p>
</div>
<script>
const btn=document.createElement('button');btn.className='theme-btn';btn.textContent='🌙';
btn.onclick=()=>{{const t=document.documentElement.dataset.theme==='dark'?'light':'dark';
  document.documentElement.dataset.theme=t;btn.textContent=t==='dark'?'🌙':'☀️'}};
document.body.prepend(btn);
</script>
</body>
</html>'''
    OUT.write_text(html)
    print(f"生成 {OUT}  ({len(html)//1024} KB)")


if __name__ == "__main__":
    build()
