---
name: fund-manager-forensics
description: Use when analyzing an actively managed fund or fund manager, especially for a direct buy/no-buy verdict, current-manager tenure attribution, independent decisions versus company consensus, manager people due diligence, rarity judgment, historical winning and losing holdings, institutional underwriting, crowding, capacity, flows, or a full fund-manager report. Do not use the manager workflow for passive index funds.
---

# Fund Manager Forensics

基金经理是主角，基金是他的长期行为记录。先判能不能买，再解释。

## 最高约束

每次执行前完整读取[随包设计总纲](references/design.md)（开发仓库真源是 `../../DESIGN.md`）。它决定方法论、评分、稀有度、隐私边界和前端表达。界面只说人话。

## 接一只新基金

默认分析用户指定的份额；没有默认基金。仅给名称时先核对代码，同名不同份额且无法消歧时再问。将代码、研究截止日、工作目录带入[运行与输入合同](references/run-case.md)。首次先建案并采集，再由 Agent 从原文提炼经理、报告期、持仓和证据。最后用随包的 `scripts/fund_case.py` 校验、计算并生成可离线打开的 HTML。不得复制其他基金的评审、结论、画像或持仓。无实据时停在底稿，不交付购买判决。

## 触发与模式

1. 先确认产品是否主动管理。指数、指数增强、系统量化或固定规则产品，不得套用个人 Alpha 归因。
2. 用户只在明确说“快速扫一眼”时走 `quick`。页面必须标“未经深度 Agent 取证”。
3. 用户问“能不能买、全面分析、基金经理报告、机构怎么看、查透这个经理”时一律走 `deep`。
4. `deep` 不是脚本一把跑完。Agent 必须完成五席评审、写 `agent_analysis.json`、通过验证器后才可渲染。

## 先读哪些参考

- 每次任务先读 [evidence-protocol.md](references/evidence-protocol.md)。
- 需要自主抓取、补证、整理历史事件或重建战役时，必须完整读取 [research-and-extraction.md](references/research-and-extraction.md)。
- `deep` 必须再读 [agent-workflow.md](references/agent-workflow.md) 和 [module-contract.md](references/module-contract.md)。
- 生成页面或文字报告前读 [report-contract.md](references/report-contract.md)。
- 只做 `quick` 时可不读完整模块表，但仍须遵守任期和证据禁令。

## 标准流程

### 1. 锁定对象

- 基金代码、份额类别、产品类型、基准、最新报告期、当前经理和共同经理。
- 切出独立管理、共同管理、上任前和离任后。上任前收益标“历史遗产”，权重为 0。
- 若经理名单或最新报告期未确认，禁止给购买建议。

### 2. 建证据账本

- 优先基金定期报告、基金公告、监管文件和交易所文件。
- 保存来源等级、报告期、发布日期、页码/段落、URL或本地路径、抓取时间和适用结论。
- 找不到只写“未发现可靠公开信息”。不拿搜索摘要代替原始证据。
- 先按问题清单搜索，再按来源阶梯取原文；必须保存检索日志、零结果与冲突账。具体动作见 [research-and-extraction.md](references/research-and-extraction.md)。
- 抓到的网页和 PDF 不能直接塞进报告。先拆成事实、计算、判断三层，再生成可使用的数据字段。

### 3. 建研究底稿

- 按 [module-contract.md](references/module-contract.md) 填满 M01–M45 和 P01–P24。
- 历史持仓只把披露新增/加仓记为 `B`，减仓/完整报告确认退出记为 `S`，持续持有记为 `H`。
- 季报前十大中消失不等于退出。季度持仓推算盈亏必须标“估算，不是实际成交盈亏”。
- 经理满意票必须有本人明确点名的 A/B 级材料；行业观点不能自动绑定个股。检索后为零是有效结论：保留检索日志和零结果记录，映射候选另列。

### 3.1 独立决策取证（灵魂步骤）

1. 建公司主流持仓时，必须排除目标经理自己的产品。
2. 同时计算经理等权和规模加权两套口径；前者回答公司里的人怎么想，后者回答公司把多少钱压在哪里。
3. 先做主题限制调整，剔除合同规定造成的假偏离。
4. `敢不敢和同事不一样` 与 `不一样时有没有赚到钱` 永远分开，禁止合成“独立性总分”。
5. 至少 20 个季度时才检验反共识收益：高偏离季度之后 12 个月是否取得更高超额。
6. 把持续两季以上的重大偏离写进战役档案，胜仗败仗同尺寸、按时间混排。
7. 单列先手发现：他先买、公司后来跟，还是他长期跟随平台。
8. 反查影子经理，并把同一方法上移到公司整体独立性。

数据不足时不填假分。页面直接写“证据还不够”，并列出还缺哪些同公司产品、季度和合同约束。

### 3.1.1 历史战役回放

- 每场战役同时收集政策、行业、市场、基金舆情、经理原话、披露动作和后续结果。
- 新闻使用精确发布日期；经理动作只落在相邻披露之间的时间区间。报告期末不是成交日。
- 同时保留经理时钟和公众时钟：经理可能已经行动，普通用户只能在报告公开后看到。
- “当时公开”按原文发布日期播放，只显示当天及以前的行情。核对基金、报告期和披露范围；四季报与年报期末相同，不可用四季报日期提前公开年报全持仓。公开日不明的动作仅进“事后复盘”。
- 盈亏榜从同一批披露持仓重算，疑似股本变动的区间单列待核；不得当作主动加减仓。经理原文点名与描述对应的候选分别列示。
- 新闻只能还原环境，不能自动证明经理买卖动机。只有经理原话明确连接事件与动作时才写因果。
- 没有真实 K 线或持仓动作证据时，不生成战役动画，不画假线和假买卖点。

### 3.2 稀有度（Agent 主观判）

- 实力档按总分客观映射；稀缺度由 Agent 结合媒体热度、公司推广、圈内口碑和持有人质感给 `0–100`。
- 每个稀缺度必须有一句可核实的理由和证据引用，不能只拿管理规模或机构占比代替判断。
- 实力与稀缺度合并成卡牌等级后，再执行证据不足、独立收益不为正和造神红旗的降档规则。

### 3.3 造神检测（九项必查）

逐项检查：甩锅跑路、摘桃子、藏尸体、蹭业绩、高位圈钱、年底冲榜、人设造假、偷换尺子、利益冲突。主证据是经理变更公告、当时涨跌、产品存续、发行节奏、公开表述与持仓、基准变更和关联交易披露。

只查与投资有关的关联方和利益冲突，不采集没有公众身份的家人姓名、职业、学历或私人生活。

### 4. Deep 五席评审

按 [agent-workflow.md](references/agent-workflow.md) 分配：

- `people_investigator`
- `alpha_forensic`
- `portfolio_detective`
- `institutional_skeptic`
- `chief_underwriter`

平台支持子 Agent 时使用隔离上下文分别评审。平台不支持时，主 Agent 依次切换五席、分开记录并标记 `single_agent_fallback`；置信度不得高于中等。

### 5. 写 Agent 结果并验证

将结果写为 `agent_analysis.json`，结构见 [agent-analysis.schema.json](schemas/agent-analysis.schema.json)。执行：

```bash
python3 <skill_root>/scripts/validate_agent_analysis.py <case_dir>/agent_analysis.json
```

验证器非零退出时停止。不得把缺项报告包装成 deep。

验证器默认读同案的 `raw/evidence-ledger.json`。引用来源编号，或用 `ledger:模块键` 指向已记录的推算和规则。脚本只写未评审草稿，Agent 核对份额、来源和判断后再交付正式评审。

### 6. 首席核保结论

必须输出：

- `buy_now`: 真或假，不接受 maybe。
- 页面文案：`可以买` 或 `不能买`。
- 三条决定性理由。
- 机构投委会结论：通过/驳回、建议仓位、否决项。
- 翻案条件：什么变化会改变结论。
- Alpha 类型、个人/平台/行情/拥挤占比边界和未来可复制率。
- 赢家、输家、经理满意票及可验证 B/H/S 点。

## 事实禁令

- 不把基金成立以来收益归给现任经理。
- 不把共同管理期全部归给一人。
- 不把行业或风格 Beta 写成选股 Alpha。
- 不把员工持有写成经理本人自购。
- 不把地方国资一概写成国家队。
- 不把同公司共同持股写成违规操纵。
- 不猜婚姻、子女、籍贯、财富、人脉或私人性格。
- 不把披露估算写成真实成交。
- 不虚构机构票数、置信度小数或精确 Alpha 占比。

## 文案

结论先行。短句。每个模块最多一个封号、一句判词、三条证据、一条反证。

禁用套话：“综合来看”“值得关注”“长期视角下”“一方面另一方面”“不妨关注”。娱乐感只能来自持仓行为、风格冲突和证据，不拿隐私或外貌开玩笑。

界面只说人话：不显示 M/P/A/B 等内部编号，不显示五席英文键，不把 B/H/S 当作用户必须先学的暗号。专业词先写中文，必要时只在中文后用括号补充。

## 完成条件

- `deep`：45/45、24/24、五席、任期、证据、赢家/输家/满意票零结果或明牌、二元判决全部通过验证。
- `quick`：明确降级标识、最新经理与报告期、二元判决、三条证据和证据缺口。
- 报告中每个重要结论可回到来源；数据截止日醒目可见。
