# 竞品调研总结 · 2026-08

## TL;DR

**你要做的事,开源世界没有人做。** 五个核心关键词(active share holdings / fund holdings overlap / portfolio crowding / herding / fund manager skill)在 GitHub 搜索结果全部为零(≥15 星仓库数)。

数据侧 akshare 覆盖度比预期好,能拿到 2.5/3 样关键数据。半年报全持仓仍需自己解析 PDF。

pyfolio-reloaded 的因子归因(`perf_attrib`)可以复用,但 Non-Consensus / 决策级归属 / 跨期模式统计这三层必须自建。

---

## 现有库的结构性盲区

所有通用量化库(pyfolio / quantstats / ffn / Riskfolio / skfolio)共享三个盲区:

### 1. 分析单元是"组合",不是"管理组合的人"

组合在这些库眼里是匿名的、无历史的、孤立的 —— 没有"这个人还管过别的产品"、"这个决策他以前也做过"、"同期其他人怎么做的"这些概念。

你的 Non-Consensus(需横截面对照)、Correct(需决策归属)、Repeatable(需时序模式)三个维度,全部落在这个分析单元之外。

### 2. 归因是"期间可加分解",不是"事件级归属"

pyfolio 的 `perf_attrib` 每天独立算因子暴露,把某段收益拆到因子上。但它没有"决策"这个概念。

你要的是:识别「2020Q2 低配白酒超配新能源」这个离散动作 → 锚定在决策时点 → 追踪 12 个月后的相对贡献。

这需要三件现有库都没有的能力:
- 从持仓变化中识别决策事件
- 把"公司主流观点"定义成对照基准
- 归因窗口锚在决策时点而非日历期间

### 3. 没有"对照组"的概念

所有库的基准都是指数或另一条净值曲线。**没有任何库支持"用同公司其他经理的持仓合成一个基准"**。

而这正是 House Consensus 的全部内容 —— 也是判断"他敢不敢不一样"的唯一办法。

---

## 值得知道的六个项目

| 项目 | 星 | 状态 | 它到底做了什么 |
|---|---:|---|---|
| **akshare** | 21.9k | 活跃(3天前) | 中国金融数据总入口,本 Skill 的地基 |
| quantstats | 7.5k | 活跃(20天前) | 净值层统计报表,无归因 |
| ffn | 2.6k | 活跃(2天前) | 多条净值并排比较,`GroupStats` 能出并排表 |
| **pyfolio-reloaded** | 604 | 半停(237天) | **唯一做持仓层因子归因的**,`perf_attrib` 可复用 |
| investool | 2.2k | 半停(428天) | Go,做了基金持仓相似度,但是基金间两两比,不是经理间 |
| who-is-the-best-manager | 26 | 活跃(47天前) | 手工挑选四位经理可溯源对比,Claude Skill 形态,方向最接近但不可规模化 |

原版 quantopian/pyfolio 已停更 961 天、166 个未处理 issue,stefan-jansen 的 `-reloaded` 系列(pyfolio / empyrical / alphalens)是现在的事实标准。

Brinson 归因最大的开源实现是 89 星、2020 年停更、还依赖 Wind。**没有生产级开源 Brinson 实现。**

---

## 数据侧:akshare 能拿到 2.5 样

三样关键数据,akshare 能拿到 **2.5 样**:

| 需要 | 接口 | 能拿到吗 |
|---|---|---|
| 逐季持仓 | `fund_portfolio_hold_em` | ✅ 比预期好,一次调用拿全年四季度 |
| 经理变更公告 | `fund_announcement_personnel_em` | ⚠️ 能拿,**但只有标题+日期**,要正则抽人名或取全文 |
| 公司全部产品 | `fund_manager_em` groupby 公司 | ⚠️ 只反映**当前在任**,历史离任经理管过的产品会漏 |
| 半年报全持仓 | — | ❌ 得自己解析 PDF |

### 两个意外发现

**1. "增聘"公告是甩锅自动线索**

`fund_announcement_personnel_em` 的公告标题**区分"调整"和"增聘"** —— 下跌期标题含"增聘"且接任者从业 < 2 年,往往就是甩锅前兆。

这比原本设想的手工核对公告省事得多,造神检测的主证据链能自动化一半:标题"增聘" + 回撤数据可自动筛出红旗候选,剩下的人工核对。

**2. 横截面接口效率高一个量级**

`fund_report_stock_cninfo(date="20210630")` 走巨潮,返回的是**横截面**(某报告期全市场基金持股)。

算全市场拥挤度不用逐只循环,直接一次拿到 —— 构建 House Consensus 时如果要用全公司产品(>50 只),走这个比循环 `fund_portfolio_hold_em` 快得多。

### 反爬是真实问题

akshare issues 里"频率限制"、东财接口失效反复出现,社区有个专门补丁 `akshare-proxy-patch`(184 星,2026-08 还在更新)。

必须自建缓存层 + 随机延时 0.8–2.5 秒,失败不重试超过 3 次。大批量任务(>50 个标的)改走横截面接口。

---

## 中文基金项目停在哪

绝大多数是净值追踪、4433 筛选、收益率排名。搜"基金持仓"出来 15 个仓库,除 investool 外**全部 ≤15 星**,多为个人记账工具。

天花板不在"净值排名",而在"单期持仓快照展示"。

真正没人做的是**跨期行为序列 + 相对同公司基准的偏离度** —— 也就是"敢不敢不一样、不一样时对不对"。这个空白是真的。

---

## 可复用的东西(只有两块)

**1. pyfolio-reloaded 的 `perf_attrib`**

作为"这次超额是 beta 还是 alpha"的过滤器。输入日度持仓 + 因子收益 + 因子暴露,输出 common_returns(因子解释部分)和 specific_returns(alpha)。

用在 STEP 7 Alpha 尸检的第一步 —— 剥离因子部分,剩下的才是真 alpha。

**2. empyrical / ffn 的指标计算**

Sharpe / Sortino / Max DD / Calmar / tail ratio 等。用在 STEP 8 能力徽章、STEP 11 Forward Alpha。

**不要用它们的 `benchmark` 参数** —— 那是指数基准,不是你的 House Portfolio。

---

## 为什么不用 Brinson

Brinson 需要**基准的行业权重**,但你的基准是 House Portfolio —— 一个动态合成的组合,行业权重本身就是要算的东西,不是给定的。

更合适的路径:直接算主动权重差(`w_m - w_h`),分个股层和行业层,不走配置/选股拆分。

---

## 对 Skill 设计的影响

**1. 数据层直接用 akshare 指定接口**

之前写"不要写爬虫脚本,agent 自己去查"的判断需要修正一半:akshare 覆盖度够,持仓和公告都有稳定接口 —— 这部分该直接调库。

但"公司产品清单只反映当前在任"这个偏差是真的,历史 House Consensus 必须用公告数据回补,这一步仍要 agent 判断。

**2. PDF 全持仓解析绕不过去**

个股层 Divergence 只能用半年报/年报全持仓,而这块没有现成接口。

**3. 造神检测能半自动化**

"增聘"公告 + 回撤数据 → 自动筛出甩锅候选 → 剩下的人工核对。能省掉 70% 手工。

**4. 三层核心逻辑必须自建**

Non-Consensus 的横截面对照、决策事件识别、Repeatable 的模式统计,没有轮子可造重复。

---

## 搜索记录

使用的查询词:

```
performance attribution portfolio
factor model returns attribution
fund performance analysis
active share holdings
fund holdings overlap
portfolio crowding
herding institutional holdings
fund manager skill
基金 公募 fund 基金经理 持仓 holdings akshare tushare A股
```

每个词跑 `gh search repos --limit 40`,按星数 / 最后 push 时间 / issue 活跃度筛选。

交叉验证了 agent 报告的六个关键项目的元数据。
