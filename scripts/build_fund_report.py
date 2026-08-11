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
ab = A["ability"]
ti = ab["timing"]
hs = None
_hp = os.path.join(ROOT, ".cache", f"fund_{CODE}", "house_analysis.json")
if os.path.exists(_hp):
    hs = json.load(open(_hp))
years = A["years"]
regimes = A["managers"]          # 新→旧
scale = A["scale"]
meta = A["meta"]

# ---- 前端 JS 适配:真实代码无 sh./sz. 前缀;灾难片系数用真实回撤 ----
main_js = main_js.replace("s.code.split('.')[1]", "s.code.split('.').pop()")
main_js = main_js.replace("w * 0.674", f"w * {1 - m['max_dd']/100:.3f}")
main_js = main_js.replace("/*__RPDATA__*/{}", json.dumps(A["replay"], ensure_ascii=False, separators=(",", ":")))
events_path = os.path.join(ROOT, ".cache", f"fund_{CODE}", "events.json")
events = open(events_path).read() if os.path.exists(events_path) else "[]"
main_js = main_js.replace("/*__RPEVENTS__*/[]", events)

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

inst_bars = ""
_inst = ab.get("inst_series") or []
_im = max((x["inst"] for x in _inst), default=1)
for x in _inst[-8:]:
    inst_bars += f"""<div class="bar-row" style="grid-template-columns:64px 1fr 56px;padding:3px 0">
      <span class="k" style="font-size:11px">{x['date']}</span>
      <div class="bar-track" style="height:9px"><div class="bar-fill" data-w="{x['inst']/_im*100:.0f}" style="background:var(--cyan)"></div></div>
      <span class="v" style="font-size:12px">{x['inst']:.1f}%</span></div>"""

bear_rows = ""
for b in ab["bear_defense"]:
    cls = "ok" if b["excess"] > 0 else "danger"
    bear_rows += f"""<tr><td class="v" style="text-align:left">{b['year']}</td>
      <td class="v danger">{b['fund']:+.1f}%</td><td class="v">{b['idx']:+.1f}%</td>
      <td class="v {cls}">{b['excess']:+.1f}</td></tr>"""

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

# ---- 独立战争 block ----
if hs:
    lt = hs["latest"]
    ct = hs["contrarian"]
    is_lone = lt["divergence"] > lt["peer_avg_div"]

    # 22 季度分歧时序
    ts_bars = ""
    _dmax = max(x["divergence"] for x in hs["series"])
    for x in hs["series"]:
        ts_bars += f"""<div class="bar-row" style="grid-template-columns:44px 1fr 46px;padding:2px 0">
          <span class="k" style="font-size:10.5px">{x['q']}</span>
          <div class="bar-track" style="height:7px"><div class="bar-fill" data-w="{x['divergence']/_dmax*100:.0f}" style="background:var(--indep)"></div></div>
          <span class="v" style="font-size:11px">{x['divergence']:.0f}%</span></div>"""

    # 他独在哪:双权重对比行
    def wrow(name, w_his, w_house):
        m = max(w_his, w_house, 0.1)
        return f"""<div style="display:grid;grid-template-columns:76px 1fr 110px;gap:10px;align-items:center;padding:7px 0;border-bottom:1px dashed var(--line);font-size:12.5px">
          <b style="white-space:nowrap">{name}</b>
          <div><div class="bar-track" style="height:8px;margin-bottom:3px"><div class="bar-fill" data-w="{w_his/m*100:.0f}" style="background:var(--indep)"></div></div>
          <div class="bar-track" style="height:8px"><div class="bar-fill" data-w="{w_house/m*100:.0f}" style="background:var(--ghost)"></div></div></div>
          <span style="text-align:right;font-variant-numeric:tabular-nums"><b class="indep">{w_his:.1f}%</b> <span style="color:var(--ghost)">vs {w_house:.2f}%</span></span>
        </div>"""
    only_rows = "".join(wrow(x["name"], x["his_w"], x["house_w"]) for x in lt["only_his"])
    not_rows = "".join(wrow(x["name"], x["his_w"], x["house_w"]) for x in lt["not_his"])

    top_chips = ""
    for t in lt["house_top"]:
        cls = "ok" if t["he_holds"] else "no"
        lab = f"他 {t['his_w']:.1f}%" if t["he_holds"] else "他不碰"
        top_chips += f'<span class="chip {cls}">{t["name"]} · 公司 {t["w"]:.1f}% · {lab}</span>'

    # 第二把尺子:全市场
    mk = hs.get("market")
    if mk and mk.get("latest"):
        mlt = mk["latest"]
        crowd_bars = ""
        _cmax = max(x["crowd_weight"] for x in mk["series"])
        for x in mk["series"]:
            warn_cls = "warn" if x["crowd_weight"] == _cmax else ""
            crowd_bars += f"""<div class="bar-row" style="grid-template-columns:44px 1fr 46px;padding:2px 0">
              <span class="k" style="font-size:10.5px">{x['q']}</span>
              <div class="bar-track" style="height:7px"><div class="bar-fill cyanf {warn_cls}" data-w="{x['crowd_weight']/_cmax*100:.0f}" style="background:var(--cyan)"></div></div>
              <span class="v" style="font-size:11px">{x['crowd_weight']:.0f}%</span></div>"""
        mkt_chips = ""
        for t in mlt["mkt_top"]:
            if t["he_holds"] and t["his_w"] > t["w"]:
                cls, lab = "no", f"他超配 {t['his_w']:.1f}%"
            elif t["he_holds"]:
                cls, lab = "", f"他 {t['his_w']:.1f}%"
            else:
                cls, lab = "ok", "他不碰"
            mkt_chips += f'<span class="chip {cls}">{t["name"]} · 全市场 {t["w"]:.1f}% · {lab}</span>'
        over = [t["name"] for t in mlt["mkt_top"] if t["he_holds"] and t["his_w"] > t["w"] * 1.5]
        market_card = f"""
  <div class="card" style="margin-top:var(--gap);border-color:var(--cyan)">
    <span class="lbl" style="color:var(--cyan)">第二把尺子 · 跟全市场全部公募比(半年度口径)</span>
    <div class="grid g2" style="margin-top:14px">
      <div>
        <div class="rangebar" style="margin:26px 8px 30px">
          <div class="pin" style="left:{mlt["divergence"]}%;background:var(--cyan)"></div>
          <span class="rl" style="left:2%">0 · 标准公募抱团</span>
          <span class="rl" style="left:{mlt["divergence"]}%;color:var(--cyan);font-weight:900;top:-26px">vs 全市场 {mlt["divergence"]}%</span>
          <span class="rl" style="left:97%;top:-26px">100</span>
        </div>
        <div class="chips">{mkt_chips}</div>
      </div>
      <div>
        <span class="lbl">公募抱团区(全市场TOP50)占他的组合</span>
        <div style="margin-top:8px">{crowd_bars}</div>
      </div>
    </div>
    <p style="text-align:center;font-size:16px;font-weight:900;margin-top:14px">
      他不躲抱团股 —— 而是在抱团区里<span class="cyan">只挑 {"、".join(over) if over else "个别"} 下重注</span>,拥挤仓位 {mlt["crowd_weight"]}%,近两年在抬升</p>
  </div>"""
    else:
        market_card = ""

    house_block = f"""
  <div class="card" style="border-color:var(--indep);background:var(--indep-tint)">
    <span class="lbl" style="color:var(--indep)">这块回答一个问题:他跟公司其他 {lt["n_funds"]} 个基金有多不一样?不一样时赚钱吗?</span>
    <p style="font-size:12.5px;color:var(--muted);margin-top:8px">
      分歧度 = 他的持仓与「公司平均组合」的差异,<b>0% = 完全照抄公司</b>,<b>100% = 一只都不重合</b>。
      对照组:兴证全球 {lt["n_funds"]} 只权益基金(已剔除他自己管的 3 只)。</p>
    <div class="rangebar" style="margin:30px 12px 34px">
      <div class="pin" style="left:{lt["divergence"]}%;background:var(--indep)"></div>
      <div class="pin" style="left:{lt["peer_avg_div"]}%;background:var(--ghost)"></div>
      <span class="rl" style="left:2%">0 · 抄公司作业</span>
      <span class="rl" style="left:{lt["divergence"]}%;color:var(--indep);font-weight:900;top:-26px">他 {lt["divergence"]}%</span>
      <span class="rl" style="left:{lt["peer_avg_div"]}%;font-weight:800">同事间均值 {lt["peer_avg_div"]}%</span>
      <span class="rl" style="left:97%;top:-26px">100 · 完全不重合</span>
    </div>
    <p style="text-align:center;font-size:19px;font-weight:900">
      {"<span class='indep'>比同事之间还独 —— 真孤狼</span>" if is_lone else "同事们本来就各管各的,他反而<span class='indep'>略偏向公司平均</span> —— 不是孤狼"}</p>
  </div>

  {market_card}

  <div class="grid g2" style="margin-top:var(--gap)">
    <div class="card">
      <span class="lbl" style="color:var(--indep)">他独有的重注 · 公司几乎没人买({lt["q"]})</span>
      <p style="font-size:11px;color:var(--ghost);margin-top:4px">紫条 = 他的仓位 · 灰条 = 公司平均</p>
      <div style="margin-top:10px">{only_rows}</div>
    </div>
    <div class="card">
      <span class="lbl">公司在买 · 他不碰({lt["q"]})</span>
      <p style="font-size:11px;color:var(--ghost);margin-top:4px">这是他「不做什么」的部分 —— 同样是独立性</p>
      <div style="margin-top:10px">{not_rows}</div>
      <div class="chips" style="margin-top:12px">{top_chips}</div>
    </div>
  </div>

  <div class="grid g2" style="margin-top:var(--gap)">
    <div class="card">
      <span class="lbl">分歧度走势 · {len(hs["series"])} 个季度</span>
      <p style="font-size:11px;color:var(--ghost);margin-top:4px">长期稳定在 76-90%:独立结构是常态,不是某一次赌博</p>
      <div style="margin-top:10px">{ts_bars}</div>
    </div>
    <div class="card">
      <span class="lbl">关键检验:不一样的时候,赚钱了吗?</span>
      <div class="duo" style="margin-top:12px">
        <div class="side" style="border-color:var(--indep)"><div class="k">分歧最高的季度 · 随后6个月超额</div><div class="n indep">{"%+.1f%%" % ct["high_div_fwd6"]}</div></div>
        <div class="vs2">VS</div>
        <div class="side" style="border-color:var(--ok)"><div class="k">分歧最低的季度</div><div class="n ok">{"%+.1f%%" % ct["low_div_fwd6"]}</div></div>
      </div>
      <div class="punchline" style="margin-top:16px;font-size:16px;padding:16px 20px;border-left-width:8px">
        {"他的超额恰恰来自最独的时候 —— 独立判断值钱。" if ct["high_div_fwd6"]>ct["low_div_fwd6"] else "分歧没带来超额 —— 他的 Alpha 来自<span class='em'>选股深度</span>,不是跟公司唱反调。买他 ≠ 买一个逆行者。"}
      </div>
      <p style="font-size:11px;color:var(--ghost);margin-top:10px">口径:{ct["n"]} 个季度按分歧度分半,对比随后 6 个月相对沪深300 超额</p>
    </div>
  </div>

  <!-- 抄作业指数 -->
  <div class="card" style="margin-top:var(--gap)">
    <span class="lbl">抄作业指数 · 他建仓 vs 你等季报</span>
    <div class="copy3">
      <div class="cc mgr"><div class="who">他 · 季末建仓时点</div><div class="num">+{ab["copy_mgr"]}%</div>
        <div class="sub">买点后 12 个月超额(n={ab["copy_n"]})</div></div>
      <div class="copy-arrow"><div class="dn">⇩</div><div class="pct">-{round((1-ab["copy_follow"]/ab["copy_mgr"])*100) if ab["copy_mgr"] else 0}%</div></div>
      <div class="cc ret"><div class="who">你 · 等披露后再跟</div><div class="num">+{ab["copy_follow"]}%</div>
        <div class="sub">季报+30天 / 中年报+60天</div></div>
    </div>
    <p style="text-align:center;font-size:16px;font-weight:900;margin-top:14px">低换手打法 · <span class="ok">季报仍有参考价值</span>(超额保留 {round(ab["copy_follow"]/ab["copy_mgr"]*100) if ab["copy_mgr"] else 0}%)</p>
  </div>"""
else:
    house_block = """
  <div class="card"><span class="lbl">独立战争</span>
    <p style="font-size:13px;color:var(--muted);margin-top:10px">同门持仓数据抓取中,本模块待生成。</p></div>"""

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
  <span class="tab" data-sec="s35"><span class="n">04</span>独立战争</span>
  <span class="tab" data-sec="s4"><span class="n">05</span>你会怎么亏</span>
  <span class="tab" data-sec="s5"><span class="n">06</span>机构视角</span>
  <span class="tab" data-sec="s6"><span class="n">07</span>怎么用</span>
</nav>

<!-- ============ 01 判决书 ============ -->
<section id="s1" class="sec">
  <div class="sec-head">
    <span class="sec-num">01</span><span class="sec-ti">判决书</span>
    <span class="sec-sub">真实数据 · 证据覆盖 10/12</span><span class="sec-line"></span>
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
            <span class="tag purple">会买 · 拿得住 · 不会卖</span>
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
      <span class="lbl">总评分 · 评的是行为,不是净值</span>
      <div class="score-giant" data-count="{ab["total_score"]}">0</div>
      <div style="margin-top:14px;text-align:left">
        <div class="bar-row" style="grid-template-columns:96px 1fr 40px;padding:3px 0">
          <span class="k" style="font-size:12px">择时能力 ⚠</span>
          <div class="bar-track" style="height:9px"><div class="bar-fill warn" data-w="{ab["timing_score"]}"></div></div>
          <span class="v warn" style="font-size:12.5px">{ab["timing_score"]}</span></div>
        <div class="bar-row" style="grid-template-columns:96px 1fr 40px;padding:3px 0">
          <span class="k" style="font-size:12px">控制能力</span>
          <div class="bar-track" style="height:9px"><div class="bar-fill ok" data-w="{ab["control_score"]}"></div></div>
          <span class="v ok" style="font-size:12.5px">{ab["control_score"]}</span></div>
        <div class="bar-row" style="grid-template-columns:96px 1fr 40px;padding:3px 0">
          <span class="k" style="font-size:12px">超额质量</span>
          <div class="bar-track" style="height:9px"><div class="bar-fill" data-w="{ab["quality_score"]}"></div></div>
          <span class="v" style="font-size:12.5px">{ab["quality_score"]}</span></div>
      </div>
      <div style="font-size:11px;color:var(--ghost);margin-top:8px">择时35% + 控制35% + 超额质量30%(信息比率) · 规则可复算</div>
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
        <span class="rp-tab" data-cat="now">当前持仓</span>
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
          <i><b class="mk s">卖</b>主动减/清仓</i>
          <i><b class="mk" style="background:#fbbf24;color:#0a0d10">被</b>被动减(触线/赎回)</i>
          <i><span style="display:inline-block;width:16px;border-top:2px solid #34d399"></span>成本线</i>
          <i><span style="display:inline-block;width:16px;border-top:2px dashed #f87171"></span>卖出线</i>
          <span class="kinfo" id="rpKinfo"></span>
        </div>
        <div class="rp-controls">
          <button class="rp-play" id="rpPlay">▶ 战役回放</button>
          <div class="rp-speed" id="rpSpeed">
            <span data-x="1" class="on">1x</span><span data-x="2">2x</span><span data-x="4">4x</span>
          </div>
          <div class="rp-zoom" id="rpZoomBox">
            <span data-z="out">−</span><span data-z="reset" style="font-size:11px">默认</span><span data-z="in">+</span>
          </div>
          <div class="rp-news" id="rpNews">
            <span class="nd" id="rpNd">—</span>
            <span class="ni ghost" id="rpNi">按「战役回放」重演当年:新闻在上,他的操作在下</span>
          </div>
        </div>
        <div class="rp-chart" id="rpChart"></div>
        <div class="rp-verdict" id="rpVerdict"></div>
        <div class="rp-grades" id="rpGrades"></div>
        <div class="rp-foot">买卖点按季报持股数变化推断(前十大消失≠卖出,仅全持仓期缺席记为清仓) · 减仓自动判定主动/被动(上季仓位≥9.3%触双十线;基金份额缩水>12%且减幅相当记为赎回被动) · 盈亏为持仓区间估算 · K线为真实行情(周K·前复权)</div>
      </div>
    </div>
  </div>

  <!-- 买卖点验尸:59买 + 49卖 全部拿12个月后的走势验 -->
  <div class="card" style="margin-top:var(--gap);border-color:var(--indep);background:var(--indep-tint)">
    <span class="lbl" style="color:var(--indep)">买卖点验尸 · {ti["n_buy"]+ti["n_sell"]} 个动作全部拿 12 个月后的走势验</span>
    <div style="margin-top:16px">
      <div class="bar-row" style="grid-template-columns:150px 1fr 56px">
        <span class="k">买点胜率(超额口径)</span>
        <div class="bar-track"><div class="bar-fill ok" data-w="{ti["buy_win_rate"]}"></div></div>
        <span class="v ok">{ti["buy_win_rate"]}%</span></div>
      <div class="bar-row" style="grid-template-columns:150px 1fr 56px">
        <span class="k">卖点躲跌率(仅主动)</span>
        <div class="bar-track"><div class="bar-fill warn" data-w="{ti["dodge_rate"]}"></div></div>
        <span class="v warn">{ti["dodge_rate"]}%</span></div>
    </div>
    <div class="chips" style="margin-top:12px">
      <span class="chip">被动减仓已剔除 <b>{ab["passive_cap"]+ab["passive_redeem"]} 次</b>(触10%线 {ab["passive_cap"]} · 遭赎回 {ab["passive_redeem"]})</span>
      <span class="chip purple">被动卖出不是决策 · 不计入择时评分</span>
    </div>
    <p style="text-align:center;font-size:19px;font-weight:900;margin-top:14px">
      会买(买后 12 个月平均超额 <span class="ok">+{ti["buy_avg_excess"]}%</span>) ·
      <span class="danger">不会卖</span>(卖掉的 12 个月平均又涨 <span class="danger">+{ti["sell_avg_fwd"]}%</span>)</p>
  </div>

  <div class="grid g2" style="margin-top:var(--gap)">
    <div class="card">
      <span class="lbl">最好与最差的买点</span>
      <div class="grid g2" style="margin-top:14px;gap:10px">
        <div class="stat" style="border-color:var(--ok)"><span class="lbl">🏆 {ti["best_buy"]["name"]} · {ti["best_buy"]["label"]} {ti["best_buy"]["q"]}</span>
          <span class="v ok" style="font-size:26px">+{ti["best_buy"]["fwd"]}%</span><span class="sub">此后 12 个月</span></div>
        <div class="stat" style="border-color:var(--danger)"><span class="lbl">💀 {ti["worst_buy"]["name"]} · {ti["worst_buy"]["label"]} {ti["worst_buy"]["q"]}</span>
          <span class="v danger" style="font-size:26px">{ti["worst_buy"]["fwd"]}%</span><span class="sub">此后 12 个月</span></div>
      </div>
      <div class="chips" style="margin-top:12px">
        <span class="chip ok">买入动作 {ti["n_buy"]} 次 · 平均跑赢大盘 {ti["buy_avg_excess"]} 个点</span>
      </div>
    </div>
    <div class="card">
      <span class="lbl">最好与最差的卖点</span>
      <div class="grid g2" style="margin-top:14px;gap:10px">
        <div class="stat" style="border-color:var(--ok)"><span class="lbl">🏆 {ti["best_sell"]["name"]} · {ti["best_sell"]["label"]} {ti["best_sell"]["q"]}</span>
          <span class="v ok" style="font-size:26px">躲过 {ti["best_sell"]["fwd"]}%</span><span class="sub">卖后 12 个月它跌了这么多</span></div>
        <div class="stat" style="border-color:var(--danger)"><span class="lbl">💀 {ti["worst_sell"]["name"]} · {ti["worst_sell"]["label"]} {ti["worst_sell"]["q"]}</span>
          <span class="v danger" style="font-size:26px">卖飞 +{ti["worst_sell"]["fwd"]}%</span><span class="sub">卖后 12 个月它又涨了这么多</span></div>
      </div>
      <div class="chips" style="margin-top:12px">
        <span class="chip no">卖出动作 {ti["n_sell"]} 次 · 只有 {ti["dodge_rate"]}% 躲过了下跌</span>
      </div>
    </div>
  </div>

  <!-- 控制能力证据 -->
  <div class="grid g2" style="margin-top:var(--gap)">
    <div class="card">
      <span class="lbl">控制能力 · 跌市防守(全真实)</span>
      <table style="margin-top:12px">
        <tr><th>熊市年</th><th style="text-align:right">他</th><th style="text-align:right">沪深300</th><th style="text-align:right">防守超额</th></tr>
        {bear_rows}
      </table>
      <div class="chips" style="margin-top:12px">
        <span class="chip">大盘最差 10 个月 · 平均超额 {ab["worst10_excess"]}%</span>
      </div>
    </div>
    <div class="card">
      <span class="lbl">浮亏时他干什么 + 净值层择时</span>
      <div class="exits" style="margin-top:8px">
        <div class="ex"><div class="n ok">{ab["loss_cut"]}</div><div class="k">止损砍仓</div></div>
        <div style="font-size:13px;color:var(--ghost);font-weight:900">VS</div>
        <div class="ex"><div class="n warn">{ab["loss_add"]}</div><div class="k">越跌越买</div></div>
      </div>
      <div class="chips" style="margin-top:14px;justify-content:center;display:flex">
        <span class="chip ok">偏纪律型 · 不死扛</span>
      </div>
      <div style="margin-top:16px;padding-top:14px;border-top:1px solid var(--line)">
        <div class="chips">
          <span class="chip purple">TM 择时回归 γ = <b>+{ab["tm_gamma"]}</b>(t={ab["tm_t"]},显著)</span>
          <span class="chip">仓位调向 {ab["pos_moves"]} 次 · 对 {ab["pos_same_dir"]} 次</span>
        </div>
        <p style="font-size:11px;color:var(--ghost);margin-top:10px">净值层面存在统计显著的正择时;个股层面的短板集中在"卖出"这一个动作上。</p>
      </div>
    </div>
  </div>
</section>

<!-- ============ 04 独立战争 ============ -->
<section id="s35" class="sec">
  <div class="sec-head">
    <span class="sec-num">04</span><span class="sec-ti">独立战争</span>
    <span class="sec-sub" style="color:var(--indep)">同门 {hs["latest"]["n_funds"] if hs else "—"} 只权益基金作对照组 · 已排除其自管产品</span><span class="sec-line"></span>
  </div>
  {house_block}
</section>

<!-- ============ 05 你会怎么亏 ============ -->
<section id="s4" class="sec">
  <div class="sec-head">
    <span class="sec-num">05</span><span class="sec-ti">你会怎么亏</span>
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
    <span class="sec-num">06</span><span class="sec-ti">机构视角</span>
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

  <!-- 多因子拆解 + 机构画像 + 到手率 -->
  <div class="grid g2" style="margin-top:var(--gap)">
    <div class="card">
      <span class="lbl">多因子运气拆解 · 月度收益回归 4 因子(n={ab["factor"]["n"]})</span>
      <div class="grid g2" style="margin-top:14px;gap:10px">
        <div class="stat hl"><span class="lbl">剥掉风格后年化 Alpha</span><span class="v ok" style="font-size:26px">+{ab["factor"]["alpha_ann"]}%</span><span class="sub">市场+大小盘+成长价值都剥掉</span></div>
        <div class="stat"><span class="lbl">R²</span><span class="v" style="font-size:26px">{ab["factor"]["r2"]}</span><span class="sub">风格解释八成,两成靠选股</span></div>
      </div>
      <div class="chips" style="margin-top:12px">
        <span class="chip">市场 β <b>{ab["factor"]["b_mkt"]}</b></span>
        <span class="chip">中盘暴露 <b>{ab["factor"]["b_size5"]:+.2f}</b></span>
        <span class="chip">小盘暴露 <b>{ab["factor"]["b_size10"]:+.2f}</b></span>
        <span class="chip purple">成长暴露 <b>{ab["factor"]["b_growth"]:+.2f}</b></span>
      </div>
      <p style="font-size:11px;color:var(--ghost);margin-top:10px">成长暴露显著为正,大盘为主 —— 风格箱「大盘成长」由回归证实,Alpha 不是风格红利。</p>
    </div>
    <div class="card">
      <span class="lbl">机构资金画像(真实持有人结构) + 基民到手</span>
      <div style="margin-top:12px">{inst_bars}</div>
      <div class="duo" style="margin-top:14px">
        <div class="side"><div class="k">基金年化(时间加权)</div><div class="n ok" style="font-size:30px">{ab["twr"]}%</div></div>
        <div class="vs2">VS</div>
        <div class="side"><div class="k">基民年化(资金加权·估算)</div><div class="n" style="font-size:30px">{ab["mwr"]}%</div></div>
      </div>
      <div class="chips" style="margin-top:10px">
        <span class="chip ok">到手率 {round(ab["mwr"]/ab["twr"]*100)}% · 封闭两年管住了追涨杀跌的手</span>
      </div>
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
    <span class="sec-num">07</span><span class="sec-ti">怎么用</span>
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
      <span class="lbl">证据缺口 · 仍未覆盖(已从 6 项缩到 3 项)</span>
      <div class="trig" style="margin-top:14px">
        <span>门派识别(需持仓聚类)</span>
        <span>Idea 先手/跟随(需同门逐季对齐)</span>
        <span>影子经理检测</span>
      </div>
      <p style="font-size:12px;color:var(--muted);margin-top:12px">独立战争/多因子/抄作业/机构画像/到手率/造神检测已补跑。按 SKILL 硬规则,剩余缺口继续在报告中明示。</p>
    </div>
  </div>

  <!-- 造神检测九项 -->
  <div class="card" style="margin-top:var(--gap)">
    <span class="lbl">造神检测 · 九项审查(半自动 · 基于公告与回撤对照)</span>
    <div class="checks" style="margin-top:14px">
      <div class="check"><span class="ck">✓</span>甩锅跑路 —— 4 次变更均为副手,他 8 年半从未离任</div>
      <div class="check"><span class="ck">✓</span>摘桃子 —— 基金自成立即由他管,无接盘他人业绩</div>
      <div class="check"><span class="ck">✓</span>藏尸体 —— 在管 3 只产品无清盘、无迷你化</div>
      <div class="check"><span class="ck">✓</span>人设造假 —— 履历与公开备案一致</div>
      <div class="check"><span class="ck">✓</span>偷换尺子 —— 业绩基准八年未变更</div>
      <div class="check" style="border-color:var(--warn)"><span class="ck" style="color:var(--warn)">⚠</span>高位圈钱 —— 2018-01 牛市顶部一日募 327 亿,次年 -16.8%(公司行为,他是代言人)</div>
      <div class="check" style="opacity:.6"><span class="ck" style="color:var(--ghost)">○</span>蹭业绩 —— 未详查</div>
      <div class="check" style="opacity:.6"><span class="ck" style="color:var(--ghost)">○</span>年底冲排名 —— 未检测</div>
      <div class="check" style="opacity:.6"><span class="ck" style="color:var(--ghost)">○</span>利益冲突 —— 披露有限,只能记「未发现」</div>
    </div>
    <div class="chips" style="margin-top:14px">
      <span class="chip ok">5 项通过</span>
      <span class="chip" style="border-color:var(--warn);color:var(--warn)">1 项留意</span>
      <span class="chip">3 项未查证(不写成「不存在」)</span>
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
