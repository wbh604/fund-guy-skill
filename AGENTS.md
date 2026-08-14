# Fund Guy Skill · Agent 指南

这是一个基金经理行为审计 skill:输入基金代码,逐笔验证经理的买卖决策,产出单文件交互报告。
**评的是行为,不是净值。**

## 核心文档(按顺序)

1. `skills/fund-manager-alpha/SKILL.md` —— 完整方法论:18 条硬规则、三层取数模型、评分公式。**任何分析任务先读它**
2. `skills/fund-manager-alpha/references/` —— 算法细节(House Consensus/任期切割/经理尽调)
3. `DESIGN.md` —— 设计决策记录(为什么这么做)

## 快速执行

```bash
pip install -r requirements.txt
python run.py <基金代码>               # 完整管线:取数 → 分析 → 出报告
python run.py <基金代码> --no-browser  # 无 GUI 环境
```

产出 `assets/fund-<code>.html`。`scripts/` 下是一次真实运行(163417)的参考实现,
接口失效时按 SKILL 的三层取数模型自行补数,不要死修脚本。

## 不可违反的三条

1. **先做任期切割** —— 前任业绩混入现任评价 = 分析作废
2. **绝不编数** —— 拿不到就写"未获取",没有出处的数字不进报告
3. **定性判断由 Agent 做** —— 公告全文解读、Mandate 约束抽取仍没有脚本。造神九项能用本品公告/任期/持仓筛的已自动出结论(三级证据制);季报原文、亲属任职、招募书全文对照仍标未获取。行业用东财/港股公开分类自动取,禁止手写某只基金的对照表;窗口、费率、风格指数、同门对照、K 线 fund 事件全部按所选基金重算

## 目录速查

```
skills/fund-manager-alpha/   # 方法论主文档 + references
scripts/                     # 参考实现(fetch → analyze → build)
commands/                    # Claude Code 斜杠命令(analyze-fund/quick-check/find-similar)
.claude-plugin/              # Claude Code 插件清单
.cursor/skills/              # Cursor 项目技能入口
.agents/skills/              # Codex 项目技能入口
assets/                      # 报告模板 + 演示产物(演示版已对经理姓名照片打码)
run.py                       # 一键入口
```

## 边界

- 输出不构成投资建议;报告必须带免责声明和数据来源标注
- 演示/公开发布必须打码经理姓名与照片(`build_fund_report.py` 的 `MASK` 开关)
- 原始数据落 `.cache/`(已 gitignore),不得提交
