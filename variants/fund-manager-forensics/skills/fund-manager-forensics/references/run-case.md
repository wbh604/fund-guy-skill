# 从空目录到报告

需要 Python 3.10+，标准库即可。工作区放在用户指定位置，不写入安装目录。下列命令的 CODE 是六位**份额代码**。报告期末与原文公开日分开；历史研究以 AS_OF 当天可见的证据为限。

1. 建案：`python3 <skill>/scripts/fund_case.py CODE --workspace ROOT --case SLUG --init --as-of AS_OF --collect-nav`。缺省 SLUG 为代码；同基金不同截面用不同 SLUG。断网后仅重跑 `--collect-nav`，不重建或覆盖研究。
2. 在 `ROOT/SLUG/case.json` 填写实际的 fund.short_name、share_class（无分级记“单一份额”）、management（确认主动才填 active）、subject、managers（name、start_date，可有 end_date）、report_date、identity_refs。snapshot 是指标字典，top_holdings 使用 name、code、weight_pct（占净值百分数）。未查到的项留空，不照搬样例。
3. 在 `raw/evidence-ledger.json` 填 meta.fund_code、evidence_cutoff（报告期末）、retrieved_at。sources 每条有 id（如 A01）、grade、title、url、published_at、page_or_paragraph。身份引用须指向法定原文。modules、people 是字段字典，每条可有 conclusion、status、value、evidence_ref。家庭无可靠公开资料时不采集。将检索记录、反证、冲突和零结果留在本案。
4. 从报告表格提炼 `raw/holdings-disclosed.json`：顶层 fund_code 和按期末升序的 periods；每期包含 period（如 2025Q3、2025FY）、report_date、published_at、evidence_ref、is_complete、holdings。holdings 按证券代码索引，值含 name、shares（股）、market_value（人民币元）、weight_pct。四季报可以使用 FY 期末标签，但 is_complete 仍为 false。未证实是全量明细不可标 true。期初、期末与管理人变更日期不能混用。
5. 明确点名与推测分别写进 `raw/manager-statements.json` 的 explicit_named_stocks 和 cases，每条带 code、name、manager_statement、evidence_refs 和定位；明确点名须引用 A/B 级来源；顶层带 fund_code、conclusion。事件如有，写 `raw/historical-events.json`，带 fund_code、events 和 search_log。两者均可缺；“未提交”不等于“查完为零”。对已有持仓估算/点名股可用 `--collect-prices` 取得有市场路由的周K，失败见 raw/price-gaps.json，不画替代曲线。
6. 快报：按本案事实完成 quick_review.draft.json，填写三条理由、机构视角、翻案条件、来源、缺口，自行复核后另存 quick_review.json，agent_reviewed 才设 true。运行 `python3 <skill>/scripts/fund_case.py CODE --workspace ROOT --case SLUG --mode quick`，打开 quick.html。
7. 深度：完成 agent_analysis.draft.json 及[五席评审](agent-workflow.md)，稀有度和独立性字段见[完整结构](../schemas/agent-analysis.schema.json)。评审与案例必须同份额、同研究日、同目标经理。另存 agent_analysis.json，再用同一命令的 `--mode deep` 生成 report.json 和 report.html。缺深度评审时命令报错，不自动改成快报。

另有可选的 `--collect-holdings --from-year YYYY`，需要 Python 环境已有 requests 和 beautifulsoup4；没有依赖时可直接走第 4 步。输出 holdings-provider.draft.json 仅是数据库候选，不会覆盖已核对的 holdings-disclosed.json。核对代码、公开日、数量单位和季报/年报范围后才能转入正式账。

命令不会凭代码推断“可以买”。净值是**单位净值**，不可将跨分红的变化称作投资者总回报；比较业绩使用法定报告的净值增长率与同期基准。五种历史美术样张不随通用报告加载，避免把样例人物、判词带到新基金。
