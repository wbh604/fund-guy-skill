#!/usr/bin/env python3
"""Fund Guy Skill 一键运行入口 — 适用于 Claude Code / Codex / Cursor / 命令行 / 任何 agent。

用法:
    python run.py 163417                 # 完整管线:取数 → 分析 → 出报告,并打开浏览器
    python run.py 163417 --no-browser    # 不自动打开浏览器(服务器/CI/Codex 环境)
    python run.py 163417 --skip-fetch    # 已有 .cache 数据,只重跑分析和报告

跑完输出单文件报告 assets/fund-<code>.html(自包含,可直接分享)。

注意:脚本是一次真实运行的参考实现。任何一步取数失败时不会中断整个管线,
但分析步骤缺数据会失败 —— 那说明接口变了,请让 Agent 按 skills/fund-manager-alpha/SKILL.md
的三层取数模型自行补数,而不是死修脚本。
"""
import argparse
import os
import subprocess
import sys
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(ROOT, ".venv", "bin", "python")
if not os.path.exists(PY):
    PY = sys.executable

FETCH_STEPS = [
    ("fetch_fund.py", "基金主数据(净值/持仓/经理/持有人)"),
    ("fetch_stock_klines.py", "重仓股周K(baostock + 新浪)"),
    ("fetch_pingzhong.py", "pingzhongdata(申赎/平台评分/照片)"),
    ("fetch_house.py", "同门基金持仓(独立战争对照组)"),
    ("fetch_market_similar.py", "全市场撞车榜反查"),
    ("fetch_top_funds.py", "今年收益 TOP10 同步度"),
]
BUILD_STEPS = [
    ("analyze_fund.py", "行为分析:验尸/评分/被动减仓判定"),
    ("analyze_house.py", "分歧度/市场共识"),
    ("build_fund_report.py", "生成单文件报告"),
]


def run_step(script, desc, code, required):
    print(f"\n▶ {script} — {desc}")
    r = subprocess.run([PY, os.path.join(ROOT, "scripts", script), code])
    if r.returncode != 0:
        if required:
            print(f"✗ {script} 失败。缺数据无法继续 —— 请按 skills/fund-manager-alpha/SKILL.md "
                  "的三层取数模型让 Agent 补数后重跑。")
            sys.exit(1)
        print(f"⚠ {script} 失败(非致命),对应模块会在报告中标「未获取」。")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("code", help="基金代码,如 163417")
    ap.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    ap.add_argument("--skip-fetch", action="store_true", help="跳过取数,直接分析+出报告")
    args = ap.parse_args()
    code = args.code.strip()

    if not args.skip_fetch:
        # 前两步是分析的硬依赖;其余失败只降级
        for i, (script, desc) in enumerate(FETCH_STEPS):
            run_step(script, desc, code, required=(i < 2))
    for script, desc in BUILD_STEPS:
        run_step(script, desc, code, required=(script != "analyze_house.py"))

    out = os.path.join(ROOT, "assets", f"fund-{code}.html")
    print(f"\n✅ 报告已生成: {out}")
    if not args.no_browser and os.path.exists(out):
        webbrowser.open(f"file://{out}")


if __name__ == "__main__":
    main()
