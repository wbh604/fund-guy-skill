# Deep Agent 工作流

Deep 报告必须完成四席独立研究和一席首席核保。四席不能共享结论草稿后再改写。

## 1. people_investigator

负责 P01–P24、M04、M05、M12、M13、M20、M34。

交付：能力形成时间线、哲学指纹、行为模式、错误档案、先手发现、职业动机、家庭公开信息边界、合规人物风险。

独立决策部分必须与组合调查员协作完成：排除目标经理自己的产品，用经理等权与规模加权分别建公司主流持仓；做主题限制调整后，分别回答“敢不敢和同事不一样”和“不一样时有没有赚到钱”，两个答案永远分开。继续检查反共识收益、战役档案、先手发现、影子经理和公司整体独立性。

禁令：不猜学校、婚姻、子女、籍贯、财富、人脉、情绪或道德；采访只能证明他说过，持仓才能证明做过。

## 2. alpha_forensic

负责 M02、M06–M08、M14、M35、M36。

交付：任期段、牛熊/风格阶段、基准对比、Alpha/Beta 拆解、Top Winner Dependency、规模前后、尾部风险、未来可复制区间。

禁令：共同管理期不算个人全额；不能用精确小数伪装无法识别的 Alpha 分解。

## 3. portfolio_detective

负责 M09–M11、M16–M19、M21、M24、M33。

交付：披露持仓事件、赢家、输家、经理满意票、B/H/S 时间线、风格漂移、抱团、拥挤、影子经理、退出压力和经济暴露。

禁令：前十大消失不等于卖出；估算盈亏不是实际成交盈亏；观点未点名不能绑定股票。

## 4. institutional_skeptic

负责 M01、M15、M22、M23、M25–M32、M37、M43。

交付：产品识别、平台/团队、策略容量、持有人、申赎、资本五要素、机构变化、踩踏、合规、证据质量和投委会否决项。

禁令：员工持有不等于经理自购；地方国资不等于国家队；机构持有不等于未来收益。

## 5. chief_underwriter

负责 M03、M38–M42、M44、M45，并裁决四席冲突。

必须：

1. 先列冲突和双方证据，再选择一方或降置信度。
2. 给 `buy_now: true/false` 和 `可以买/不能买`。
3. 给三条理由、机构结论、建议仓位、否决项、翻案条件。
4. 区分经理个人、共同经理、平台、行业/风格和一次性收益。
5. 确认 45/45、24/24、任期、三类交易股票与证据账本。
6. 确认独立决策双分数没有合并；数据不足时保留空值并把缺口写成人话。
7. 亲自给出 0–100 稀缺度和一句可核实的理由，不得由规模公式代打。

## 运行方式

有子 Agent：四席可并行读取同一原始证据，不共享彼此结论；全部回来后由 chief_underwriter 合并。

无子 Agent：主 Agent 按上述顺序做五轮独立笔记，`single_agent_fallback: true`，最终置信度不得高于中等。

## agent_analysis.json 最小结构

```json
{
  "schema_version": "1.0.0",
  "analysis_mode": "deep",
  "agent_reviewed": true,
  "single_agent_fallback": false,
  "reviewers": {
    "people_investigator": {"reviewed": true},
    "alpha_forensic": {"reviewed": true},
    "portfolio_detective": {"reviewed": true},
    "institutional_skeptic": {"reviewed": true},
    "chief_underwriter": {"reviewed": true}
  },
  "manager_tenure": {
    "cut_complete": true,
    "current_manager": "姓名",
    "periods": [{"start": "YYYY-MM-DD", "end": null, "weight": 1.0}],
    "evidence_refs": ["A01"]
  },
  "module_reviews": {"M01": {}},
  "people_reviews": {"P01": {}},
  "trade_reviews": {"winners": [], "losers": [], "manager_approved": []},
  "conflicts": [],
  "verdict": {
    "buy_now": false,
    "label": "不能买",
    "institutional_view": "驳回核心仓申请",
    "reasons": ["理由"],
    "flip_conditions": ["条件"],
    "evidence_refs": ["A01"]
  }
}
```

## HARD GATE

生成 Deep 报告前必须：`agent_reviewed=true`、五席完成、任期切割完成、M01–M45 为 45/45、P01–P24 为 24/24、三类交易清单非空、重要结论有证据、`buy_now` 为布尔值。

运行 `scripts/validate_agent_analysis.py`。任何错误都要先修复，不得降级后继续标 Deep。
