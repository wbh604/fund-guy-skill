#!/usr/bin/env python3
"""用真实数据生成基金报告页(复用 v2 设计系统与买卖复盘模块)。

用法: python scripts/build_fund_report.py 163417 → assets/fund-163417.html
"""
import json, os, re, sys

CODE = sys.argv[1] if len(sys.argv) > 1 else "163417"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = json.load(open(os.path.join(ROOT, ".cache", f"fund_{CODE}", "analysis.json")))
TPL = open(os.path.join(ROOT, "assets", "prototype-v2.template.html")).read()
LIB = open(os.path.join(ROOT, "assets", "vendor", "lightweight-charts.js")).read()

css = re.search(r"<style>(.*?)</style>", TPL, re.S).group(1)
main_js = re.search(r"<script>/\*__LWCHARTS__\*/</script>\n<script>(.*?)</script>\n</body>", TPL, re.S).group(1)

m = A["nav_metrics"]
pro = A["pro"]
years = A["years"]
regimes = A["managers"]          # 新→旧
scale = A["scale"]
meta = A["meta"]

# ---- 前端 JS 适配:真实代码无 sh./sz. 前缀;灾难片系数用真实回撤 ----
main_js = main_js.replace("s.code.split('.')[1]", "s.code.split('.').pop()")
main_js = main_js.replace("w * 0.674", f"w * {1 - m['max_dd']/100:.3f}")
main_js = main_js.replace("/*__RPDATA__*/{}", json.dumps(A["replay"], ensure_ascii=False, separators=(",", ":")))

# ---- 计算显示量 ----
wins = sum(1 for y in years if y["win"])
dots = "".join(f'<i class="{"w" if y["win"] else "l"}"></i>' for y in years)
uw_years = m["underwater_days"] // 365
uw_months = m["underwater_days"] // 30
total = m["total_ret"]
n_years = 8.5
cagr = ((1 + total/100) ** (1/n_years) - 1) * 100

regime_rows = ""
palette = {"独管": "var(--accent)", "共管": "var(--indep)"}
for r in reversed(regimes):  # 旧→新
    solo = "独管" if " " not in r["managers"].strip() else "共管"
    ret = r["ret"].replace("%", "")
    try:
        retf = float(ret)
    except ValueError:
        retf = 0
    cls = "ok" if retf > 0 else "danger"
    period = f'{r["start"][:7]}→{r["end"][:7] if r["end"] != "至今" else "至今"}'
    regime_rows += f'''<tr><td style="font-size:12.5px;white-space:nowrap">{period}</td>
      <td style="font-size:13px;white-space:nowrap"><b>{r["managers"]}</b>
        <span class="tag {'good' if solo=='独管' else 'purple'}" style="margin-left:6px">{solo}</span></td>
      <td style="font-size:11.5px;color:var(--muted);white-space:nowrap">{r["days"].replace("又","")}</td>
      <td class="v {cls}">{r["ret"]}</td></tr>'''

years_rows = ""
for y in years:
    csi = f'{y["csi300"]:+.1f}%' if y["csi300"] is not None else "—"
    years_rows += f'''<tr><td class="v" style="text-align:left">{y["year"]}</td>
      <td class="v {'ok' if y['fund']>0 else 'danger'}">{y["fund"]:+.1f}%</td>
      <td class="v">{csi}</td>
      <td class="v">{'<span class="ok">跑赢</span>' if y["win"] else '<span class="danger">跑输</span>'}</td>
      <td style="font-size:12px;color:var(--muted);text-align:right">{y["rank"]}</td></tr>'''

# 规模条(每年Q2/Q4 取样,避免太密)
sc = [s for s in scale if s["q"].endswith("2") or s["q"].endswith("4")]
sc_max = max(s["yi"] for s in sc)
scale_bars = "".join(
    f'''<div class="bar-row" style="grid-template-columns:64px 1fr 70px">
      <span class="k">{s["q"]}</span>
      <div class="bar-track"><div class="bar-fill {'warn' if s['yi']==sc_max else ''}" data-w="{s['yi']/sc_max*100:.0f}"></div></div>
      <span class="v">{s["yi"]:.0f} 亿</span></div>''' for s in sc)

html = f'''<!DOCTYPE html>
<html lang="zh-CN" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>基金经理照妖镜 · 谢治宇 · 兴全合宜(真实数据)</title>
<style>{css}</style>
</head>
<body>
<div class="mock-tag" style="background:var(--ok)">真实公开数据</div>
<button class="theme-btn" id="themeBtn" title="切换主题">🌙</button>

<div class="wrap">

<div class="topbar">
  <span class="brand-dot"></span>
  <span class="brand-txt">基金经理照妖镜</span>
  <span class="date">数据截至 {m["until"]} · 全部来自公开披露</span>
</div>

<nav class="tabs" id="tabbar">
  <span class="tab on" data-sec="s1"><span class="n">01</span>判决书</span>
  <span class="tab" data-sec="s2"><span class="n">02</span>这个人</span>
  <span class="tab" data-sec="s3"><span class="n">03</span>买卖复盘</span>
  <span class="tab" data-sec="s4"><span class="n">04</span>你会怎么亏</span>
  <span class="tab" data-sec="s5"><span class="n">05</span>机构视角</span>
  <span class="tab" data-sec="s6"><span class="n">06</span>怎么用</span>
</nav>

<!-- ============ 01 判决书 ============ -->
<section id="s1" class="sec">
  <div class="sec-head">
    <span class="sec-num">01</span><span class="sec-ti">判决书</span>
    <span class="sec-sub">真实数据 · 部分模块待跑,评分为区间估算</span><span class="sec-line"></span>
  </div>

  <div class="grid hero3">
    <div class="card">
      <span class="lbl">受检对象</span>
      <div style="display:flex;align-items:center;gap:20px;margin-top:10px">
        <div style="width:88px;height:110px;border-radius:10px;background:linear-gradient(150deg,#252d39,#13181f);
          border:1px solid var(--line);display:flex;align-items:center;justify-content:center;
          font-size:34px;font-weight:900;color:var(--ghost);flex-shrink:0">谢</div>
        <div style="flex:1;min-width:0">
          <h1 style="font-size:44px;font-weight:900;letter-spacing:-.02em">谢治宇</h1>
          <p style="font-size:14px;color:var(--muted);margin-top:4px">{meta.get("基金名称","兴全合宜混合(LOF)A")} · {CODE} · 贯穿管理 8 年半</p>
          <div class="tags" style="margin-top:10px">
            <span class="tag rarity">公募顶流 · 明星卡</span>
            <span class="tag good">成立以来 +{total:.0f}%</span>
            <span class="tag purple">五任配置 · 他是常量</span>
            <span class="tag hot">最大回撤 {m["max_dd"]:.0f}%</span>
            <span class="tag hot">规模 {meta.get("最新规模","123亿")}</span>
          </div>
        </div>
        <div class="hero-style" style="text-align:right;flex-shrink:0;border-left:1px solid var(--line);padding-left:22px">
          <span class="lbl">打法</span>
          <div style="font-size:22px;font-weight:900;color:var(--indep);margin-top:8px;line-height:1.35">大盘成长<br>质量白马</div>
          <div style="font-size:11px;color:var(--ghost);margin-top:8px">A+H 两地 · 低换手<br>抱住核心资产</div>
        </div>
      </div>
    </div>

    <div class="card" style="text-align:center">
      <span class="lbl">总评分(区间估算)</span>
      <div class="score-giant" data-count="66">0</div>
      <div class="rangebar">
        <div class="seg" style="left:40%;width:26.7%"></div>
        <div class="pin" style="left:53.3%"></div>
        <span class="rl" style="left:2%">50</span>
        <span class="rl" style="left:40%">62</span>
        <span class="rl" style="left:53.3%;color:var(--accent);font-weight:900">66</span>
        <span class="rl" style="left:66.7%">70</span>
        <span class="rl" style="left:96%">80</span>
      </div>
      <div style="font-size:11px;color:var(--ghost)">证据覆盖 6/12 模块 · 独立战争与运气拆解未跑 · 上限 B+</div>
    </div>

    <div class="card" style="display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px">
      <div class="stamp" style="border-color:var(--warn);color:var(--warn);background:var(--warn-tint)">
        <span class="big">再等等</span><span class="sm">刚回本 · 别追高</span></div>
      <div style="font-size:13px;color:var(--muted);margin-top:12px">Conviction</div>
      <div style="font-size:17px;font-weight:900">中</div>
    </div>
  </div>

  <div class="punchline" style="margin-top:24px">
    2021 年 2 月买在山顶的人,等了 <span class="em">{m["underwater_days"]} 天</span>才回本 ——
    整整 <span class="em">{uw_years} 年</span>。
  </div>

  <div class="card" style="margin-top:var(--gap);display:flex;align-items:center;gap:26px;flex-wrap:wrap">
    <div>
      <span class="lbl">年度战绩 vs 沪深300 · {len(years)} 年</span>
      <div class="dots" style="margin-top:10px">{dots}</div>
      <div style="font-size:11px;color:var(--ghost);margin-top:8px">{len(years)} 年 · <b class="ok">{wins} 胜</b> · <b class="danger">{len(years)-wins} 负</b></div>
    </div>
    <div style="flex:1;min-width:280px;display:grid;grid-template-columns:1fr 1fr;gap:12px">
      <div class="stat" style="border-color:var(--ok)"><span class="lbl">成立以来累计</span><span class="v ok">+{total:.0f}%</span><span class="sub">年化约 {cagr:.1f}%</span></div>
      <div class="stat"><span class="lbl">同类排名</span><span class="v">前 32%</span><span class="sub">669 / 2124 · 成立以来</span></div>
    </div>
  </div>

  <div class="grid g4" style="margin-top:var(--gap)">
    <div class="stat hl"><span class="lbl">人</span>
      <span class="v ok">通过</span><span class="sub">8 年半从未离开 · 履历可查</span></div>
    <div class="stat"><span class="lbl">产品</span>
      <span class="v" style="color:var(--warn)">有限通过</span><span class="sub">131 亿大船 · 调头慢</span></div>
    <div class="stat"><span class="lbl">当前</span>
      <span class="v" style="color:var(--warn)">刚回本</span><span class="sub">2026-05 才收复 2021 高点</span></div>
    <div class="stat"><span class="lbl">你</span>
      <span class="v cyan">看持有期</span><span class="sub">扛得住 5 年水下再来</span></div>
  </div>
</section>

<!-- ============ 02 这个人 ============ -->
<section id="s2" class="sec">
  <div class="sec-head">
    <span class="sec-num">02</span><span class="sec-ti">这个人</span>
    <span class="sec-sub">任期切割 · 谁在开车</span><span class="sec-line"></span>
  </div>

  <div class="grid g2">
    <div class="card">
      <span class="lbl">能力形成路径(公开资料)</span>
      <div class="tl" style="margin-top:18px">
        <div class="tl-item key"><b>2007</b><span class="d">复旦硕士毕业 · 加入兴全任研究员</span></div>
        <div class="tl-item key"><b>2013-01</b><span class="d">接管兴全合润 · 成名作</span></div>
        <div class="tl-item key"><b>2018-01</b><span class="d">兴全合宜一日募集 327 亿 · 现象级发行</span></div>
        <div class="tl-item"><b>2020</b><span class="d">+71.8% · 顶流之年</span></div>
        <div class="tl-item"><b>2021–2023</b><span class="d">连续三年跑输沪深300 · 深度回撤</span></div>
        <div class="tl-item"><b>2026-05</b><span class="d">净值收复 2021 年高点</span></div>
      </div>
    </div>

    <div class="card">
      <span class="lbl">任期切割 · 他是唯一的常量</span>
      <table style="margin-top:12px">
        <tr><th>时段</th><th>阵容</th><th>时长</th><th style="text-align:right">区间收益</th></tr>
        {regime_rows}
      </table>
      <div class="chips" style="margin-top:12px">
        <span class="chip purple">副手换了 3 任 · 他从未离开</span>
        <span class="chip">业绩归属基本可记在他头上</span>
      </div>
    </div>
  </div>
</section>

<!-- ============ 03 买卖复盘 ============ -->
<section id="s3" class="sec">
  <div class="sec-head">
    <span class="sec-num">03</span><span class="sec-ti">买卖复盘</span>
    <span class="sec-sub">16 只重仓股 · 34 期真实披露推断</span><span class="sec-line"></span>
  </div>

  <div class="card replay">
    <div class="rp-head">
      <div>
        <span class="lbl">完整买卖复盘 · 真实周K + 真实持仓</span>
        <h3>他每一笔买卖,到底对不对</h3>
      </div>
      <div class="rp-tabs" id="rpTabs">
        <span class="rp-tab on" data-cat="win">赚最多</span>
        <span class="rp-tab" data-cat="lose">亏最多</span>
        <span class="rp-tab" data-cat="fly">卖飞现场</span>
      </div>
    </div>
    <div class="rp-body">
      <div class="rp-list" id="rpList"></div>
      <div class="rp-panel">
        <div class="rp-meta">
          <div>
            <span class="rp-rank" id="rpRank">第 1 名</span>
            <h2 id="rpName">—</h2>
            <span class="rp-code" id="rpCode"></span>
          </div>
          <div class="rp-amt up" id="rpAmt"></div>
        </div>
        <div class="rp-legend">
          <i><b class="mk b">买</b>买入或加仓</i>
          <i><b class="mk s">卖</b>减仓或清仓</i>
          <i><span style="display:inline-block;width:16px;border-top:2px solid #34d399"></span>成本线</i>
          <i><span style="display:inline-block;width:16px;border-top:2px dashed #f87171"></span>卖出线</i>
          <span class="kinfo" id="rpKinfo"></span>
        </div>
        <div class="rp-chart" id="rpChart"></div>
        <div class="rp-verdict" id="rpVerdict"></div>
        <div class="rp-grades" id="rpGrades"></div>
        <div class="rp-foot">买卖点按季报持股数变化推断(前十大消失≠卖出,仅全持仓期缺席记为清仓) · 盈亏为持仓区间估算 · K线为真实行情(周K·前复权)</div>
      </div>
    </div>
  </div>
</section>

<!-- ============ 04 你会怎么亏 ============ -->
<section id="s4" class="sec">
  <div class="sec-head">
    <span class="sec-num">04</span><span class="sec-ti">你会怎么亏</span>
    <span class="sec-sub">全部真实发生过</span><span class="sec-line"></span>
  </div>

  <div class="card">
    <span class="lbl">十万元灾难片 · 2021-02 山顶买入的真实经历</span>
    <div class="amount">
      <span class="lbl2">投多少</span>
      <input type="range" id="amountSlider" min="5" max="200" value="10" step="5">
      <span class="val" id="amountVal">10 万</span>
    </div>
    <div class="grid g4" style="margin-top:18px">
      <div class="stat"><span class="lbl">最差时账面剩</span><span class="v danger" id="worstVal">{10*(1-m["max_dd"]/100):.2f} 万</span><span class="sub">最大回撤 {m["max_dd"]}%</span></div>
      <div class="stat"><span class="lbl">回撤持续</span><span class="v">36 个月</span><span class="sub">2021-02 → 2024-02 一路向下</span></div>
      <div class="stat"><span class="lbl">等回本</span><span class="v danger">{uw_months} 个月</span><span class="sub">{m["uw_from"]} → {m["uw_to"][:7]}</span></div>
      <div class="stat"><span class="lbl">水下时长</span><span class="v long danger">{m["underwater_days"]} 天</span><span class="sub">超过 5 年</span></div>
    </div>
  </div>

  <div class="card" style="margin-top:var(--gap)">
    <span class="lbl">年度成绩单 vs 沪深300(全真实)</span>
    <table style="margin-top:12px">
      <tr><th>年份</th><th style="text-align:right">本基金</th><th style="text-align:right">沪深300</th><th style="text-align:right">胜负</th><th style="text-align:right">同类排名</th></tr>
      {years_rows}
    </table>
  </div>
</section>

<!-- ============ 05 机构视角 ============ -->
<section id="s5" class="sec">
  <div class="sec-head">
    <span class="sec-num">05</span><span class="sec-ti">机构视角</span>
    <span class="sec-sub">专业口径 · 全部由日净值与季报计算</span><span class="sec-line"></span>
  </div>

  <div class="grid g4">
    <div class="stat"><span class="lbl">夏普比率</span><span class="v">{pro["sharpe"]}</span><span class="sub">每冒 1 份风险赚多少 · 全期含深熊</span></div>
    <div class="stat"><span class="lbl">卡玛比率</span><span class="v">{pro["calmar"]}</span><span class="sub">年化收益 ÷ 最大回撤</span></div>
    <div class="stat hl"><span class="lbl">信息比率</span><span class="v ok">{pro["ir"]}</span><span class="sub">超额的稳定性 · &gt;0.5 属优秀</span></div>
    <div class="stat"><span class="lbl">月度胜率</span><span class="v">{pro["mwin"]}%</span><span class="sub">{pro["n_months"]} 个月 vs 沪深300</span></div>
  </div>

  <div class="card" style="margin-top:var(--gap)">
    <span class="lbl">上行 / 下行捕获 · 机构最看重的一组数</span>
    <div class="duo">
      <div class="side" style="border-color:var(--ok)"><div class="k">大盘涨的时候 · 他吃到</div><div class="n ok">{pro["up_cap"]}%</div></div>
      <div class="vs2">VS</div>
      <div class="side"><div class="k">大盘跌的时候 · 他挨</div><div class="n">{pro["dn_cap"]}%</div></div>
    </div>
    <div class="chips" style="margin-top:14px">
      <span class="chip ok">涨时多吃 {pro["up_cap"]-100} 个点 · 跌时少挨 {100-pro["dn_cap"]} 个点</span>
      <span class="chip">同时大于/小于 100 = 真本事的形状</span>
    </div>
  </div>

  <div class="grid g4" style="margin-top:var(--gap)">
    <div class="stat"><span class="lbl">年化 Alpha</span><span class="v ok">+{pro["alpha"]}%</span><span class="sub">CAPM · vs 沪深300</span></div>
    <div class="stat"><span class="lbl">Beta</span><span class="v">{pro["beta"]}</span><span class="sub">跟大盘同涨跌的程度</span></div>
    <div class="stat"><span class="lbl">跟踪误差</span><span class="v">{pro["te"]}%</span><span class="sub">敢偏离指数 · 主动味十足</span></div>
    <div class="stat"><span class="lbl">R²</span><span class="v">{pro["r2"]}</span><span class="sub">收益只有七成能用大盘解释</span></div>
  </div>

  <div class="grid g2" style="margin-top:var(--gap)">
    <div class="card">
      <span class="lbl">持仓特征(季报口径)</span>
      <div class="grid g2" style="margin-top:14px;gap:10px">
        <div class="stat" style="padding:14px"><span class="lbl">前十大集中度 · 均值</span><span class="v" style="font-size:24px">{pro["top10_avg"]}%</span></div>
        <div class="stat" style="padding:14px;border-color:var(--warn)"><span class="lbl">最新一期</span><span class="v warn" style="font-size:24px">{pro["top10_latest"]}%</span><span class="sub">集中度在抬升</span></div>
        <div class="stat" style="padding:14px"><span class="lbl">持股数量</span><span class="v" style="font-size:24px">{pro["n_stocks"]} 只</span><span class="sub">{pro["n_stocks_period"]} 年报全持仓</span></div>
        <div class="stat" style="padding:14px"><span class="lbl">年化波动</span><span class="v" style="font-size:24px">{pro["vol"]}%</span></div>
      </div>
    </div>
    <div class="card">
      <span class="lbl">风格箱(晨星口径 · 按持仓估)</span>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:2px;background:var(--line);border:2px solid var(--line);border-radius:8px;overflow:hidden;margin-top:14px;max-width:340px">
        <div style="background:var(--surface);padding:14px;text-align:center;font-size:11px;color:var(--ghost)">大盘价值</div>
        <div style="background:var(--surface);padding:14px;text-align:center;font-size:11px;color:var(--ghost)">大盘均衡</div>
        <div style="background:var(--accent-tint);padding:14px;text-align:center;font-size:12px;font-weight:900;color:var(--accent);outline:2px solid var(--accent);outline-offset:-2px">大盘成长 ●</div>
        <div style="background:var(--surface);padding:14px;text-align:center;font-size:11px;color:var(--ghost)">中盘价值</div>
        <div style="background:var(--surface);padding:14px;text-align:center;font-size:11px;color:var(--ghost)">中盘均衡</div>
        <div style="background:var(--surface);padding:14px;text-align:center;font-size:11px;color:var(--ghost)">中盘成长</div>
        <div style="background:var(--surface);padding:14px;text-align:center;font-size:11px;color:var(--ghost)">小盘价值</div>
        <div style="background:var(--surface);padding:14px;text-align:center;font-size:11px;color:var(--ghost)">小盘均衡</div>
        <div style="background:var(--surface);padding:14px;text-align:center;font-size:11px;color:var(--ghost)">小盘成长</div>
      </div>
      <div class="chips" style="margin-top:12px"><span class="chip purple">A+H 双市场 · 质量成长风格</span></div>
    </div>
  </div>

  <div class="grid g2" style="margin-top:var(--gap)">
    <div class="card">
      <span class="lbl">规模变化(估算 · 亿元)</span>
      <div style="margin-top:14px">{scale_bars}</div>
    </div>
    <div class="card">
      <span class="lbl">你要付的钱</span>
      <div class="chips" style="margin-top:16px">
        <span class="chip">申购(<100万) <b>1.5%</b></span>
        <span class="chip">管理费 <b>年 1.5%*</b></span>
        <span class="chip no">7天内赎回 <b>1.5%</b></span>
      </div>
      <div class="chips" style="margin-top:10px">
        <span class="chip">持有<i style="font-style:normal">≥</i>2年赎回 <b>0</b></span>
      </div>
      <p style="font-size:11px;color:var(--ghost);margin-top:14px">*管理费率以最新招募说明书为准</p>
      <div style="margin-top:20px">
        <span class="lbl">发行即巅峰</span>
        <div class="duo" style="margin-top:12px">
          <div class="side"><div class="k">2018 首发</div><div class="n">327 亿</div></div>
          <div class="vs2">→</div>
          <div class="side"><div class="k">现在</div><div class="n ok">131 亿</div></div>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- ============ 06 怎么用 ============ -->
<section id="s6" class="sec">
  <div class="sec-head">
    <span class="sec-num">06</span><span class="sec-ti">怎么用</span>
    <span class="sec-sub">判决参数 · 未跑模块</span><span class="sec-line"></span>
  </div>

  <div class="grid g2">
    <div class="card">
      <span class="lbl">判决参数</span>
      <div class="chips" style="margin-top:16px">
        <span class="chip">定位 <b>核心仓候选</b></span>
        <span class="chip">仓位 <b>≤10%</b></span>
        <span class="chip">持有 <b>≥5 年</b></span>
        <span class="chip">扛得住 <b>-52%</b></span>
      </div>
      <div class="chips" style="margin-top:12px">
        <span class="chip no">✕ 刚回本就追</span>
        <span class="chip no">✕ 拿不住 3 年</span>
      </div>
    </div>

    <div class="card">
      <span class="lbl">证据缺口 · 以下模块未跑,评分被压上限</span>
      <div class="trig" style="margin-top:14px">
        <span>独立战争(需全公司基金持仓)</span>
        <span>运气拆解(需因子回归)</span>
        <span>造神检测九项详查</span>
        <span>抄作业指数</span>
        <span>机构资金画像</span>
        <span>Alpha 到手率</span>
      </div>
      <p style="font-size:12px;color:var(--muted);margin-top:12px">按 SKILL 硬规则:证据置信度不足时,评级上限 B+,评分只给区间。</p>
    </div>
  </div>

  <div class="foot">
    <b style="color:var(--muted)">基金经理照妖镜 · 真实公开数据运行</b><br>
    数据来源:天天基金/雪球/巨潮公开披露(akshare) · 行情 baostock/新浪 · 买卖点为季报持股数推断,非实际成交<br>
    非个性化投资建议 · 基金过往业绩不预示未来表现 · 判决有效期至下一期持仓披露
  </div>
</section>

</div>

<script>{LIB.replace("</script>", "<\\/script>")}</script>
<script>{main_js}</script>
</body>
</html>'''

out = os.path.join(ROOT, "assets", f"fund-{CODE}.html")
open(out, "w").write(html)
print(f"→ {out}  ({len(html)//1024}KB)")
