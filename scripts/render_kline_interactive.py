"""生成交互式 K 线买卖复盘页。

读取 .cache/holdings/portfolio.json(持仓+B/S点)与 .cache/holdings/*.json(真实日K),
用 lightweight-charts 生成可拖动/缩放、可切换股票的页面。

用法: python scripts/render_kline_interactive.py
产出: assets/kline-interactive.html
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORTFOLIO = ROOT / ".cache" / "holdings" / "portfolio.json"
HLD_DIR = ROOT / ".cache" / "holdings"
OUT = ROOT / "assets" / "kline-interactive.html"
VENDOR = "vendor/lightweight-charts.js"  # 相对 assets/ 的路径

SKILL_META = {
    "a": ("买对", "#34d399"),
    "c": ("买贵", "#fbbf24"),
    "f": ("卖飞", "#f87171"),
    "d": ("割肉", "#f87171"),
}

HTML = """<!DOCTYPE html>
<html lang="zh-CN" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>持仓买卖复盘 · 交互式K线</title>
<style>
:root{--bg:#080a0d;--surface:#11151b;--raised:#171d25;--ink:#f2f5f8;--muted:#8b95a3;
  --ghost:#5a6472;--line:#1e242d;--line-hard:#2c343f;--ok:#34d399;--danger:#f87171;
  --warn:#fbbf24;--indep:#a78bfa;--radius:16px}
[data-theme="light"]{--bg:#eef1f5;--surface:#fff;--raised:#f6f8fa;--ink:#0d1420;
  --muted:#4a5568;--ghost:#94a3b8;--line:#dfe5ec;--line-hard:#0d1420;--ok:#047857;
  --danger:#be123c;--warn:#b45309;--indep:#6d28d9}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);font-family:Inter,'PingFang SC',system-ui,sans-serif;
  font-variant-numeric:tabular-nums;line-height:1.6;padding:24px 20px 80px}
.wrap{max-width:1240px;margin:0 auto}
.top{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-bottom:6px}
.top h1{font-size:24px;font-weight:900;letter-spacing:.05em}
.top .sub{font-size:12.5px;color:var(--muted)}
.theme-btn{position:fixed;right:20px;top:20px;width:46px;height:46px;border-radius:50%;
  border:2px solid var(--line-hard);background:var(--surface);color:var(--ink);font-size:19px;cursor:pointer}
.legend{display:flex;gap:18px;font-size:12px;color:var(--muted);margin:12px 0 16px;flex-wrap:wrap}
.legend i{display:inline-block;width:11px;height:11px;border-radius:2px;margin-right:6px;vertical-align:-1px}
.legend .r{background:#e0483e}.legend .g{background:#1e9e6e}
.layout{display:grid;grid-template-columns:340px 1fr;gap:18px;align-items:start}
@media(max-width:960px){.layout{grid-template-columns:1fr}}
/* 左侧持仓列表 */
.side{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:16px;max-height:76vh;overflow-y:auto}
.side .tt{font-size:11px;font-weight:800;letter-spacing:.2em;color:var(--ghost);margin-bottom:10px}
.si{display:flex;align-items:center;gap:12px;padding:11px 12px;border-radius:10px;cursor:pointer;
  border:1px solid transparent;transition:.15s;margin-bottom:4px}
.si:hover{background:var(--raised)}
.si.on{background:var(--raised);border-color:var(--indep)}
.si .nm{font-weight:800;font-size:14px;flex:1}
.si .code{font-size:10px;color:var(--ghost)}
.si .wt{font-size:11px;color:var(--ghost);background:var(--sunk);padding:2px 7px;border-radius:10px}
.si .sk{font-size:10px;font-weight:800;padding:3px 8px;border-radius:4px;white-space:nowrap}
.si .pts{font-size:10px;color:var(--muted);margin-top:2px}
.si .inner{flex:1}
/* 右侧图表 */
.chart-panel{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:18px}
.chart-head{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;margin-bottom:6px}
.chart-head .n{font-size:22px;font-weight:900}
.chart-head .code{font-size:12px;color:var(--ghost)}
.chart-head .ind{font-size:11px;color:var(--muted);background:var(--sunk);padding:3px 10px;border-radius:10px}
.chart-head .skill{margin-left:auto;font-size:11px;font-weight:800;padding:5px 12px;border-radius:20px}
.chart-verdict{font-size:13.5px;color:var(--muted);margin:8px 0 12px;line-height:1.7}
.chart-verdict b{color:var(--ink)}
#chart{width:100%;height:520px}
.chart-foot{display:flex;align-items:center;gap:16px;font-size:12px;color:var(--muted);margin-top:10px;flex-wrap:wrap}
.chart-foot .sep{color:var(--ghost)}
.hint{font-size:11px;color:var(--ghost);margin-top:6px}
.foot{margin-top:40px;font-size:11px;color:var(--ghost);text-align:center;line-height:2}
</style>
</head>
<body>
<div class="wrap">
  <div class="top">
    <h1>持仓买卖复盘</h1>
    <span class="sub">五年 14 只持仓 · 点击左侧切换 · K线可拖动缩放</span>
  </div>
  <div class="legend">
    <span><i class="r"></i>涨</span><span><i class="g"></i>跌</span>
    <span>▲ 买入/加仓</span><span>▼ 卖出/止损</span>
    <span>提示:拖动平移 · 滚轮缩放</span>
  </div>
  <div class="layout">
    <div class="side" id="side">
      <div class="tt">持仓列表 · 点击查看K线</div>
    </div>
    <div class="chart-panel">
      <div class="chart-head">
        <span class="n" id="cname">—</span>
        <span class="code" id="ccode"></span>
        <span class="ind" id="cind"></span>
        <span class="skill" id="cskill"></span>
      </div>
      <div class="chart-verdict" id="cverdict"></div>
      <div id="chart"></div>
      <div class="chart-foot">
        <span id="crange"></span>
        <span class="sep">·</span>
        <span id="crating"></span>
        <span class="sep">·</span>
        <span id="cweight"></span>
      </div>
      <div class="hint">买卖点标注:▲ 买入/加仓 ▼ 卖出/止损 · 拖动查看完整 7 年走势 · 滚轮缩放</div>
    </div>
  </div>
  <p class="foot">K线为真实历史数据(baostock 日K,前复权)· B/S 买卖点与复盘为界面演示用模拟数据<br>非投资建议</p>
</div>
<script src="VENDOR"></script>
<script>
const DATA = DATA_JSON;
const meta = {
  'a':['买对','#34d399'],'c':['买贵','#fbbf24'],'f':['卖飞','#f87171'],'d':['割肉','#f87171']
};
let chart=null, series=null, markers=null;
let currentName=null;

// 颜色(随主题)
const isDark = ()=>document.documentElement.dataset.theme==='dark';

function fmtDate(ts){const d=new Date(ts*1000);return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');}

function buildSide(){
  const side=document.getElementById('side');
  DATA.stocks.forEach(s=>{
    const el=document.createElement('div');
    el.className='si';
    const [sk,scc]=meta[s.skill_key]||[s.skill,'#8b95a3'];
    const ptCount=s.points.filter(p=>p.act==='sell').length+'卖 / '+s.points.length+'笔';
    el.innerHTML=`<div class="inner"><div class="nm">${s.name}</div>
      <div class="pts">${s.industry} · ${s.weight}%仓</div></div>
      <span class="wt">${ptCount}</span>
      <span class="sk" style="background:${scc}1a;color:${scc};border:1px solid ${scc}44">${sk}</span>`;
    el.onclick=()=>{select(s);};
    side.appendChild(el);
  });
}

function buildChart(s){
  if(chart){chart.remove();chart=null;series=null;}
  const container=document.getElementById('chart');
  chart=LightweightCharts.createChart(container,{
    width:container.clientWidth,
    height:520,
    layout:{background:{type:'solid',color:isDark()?'#11151b':'#ffffff'},
      textColor:isDark()?'#8b95a3':'#4a5568',fontSize:11},
    grid:{vertLines:{color:isDark()?'#1e242d':'#eef1f5'},
      horzLines:{color:isDark()?'#1e242d':'#eef1f5'}},
    timeScale:{borderColor:isDark()?'#2c343f':'#dfe5ec',timeVisible:true,rightOffset:8,barSpacing:7},
    crosshair:{mode:0},
    localization:{locale:'zh-CN'},
    autoSize:true,
  });
  series=chart.addCandlestickSeries({
    upColor:'#e0483e',downColor:'#1e9e6e',borderUpColor:'#e0483e',
    borderDownColor:'#1e9e6e',wickUpColor:'#e0483e',wickDownColor:'#1e9e6e',
  });
  series.setData(s.kline.map(k=>({time:k.t,open:k.o,high:k.h,low:k.l,close:k.c})));
  // 买卖点
  const mk=s.points.map(p=>{
    const ts=Math.floor(new Date(p.date+'T00:00:00Z').getTime()/1000);
    return {time:ts,position:p.act==='buy'?'belowBar':'aboveBar',
      color:p.act==='buy'?'#1e9e6e':'#e0483e',
      shape:p.act==='buy'?'arrowUp':'arrowDown',
      text:p.label+' '+(p.note||'')};
  });
  series.setMarkers(mk);
  // 最近一根
  chart.timeScale().fitContent();
}

function select(s){
  currentName=s.name;
  document.querySelectorAll('.si').forEach((el,i)=>{
    el.classList.toggle('on',DATA.stocks[i].name===s.name);
  });
  document.getElementById('cname').textContent=s.name;
  document.getElementById('ccode').textContent=s.code;
  document.getElementById('cind').textContent=s.industry+' · 仓位 '+s.weight+'%';
  const [sk,scc]=meta[s.skill_key]||[s.skill,'#8b95a3'];
  const skEl=document.getElementById('cskill');
  skEl.textContent=sk;skEl.style.color=scc;skEl.style.background=scc+'1a';
  skEl.style.border='1px solid '+scc+'44';
  document.getElementById('cverdict').innerHTML='<b>复盘:</b>'+s.verdict;
  document.getElementById('crating').textContent='评级: '+s.rating;
  document.getElementById('cweight').textContent='建议仓位不超过5%';
  const last=s.kline[s.kline.length-1];
  const first=s.kline[0];
  document.getElementById('crange').textContent=first.t+' → '+last.t+' · '+s.kline.length+' 根日K';
  buildChart(s);
}

// 主题
const btn=document.createElement('button');btn.className='theme-btn';btn.textContent='🌙';
btn.onclick=()=>{
  const t=isDark()?'light':'dark';
  document.documentElement.dataset.theme=t;btn.textContent=t==='dark'?'🌙':'☀️';
  if(currentName){const s=DATA.stocks.find(x=>x.name===currentName);buildChart(s);}
};
document.body.prepend(btn);

buildSide();
select(DATA.stocks[0]);
</script>
</body>
</html>
"""


def build():
    pf = json.loads(PORTFOLIO.read_text())
    stocks_out = []
    for s in pf["stocks"]:
        kf = HLD_DIR / f'{s["name"]}.json'
        kline = json.loads(kf.read_text()) if kf.exists() else []
        # 只保留交易点日期范围内的,但保留全部用于拖动查看
        stocks_out.append({**s, "kline": kline})

    data_json = json.dumps({"stocks": stocks_out}, ensure_ascii=False)
    html = HTML.replace("VENDOR", VENDOR).replace("DATA_JSON", data_json)
    OUT.write_text(html)
    print(f"生成 {OUT} ({len(html)//1024} KB, {len(stocks_out)} 只股票)")


if __name__ == "__main__":
    build()
