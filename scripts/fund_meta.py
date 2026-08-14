#!/usr/bin/env python3
"""本品日历/风格对照。窗口和尺子必须跟所选基金走,禁止写死 163417/2018。"""
import json
import os
import re
import sys
from datetime import date, timedelta


def require_code():
    """单脚本入口必须带 6 位代码。禁止默认落到 163417 上 silently 跑错基金。"""
    arg = sys.argv[1].strip() if len(sys.argv) > 1 else ""
    if not re.fullmatch(r"[0-9]{6}", arg):
        sys.stderr.write(f"用法: python {os.path.basename(sys.argv[0])} <6位基金代码>\n")
        sys.exit(2)
    return arg


def mask_on(code):
    """演示打码。FUND_MASK=0 强制关,=1 强制开;默认只打码公开发布的 163417。"""
    env = os.environ.get("FUND_MASK")
    if env == "0":
        return False
    if env == "1":
        return True
    return code == "163417"


def ensure_masked_photo(src, dst):
    """MASK 时把原图像素化。已有 masked 文件不覆盖。Pillow 优先,否则 macOS sips。"""
    if os.path.exists(dst):
        return dst
    if not src or not os.path.exists(src):
        return None
    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
    try:
        from PIL import Image
        im = Image.open(src).convert("RGB")
        w, h = im.size
        bw = 12
        bh = max(1, int(bw * h / max(w, 1)))
        im.resize((bw, bh), Image.NEAREST).resize((w, h), Image.NEAREST).save(dst)
        return dst
    except Exception:
        pass
    if sys.platform == "darwin":
        import subprocess
        try:
            subprocess.run(["sips", "-z", "14", "11", src, "--out", dst],
                           check=True, capture_output=True)
            subprocess.run(["sips", "-z", "110", "88", dst],
                           check=True, capture_output=True)
            return dst if os.path.exists(dst) else None
        except Exception:
            return None
    return None


def _basic_map(d):
    p = os.path.join(d, "basic.json")
    if not os.path.exists(p):
        return {}
    rows = json.load(open(p))
    if rows and isinstance(rows[0], dict) and "item" in rows[0]:
        return {r["item"]: r["value"] for r in rows}
    return {}


def found_on(d):
    v = str(_basic_map(d).get("成立时间") or "")
    return v[:10] if len(v) >= 10 and v[:4].isdigit() else None


def hold_years(d):
    ys = []
    for f in os.listdir(d):
        if f.startswith("hold_") and f.endswith(".json") and f[5:9].isdigit():
            ys.append(int(f[5:9]))
    return sorted(set(ys))


def kline_window(d):
    """周K区间:成立日前约 13 个月 → 今年年底(买卖点前后要看到)。"""
    today = date.today()
    fo = found_on(d)
    if fo:
        start = (date.fromisoformat(fo) - timedelta(days=400)).isoformat()
    else:
        hy = hold_years(d)
        start = f"{(hy[0] if hy else today.year) - 1}-01-01"
    end = date(today.year, 12, 31).isoformat()
    return start, end


def index_start(d):
    fo = found_on(d)
    y = int(fo[:4]) - 1 if fo else (hold_years(d) or [date.today().year])[0] - 1
    return f"{max(y, 2005)}-01-01"


def house_years(d):
    """同门/市场横截面:本品有持仓的最近 5 个自然年。"""
    hy = hold_years(d)
    if hy:
        return hy[-5:]
    y = date.today().year
    return list(range(y - 4, y + 1))


def market_periods(d):
    today = date.today()
    out = []
    for y in house_years(d):
        out.append(f"{y}0630")
        if y < today.year or today.month >= 8:
            out.append(f"{y}1231")
    return out


def q_end(q):
    y, n = int(q[:4]), int(q[-1])
    return f"{y}-{['03-31', '06-30', '09-30', '12-31'][n - 1]}"


def q_shift(q, steps=-1):
    y, n = int(q[:4]), int(q[-1])
    idx = y * 4 + (n - 1) + steps
    y, r = divmod(idx, 4)
    return f"{y}Q{r + 1}"


def latest_hold_q(d):
    qs = []
    if not os.path.isdir(d):
        return None
    for f in os.listdir(d):
        if not (f.startswith("hold_") and f.endswith(".json") and f[5:9].isdigit()):
            continue
        try:
            rows = json.load(open(os.path.join(d, f)))
        except Exception:
            continue
        for r in rows:
            s = r.get("季度") or ""
            m = re.match(r"(\d{4})年(\d)季度", s)
            if m:
                qs.append(f"{m.group(1)}Q{m.group(2)}")
    return max(qs) if qs else None


def report_dates(d, n=2):
    """本品最新持仓季及再往前几季的报告日,供全市场反查/十大股东。"""
    q = latest_hold_q(d)
    if not q:
        today = date.today()
        q = f"{today.year}Q{(today.month - 1) // 3 + 1}"
    out = []
    for i in range(n):
        out.append(q_end(q_shift(q, -i)))
    return out


def style_bench(d):
    """闸门/换手对照用的风格指数。成长β≥0 用大盘成长,否则用大盘价值。"""
    bg = None
    p = os.path.join(d, "analysis.json")
    if os.path.exists(p):
        try:
            bg = (json.load(open(p)).get("ability") or {}).get("factor") or {}
            bg = bg.get("b_growth")
        except Exception:
            bg = None
    if bg is not None and float(bg) < 0:
        return "idx_value", "价值"
    return "idx_growth", "成长"
