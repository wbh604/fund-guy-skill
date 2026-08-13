---
name: fund-manager-alpha
description: 基金经理深度行为审计引擎。逐笔买卖验尸(拿12个月后走势验对错)、独立决策取证(同门/全市场/热榜三把尺子)、K线战役回放、抄作业指数、被动减仓判定、造神检测、闸门时间轴,产出单文件交互 HTML 报告。当用户要求分析某只基金或基金经理、判断能不能买、经理水平如何、独立性如何、Alpha 是本事还是运气时使用。关键词:基金、基金经理、公募、Alpha、抱团、持仓分析、业绩归因、能不能买。
---

# Fund Manager Alpha · 基金经理行为审计(入口)

> 评的是行为,不是净值。

完整方法论在本仓库 `skills/fund-manager-alpha/SKILL.md`(17 条硬规则、三层取数模型、
行为评分公式、报告模块规范)—— **动手前先完整读它**,本文件只是入口。

## 快速开始

```bash
pip install -r requirements.txt
python run.py <基金代码>              # 一键:取数 → 分析 → 出报告
python run.py <基金代码> --skip-fetch # 已有 .cache 数据时
```

产出:`assets/fund-<code>.html`(自包含单文件,离线可看可分享)。

参考脚本在仓库根 `scripts/`(fetch → analyze → build,README 有逐条命令)。
接口失效时不要死修脚本,按主文档的三层取数模型(公开 API → 浏览器抓取 → 请用户登录)自行补数。

## 三条不可违反

1. **先做任期切割** —— 前任业绩混入现任评价 = 分析作废
2. **绝不编数** —— 拿不到就标"未获取"并压置信度,没有出处的数字不进报告
3. **定性判断由你做** —— 行业归类、公告解读、造神检测没有脚本,也永远不该有

## 更多

- 完整硬规则与工作流:`skills/fund-manager-alpha/SKILL.md`
- 算法细节:`skills/fund-manager-alpha/references/`
- 设计决策:`DESIGN.md`
