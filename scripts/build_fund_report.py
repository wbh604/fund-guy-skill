#!/usr/bin/env python3
"""用真实数据生成基金报告页(复用 v2 设计系统与买卖复盘模块)。

用法: python scripts/build_fund_report.py 163417 → assets/fund-163417.html
"""
import json, os, re, sys
from collections import Counter
from datetime import date as _date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fund_meta import require_code, mask_on, ensure_masked_photo
CODE = require_code()
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
msim = None
_mp = os.path.join(ROOT, ".cache", f"fund_{CODE}", "market_similar.json")
if os.path.exists(_mp):
    msim = json.load(open(_mp))

topf = None
_tp = os.path.join(ROOT, ".cache", f"fund_{CODE}", "top_funds.json")
if os.path.exists(_tp):
    topf = json.load(open(_tp))

years = A["years"]
regimes = A["managers"]          # 新→旧
scale = A["scale"]
meta = A["meta"]

def _parse_day(s):
    if not s or s in ("至今", "—"):
        return _date.today()
    y, mo, d = map(int, s[:10].split("-"))
    return _date(y, mo, d)

def _fmt_tenure(days):
    if days is None or days < 0:
        return "任期未获取"
    y = days / 365.25
    if y < 1:
        return f"{max(1, round(days / 30.4))} 个月"
    whole, frac = int(y), y - int(y)
    if frac >= 0.75:
        return f"{whole + 1} 年"
    if frac >= 0.25:
        return f"{whole} 年半"
    return f"{whole} 年"

def _lead_manager(rows):
    c = Counter()
    for r in rows:
        for n in str(r.get("managers") or "").split():
            c[n] += 1
    current = str((rows[0].get("managers") if rows else "") or "").split()
    if current:
        return max(current, key=lambda n: (c[n], -current.index(n)))
    if c:
        return c.most_common(1)[0][0]
    return (meta.get("基金经理") or "未获取").split()[0]

mgr_name = _lead_manager(regimes)
_tenure_days, _first_start, _n_with_lead = 0, None, 0
for r in regimes:
    if mgr_name not in str(r.get("managers") or "").split():
        continue
    _n_with_lead += 1
    _tenure_days += max(0, (_parse_day(r.get("end")) - _parse_day(r.get("start"))).days)
    if _first_start is None or (r.get("start") or "") < _first_start:
        _first_start = r.get("start")
tenure_txt = _fmt_tenure(_tenure_days)
fund_name = meta.get("基金名称") or meta.get("基金全称") or CODE
company = meta.get("基金公司") or ""
company_short = re.sub(r"(基金管理有限公司|基金有限公司|股份有限公司|有限公司)$", "", company) or "未获取"
found_on = (meta.get("成立时间") or "")[:10]
lead_from_inception = bool(
    _first_start and found_on and abs((_parse_day(_first_start) - _parse_day(found_on)).days) <= 14
)
lead_always = bool(regimes) and _n_with_lead == len(regimes)

try:
    n_years = max(0.5, (_parse_day(m["until"]) - _parse_day(m["since"])).days / 365.25)
except Exception:
    n_years = max(0.5, len(years) or 1)

# 公开发布的 163417 演示默认打码;FUND_MASK=0 可关,=1 可对任意基金开
MASK = mask_on(CODE)

# 经理照片:有就内嵌 base64(单文件可分享),没有回退现任经理首字。禁止写死「谢」
_raw_photo = os.path.join(ROOT, ".cache", f"fund_{CODE}", "manager_photo.png")
_masked_photo = os.path.join(ROOT, ".cache", f"fund_{CODE}", "manager_photo_masked.png")
if MASK:
    ensure_masked_photo(_raw_photo, _masked_photo)
    _pp_photo = _masked_photo if os.path.exists(_masked_photo) else _raw_photo
else:
    _pp_photo = _raw_photo
if os.path.exists(_pp_photo):
    import base64
    _b64 = base64.b64encode(open(_pp_photo, "rb").read()).decode()
    photo_html = (f'<img src="data:image/png;base64,{_b64}" alt="基金经理" '
                  'style="width:88px;height:110px;border-radius:10px;object-fit:cover;object-position:top;'
                  'border:1px solid var(--line);flex-shrink:0;background:#fff">')
else:
    _ini = (mgr_name[:1] if mgr_name and mgr_name != "未获取" else "?")
    photo_html = (f'<div style="width:88px;height:110px;border-radius:10px;background:linear-gradient(150deg,#252d39,#13181f);'
                  f'border:1px solid var(--line);display:flex;align-items:center;justify-content:center;'
                  f'font-size:34px;font-weight:900;color:var(--ghost);flex-shrink:0">{_ini}</div>')

# 行业来自 fetch_stock_industry.py(东财/港股 F10),禁止手写对照表
for _s in A["replay"]["stocks"]:
    if not _s.get("industry"):
        _s["industry"] = ""

# ---- 前端 JS 适配:真实代码无 sh./sz. 前缀;灾难片系数用真实回撤 ----
main_js = main_js.replace("s.code.split('.')[1]", "s.code.split('.').pop()")
main_js = main_js.replace("w * 0.674", f"w * {1 - m['max_dd']/100:.3f}")
main_js = main_js.replace("/*__RPDATA__*/{}", json.dumps(A["replay"], ensure_ascii=False, separators=(",", ":")))
events_path = os.path.join(ROOT, ".cache", f"fund_{CODE}", "events.json")
events = open(events_path).read() if os.path.exists(events_path) else "[]"
main_js = main_js.replace("/*__RPEVENTS__*/[]", events)

# ---- 平台评分对照(东财五维,仅展示不计分) ----
platform_card = ""
_pf = (ab.get("platform") or {}).get("mgr_power")
if _pf and _pf.get("data"):
    _pf_avr = float(_pf["avr"])
    _pf_chips = ""
    for _c, _v in zip(_pf["categories"], _pf["data"]):
        if _c == "择时能力":
            _pf_chips += f'<span class="chip warn">{_c} {_v:.0f} · <b>我们只给 {ab["timing_score"]}</b></span>'
        else:
            _pf_chips += f'<span class="chip">{_c} {_v:.0f}</span>'
    platform_card = f"""
  <div class="card" style="margin-top:var(--gap)">
    <span class="lbl">别人家的评分 · 天天基金怎么打</span>
    <div style="display:grid;grid-template-columns:1fr auto 1fr;gap:18px;align-items:center;margin-top:12px">
      <div style="text-align:center">
        <div style="font-size:40px;font-weight:900;color:var(--muted)">{_pf_avr:.0f}</div>
        <div style="font-size:12px;color:var(--ghost)">平台评分 · 看净值曲线和从业年头</div>
      </div>
      <div style="font-size:14px;font-weight:900;color:var(--ghost)">VS</div>
      <div style="text-align:center">
        <div style="font-size:40px;font-weight:900;color:var(--acc,var(--indep))">{ab["total_score"]}</div>
        <div style="font-size:12px;color:var(--ghost)">我们的行为评分 · 逐笔验他的买卖</div>
      </div>
    </div>
    <div class="chips" style="margin-top:12px;justify-content:center;display:flex;flex-wrap:wrap">{_pf_chips}</div>
    <p style="text-align:center;font-size:15px;font-weight:800;margin-top:12px">
      差的这 {_pf_avr - ab["total_score"]:.0f} 分,主要差在一件事:<span class="danger">平台没看他"什么时候卖"</span> —— 我们看了,{ti["n_sell"]} 次清仓只有 {ti["dodge_rate"]}% 卖对。</p>
  </div>"""

# ---- 计算显示量 ----
wins = sum(1 for y in years if y["win"])
dots = "".join(f'<i class="{"w" if y["win"] else "l"}"></i>' for y in years)
uw_years = m["underwater_days"] // 365
uw_months = m["underwater_days"] // 30
total = m["total_ret"]
cagr = ((1 + total/100) ** (1/n_years) - 1) * 100

career_tl = ""
for r in reversed(regimes):
    names = r.get("managers") or "未获取"
    solo = "独管" if " " not in names.strip() else "共管"
    career_tl += (f'<div class="tl-item"><b>{(r.get("start") or "")[:7]}</b>'
                  f'<span class="d">{names} · {solo} · 区间 {r.get("ret") or "未获取"}</span></div>')
if not career_tl:
    career_tl = '<div class="tl-item"><b>—</b><span class="d">任期数据未获取</span></div>'

rank_v, rank_sub = "未获取", "同类排名本次未取"
_ach_p = os.path.join(ROOT, ".cache", f"fund_{CODE}", "achieve.json")
if os.path.exists(_ach_p):
    for _row in json.load(open(_ach_p)):
        if _row.get("周期") == "成立以来" and _row.get("周期收益同类排名"):
            _rk = str(_row["周期收益同类排名"])
            _m = re.match(r"(\d+)/(\d+)", _rk.replace(" ", ""))
            if _m:
                _a, _b = int(_m.group(1)), int(_m.group(2))
                rank_v = f"前 {round(_a / _b * 100)}%"
                rank_sub = f"{_a} / {_b} · 成立以来"
            else:
                rank_v, rank_sub = _rk, "成立以来同类"
            break

_fac = ab.get("factor") or {}
_bg, _bs = _fac.get("b_growth"), _fac.get("b_size10")
if _bg is None:
    style_title, style_sub = "未鉴定", "打法不从模板抄<br>对照持仓与因子"
else:
    _size = "小盘" if (_bs or 0) > 0.25 else "大盘"
    _g = "成长" if (_bg or 0) > 0.2 else ("价值" if (_bg or 0) < -0.2 else "均衡")
    style_title = f"{_size}<br>{_g}"
    style_sub = f"因子暴露 · 成长β {_bg:+.2f}"

scale_now = meta.get("最新规模") or (f"{scale[-1]['yi']:.0f} 亿" if scale else "未获取")
scale_first = f"{scale[0]['yi']:.0f} 亿" if scale else "未获取"
scale_first_q = scale[0]["q"] if scale else (found_on[:7] if found_on else "成立")
fund_type = meta.get("基金类型") or "类型未获取"
style_plain = style_title.replace("<br>", "")

_fees = {}
_fp = os.path.join(ROOT, ".cache", f"fund_{CODE}", "fees.json")
if os.path.exists(_fp):
    _fees = json.load(open(_fp)) or {}
_fee_bits = []
if _fees.get("mgmt"):
    _fee_bits.append(f'<span class="chip">管理费 <b>{_fees["mgmt"]}</b>/年</span>')
if _fees.get("custodian"):
    _fee_bits.append(f'<span class="chip">托管费 <b>{_fees["custodian"]}</b>/年</span>')
if _fees.get("sales"):
    _fee_bits.append(f'<span class="chip">销售服务费 <b>{_fees["sales"]}</b>/年</span>')
fee_chips = "".join(_fee_bits) if _fee_bits else '<span class="chip">费率未获取</span>'
fee_note = ("来源:东方财富基金费率页,每日净值已扣除管理/托管/销售服务费"
            if _fee_bits else "本次未从费率页取到数字,以该基金最新招募说明书为准")

# ---- 其余判词必须从本品数据出,禁止抄合宜/谢治宇 ----
peak_buy = (m.get("uw_from") or m.get("dd_from") or m["since"])[:10]
dd_from = (m.get("dd_from") or m["since"])[:10]
dd_to = (m.get("dd_to") or m["until"])[:10]
try:
    dd_months = max(1, round((_parse_day(dd_to) - _parse_day(dd_from)).days / 30.4))
except Exception:
    dd_months = uw_months
uw_sub = f"超过 {uw_years} 年" if uw_years >= 1 else f"{uw_months} 个月"
disaster_title = f"十万元灾难片 · {peak_buy[:7]} 高点买入的真实回撤"
punchline = (f"{int(peak_buy[:4])} 年 {int(peak_buy[5:7])} 月买在高点的人,等了 "
             f'<span class="em">{m["underwater_days"]} 天</span>才回本 —— '
             f'整整 <span class="em">{uw_years} 年</span>。')

_uw_end = (m.get("uw_to") or "")[:10]
_still_uw = (not _uw_end) or _uw_end in ("至今",) or _uw_end >= m["until"][:10]
_days_rec = None
if not _still_uw:
    try:
        _days_rec = (_parse_day(m["until"]) - _parse_day(_uw_end)).days
    except Exception:
        _days_rec = None
if _still_uw:
    stamp_big, stamp_sm, stamp_col = "还在水下", "最长水下尚未结束", "var(--danger)"
elif _days_rec is not None and _days_rec < 365:
    stamp_big, stamp_sm, stamp_col = "再等等", "刚回本 · 别追高", "var(--warn)"
else:
    stamp_big, stamp_sm, stamp_col = "对照回撤", f"最大回撤 {m['max_dd']:.0f}%", "var(--muted)"

n_replay = len((A.get("replay") or {}).get("stocks") or [])
n_q_hold = len(scale) if scale else 0
replay_sub = f"{n_replay} 只重仓股 · {n_q_hold} 期真实披露推断" if n_replay else "重仓复盘"

buy_lab = "会买" if ti.get("buy_avg_excess", 0) > 5 else ("买点一般" if ti.get("buy_avg_excess", 0) > 0 else "买点偏弱")
sell_lab = "不会卖" if ti.get("sell_avg_fwd", 0) > 5 else ("卖点一般" if ti.get("sell_avg_fwd", 0) > 0 else "卖得掉跌")
_lc, _la = ab.get("loss_cut") or 0, ab.get("loss_add") or 0
if _lc + _la == 0:
    disc_lab = "被套后动作未鉴定"
elif _lc >= _la:
    disc_lab = "偏纪律型 · 不死扛"
else:
    disc_lab = "偏加仓型 · 越跌越买更多"
_pm, _ps = ab.get("pos_moves") or 0, ab.get("pos_same_dir") or 0
pos_lab = "对的" if _pm and _ps / _pm >= 0.6 else "未证明"
if (ti.get("dodge_rate") or 100) < 40 and (ti.get("buy_win_rate") or 0) > 50:
    short_txt = '整体仓位该多该少另说;真正的短板是单只股票"什么时候卖"。'
else:
    short_txt = f"买点胜率 {ti.get('buy_win_rate')}% · 清仓躲跌率 {ti.get('dodge_rate')}%。"

_t10a, _t10l = pro.get("top10_avg") or 0, pro.get("top10_latest") or 0
if _t10l > _t10a + 2:
    conc_lab = "集中度在抬升"
elif _t10l < _t10a - 2:
    conc_lab = "集中度在下降"
else:
    conc_lab = "集中度接近均值"
r2_mkt = f"收益大约 {round((pro.get('r2') or 0)*10)} 成能用大盘解释"
r2_fac = f"风格解释约 {round((_fac.get('r2') or 0)*10)} 成,其余靠选股"
_inst = ab.get("inst_series") or []
if len(_inst) >= 2:
    inst_sub = f"从 {_inst[0]['inst']:.1f}% 到 {_inst[-1]['inst']:.1f}%"
else:
    inst_sub = "持有人结构"
_lock = (ab.get("holder_flow") or {}).get("lockup_until")
_mwr_r = round(ab["mwr"] / ab["twr"] * 100) if ab.get("twr") else None
if _mwr_r is None:
    mwr_chip = "到手率未获取"
elif _lock:
    mwr_chip = f"到手率 {_mwr_r}% · 锁定期至 {_lock[:7]}"
else:
    mwr_chip = f"到手率 {_mwr_r}% · 资金加权 vs 时间加权"
if scale and scale[0]["yi"] >= max(s["yi"] for s in scale) * 0.95:
    scale_lbl = "发行即巅峰"
else:
    scale_lbl = "规模变化"
you_fit = f"能扛住 -{m['max_dd']:.0f}% 再来"
you_fit_sub = f"最长水下 {uw_sub} · 拿不住别碰"
tenure_head = "任期切割 · 他是唯一的常量" if lead_always else "任期切割 · 谁在开车"
tenure_chip2 = "业绩归属基本可记在他头上" if lead_always else "共管期业绩不能全记在现任头上"
hold_yr = max(uw_years, 3)
verdict_hold = f"≥{hold_yr} 年"
verdict_no1 = "✕ 刚回本就追" if (not _still_uw and _days_rec is not None and _days_rec < 365) else "✕ 不看回撤就买"
verdict_no2 = f"✕ 拿不住 {hold_yr} 年"
_up_x = (pro.get("up_cap") or 100) - 100
_dn_x = 100 - (pro.get("dn_cap") or 100)
cap_chip = (f"涨时{'多吃' if _up_x>=0 else '少吃'} {abs(_up_x):.0f} 个点 · "
            f"跌时{'少挨' if _dn_x>=0 else '多挨'} {abs(_dn_x):.0f} 个点")
factor_note = (f"因子口径他偏「{style_plain}」—— 把风格白送的收益扣掉之后,"
               f"年化 Alpha 还剩 {_fac.get('alpha_ann', '未获取')}%。")
if _fac and _fac.get("n") is not None:
    factor_html = f"""
    <div class="card">
      <span class="lbl">运气拆解 · 把 {_fac["n"]} 个月的收益拆给市场和风格,剩下的才是他的本事</span>
      <div class="grid g2" style="margin-top:14px;gap:10px">
        <div class="stat hl"><span class="lbl">剥掉风格后年化 Alpha</span><span class="v ok" style="font-size:26px">+{_fac["alpha_ann"]}%</span><span class="sub">市场+大小盘+成长价值都剥掉</span></div>
        <div class="stat"><span class="lbl">R²</span><span class="v" style="font-size:26px">{_fac["r2"]}</span><span class="sub">{r2_fac}</span></div>
      </div>
      <div class="chips" style="margin-top:12px">
        <span class="chip">市场 β <b>{_fac["b_mkt"]}</b></span>
        <span class="chip">中盘暴露 <b>{_fac.get("b_size5", 0):+.2f}</b></span>
        <span class="chip">小盘暴露 <b>{_fac.get("b_size10", 0):+.2f}</b></span>
        <span class="chip purple">成长暴露 <b>{_fac.get("b_growth", 0):+.2f}</b></span>
      </div>
      <p style="font-size:11px;color:var(--ghost);margin-top:10px">{factor_note}</p>
    </div>"""
else:
    factor_html = """
    <div class="card">
      <span class="lbl">运气拆解</span>
      <p style="font-size:13px;color:var(--muted);margin-top:12px">风格指数未获取,因子暴露记未鉴定,不编 Beta。</p>
    </div>"""
def _style_cell(label):
    on = style_plain == label
    if on:
        return (f'<div style="background:var(--accent-tint);padding:14px;text-align:center;font-size:12px;'
                f'font-weight:900;color:var(--accent);outline:2px solid var(--accent);outline-offset:-2px">{label} ●</div>')
    return f'<div style="background:var(--surface);padding:14px;text-align:center;font-size:11px;color:var(--ghost)">{label}</div>'
style_box = "".join(_style_cell(x) for x in (
    "大盘价值", "大盘均衡", "大盘成长", "中盘价值", "中盘均衡", "中盘成长",
    "小盘价值", "小盘均衡", "小盘成长"))

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

inst_latest = (ab.get("inst_series") or [{"inst":0}])[-1]
try:
    import json as _j
    _h2 = _j.load(open(os.path.join(ROOT, ".cache", f"fund_{CODE}", "holders2.json")))
    inst_latest["internal"] = _h2[0]["internal"]
except Exception:
    pass
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
sc_max = max((s["yi"] for s in sc), default=1) or 1
scale_bars = "".join(
    f'''<div class="bar-row" style="grid-template-columns:64px 1fr 70px">
      <span class="k">{s["q"]}</span>
      <div class="bar-track"><div class="bar-fill {'warn' if s['yi']==sc_max else ''}" data-w="{s['yi']/sc_max*100:.0f}"></div></div>
      <span class="v">{s["yi"]:.0f} 亿</span></div>''' for s in sc)

# 现在的牌面:前十大按东财/港股所属行业归堆(没有行业就用一级板块)。不依赖同门数据。
_cur = [s for s in A["replay"]["stocks"] if s.get("cur_w")]
_themes = {}
for s in _cur:
    t = (s.get("industry") or s.get("board") or "").strip() or "未分类"
    _themes.setdefault(t, {"w": 0.0, "names": []})
    _themes[t]["w"] += s["cur_w"]
    _themes[t]["names"].append(s["name"])
_themes = sorted(_themes.items(), key=lambda kv: -kv[1]["w"])
_top10_w = sum(s["cur_w"] for s in _cur)
_tmax = _themes[0][1]["w"] if _themes else 1
theme_rows = ""
for tname, tv in _themes:
    chips = "".join(f'<span class="rgrade" style="padding:2px 8px;font-size:10.5px">{n}</span>' for n in tv["names"])
    theme_rows += f"""<div style="display:grid;grid-template-columns:minmax(120px,.9fr) 1.1fr 1fr 58px;gap:12px;align-items:center;padding:9px 0;border-bottom:1px dashed var(--line);font-size:13px">
          <b>{tname}</b>
          <div style="display:flex;gap:4px;flex-wrap:wrap">{chips}</div>
          <div class="bar-track" style="height:12px"><div class="bar-fill" data-w="{tv['w']/_tmax*100:.0f}" style="background:var(--indep)"></div></div>
          <span class="v indep" style="text-align:right">{tv['w']:.1f}%</span>
        </div>"""
if not _themes:
    _theme_line = "最新前十大的行业未获取,不编"
elif all(k == "未分类" for k, _ in _themes):
    _theme_line = "重仓股行业未取到,前十大无法归堆"
else:
    t1, v1 = _themes[0]
    share1 = (v1["w"] / _top10_w * 100) if _top10_w else 0
    if len(_themes) == 1:
        _theme_line = (f'押注很集中:前十大几乎都在<span class="indep">{t1} {v1["w"]:.0f}%</span>')
    elif share1 >= 50:
        t2, v2 = _themes[1]
        _theme_line = (f'前十大里<span class="indep">{t1} 占 {v1["w"]:.0f}%</span>'
                       f'(占前十大 {share1:.0f}%),第二块是 {t2} {v2["w"]:.0f}%')
    else:
        t2, v2 = _themes[1]
        _theme_line = (f'最大两块是<span class="indep">{t1} {v1["w"]:.0f}%</span>'
                       f'和 {t2} {v2["w"]:.0f}%,其余拆散')
theme_card = f"""
  <div class="card" id="card-theme" style="margin-top:var(--gap)">
    <span class="lbl">他现在的牌面 · 前十大重仓按行业归堆</span>
    <div style="margin-top:12px">{theme_rows or '<p style="color:var(--ghost)">最新前十大未获取</p>'}</div>
    <p style="text-align:center;font-size:17px;font-weight:900;margin-top:14px">{_theme_line}</p>
    <p style="font-size:11px;color:var(--ghost);margin-top:6px">前十大合计 {_top10_w:.1f}%,其余仓位季报不披露 · 行业来自东财/港股 F10 公开分类,不是手工对照</p>
  </div>"""

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

    # 抄作业判词:保留率分档解读
    _retain = round(ab["copy_follow"] / ab["copy_mgr"] * 100) if ab["copy_mgr"] else 0
    _lead = round(ab["copy_mgr"] - ab["copy_follow"], 1)
    if _retain >= 70:
        _cv_head = f"""作业可抄 —— 他的本事在<span class="em">选什么</span>,不在什么时候买"""
        _cv_body = f"""等季报再抄,超额还能拿 <b>{_retain}%</b> —— 买点先手一年只值 <b>{_lead} 个点</b>。
          这与他的择时分 <b>{ab["timing_score"]}(弱项)</b>互相印证:选股是真本事,择时做T不是。
          理论上你照季报自己抄,还省下每年管理费。"""
    elif _retain >= 40:
        _cv_head = "作业半可抄 —— 先手有价值,但不致命"
        _cv_body = f"""等季报再抄保留 <b>{_retain}%</b> 超额,先手价值 {_lead} 个点/年。抄不抄看你嫌不嫌麻烦。"""
    else:
        _cv_head = "他有先手,抄不到 —— 择时是他 Alpha 的一部分"
        _cv_body = f"""披露滞后吃掉 <b>{100-_retain}%</b> 超额,想要他的收益只能买基金。"""
    copy_verdict = f"""
    <div class="punchline" style="margin-top:16px;font-size:17px;padding:16px 22px;border-left-width:8px">{_cv_head}</div>
    <p style="font-size:13.5px;color:var(--muted);margin-top:12px;line-height:1.7">{_cv_body}</p>
    <div class="chips" style="margin-top:10px">
      <span class="chip ok">超额保留率 {_retain}%</span>
      <span class="chip">买点先手 {_lead} 个点/年</span>
      <span class="chip purple">与择时分 {ab["timing_score"]} 互证</span>
    </div>
    <p style="font-size:11px;color:var(--ghost);margin-top:10px">诚实提醒:抄作业抄得到买单,抄不到卖点和调仓 —— 他的卖出(躲跌率 {ti["dodge_rate"]}%)恰好也是弱项,这条损失不大;但新进小票你看到季报时他已建完仓。</p>"""

    # 今年最猛 TOP10 vs 他:持仓同步度
    top_card = ""
    if topf and topf.get("funds"):
        _tf = topf["funds"]
        _avg = sum(x["n_shared"] for x in _tf) / len(_tf)
        top_rows = ""
        for i, x in enumerate(_tf):
            chips = "".join(f'<span class="rgrade" style="padding:2px 8px;font-size:10.5px">{n}</span>' for n in x["shared"]) or '<span style="color:var(--ghost);font-size:11px">零重合</span>'
            top_rows += f"""<div style="display:grid;grid-template-columns:24px minmax(170px,1.3fr) 86px 1fr .9fr 52px;gap:10px;align-items:center;padding:8px 0;border-bottom:1px dashed var(--line);font-size:12.5px">
              <span style="color:var(--ghost);font-weight:900">{i+1:02d}</span>
              <div><b>{x['name']}</b><br><span style="color:var(--ghost);font-size:11px">{x['code']}</span></div>
              <span class="v warn" style="font-size:13px">+{x['ytd']:.0f}%</span>
              <div style="display:flex;gap:4px;flex-wrap:wrap">{chips}</div>
              <div class="bar-track" style="height:10px"><div class="bar-fill" data-w="{x['n_shared']*10}" style="background:var(--warn)"></div></div>
              <span class="v warn" style="text-align:right">{x['n_shared']}/10</span>
            </div>"""
        if _avg >= 4:
            top_verdict = (f"今年最猛的 10 只基金,平均跟他撞 {_avg:.1f}/10 只重仓 —— "
                           "<span class='warn'>他就压在今年的主升浪上</span>,涨得快,退潮时也一起挨打")
        else:
            top_verdict = (f"今年最猛的 10 只基金,平均只跟他撞 {_avg:.1f}/10 只重仓 —— "
                           "<span class='warn'>他的收益不是追今年热点榜追来的</span>,想蹭排行榜热度的人别买他")
        top_card = f"""
  <div class="card" style="margin-top:var(--gap);border-color:var(--warn)">
    <span class="lbl" style="color:var(--warn)">今年全市场最猛的 10 只 · 跟他的持仓同步度</span>
    <p style="font-size:11px;color:var(--ghost);margin-top:4px">开放式基金今年收益榜(截至 {topf["asof"]}) · 已剔除指数/联接/QDII与重复份额 · 同步度 = 对方最新前十大与他前十大同名只数</p>
    <div style="margin-top:10px">{top_rows}</div>
    <p style="text-align:center;font-size:16px;font-weight:900;margin-top:14px">{top_verdict}</p>
  </div>"""

    # 持仓最像的同门基金
    sim_rows = ""
    _sim = hs.get("similar_funds") or []
    _smax = max((x["overlap"] for x in _sim), default=1)
    for x in _sim:
        chips = "".join(f'<span class="rgrade" style="padding:2px 8px;font-size:10.5px">{n}</span>' for n in x["shared"])
        sim_rows += f"""<div style="display:grid;grid-template-columns:minmax(150px,1.3fr) 90px 1fr 58px;gap:12px;align-items:center;padding:9px 0;border-bottom:1px dashed var(--line);font-size:13px">
          <div><b>{x['name']}</b><span style="color:var(--ghost);font-size:11px"> {x['code']}</span><br>
            <span style="color:var(--muted);font-size:11px">经理 {x['managers']}</span></div>
          <div style="display:flex;gap:4px;flex-wrap:wrap">{chips}</div>
          <div class="bar-track" style="height:10px"><div class="bar-fill" data-w="{x['overlap']/_smax*100:.0f}" style="background:var(--indep)"></div></div>
          <span class="v indep" style="text-align:right">{x['overlap']:.0f}%</span>
        </div>"""

    # 全市场撞车榜(与同门榜同款:进度条 + 重复率)
    mkt_sim_rows = ""
    if msim and msim.get("funds"):
        _nmax = msim["n_stocks_checked"]
        for x in msim["funds"][:8]:
            rate = x["n"] / _nmax * 100
            chips = "".join(f'<span class="rgrade" style="padding:2px 8px;font-size:10.5px">{n}</span>' for n in x["stocks"][:4])
            mkt_sim_rows += f"""<div style="display:grid;grid-template-columns:minmax(130px,1.2fr) 90px 1fr 58px;gap:10px;align-items:center;padding:8px 0;border-bottom:1px dashed var(--line);font-size:12.5px">
              <div><b>{x['fund']}</b><br><span style="color:var(--ghost);font-size:11px">撞了 {x['n']}/{_nmax} 只重仓</span></div>
              <div style="display:flex;gap:4px;flex-wrap:wrap">{chips}</div>
              <div class="bar-track" style="height:10px"><div class="bar-fill" data-w="{rate:.0f}" style="background:var(--cyan)"></div></div>
              <span class="v cyan" style="text-align:right">{rate:.0f}%</span>
            </div>"""
    else:
        mkt_sim_rows = '<p style="font-size:12px;color:var(--muted)">全市场反查未运行</p>'

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
      分歧度 = 他的持仓与「公司平均组合」有多不一样,<b>0 分 = 完全照抄公司</b>,<b>100 分 = 一只都不重合</b>。
      对照组:{company_short} {lt.get("n_active", lt["n_funds"])} 只真·权益基金(剔除了他自管的产品与债性太重的),
      每只都先折算成同样的满仓口径再比,不然比不公平。</p>
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
        <div class="side" style="border-color:var(--indep)"><div class="k">最不像公司的那些季度<br>随后 6 个月跑赢大盘</div><div class="n indep">{"%+.1f%%" % ct["high_div_fwd6"]}</div></div>
        <div class="vs2">VS</div>
        <div class="side" style="border-color:var(--ok)"><div class="k">最像公司的那些季度<br>随后 6 个月跑赢大盘</div><div class="n ok">{"%+.1f%%" % ct["low_div_fwd6"]}</div></div>
      </div>
      <div class="punchline" style="margin-top:16px;font-size:16px;padding:16px 20px;border-left-width:8px">
        {"他的超额恰恰来自最独的时候 —— 独立判断值钱。" if ct["high_div_fwd6"]>ct["low_div_fwd6"] else "分歧没带来超额 —— 他的 Alpha 来自<span class='em'>选股深度</span>,不是跟公司唱反调。买他 ≠ 买一个逆行者。"}
      </div>
      <p style="font-size:11px;color:var(--ghost);margin-top:10px">算法:{ct["n"]} 个季度按"像不像公司"分成两半,各自看随后 6 个月跑赢沪深300 多少</p>
    </div>
  </div>

  <!-- 抄作业指数 -->
  <div class="card" style="margin-top:var(--gap)">
    <span class="lbl">抄作业指数 · 他建仓 vs 你等季报</span>
    <div class="copy3">
      <div class="cc mgr"><div class="who">他 · 季末建仓时点</div><div class="num">+{ab["copy_mgr"]}%</div>
        <div class="sub">{ab["copy_n"]} 次买入取平均 · 买后 12 个月跑赢大盘的幅度</div></div>
      <div class="copy-arrow"><div class="dn">⇩</div><div class="pct">-{round((1-ab["copy_follow"]/ab["copy_mgr"])*100) if ab["copy_mgr"] else 0}%</div></div>
      <div class="cc ret"><div class="who">你 · 等披露后再跟</div><div class="num">+{ab["copy_follow"]}%</div>
        <div class="sub">季报+30天 / 中年报+60天</div></div>
    </div>
    {copy_verdict}
  </div>

  {theme_card}

  <!-- 持仓最像的基金:同门 + 全市场 -->
  <div class="grid g2" style="margin-top:var(--gap)">
    <div class="card">
      <span class="lbl">同门里跟他最像(持仓重合度)</span>
      <div style="margin-top:12px">{sim_rows}</div>
    </div>
    <div class="card">
      <span class="lbl">全市场撞车榜 · 也同时持有他多只重仓的主动基金</span>
      <p style="font-size:11px;color:var(--ghost);margin-top:4px">反查他 {msim["n_stocks_checked"] if msim else 7} 只 A 股重仓的基金持有人 · 已剔除指数/ETF与同门 {company_short} · {msim["period"] if msim else ""}</p>
      <div style="margin-top:10px">{mkt_sim_rows}</div>
    </div>
  </div>

  {top_card}
  <div class="alert info" style="margin-top:14px;display:flex;gap:10px;padding:14px 16px;border-radius:8px;background:var(--indep-tint);border:1px solid var(--indep);font-size:13px">
    <span>💬</span><span><b>想深挖哪只?直接说「分析 睿远成长价值」或任何一只</b>,同一套流程(买卖复盘/择时控制/独立战争)再跑一遍。
    重合度高 ≠ 一样好 —— 抄作业的人未必有他的买点。</span>
  </div>"""
else:
    house_block = f"""
  <div class="card"><span class="lbl">独立战争</span>
    <p style="font-size:13px;color:var(--muted);margin-top:10px">同门持仓数据抓取中,本模块待生成。</p></div>
  {theme_card}"""

# ---- 闸门时间轴(对照卡,不进总分) ----
css += """
.gate-svg{width:100%;height:96px;display:block}
.gate-legend{display:flex;gap:14px;flex-wrap:wrap;font-size:11px;color:var(--ghost);margin:8px 0 2px}
.gate-legend i{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:5px;vertical-align:middle}
.gate-row{display:grid;grid-template-columns:86px 86px 1fr minmax(168px,1.05fr);gap:12px;align-items:start;padding:11px 0;border-bottom:1px dashed var(--line);font-size:13px}
.gate-row .when{font-weight:800;font-variant-numeric:tabular-nums}
.gate-row .act{font-size:12px;font-weight:800}
.gate-row .why{color:var(--muted);font-size:12.5px;line-height:1.55}
.gate-row .fwd{font-size:12px;font-variant-numeric:tabular-nums;text-align:right;color:var(--muted);line-height:1.55}
@media(max-width:720px){.gate-row{grid-template-columns:1fr;gap:4px}.gate-row .fwd{text-align:left}}
"""

def _pp(x, signed=True):
    if x is None:
        return "未获取"
    return f"{x:+.1f}%" if signed else f"{x:.0f}%"

def _gate_spark(csi_rows, events, buys, w=760, h=92, start=None):
    start = start or (m.get("since") or found_on or "1998-01-01")[:10]
    rows = [r for r in csi_rows if r["date"][:10] >= start]
    if len(rows) < 8:
        return ""
    if len(rows) > 140:
        step = max(1, len(rows) // 140)
        rows = rows[::step]
    xs = [r["close"] for r in rows]
    lo, hi = min(xs), max(xs)
    span = (hi - lo) or 1
    n = len(rows) - 1
    def xy(i, v):
        return (8 + i / n * (w - 16), h - 16 - (v - lo) / span * (h - 30))
    def x_at(d):
        prev = 0
        for i, r in enumerate(rows):
            if r["date"][:10] > d:
                return xy(prev, xs[prev])[0]
            prev = i
        return xy(n, xs[-1])[0]
    def y_at(d):
        prev = xs[0]
        for r in csi_rows:
            if r["date"][:10] > d:
                break
            prev = r["close"]
        return h - 16 - (prev - lo) / span * (h - 30)
    pts = " ".join(f"{xy(i, v)[0]:.1f},{xy(i, v)[1]:.1f}" for i, v in enumerate(xs))
    kind_fill = {
        "close_launch": "var(--warn)", "close_limit": "var(--danger)",
        "open": "var(--danger)", "open_unlock": "var(--ghost)",
    }
    marks = []
    for e in events:
        cx, cy = x_at(e["date"]), y_at(e["date"])
        fill = kind_fill.get(e["kind"], "var(--accent)")
        r = 5 if e.get("in_sample") else 3.5
        marks.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{fill}" stroke="var(--bg)" stroke-width="1.5"/>')
    for b in buys:
        cx, cy = x_at(b["date"]), y_at(b["date"])
        marks.append(f'<rect x="{cx-3.5:.1f}" y="{cy-3.5:.1f}" width="7" height="7" fill="var(--cyan)" stroke="var(--bg)" stroke-width="1"/>')
    return f'''<svg class="gate-svg" viewBox="0 0 {w} {h}" role="img" aria-label="沪深300与闸门时点">
      <polyline fill="none" stroke="var(--muted)" stroke-width="1.6" points="{pts}" opacity=".85"/>
      {''.join(marks)}
      <text x="8" y="{h-3}" fill="var(--ghost)" font-size="10">{rows[0]["date"][:4]}</text>
      <text x="{w-40}" y="{h-3}" fill="var(--ghost)" font-size="10">{rows[-1]["date"][:4]}</text>
    </svg>'''

_gates = ab.get("gates")
_style_nm = (_gates or {}).get("style_name") or "成长"
_csi_p = os.path.join(ROOT, ".cache", f"fund_{CODE}", "csi300.json")
_csi_rows = json.load(open(_csi_p)) if os.path.exists(_csi_p) else []

god_hype = "高位圈钱 —— 闸门时间轴未跑,未鉴定"
gate_card = """
  <div class="card" style="margin-top:var(--gap)">
    <span class="lbl">闸门时间轴</span>
    <p style="font-size:13px;color:var(--muted);margin-top:10px">申购闸门公告未获取,本对照卡暂缺。</p>
  </div>"""

if _gates:
    _ev = _gates.get("events") or []
    _sb = _gates.get("self_buy_company") or []
    _ct = _gates.get("counts") or {}
    _spark = _gate_spark(_csi_rows, _ev, _sb)
    KIND_LAB = {
        "close_launch": ("募满关闸", "var(--warn)"),
        "close_limit": ("限额关门", "var(--danger)"),
        "open": ("打开申购", "var(--danger)"),
        "open_unlock": ("合同开放", "var(--ghost)"),
    }
    ZONE_LAB = {"high": "高位", "low": "低位", "mid": "中位", "mixed": "高低分裂", "unknown": "分位未获取"}
    rows_html = ""
    for e in _ev:
        lab, col = KIND_LAB.get(e["kind"], (e["kind"], "var(--muted)"))
        if e["kind"] == "close_limit" and e.get("limit_yuan"):
            lab = f"限额≤{e['limit_yuan']//10000}万"
        z = ZONE_LAB.get(e["zone"], e["zone"])
        tag = "进样本" if e.get("in_sample") else ("假信号" if e.get("fake") else "不进样本")
        tag_col = "var(--ok)" if e.get("in_sample") else "var(--ghost)"
        lim = ""
        if e.get("limit_yuan") and e["kind"] == "close_limit":
            lim = f"单户{e['limit_yuan']//10000}万元以上拒收 · "
        elif e.get("limit_yuan") and e["kind"] == "open":
            lim = f"恢复接受{e['limit_yuan']//10000}万元以上申购 · "
        pct = f"沪深300近3年{e['csi_pct']}%分位 · {_style_nm}指数{e['growth_pct']}%分位"
        fwd = (f"这天之后 12 个月<br>"
               f"沪深300 <b>{_pp(e.get('fwd_csi'))}</b><br>"
               f"本基金 <b>{_pp(e.get('fwd_fund'))}</b><br>"
               f"{_style_nm}指数 {_pp(e.get('fwd_growth'))}")
        if e.get("fwd_pending"):
            fwd = "12 个月窗口尚未到期"
        rows_html += f"""<div class="gate-row">
          <div class="when">{e['date']}</div>
          <div class="act" style="color:{col}">{lab}<br>
            <span class="tag" style="border-color:{tag_col};color:{tag_col};font-size:10px">{tag} · {z}</span></div>
          <div class="why">{lim}{pct}<br>{e.get('note') or ''}</div>
          <div class="fwd">{fwd}</div>
        </div>"""

    sb_chips = ""
    for b in _sb:
        z = ZONE_LAB.get(b.get("zone"), "")
        sb_chips += (f'<span class="chip">{b["date"][:7]} 公司自购 · {z}'
                     f' · 随后12个月沪深300 {_pp(b.get("fwd_csi"))}</span>')
    if not _sb:
        sb_chips = '<span class="chip">公司自购 未获取</span>'

    _int = _gates.get("internal_holders") or []
    int_txt = "员工持有比例 未获取"
    if len(_int) >= 2:
        int_txt = (f"员工持有 {_int[0]['internal']}({_int[0]['date'][:7]}) → "
                   f"{_int[-1]['internal']}({_int[-1]['date'][:7]}) · 员工≠经理自购")
    elif _int:
        int_txt = f"员工持有 {_int[0]['internal']} · 员工≠经理自购"

    hc, ho = _ct.get("high_close", 0), _ct.get("high_open", 0)
    lc, lo_ = _ct.get("low_close", 0), _ct.get("low_open", 0)
    if hc and ho:
        _ghead = f"高位关过 {hc} 回,也高位开过 {ho} 回 —— 「有良心」这组证据撑不住"
    elif hc and not ho:
        _ghead = f"高位关过 {hc} 回,没在高位开过门"
    elif ho and not hc:
        _ghead = f"高位开过 {ho} 回,没在高位关过门"
    else:
        _ghead = "裁量闸门没有落在高低分位上,这一项暂不下结论"

    _bits = []
    for e in _ev:
        if e["kind"] == "close_launch":
            _bits.append(f"{e['date'][:7]} 顶部募满即关,随后 12 个月沪深300 {_pp(e.get('fwd_csi'))}、本基金 {_pp(e.get('fwd_fund'))}")
        elif e.get("in_sample") and e["kind"] == "close_limit" and e["zone"] == "high":
            _bits.append(f"{e['date'][:7]} 在沪深300 {e['csi_pct']}% 分位限额关门,随后 12 个月沪深300 {_pp(e.get('fwd_csi'))}(同门当天没限购)")
        elif e.get("in_sample") and e["quadrant"] == "high_open":
            _bits.append(f"{e['date'][:7]} {_style_nm}指数 {e['growth_pct']}% 分位打开申购,随后 12 个月本基金 {_pp(e.get('fwd_fund'))}")
    # 2020-11 连发只取第一条进判词,避免 2 万/1 万说两遍
    _seen_m = set()
    _uniq = []
    for b in _bits:
        k = b[:7]
        if k in _seen_m:
            continue
        _seen_m.add(k)
        _uniq.append(b)
    _gbody = "。".join(_uniq) + "。时间线是已确认事实;「拦人」或「圈钱」的动机最多是较强推断。对照卡,不计入行为总分。"

    n_peer = len(_gates.get("peers_checked") or [])
    gate_card = f"""
  <div class="card" style="margin-top:var(--gap)">
    <span class="lbl">闸门时间轴 · 限购/开门 vs 市场高低点(对照卡,不进总分)</span>
    <p style="font-size:11px;color:var(--ghost);margin-top:4px">
      闸门 = 暂停大额 / 限额从大砍到小 / 取消限购 / 提前结束募集 · 假闸门已剔除假期双边暂停 {_ct.get('n_operational', 0)} 条
      · 对照沪深300 + {_style_nm}风格指数,近 3 年分位 ≥80% 为高位、≤20% 为低位
      · 同门对照 {n_peer} 只主动权益 · 验尸窗口与买卖点相同:之后 12 个月</p>
    <div style="margin-top:10px;background:var(--raised);border:1px solid var(--line);border-radius:10px;padding:8px 10px 4px">{_spark}</div>
    <div class="gate-legend">
      <span><i style="background:var(--muted)"></i>沪深300</span>
      <span><i style="background:var(--warn)"></i>募满关闸</span>
      <span><i style="background:var(--danger)"></i>限额关门 / 打开申购</span>
      <span><i style="background:var(--ghost)"></i>合同开放(不进样本)</span>
      <span><i style="background:var(--cyan);border-radius:1px"></i>公司固有资金自购</span>
    </div>
    <div style="margin-top:4px">{rows_html}</div>
    <div class="punchline" style="margin-top:16px;font-size:17px;padding:16px 22px;border-left-width:8px">{_ghead}</div>
    <p style="font-size:13.5px;color:var(--muted);margin-top:12px;line-height:1.7">{_gbody}</p>
    <div class="chips" style="margin-top:10px">
      <span class="chip">高位关门 {hc} 回</span>
      <span class="chip no">高位开门 {ho} 回</span>
      <span class="chip">低位关门 {lc} 回</span>
      <span class="chip">低位开门 {lo_} 回</span>
      <span class="chip">假期假闸门 {_ct.get('n_operational', 0)} 条已剔除</span>
    </div>
    <p style="font-size:12px;color:var(--muted);margin-top:14px"><b>自购叠上去</b> · 经理个人自购{_gates.get('self_buy_manager') or '未获取'} · {int_txt}</p>
    <div class="chips" style="margin-top:8px">{sb_chips}</div>
    <p style="font-size:11px;color:var(--ghost);margin-top:8px">公司自购公告写的是「旗下权益类」,未逐只确认是否含本基金 · 按硬规则记线索,不记成他本人掏钱</p>
  </div>"""

    _open_hi = next((e for e in _ev if e.get("in_sample") and e.get("quadrant") == "high_open"), None)
    _launch = _gates.get("launch_close") or next((e for e in _ev if e["kind"] == "close_launch"), None)
    if _launch:
        god_hype = (f"高位圈钱 —— {_launch['date'][:7]} 提前结束募集,"
                    f"随后 12 个月沪深300 {_pp(_launch.get('fwd_csi'))}、本基金 {_pp(_launch.get('fwd_fund'))}")
        if _open_hi:
            god_hype += (f";{_open_hi['date'][:7]} {_style_nm}指数 {_open_hi['growth_pct']}% 分位打开万元以上申购,"
                         f"随后 12 个月本基金 {_pp(_open_hi.get('fwd_fund'))}")
        god_hype += "。高位关过门,也高位开过门(公告时间线=已确认事实,圈钱动机=较强推断;公司发行他是代言人)"

yearend_card = ""
clone_card = ""
flow_card = ""
god_yearend = "年底冲排名 —— 未检测"

god_yearend_html = ('<div class="check" style="opacity:.6">'
                    '<span class="ck" style="color:var(--ghost)">○</span>年底冲排名 —— 未检测</div>')
god_n_pass, god_n_flag, god_n_miss = 5, 1, 3

_ye = ab.get("yearend") or {}
if _ye.get("metrics"):
    ym = _ye["metrics"]
    yearend_card = f"""
  <div class="card" style="margin-top:var(--gap)">
    <span class="lbl">年底冲排名 · Q4 vs 其他季度(对照卡,不进总分)</span>
    <p style="font-size:11px;color:var(--ghost);margin-top:4px">成立首年 {ym.get('skip_year') or '—'} 当建仓年已剔除 · Q1/Q3 只有前十大,不拿持股只数比 · 样本 Q4 {ym['n_q4']} 期 / 其他 {ym['n_other']} 期</p>
    <div class="grid g4" style="margin-top:14px;gap:10px">
      <div class="stat"><span class="lbl">前十大集中度</span><span class="v" style="font-size:22px">Q4 {ym['top10_q4']}%</span><span class="sub">其他季 {ym['top10_other']}%</span></div>
      <div class="stat"><span class="lbl">单票上限</span><span class="v" style="font-size:22px">Q4 {ym['max_q4']}%</span><span class="sub">其他季 {ym['max_other']}%</span></div>
      <div class="stat"><span class="lbl">前十大换血率</span><span class="v" style="font-size:22px">Q4 {ym['churn_q4']}</span><span class="sub">其他季 {ym['churn_other']}</span></div>
      <div class="stat"><span class="lbl">当季收益</span><span class="v" style="font-size:22px">Q4 {_pp(ym['ret_q4'])}</span><span class="sub">其他季 {_pp(ym['ret_other'])}</span></div>
    </div>
    <p style="font-size:11px;color:var(--ghost);margin-top:8px">股票仓位(仅中报/年报全持仓) Q4 {ym.get('equity_q4')}% vs 中报 {ym.get('equity_q2')}%</p>
    <div class="punchline" style="margin-top:14px;font-size:16px;padding:14px 20px;border-left-width:8px">{_ye['verdict']}</div>
  </div>"""
    if _ye.get("flagged"):
        god_yearend = f"年底冲排名 —— {_ye['verdict']}"
        god_yearend_html = (f'<div class="check" style="border-color:var(--warn)">'
                            f'<span class="ck" style="color:var(--warn)">⚠</span>{god_yearend}</div>')
        god_n_pass, god_n_flag, god_n_miss = 5, 2, 2
    else:
        god_yearend = (f"年底冲排名 —— Q4 前十大 {ym['top10_q4']}% 不高于其他季 {ym['top10_other']}%,"
                       f"当季收益 {_pp(ym['ret_q4'])} vs {_pp(ym['ret_other'])}。未检出赌名次")
        god_yearend_html = f'<div class="check"><span class="ck">✓</span>{god_yearend}</div>'
        god_n_pass, god_n_flag, god_n_miss = 6, 1, 2

_cl = ab.get("clones") or {}
if _cl.get("available"):
    cl_rows = ""
    for p in _cl.get("pairs") or []:
        chips = "".join(f'<span class="rgrade" style="padding:2px 8px;font-size:10.5px">{n}</span>' for n in p.get("shared_names") or [])
        cl_rows += f"""<div style="display:grid;grid-template-columns:minmax(150px,1.4fr) 90px 1fr 70px;gap:12px;align-items:center;padding:9px 0;border-bottom:1px dashed var(--line);font-size:13px">
          <div><b>{p['name']}</b><span style="color:var(--ghost);font-size:11px"> {p['code']}</span><br>
            <span style="color:var(--muted);font-size:11px">{p.get('q')} · 前十大撞 {p['n_shared']}/10</span></div>
          <div style="display:flex;gap:4px;flex-wrap:wrap">{chips}</div>
          <div class="bar-track" style="height:10px"><div class="bar-fill" data-w="{min(100,p['n_shared']*10)}" style="background:var(--warn)"></div></div>
          <span class="v warn" style="text-align:right">{p['overlap_w']}%</span>
        </div>"""
    clone_card = f"""
  <div class="card" style="margin-top:var(--gap)">
    <span class="lbl">一车多牌 · 他名下其他产品跟这一只重不重样(对照卡,不进总分)</span>
    <p style="font-size:11px;color:var(--ghost);margin-top:4px">名下主动权益 {_cl.get('n_products')} 只(含本品) · 重合权重 = 双方前十大共有股票上取较小权重再加总 · {(_cl.get('pairs') or [{}])[0].get('q','')} 全持仓前十大</p>
    <div style="margin-top:10px">{cl_rows}</div>
    <div class="punchline" style="margin-top:14px;font-size:16px;padding:14px 20px;border-left-width:8px">{_cl['verdict']}</div>
  </div>"""
elif _cl.get("reason"):
    clone_card = f"""
  <div class="card" style="margin-top:var(--gap)">
    <span class="lbl">一车多牌</span>
    <p style="font-size:13px;color:var(--muted);margin-top:10px">{_cl['reason']}</p>
  </div>"""

_co = ab.get("cohorts") or {}
_hf = ab.get("holder_flow") or {}
if _co.get("events") or _hf.get("rows"):
    co_rows = ""
    for e in _co.get("events") or []:
        lab = {"unlock_redeem": "到期赎回", "net_out": "打开后净缩", "inflow": "净申购批次",
               "rebuild": "解锁后回流", "flat": "份额不动", "missing": "未获取"}.get(e.get("label"), e.get("label"))
        co_rows += f"""<div class="gate-row">
          <div class="when">{e.get('date','')}</div>
          <div class="act">{lab}</div>
          <div class="why">{e.get('note') or ''}</div>
          <div class="fwd">12个月本基金<br><b>{_pp(e.get('fwd_fund')) if e.get('fwd_fund') is not None else '—'}</b></div>
        </div>"""
    hf_rows = ""
    ZONE_LAB = {"high": "高位", "low": "低位", "mid": "中位", "mixed": "混杂", "unknown": "—"}
    for r in _hf.get("rows") or []:
        tag = (r.get("tags") or ["—"])[0]
        zc = "var(--danger)" if r.get("zone")=="high" else ("var(--ok)" if r.get("zone")=="low" else "var(--ghost)")
        hf_rows += f"""<div style="display:grid;grid-template-columns:86px 70px 70px 1fr 72px;gap:8px;align-items:center;padding:7px 0;border-bottom:1px dashed var(--line);font-size:12.5px">
          <b>{r['date'][:7]}</b>
          <span>机构 {r.get('inst')}%</span>
          <span>{r.get('share_yi'):.0f} 亿份</span>
          <span style="color:var(--muted)">{tag}</span>
          <span style="text-align:right;color:{zc}">{ZONE_LAB.get(r.get('zone'),'')} · 12m {_pp(r.get('fwd_fund'))}</span>
        </div>"""
    flow_card = f"""
  <div class="card" style="margin-top:var(--gap)">
    <span class="lbl">开门批次命运 · 门开了之后那批钱怎样了(对照卡,不进总分)</span>
    <p style="font-size:11px;color:var(--ghost);margin-top:4px">净份额变化,申购赎回拆不开 · 净缩不能写成没人买,也不能写成开门收钱</p>
    <div style="margin-top:8px">{co_rows}</div>
    <div class="punchline" style="margin-top:14px;font-size:16px;padding:14px 20px;border-left-width:8px">{_co.get('verdict') or ''}</div>
  </div>
  <div class="card" style="margin-top:var(--gap)">
    <span class="lbl">持有人换手 · 机构高位走了没有,散户山顶进了没有</span>
    <p style="font-size:11px;color:var(--ghost);margin-top:4px">锁定期至 {_hf.get('lockup_until') or '—'} · 份额不动时机构占比变化是场内换手,不是申购 · 12 个月 = 该报告日后本基金涨跌</p>
    <div style="margin-top:8px">{hf_rows}</div>
    <div class="punchline" style="margin-top:14px;font-size:16px;padding:14px 20px;border-left-width:8px">{_hf.get('verdict') or ''}</div>
  </div>"""

def _ck_ok(text):
    return f'<div class="check"><span class="ck">✓</span>{text}</div>'
def _ck_warn(text):
    return f'<div class="check" style="border-color:var(--warn)"><span class="ck" style="color:var(--warn)">⚠</span>{text}</div>'
def _ck_miss(text):
    return f'<div class="check" style="opacity:.6"><span class="ck" style="color:var(--ghost)">○</span>{text}</div>'

def _god_line(it):
    text = f"{it.get('name')} —— {it.get('text')}"
    st = it.get("status")
    if st == "pass":
        return _ck_ok(text)
    if st == "flag":
        return _ck_warn(text)
    return _ck_miss(text)

_god = ab.get("god") or {}
_god_items = _god.get("items") or []
if _god_items:
    god_rows_html = "\n      ".join(_god_line(it) for it in _god_items)
    god_n_pass = _god.get("n_pass", sum(1 for x in _god_items if x.get("status") == "pass"))
    god_n_flag = _god.get("n_flag", sum(1 for x in _god_items if x.get("status") == "flag"))
    god_n_miss = _god.get("n_miss", sum(1 for x in _god_items if x.get("status") == "miss"))
else:
    n_reg = len(regimes)
    if lead_always:
        god_dump_html = _ck_ok(f"甩锅跑路 —— {n_reg} 次变更他都在任,任期 {tenure_txt} 从未离任")
    else:
        god_dump_html = _ck_warn(
            f"甩锅跑路 —— 他不是全程在任(最早 {(_first_start or '未获取')[:7]}),现任任期不能包装前任")
    if lead_from_inception:
        god_peach_html = _ck_ok("摘桃子 —— 基金自成立即由他管,无接盘他人业绩")
    elif _first_start:
        god_peach_html = _ck_warn(
            f"摘桃子 —— 他 {_first_start[:10]} 才上台,成立以来业绩不能全记在他头上")
    else:
        god_peach_html = _ck_miss("摘桃子 —— 任期起点未获取")
    _nprod = (ab.get("clones") or {}).get("n_products")
    if _nprod:
        god_body_html = _ck_miss(f"藏尸体 —— 公开名下 {_nprod} 只主动权益,清盘/迷你化未逐只查")
    else:
        god_body_html = _ck_miss("藏尸体 —— 名下产品清单未获取,清盘未查")
    god_persona_html = _ck_miss("人设造假 —— 履历未逐条核对,不从别的基金抄")
    god_ruler_html = _ck_miss("偷换尺子 —— 业绩基准是否中途改过未查")
    if "未鉴定" in god_hype or "未跑" in god_hype:
        god_hype_html = _ck_miss(god_hype)
    else:
        god_hype_html = _ck_warn(god_hype)
    god_n_pass = (1 if lead_always else 0) + (1 if lead_from_inception else 0)
    god_n_flag = (0 if lead_always else 1) + (0 if lead_from_inception else 1)
    if "未鉴定" not in god_hype and "未跑" not in god_hype:
        god_n_flag += 1
    if _ye.get("metrics"):
        if _ye.get("flagged"):
            god_n_flag += 1
        else:
            god_n_pass += 1
    god_n_miss = 9 - god_n_pass - god_n_flag
    god_rows_html = "\n      ".join([
        god_dump_html, god_peach_html, god_body_html, god_persona_html,
        god_ruler_html, god_hype_html, god_yearend_html,
        _ck_miss("蹭业绩 —— 未详查"),
        _ck_miss("利益冲突 —— 披露有限,只能记「未发现」"),
    ])

html = f'''<!DOCTYPE html>
<html lang="zh-CN" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>基佬skill · {mgr_name} · {fund_name}(真实数据)</title>
<style>{css}</style>
</head>
<body>
<div class="mock-tag" style="background:var(--ok)">真实公开数据</div>
<button class="theme-btn" id="themeBtn" title="切换主题">🌙</button>

<div class="wrap">

<div class="topbar">
  <span class="brand-dot"></span>
  <span class="brand-txt">基佬skill <span style="opacity:.45;font-size:.85em;letter-spacing:.08em">FUND GUY SKILL</span></span>
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
    <span class="sec-sub">真实公开数据 · 任期已切割</span><span class="sec-line"></span>
  </div>

  <div class="grid hero3">
    <div class="card">
      <span class="lbl">受检对象</span>
      <div style="display:flex;align-items:center;gap:20px;margin-top:10px">
        {photo_html}
        <div style="flex:1;min-width:0">
          <h1 style="font-size:44px;font-weight:900;letter-spacing:-.02em">{mgr_name}</h1>
          <p style="font-size:14px;color:var(--muted);margin-top:4px">{fund_name} · {CODE} · 贯穿管理 {tenure_txt}</p>
          <div class="tags" style="margin-top:10px">
            <span class="tag rarity">{fund_type} · {company_short}</span>
            <span class="tag good">成立以来 +{total:.0f}%</span>
            <span class="tag purple">{len(regimes)} 任配置 · 现任 {mgr_name}</span>
            <span class="tag hot">最大回撤 {m["max_dd"]:.0f}%</span>
            <span class="tag hot">规模 {scale_now}</span>
          </div>
        </div>
        <div class="hero-style" style="text-align:right;flex-shrink:0;border-left:1px solid var(--line);padding-left:22px">
          <span class="lbl">打法</span>
          <div style="font-size:22px;font-weight:900;color:var(--indep);margin-top:8px;line-height:1.35">{style_title}</div>
          <div style="font-size:11px;color:var(--ghost);margin-top:8px">{style_sub}</div>
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
      <div style="font-size:11px;color:var(--ghost);margin-top:8px">择时35% + 控制35% + 超额质量30%(赚得稳不稳) · 每一分都有规则,可复算</div>
    </div>

    <div class="card" style="display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px">
      <div class="stamp" style="border-color:{stamp_col};color:{stamp_col};background:color-mix(in srgb,{stamp_col} 14%,transparent)">
        <span class="big">{stamp_big}</span><span class="sm">{stamp_sm}</span></div>
      <div style="font-size:13px;color:var(--muted);margin-top:12px">这个判断我们敢押多少</div>
      <div style="font-size:17px;font-weight:900">证据缺口见末页</div>
    </div>
  </div>

  {platform_card}

  <div class="punchline" style="margin-top:24px">
    {punchline}
  </div>

  <div class="card" style="margin-top:var(--gap);display:flex;align-items:center;gap:26px;flex-wrap:wrap">
    <div>
      <span class="lbl">年度战绩 vs 沪深300 · {len(years)} 年</span>
      <div class="dots" style="margin-top:10px">{dots}</div>
      <div style="font-size:11px;color:var(--ghost);margin-top:8px">{len(years)} 年 · <b class="ok">{wins} 胜</b> · <b class="danger">{len(years)-wins} 负</b></div>
    </div>
    <div style="flex:1;min-width:280px;display:grid;grid-template-columns:1fr 1fr;gap:12px">
      <div class="stat" style="border-color:var(--ok)"><span class="lbl">成立以来累计</span><span class="v ok">+{total:.0f}%</span><span class="sub">年化约 {cagr:.1f}%</span></div>
      <div class="stat"><span class="lbl">同类排名</span><span class="v">{rank_v}</span><span class="sub">{rank_sub}</span></div>
    </div>
  </div>

  <div class="grid g4" style="margin-top:var(--gap)">
    <div class="stat hl"><span class="lbl">这个人行不行</span>
      <span class="v ok">{"行" if lead_always else "看任期"}</span><span class="sub">{tenure_txt}{"全程在任" if lead_always else "不是全程在任"} · 以公开披露为准</span></div>
    <div class="stat"><span class="lbl">这只基金行不行</span>
      <span class="v" style="color:var(--warn)">对照规模</span><span class="sub">{scale_now} · 规模来自披露,不是能力分</span></div>
    <div class="stat"><span class="lbl">现在买合适吗</span>
      <span class="v" style="color:var(--warn)">对照回撤</span><span class="sub">最长水下 {uw_years} 年 · 最大回撤 {m["max_dd"]:.0f}%</span></div>
    <div class="stat"><span class="lbl">适不适合你</span>
      <span class="v long cyan">{you_fit}</span><span class="sub">{you_fit_sub}</span></div>
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
      <span class="lbl">能力形成路径(公开任期,不抄别人履历)</span>
      <div class="tl" style="margin-top:18px">
        {career_tl}
      </div>
    </div>

    <div class="card">
      <span class="lbl">{tenure_head}</span>
      <table style="margin-top:12px">
        <tr><th>时段</th><th>阵容</th><th>时长</th><th style="text-align:right">区间收益</th></tr>
        {regime_rows}
      </table>
      <div class="chips" style="margin-top:12px">
        <span class="chip purple">{len(regimes)} 任配置 · {"他从未离开" if lead_always else "现任不是全程常量"}</span>
        <span class="chip">{tenure_chip2}</span>
      </div>
    </div>
  </div>
</section>

<!-- ============ 03 买卖复盘 ============ -->
<section id="s3" class="sec">
  <div class="sec-head">
    <span class="sec-num">03</span><span class="sec-ti">买卖复盘</span>
    <span class="sec-sub">{replay_sub}</span><span class="sec-line"></span>
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

  <!-- 买卖点验尸:全部拿12个月后的走势验(卖出只认主动清仓) -->
  <div class="card" style="margin-top:var(--gap);border-color:var(--indep);background:var(--indep-tint)">
    <span class="lbl" style="color:var(--indep)">买卖点验尸 · {ti["n_buy"]} 次买入 + {ti["n_sell"]} 次清仓,全部拿 12 个月后的走势验</span>
    <div style="margin-top:16px">
      <div class="bar-row" style="grid-template-columns:170px 1fr 56px">
        <span class="k">买点胜率 · 跑赢大盘算赢</span>
        <div class="bar-track"><div class="bar-fill ok" data-w="{ti["buy_win_rate"]}"></div></div>
        <span class="v ok">{ti["buy_win_rate"]}%</span></div>
      <div class="bar-row" style="grid-template-columns:170px 1fr 56px">
        <span class="k">清仓躲跌率 · 卖光后真跌了算对</span>
        <div class="bar-track"><div class="bar-fill warn" data-w="{ti["dodge_rate"]}"></div></div>
        <span class="v warn">{ti["dodge_rate"]}%</span></div>
    </div>
    <div class="chips" style="margin-top:12px">
      <span class="chip">部分减仓不算卖飞(大头还在,后面涨跌他都有份)</span>
      <span class="chip">被动减仓已剔除 <b>{ab["passive_cap"]+ab["passive_redeem"]} 次</b>(触10%线 {ab["passive_cap"]} · 遭赎回 {ab["passive_redeem"]})</span>
    </div>
    <p style="text-align:center;font-size:19px;font-weight:900;margin-top:14px">
      {buy_lab}(买后 12 个月平均超额 <span class="ok">+{ti["buy_avg_excess"]}%</span>) ·
      <span class="danger">{sell_lab}</span>(清仓的股票 12 个月平均又涨 <span class="danger">+{ti["sell_avg_fwd"]}%</span>)</p>
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
      <span class="lbl">最好与最差的清仓 · 只看卖光离场的</span>
      <div class="grid g2" style="margin-top:14px;gap:10px">
        <div class="stat" style="border-color:var(--ok)"><span class="lbl">🏆 {ti["best_sell"]["name"]} · {ti["best_sell"]["label"]} {ti["best_sell"]["q"]}</span>
          <span class="v ok" style="font-size:26px">躲过 {ti["best_sell"]["fwd"]}%</span><span class="sub">卖后 12 个月它跌了这么多</span></div>
        <div class="stat" style="border-color:var(--danger)"><span class="lbl">💀 {ti["worst_sell"]["name"]} · {ti["worst_sell"]["label"]} {ti["worst_sell"]["q"]}</span>
          <span class="v danger" style="font-size:26px">卖飞 +{ti["worst_sell"]["fwd"]}%</span><span class="sub">卖后 12 个月它又涨了这么多</span></div>
      </div>
      <div class="chips" style="margin-top:12px">
        <span class="chip no">主动清仓 {ti["n_sell"]} 次 · 只有 {ti["dodge_rate"]}% 卖在了下跌前</span>
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
      <span class="lbl">股票被套的时候,他干什么</span>
      <p style="font-size:12px;color:var(--muted);margin-top:8px">手里的股票跌破他的买入成本后,他一共做过 <b>{ab["loss_cut"] + ab["loss_add"]}</b> 次动作 ——</p>
      <div class="exits" style="margin-top:8px">
        <div class="ex"><div class="n ok">{ab["loss_cut"]} 次</div><div class="k">认错砍掉</div></div>
        <div style="font-size:13px;color:var(--ghost);font-weight:900">VS</div>
        <div class="ex"><div class="n warn">{ab["loss_add"]} 次</div><div class="k">越跌越买</div></div>
      </div>
      <div class="chips" style="margin-top:14px;justify-content:center;display:flex">
        <span class="chip ok">{disc_lab}</span>
      </div>
      <div style="margin-top:16px;padding-top:14px;border-top:1px solid var(--line)">
        <div class="chips">
          <span class="chip purple">整只基金的加减仓时机:<b>{pos_lab}</b></span>
          <span class="chip">大幅调整仓位 {ab["pos_moves"]} 次 · 方向踩对 {ab["pos_same_dir"]} 次</span>
        </div>
        <p style="font-size:11px;color:var(--ghost);margin-top:10px">{short_txt}<span style="opacity:.6">(择时回归 γ=+{ab["tm_gamma"]},t={ab["tm_t"]})</span></p>
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
  {clone_card}
</section>

<!-- ============ 05 你会怎么亏 ============ -->
<section id="s4" class="sec">
  <div class="sec-head">
    <span class="sec-num">05</span><span class="sec-ti">你会怎么亏</span>
    <span class="sec-sub">全部真实发生过</span><span class="sec-line"></span>
  </div>

  <div class="card">
    <span class="lbl">{disaster_title}</span>
    <div class="amount">
      <span class="lbl2">投多少</span>
      <input type="range" id="amountSlider" min="5" max="200" value="10" step="5">
      <span class="val" id="amountVal">10 万</span>
    </div>
    <div class="grid g4" style="margin-top:18px">
      <div class="stat"><span class="lbl">最差时账面剩</span><span class="v danger" id="worstVal">{10*(1-m["max_dd"]/100):.2f} 万</span><span class="sub">最大回撤 {m["max_dd"]}%</span></div>
      <div class="stat"><span class="lbl">回撤持续</span><span class="v">{dd_months} 个月</span><span class="sub">{dd_from[:7]} → {dd_to[:7]}</span></div>
      <div class="stat"><span class="lbl">等回本</span><span class="v danger">{uw_months} 个月</span><span class="sub">{m["uw_from"]} → {m["uw_to"][:7]}</span></div>
      <div class="stat"><span class="lbl">水下时长</span><span class="v long danger">{m["underwater_days"]} 天</span><span class="sub">{uw_sub}</span></div>
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
      <span class="chip ok">{cap_chip}</span>
      <span class="chip">同时大于/小于 100 = 真本事的形状</span>
    </div>
  </div>

  <div class="grid g4" style="margin-top:var(--gap)">
    <div class="stat"><span class="lbl">年化 Alpha</span><span class="v ok">+{pro["alpha"]}%</span><span class="sub">CAPM · vs 沪深300</span></div>
    <div class="stat"><span class="lbl">Beta</span><span class="v">{pro["beta"]}</span><span class="sub">跟大盘同涨跌的程度</span></div>
    <div class="stat"><span class="lbl">跟踪误差</span><span class="v">{pro["te"]}%</span><span class="sub">敢偏离指数 · 主动味十足</span></div>
    <div class="stat"><span class="lbl">R²</span><span class="v">{pro["r2"]}</span><span class="sub">{r2_mkt}</span></div>
  </div>

  <div class="grid g2" style="margin-top:var(--gap)">
    <div class="card">
      <span class="lbl">持仓特征(季报口径)</span>
      <div class="grid g2" style="margin-top:14px;gap:10px">
        <div class="stat" style="padding:14px"><span class="lbl">前十大集中度 · 均值</span><span class="v" style="font-size:24px">{pro["top10_avg"]}%</span></div>
        <div class="stat" style="padding:14px;border-color:var(--warn)"><span class="lbl">最新一期</span><span class="v warn" style="font-size:24px">{pro["top10_latest"]}%</span><span class="sub">{conc_lab}</span></div>
        <div class="stat" style="padding:14px"><span class="lbl">持股数量</span><span class="v" style="font-size:24px">{pro["n_stocks"]} 只</span><span class="sub">{pro["n_stocks_period"]} 年报全持仓</span></div>
        <div class="stat" style="padding:14px"><span class="lbl">年化波动</span><span class="v" style="font-size:24px">{pro["vol"]}%</span></div>
      </div>
    </div>
    <div class="card">
      <span class="lbl">风格箱(因子暴露估,不是晨星官方格)</span>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:2px;background:var(--line);border:2px solid var(--line);border-radius:8px;overflow:hidden;margin-top:14px;max-width:340px">
        {style_box}
      </div>
      <div class="chips" style="margin-top:12px"><span class="chip purple">{style_plain} · 按因子暴露点亮,不是持仓手工格</span></div>
    </div>
  </div>

  <!-- 多因子拆解 + 机构画像 + 到手率 -->
  <div class="grid g2" style="margin-top:var(--gap)">
    {factor_html}
    <div class="card">
      <span class="lbl">谁在持有这只基金(真实持有人结构)</span>
      <div class="grid g3" style="margin-top:12px;gap:8px">
        <div class="stat" style="padding:12px"><span class="lbl">机构的钱</span><span class="v" style="font-size:22px;color:var(--cyan)">{inst_latest["inst"]:.1f}%</span><span class="sub">{inst_sub}</span></div>
        <div class="stat" style="padding:12px"><span class="lbl">散户的钱</span><span class="v" style="font-size:22px">{100-inst_latest["inst"]:.1f}%</span></div>
        <div class="stat" style="padding:12px;border-color:var(--ok)"><span class="lbl">自家员工</span><span class="v ok" style="font-size:22px">{inst_latest.get("internal","—")}</span><span class="sub">敢吃自己做的饭</span></div>
      </div>
      <div style="margin-top:10px">{inst_bars}</div>
      <p style="font-size:11px;color:var(--ghost);margin-top:8px">国家队/险资等大额单一持有人只在年报 PDF 披露,本次未获取 · 按硬规则记「未查证」</p>
      <div class="duo" style="margin-top:14px">
        <div class="side"><div class="k">基金年化(时间加权)</div><div class="n ok" style="font-size:30px">{ab["twr"]}%</div></div>
        <div class="vs2">VS</div>
        <div class="side"><div class="k">基民年化(资金加权·估算)</div><div class="n" style="font-size:30px">{ab["mwr"]}%</div></div>
      </div>
      <div class="chips" style="margin-top:10px">
        <span class="chip ok">{mwr_chip}</span>
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
      <div class="chips" style="margin-top:16px">{fee_chips}</div>
      <p style="font-size:11px;color:var(--ghost);margin-top:14px">{fee_note}</p>
      <div style="margin-top:20px">
        <span class="lbl">{scale_lbl}</span>
        <div class="duo" style="margin-top:12px">
          <div class="side"><div class="k">{scale_first_q}</div><div class="n">{scale_first}</div></div>
          <div class="vs2">→</div>
          <div class="side"><div class="k">现在</div><div class="n ok">{scale_now}</div></div>
        </div>
      </div>
    </div>
  </div>
{gate_card}
{flow_card}
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
        <span class="chip">仓位 <b>自行决定</b></span>
        <span class="chip">持有 <b>{verdict_hold}</b></span>
        <span class="chip">扛得住 <b>-{m["max_dd"]:.0f}%</b></span>
      </div>
      <div class="chips" style="margin-top:12px">
        <span class="chip no">{verdict_no1}</span>
        <span class="chip no">{verdict_no2}</span>
      </div>
    </div>

    <div class="card">
      <span class="lbl">证据缺口 · 仍未覆盖(已从 6 项缩到 2 项)</span>
      <div class="trig" style="margin-top:14px">
        <span>门派识别(需持仓聚类)</span>
        <span>Idea 先手/跟随(需同门逐季对齐)</span>
      </div>
      <p style="font-size:12px;color:var(--muted);margin-top:12px">独立战争/多因子/抄作业/机构画像/到手率/造神检测/闸门时间轴/一车多牌/开门批次/年底冲排名已补跑。按 SKILL 硬规则,剩余缺口继续在报告中明示。</p>
    </div>
  </div>

  <!-- 造神检测九项 -->
  {yearend_card}
  <div class="card" style="margin-top:var(--gap)">
    <span class="lbl">造神检测 · 九项审查(本品公告/任期/持仓筛 · 三级证据制)</span>
    <div class="checks" style="margin-top:14px">
      {god_rows_html}
    </div>
    <div class="chips" style="margin-top:14px">
      <span class="chip ok">{god_n_pass} 项通过</span>
      <span class="chip" style="border-color:var(--warn);color:var(--warn)">{god_n_flag} 项留意</span>
      <span class="chip">{god_n_miss} 项未查证(不写成「不存在」)</span>
    </div>
  </div>

  <div class="card" style="margin-top:var(--gap)">
    <span class="lbl">数据来源 · 每个数字都有出处</span>
    <table style="margin-top:12px;font-size:12px">
      <tr><th style="width:280px">数据</th><th>来源</th></tr>
      <tr><td>净值 / 规模 / 申购赎回 / 持有人结构 / 经理档案与照片 / 平台五维评分</td><td>天天基金(东方财富) fund.eastmoney.com · pingzhongdata / F10 / 经理档案页</td></tr>
      <tr><td>逐季持仓 / 基金收益排行(今年 TOP10)</td><td>东方财富,经 akshare 接口(fund_portfolio_hold_em / fund_open_fund_rank_em)</td></tr>
      <tr><td>全市场基金持仓横截面(市场共识 / 拥挤度)</td><td>巨潮资讯,经 akshare(fund_report_stock_cninfo)</td></tr>
      <tr><td>重仓股的基金持有人反查(全市场撞车榜)</td><td>东方财富数据中心(RPT_MAINDATA_MAIN_POSITIONDETAILS)</td></tr>
      <tr><td>A 股周 K 线(前复权)</td><td>baostock</td></tr>
      <tr><td>港股周 K 线</td><td>新浪财经,经 akshare(stock_hk_daily)</td></tr>
      <tr><td>指数行情(沪深300 / 中证500 / 成长价值风格)</td><td>akshare 指数接口</td></tr>
      <tr><td>同门基金持仓(独立战争对照组)</td><td>东方财富 F10,逐只抓取(剔除自管与债性产品)</td></tr>
      <tr><td>申购闸门(限购/暂停大额/恢复申购/提前结束募集/公司自购)</td><td>东方财富基金公告 JJGG type=0 · api.fund.eastmoney.com/f10/JJGG · 同门主动权益对照是否同一天限购</td></tr>
      <tr><td>名下其他产品持仓(一车多牌)</td><td>东方财富,经 akshare(fund_portfolio_hold_em),与本品同一接口</td></tr>
      <tr><td>K 线图表库</td><td>TradingView Lightweight Charts(Apache-2.0,已内嵌)</td></tr>
      <tr><td>重仓股行业 / 一级板块</td><td>东方财富 F10 公司概况 sshy / 所属板块;港股 F10 sshy(缺则行情 f127)</td></tr>
      <tr><td>管理费 / 托管费 / 销售服务费</td><td>东方财富基金费率页 jjfl</td></tr>
      <tr><td>K 线情景(本基金成立/经理变更/规模/回撤/闸门)</td><td>本品 basic/managers/规模估算/净值回撤/JJGG 闸门,自动生成 kind=fund;行业/宏观新闻若缓存里已有则保留,不从别的基金抄</td></tr>
      <tr><td>造神检测可自动筛的项</td><td>任期切割、共管/独管、JJGG 标题(基准/清盘/增聘)、牌面行业 vs 资料策略摘要、闸门分位、名下产品清单。季报原文/亲属任职/招募书全文仍标未获取</td></tr>
      <tr><td>事件核实 / 公告全文 / Mandate</td><td>分析判断(agent),非官方口径,依据均为公开资料</td></tr>
    </table>
    <p style="font-size:11px;color:var(--ghost);margin-top:10px">
      原始数据均缓存于本地 <code>.cache/</code> 留证,记录接口名+参数与抓取时间 · 买卖点为季报持股数变化推断,非实际成交记录 · 平台评分仅作对照展示,不计入行为评分</p>
  </div>

  <div class="foot">
    <b style="color:var(--muted)">基佬skill · 真实公开数据运行</b><br>
    数据截至 {m["until"]} · 非个性化投资建议 · 基金过往业绩不预示未来表现 · 判决有效期至下一期持仓披露
  </div>
</section>

</div>

<script>{LIB.replace("</script>", "<\\/script>")}</script>
<script>{main_js}</script>
</body>
</html>'''

if MASK:
    # 收集全部经理姓名(主角/共管副手/同门经理),统一遮蔽为 首字+**
    _names = set()
    _names.add(mgr_name)
    for r in regimes:
        _names.update(r["managers"].split())
    if hs:
        for x in hs.get("similar_funds") or []:
            _names.update(str(x.get("managers", "")).split())
    _names.discard("")
    for n in sorted(_names, key=len, reverse=True):
        html = html.replace(n, n[0] + "*" * max(len(n) - 1, 1))
    print(f"打码:{len(_names)} 个姓名已遮蔽 + 照片像素化")

out = os.path.join(ROOT, "assets", f"fund-{CODE}.html")
open(out, "w").write(html)
print(f"→ {out}  ({len(html)//1024}KB)")
