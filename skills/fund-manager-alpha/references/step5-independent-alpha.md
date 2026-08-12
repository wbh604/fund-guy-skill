# STEP 5 · Independent Decision Alpha 算法细则

整个 Skill 的核心模块。目标是把 `Non-Consensus + Correct + Repeatable` 三段验证做成可复算的量化流程。

## 0. 术语

| 符号 | 含义 |
|---|---|
| `w_m(i,t)` | 目标经理在 t 期对标的/行业 i 的**主动权重**(持仓权重 − 基准权重) |
| `w_h(i,t)` | House Consensus 在 t 期对 i 的主动权重 |
| `D(t)` | t 期 House Divergence |
| `α_indep` | Independent Alpha,分化后产生的超额 |

**用主动权重,不要用绝对持仓权重。** 基准不同的两只基金,绝对权重没法比。

---

## 1. House Consensus Portfolio 构建

### 样本范围

纳入:同公司**全部主动权益**基金(普通股票型、偏股混合、灵活配置、平衡混合)。

排除:指数与指数增强 / 系统化量化 / 固定规则产品 / 纯债与一级债基 / QDII(市场不可比) / 成立不满 2 个季度的新基金 / **目标经理自己管的全部产品**。

> 最后一条是关键:算"公司共识"时若把目标经理自己算进去,他越极端共识越向他靠,Divergence 被系统性低估。管理规模占公司权益 20% 以上的经理,这个偏差足以让结论反转。

### 两套权重(都必须算)

```python
# AUM 加权:反映公司真金白银的方向
w_h_aum[i][t] = Σ_f (aum[f][t] * w_active[f][i][t]) / Σ_f aum[f][t]

# 经理等权:每位基金经理一票
#   1) 先把同一经理的多只产品按 AUM 合并成该经理的 book
#   2) 再对经理数取简单平均
w_h_eq[i][t] = mean over managers m of w_active_book[m][i][t]
```

### 必须输出的判读

```
AUM 口径   白酒 +13.2%
等权口径   白酒  +9.8%
背离度     3.4pp
```

背离 > 3pp 时必须在报告里写明:**表面共识来自少数明星经理的大资金,不是公司大多数人的共同观点。**

判读规则:

| AUM vs 等权 | 结论 |
|---|---|
| 两者都高 | 真共识,公司大多数人这么想 |
| AUM 高、等权低 | **伪共识**,少数大基金拉出来的 |
| AUM 低、等权高 | 小基金的共识,大资金没跟 |

计算 `D(t)` 时**默认用经理等权口径**(它才代表"公司里的人怎么想"),AUM 口径作为对照展示。

产出 `.cache/{code}/house_consensus.json`。

---

### 1.1 门派识别 —— 平均不等于共识

AUM/等权两套口径解决了"大基金绑架平均值",但还差一步:一家公司可能根本没有统一观点,而是存在多个门派。

```
公司一半经理重仓消费,另一半重仓科技
平均 → 消费 50% + 科技 50%(看着像"均衡共识")
目标经理重仓科技 → 与平均组合差异大
但公司里实际有一半人跟他站在一起
→ 他不是孤狼,只是科技派成员
```

### 1.1.1 算法

对每个季度 t:

```
1. 收集公司全部经理(经理等权口径,先合并同一经理的复制产品)的行业向量
   v_m = 经理 m 的行业主动权重向量
2. 排除:目标经理参与共管的任何产品(防止泄漏回对照组)
3. 聚类:
   - 用 Agglomerative 聚类,距离 = 1 - 行业向量余弦相似度
   - 最优簇数 k* 用 silhouette score 取 argmax(2 ≤ k ≤ min(8, n/3))
4. 门派属性:
   - 主门派 = 最大簇;同门共识强度 = 主门派内部两两平均相似度
   - 经理到最近门派质心的距离 = distance_to_nearest_faction
   - 经理到全公司平均组合的距离 = distance_to_avg
5. 判定:
   - consensus_strength ≥ 0.6 且 distance_to_nearest_faction ≥ 0.4 → 真正逆共识
   - consensus_strength < 0.4 且 经理属于某个簇(到质心 < 0.4)→ 派系成员
   - distance_to_nearest_faction ≥ 0.5 且 distance_to_avg ≥ 0.5 → 真正独立
```

### 1.1.2 两条配套硬规则

- 同一经理管理十只复制产品,合并后只算一票
- **任何目标经理参与共管的产品,都不能进入 House Consensus** —— 否则他的持仓重新泄漏进对照组

### 1.1.3 前台输出

公司门派图:消费派 8 人 / 科技派 5 人 / 均衡派 6 人 / 目标经理属于哪个。

判词:
> 他不是跟公司唱反调,而是公司内部本来就有一支科技派。
> 或:公司有三个门派,他和谁都不像,是真正的独立决策者。

### 1.1.4 产出

写入 `house_consensus.json` 的 `factions` 字段:
```json
{"n_clusters": 3,
 "factions": [{"name": "消费派", "size": 8}, {"name": "科技派", "size": 5}],
 "consensus_strength": 0.42,
 "manager_belongs_to": null,
 "distance_to_nearest_faction": 0.71,
 "distance_to_avg": 0.66,
 "verdict": "公司有三个门派,他和谁都不像,是真正的独立决策者"}
```

---

## 2. House Divergence Score

五个层面各算,再加权合成。

### 2.1 个股层面

用主动权重的 L1 距离,并归一:

```python
raw = Σ_i |w_m(i,t) - w_h(i,t)|
stock_div = 100 * min(1, raw / 2.0)   # 2.0 = 满分标定,即平均每边偏离 100%
```

同时报告重合度作为辅助读数:

```python
overlap = Σ_i min(w_m_abs(i), w_h_abs(i))   # 用绝对权重算重合
```

⚠️ 季报只有 Top10。个股层面**只能用半年报/年报全持仓期**计算,季报期标 `partial` 并只算行业层面。不要用 Top10 冒充全持仓。

### 2.2 行业层面

同上,按申万一级行业聚合后算 L1 距离,标定值取 1.2。

### 2.3 Style Factor 层面

对经理与 House 各跑一次因子暴露回归(市值/价值/成长/质量/动量/波动),取暴露向量的欧氏距离:

```python
factor_div = 100 * min(1, ||β_m - β_h||_2 / 2.5)
```

### 2.4 经济驱动层面(防伪分散)

把行业映射到经济驱动因子(地产链、出口链、消费复苏、科技资本开支、大宗商品、利率敏感、政策补贴…),再算分布距离。

**这一层专门抓伪分散**:经理持有 15 个行业看着很分散,但若全部映射到"地产链",他的真实暴露是单一的。House 若真分散,这一层的 divergence 会很高 —— 但那是经理更集中,不是更独立。因此:

> 经济驱动层的 divergence 必须标方向:`经理更集中` 还是 `经理更分散`。只有"经理暴露在 House 没暴露的驱动上"才算独立性正分。

### 2.5 A/H 市场层面

A 股 / 港股通 / 海外 的配置比例差。产品无港股通资格时此层跳过,不计入合成。

### 2.6 合成

```python
D(t) = 0.30*stock + 0.30*industry + 0.15*factor + 0.20*economic + 0.05*market
```

季报期(无全持仓)权重重分配为:industry 0.55 / factor 0.25 / economic 0.20。

---

## 3. Mandate 调整(最容易翻车的一步)

**在算 Divergence 之前**先做,不是之后修正。

### 3.1 抽取 Mandate 约束

从基金合同/招募说明书读:行业或主题限制 · 合同基准 · 股票范围(A/港股通/存托凭证) · 市值定位 · 股票仓位上下限 · 行业集中度上限。

### 3.2 构造 Mandate-Adjusted House Consensus

不要拿全公司当对照,拿**同 mandate 的对照组**:

```
对照组优先级:
1. 同公司 + 同基准 + 同类型的其他基金      ← 最优
2. 同公司 + 同类型(基准放宽)
3. 同公司全部主动权益 × mandate 掩码       ← 兜底
```

兜底做法:把经理 mandate 禁止的行业,从 House 组合里剔除后**重新归一**,再算 Divergence。

例:科技主题基金不能买白酒 → 把白酒等消费行业从 House 组合剔除、剩余权重归一化 → 再比较。这样"不买白酒"就不再贡献任何 Divergence,只有"在科技内部的选择差异"才计分。

### 3.3 强制披露

`mandate_adjusted` 与 `mandate_note` 是 `agent_analysis.json` 必填字段。写明:约束是什么、用了哪级对照组、调整前后 Divergence 各是多少。

```
调整前 D = 91  (含"不能买白酒"造成的假独立)
调整后 D = 63  ← 报告采用这个
```

**只报调整前的数字 = 造假。**

---

## 4. Contrarian Alpha —— 分化之后赚没赚钱

### 4.1 分组

取 ≥20 个季度。按 `D(t)` 分三组:

```
High     top 30% 分位
Mid      中间 40%
Low      bottom 30% 分位
```

样本 < 20 期时改为二分(高/低各 50%),并标 `low_sample: true`。

### 4.2 前瞻收益

对每个 t,计算 t+1 起 6M / 12M / 24M 的超额,对四个基准各算一次:

```
vs 合同 Benchmark
vs 同类基金中位数
vs Shadow Benchmark      ← 剥离风格后,最严格
vs House Portfolio       ← 直接回答"比公司其他人强多少"
```

**核心结论必须用 Shadow Benchmark 和 House Portfolio 两个口径**,合同基准太松。

### 4.2.1 多周期 + 自适应(不能只用固定 12M)

固定 12M 会误伤两类经理:
- 高换手经理:持仓三个月后已变,12M 收益不再对应原决策
- 长周期经理:产业判断需两三年兑现,12M 可能只是"早对但先亏"

所以:
- 算 6M / 12M / 24M 三个固定周期
- 再加一个与经理历史中位持有期匹配的**自适应周期**
- 前台只给一句人话:"他通常不是马上对,而是要熬 12—18 个月才兑现"

### 4.2.2 两只时钟 + 抄作业指数(硬规则)

每个经理都必须算两遍:

| 时钟 | 起点 | 回答 |
|---|---|---|
| **经理时钟** | 经理实际建立仓位的时点 | 他本人有没有先手能力 |
| **普通人时钟** | 季报/半年报真正公开之日 | 普通人看到再抄,还有没有收益 |

```
经理时钟 12M 超额: +14%
披露时钟 12M 超额: +2%
→ 他有先手,但抄不到
```

或:
```
经理时钟 +9% / 披露时钟 +7% → 判断兑现慢,季报仍有参考价值
```

### 4.2.3 判断正确 vs 最后赚钱 —— 四象限(硬规则)

每张战役卡必须给四象限,不只给"赢/输":

| 判断对 | 赚钱 | 判定 |
|---|---|---|
| 对 | 赚 | 真正好决策 |
| 对 | 没赚 | 买贵了/太早/执行有问题 |
| 错 | 赚 | **运气,不计入能力** |
| 错 | 亏 | 真正错误 |

> 例:经理判断行业利润下滑,基本面确实下滑,但股票因估值扩张继续涨。
> → 方向对但卖太早,执行拖累基本面判断。不算"经理错了",也不算"赢了"。
> 例:公司业绩恶化但题材炒作上涨,经理赚了钱。
> → 结果好、决策未必好,不能直接计入选股能力。

战役卡格式增加 `quadrant: {correct, made_money, verdict}` 字段。

### 4.3 Independent Alpha

```python
α_indep = mean(fwd_12m_alpha | D in High) - mean(fwd_12m_alpha | D in Low)
```

首页展示的两个数:

```
Alpha When Divergent   +7.2%    # High 组均值
Alpha When Consensus   +1.3%    # Low 组均值
```

### 4.4 显著性(防运气)

- Newey-West 调整 t 值(前瞻窗重叠会低估标准误,必须调)
- Bootstrap 1000 次抽样,报 `α_indep` 的 90% 区间
- 区间跨 0 → 结论降级为"未能证明",**禁止写成正结论**

### 4.5 反向情形

若 High 组反而更差,结论同等重要:

> **他的独立性是负资产。** 每次他偏离公司共识,平均比跟随公司差 X pp。

此时 Independent Alpha 子项给 0 分,Independent Thinking 按 §7 折算封顶 2 分。

---

## 5. Independent Calls 战役识别

### 5.1 筛选标准(四条全中才算"重大独立判断")

1. 单行业主动权重与 House 差 ≥ 5pp,或个股差 ≥ 3pp
2. 该偏离**连续维持 ≥ 2 个季度**(一期就撤的是噪声)
3. 偏离方向明确(超配或低配,不是横跳)
4. Mandate 允许该方向(否则是假独立)

### 5.2 胜负判定

以 t+12M 相对 **House Portfolio** 的超额为准:

```
> +5pp    win
-5 ~ +5   neutral（不计入 Hit Rate 分母，但要列出）
< -5pp    loss
```

### 5.3 Hit Rate 与赔率

```python
hit_rate = wins / (wins + losses)
win_avg  = mean(excess | win)
loss_avg = mean(excess | loss)
payoff   = abs(win_avg / loss_avg)
expectancy = hit_rate*win_avg + (1-hit_rate)*loss_avg
```

**赔率与期望值必须与 Hit Rate 同屏。** 63.6% 胜率配 2.3 倍赔率,远好过 80% 胜率配 0.4 倍赔率。

### 5.4 失败案例强制条款

- 失败案例与成功案例**同等篇幅、同等卡片尺寸**
- 若 `losses == 0`,必须给出检索日志,写明"已按 §5.1 标准全量扫描 N 个季度,未发现符合条件的失败案例",而不是留空
- 报告里失败卡不许折叠隐藏

---

## 6. Idea Origination · Lead / Lag

### 6.1 定义显著超配

```
个股:主动权重 ≥ +1.5pp  且 进入前十大
行业:主动权重 ≥ +3pp
```

### 6.2 时间戳

对每个标的/行业:

```
t_m      = 经理首次显著超配的报告期
t_house  = 公司经理中累计 ≥ 1/3 达到显著超配的报告期
lead(i)  = t_house - t_m        # 单位:季度,正数 = 领先
```

### 6.3 汇总

```python
avg_lead = median(lead(i) for i in significant_bets)   # 用中位数,抗异常值
lead_ratio = count(lead > 0) / count(all bets)
idea_origination = 50 + 50 * tanh(avg_lead / 2) * lead_ratio
```

三档:

| 条件 | 判定 |
|---|---|
| `avg_lead ≥ 2` 且 `lead_ratio ≥ 0.6` | **Idea Generator** |
| `-1 < avg_lead < 2` | 平台共创 |
| `avg_lead ≤ -1` 且 `lead_ratio < 0.4` | **Idea Consumer** |

### 6.4 关键陷阱

- **只统计后来被证明对的 bet = 幸存者偏差。** 领先进入然后亏钱的也必须计入 lead 统计,但在 §5 战役档案里记为 loss。领先和正确是两件事。
- 小基金天然掉头快,大基金调仓慢。经理管理规模显著小于公司均值时,lead 有天然优势,须在 note 里说明。
- 披露频率决定分辨率:季报只能分辨到季度,不要写"领先 1.7 个月"。

---

## 7. Independent Thinking 与 Independent Alpha 的折算关系

两个分数**永不合并**,但 Thinking 的计分受 Alpha 约束:

```python
thinking_raw = D_adjusted                      # 0-100
if independent_alpha_significant and α_indep > 0:
    thinking_score = 2.0 * thinking_raw/100    # 满分 2 分
else:
    thinking_score = min(2.0, 2.0*thinking_raw/100) * 0.5   # 折半,封顶 1 分
```

界面呈现规则:

| 情形 | 渲染 |
|---|---|
| Thinking 高 + Alpha 高 | 两条都 `--ok`,标 `独立型 Alpha 经理` |
| Thinking 高 + Alpha 低/负 | Alpha 条 `--danger`,标 `有主见,但主见没价值` |
| Thinking 低 + Alpha 高 | 标 `跟随中的精选者`(Alpha 来自选股不是偏离) |
| Thinking 低 + Alpha 低 | 标 `平台跟随者` |

---

## 8. Internal Alpha Leader 与影子经理

### 8.1 领袖图谱

对公司每位经理两两算 lead 关系,构造有向图(A → B 表示 A 平均领先 B ≥ 1 季度且重合度 > 0.3)。

出度显著高于入度、且覆盖 ≥ 3 个重要行业 → `Internal Alpha Leader`。**即使他不是投资总监。**

### 8.2 影子经理检测

反向查:目标经理是否长期滞后跟随某位核心经理。

```
对每位其他经理 j:
  corr_lag1 = 组合相似度(经理_t, 经理j_{t-1})
  若 corr_lag1 > 0.6 且 显著高于 corr_lag0
  → 疑似影子经理,标记 shadow_manager: "姓名"
```

命中影子经理时,Independent Thinking 直接封顶 40 分,并在 IC 结论列为否决候选项。

---

## 9. 基金公司层面独立性(STEP 5.10)

同一套方法上移一层,对照基准换成**全市场公募**:

```
company_vs_market_divergence = D(公司 House Portfolio, 全市场公募加权组合)
```

### 关键判读矩阵

| 经理 vs 公司 | 公司 vs 市场 | 结论 |
|---|---|---|
| 高 | 高 | **真正的独立经理**,公司也不抱团 |
| 高 | 低 | 经理在公司内独立,但**公司整体抱团** → 他可能只是在拥挤赛道里换了个车道 |
| 低 | 高 | 他跟随的是一家本身独立的公司,个人独立性无法识别 |
| 低 | 低 | **双重抱团**,最危险 |

第二行必须在报告里明写,否则用户会误以为"独立"等于"避开了市场拥挤"。

---

## 10. 数据不足时的降级

| 缺失 | 处理 |
|---|---|
| 公司全产品持仓拿不到 | **整个模块不能做**。写"未发现可靠公开信息",Independent Decision Alpha 全部子项计 0 并在首页标注,禁止用同类基金冒充 House |
| 全持仓期 < 10 期 | 只做行业层,个股层标 `insufficient` |
| 季度 < 12 期 | Contrarian Alpha 标 `low_sample`,禁止给显著性结论 |
| 经理只管 1 只产品 | Master Book 交叉验证不可用,`master_book_note` 写明,置信度下调一档 |
| 公司主动权益 < 5 只 | House Consensus 不稳健,Divergence 只作定性参考 |

---

## 11. 产出结构

`.cache/{code}/house_consensus.json`:

```json
{
  "universe": {"n_funds": 38, "n_managers": 21,
               "excluded": ["自身产品 1 只", "指数增强 4 只"]},
  "quarters": [
    {"period": "2020Q4",
     "aum_weighted": {"白酒": 13.2, "新能源": 1.2},
     "manager_equal": {"白酒": 9.8, "新能源": 2.1},
     "divergence_gap": 3.4,
     "consensus_type": "伪共识"}
  ]
}
```

`independence` 字段完整结构见 SKILL.md 的 `agent_analysis.json` 样例。

---

## 12. 自查清单

- [ ] House Consensus 已排除目标经理自己的产品
- [ ] AUM 与经理等权两套都算了,背离 > 3pp 时已判读伪共识
- [ ] Mandate 调整在算 Divergence **之前**做,调整前后数字都记录
- [ ] 个股层只用全持仓期,季报期未冒充
- [ ] 经济驱动层标了方向(更集中 / 更分散)
- [ ] Contrarian Alpha 用了 Shadow Benchmark 与 House 两个口径
- [ ] Newey-West + Bootstrap 都做了,区间跨 0 未写成正结论
- [ ] 战役筛选四条标准全部应用
- [ ] 失败案例已全量扫描,为空时有检索日志
- [ ] Hit Rate 旁边有赔率和期望值
- [ ] Lead 统计包含了"领先但亏钱"的 bet
- [ ] Thinking 与 Alpha 分开呈现,未合并成单一分数
- [ ] 影子经理已排查
- [ ] 公司 vs 市场独立性已算,四象限判读已写
