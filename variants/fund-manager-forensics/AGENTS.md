# Fund Manager Forensics Agent 入口

根目录 [`DESIGN.md`](DESIGN.md) 是产品、Skill、数据和前端的最高约束。任何实现开始前必须完整读取，发生冲突时以它为准。

处理主动基金、基金经理、任期归因、Alpha/Beta、历史持仓、机构视角或买卖判断时，再完整读取：

`skills/fund-manager-forensics/SKILL.md`

所有执行规则只存在于该 canonical Skill。不要在本文件复制或改写规则。

常用验证：

```bash
python3 -m unittest discover -s tests -v
python3 skills/fund-manager-forensics/scripts/validate_agent_analysis.py <case>/agent_analysis.json
```
