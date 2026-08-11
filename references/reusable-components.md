# 可复用的开源组件

基于 2026-08 GitHub 调研,以下库的特定部分可以直接复用或参考。

## pyfolio-reloaded (stefan-jansen/pyfolio-reloaded, 604★)

**能用的:** `pyfolio.perf_attrib.perf_attrib()` 

输入:日度持仓权重 DataFrame + 因子收益 + 因子暴露 → 输出:common_returns(因子解释部分)和 specific_returns(alpha)。

这是**持仓层因子归因**,能回答"这段超额里,多少是 Size/Value/Momentum 因子带来的,多少是选股 alpha"。

**不能用的:** 它没有 Brinson 归因(配置 vs 选股拆分),没有行业基准权重的概念。每天独立算一次暴露,没有跨期归属决策的能力。

**复用场景:** STEP 7 Alpha 尸检的第一步 —— 把总超额先剥离因子部分,剩下的才是真 alpha。


## empyrical / empyrical-reloaded (stefan-jansen, 118★)

pyfolio 的计算内核。纯净值层指标:

```python
empyrical.sharpe_ratio(returns)
empyrical.sortino_ratio(returns)
empyrical.max_drawdown(returns)
empyrical.calmar_ratio(returns)
empyrical.annual_return(returns)
empyrical.stability_of_timeseries(returns)  # R² of linear fit
empyrical.tail_ratio(returns)
```

**复用场景:** STEP 8 能力徽章、STEP 11 Forward Alpha 计算。

用它算指标,但**不要用它的 `benchmark` 参数** —— 那是指数基准,不是你的 House Portfolio。


## ffn (pmorissette/ffn, 2.6k★)

`ffn.GroupStats(rets_dict)` 能把 N 条净值曲线并排出统计表:

```python
stats = ffn.GroupStats({"经理A": rets_a, "经理B": rets_b, "House": rets_house})
stats.display()
```

**复用场景:** STEP 5.5 Manager Master Book,把同一经理管的多只产品并排,快速看一致性。


## quantstats (ranaroussi/quantstats, 7.5k★)

最活跃的净值分析库,但**不建议深度依赖**。原因:

- 它的 `weights` 参数只是用静态权重合成一条指数,不是持仓分析
- HTML 报告格式固定,和你的野兽派美学不兼容
- 没有归因能力

可以抄它的 `quantstats.stats` 模块里的单指标函数(和 empyrical 重叠度高),其余不用。


## akshare (akfamily/akshare, 21.9k★)

**必用,是你的数据地基。** 五个关键接口见 SKILL.md § 取数方式。

**不能复用的:** akshare 不做分析,只做数据获取。你的分析层(House Consensus / Divergence / 归因)全部自己写。


## Riskfolio-Lib / skfolio / PyPortfolioOpt

**不复用。** 它们是优化器,不是归因工具。Riskfolio 和 skfolio 有风险贡献分解,但那是 ex-ante 风险预算(用协方差矩阵算的),不是 ex-post 收益归因(用历史持仓算的)。


## 为什么不用 Brinson

GitHub 上最大的开源 Brinson 实现是 `ShiliangZhang-nku/Brinson-Attribution`(89★,2020 年停更,依赖 Wind)。其余全是 0-3 星的学生作业。

**没有生产级开源 Brinson 实现。**

而且你的场景不适合 Brinson:Brinson 需要**基准的行业权重**,但你的基准是 House Portfolio —— 一个动态合成的组合,行业权重本身就是要算的东西,不是给定的。

更合适的路径:直接算主动权重差(`w_m - w_h`),分个股层和行业层,不走配置/选股拆分。


## 总结

| 库 | 拿什么 | 用在哪 |
|---|---|---|
| pyfolio-reloaded | `perf_attrib` | STEP 7 剥离因子 beta |
| empyrical | 单指标函数 | STEP 8 / 11 算 Sharpe / DD 等 |
| ffn | `GroupStats` | STEP 5.5 并排展示 |
| akshare | 五个接口 | 全流程数据源 |

其余全部自建。
