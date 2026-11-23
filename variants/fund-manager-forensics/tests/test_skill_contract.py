from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "fund-manager-forensics"


class SkillContractTest(unittest.TestCase):
    def test_canonical_skill_has_minimal_frontmatter(self):
        path = SKILL_ROOT / "SKILL.md"
        self.assertTrue(path.is_file(), f"missing {path}")
        text = path.read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.S)
        self.assertIsNotNone(match, "missing YAML frontmatter")
        lines = [line for line in match.group(1).splitlines() if line.strip()]
        keys = {line.split(":", 1)[0].strip() for line in lines}
        self.assertEqual(keys, {"name", "description"})
        self.assertIn("name: fund-manager-forensics", lines)

    def test_module_contract_covers_45_fund_modules_and_24_people_fields(self):
        text = (SKILL_ROOT / "references" / "module-contract.md").read_text(encoding="utf-8")
        modules = set(re.findall(r"\bM(?:0[1-9]|[1-3][0-9]|4[0-5])\b", text))
        people = set(re.findall(r"\bP(?:0[1-9]|1[0-9]|2[0-4])\b", text))
        self.assertEqual(len(modules), 45)
        self.assertEqual(len(people), 24)

    def test_agent_workflow_has_four_independent_seats_and_chief(self):
        text = (SKILL_ROOT / "references" / "agent-workflow.md").read_text(encoding="utf-8")
        for role in (
            "people_investigator",
            "alpha_forensic",
            "portfolio_detective",
            "institutional_skeptic",
            "chief_underwriter",
        ):
            self.assertIn(role, text)
        self.assertIn("45/45", text)
        self.assertIn("24/24", text)

    def test_reference_files_are_routed_from_skill(self):
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        for name in (
            "agent-workflow.md",
            "evidence-protocol.md",
            "module-contract.md",
            "report-contract.md",
        ):
            self.assertIn(name, skill)
            self.assertTrue((SKILL_ROOT / "references" / name).is_file())

    def test_zero_explicit_manager_approved_stocks_never_forces_fabrication(self):
        report_contract = (SKILL_ROOT / "references" / "report-contract.md").read_text(encoding="utf-8")
        self.assertIn("零张满意票也可完成 Deep", report_contract)
        self.assertIn("检索日志", report_contract)
        self.assertNotIn("找不到满意票时不得伪造，应在 Deep 验证前明确补证或降级为 quick", report_contract)

    def test_independent_decision_method_is_complete_and_cannot_be_collapsed(self):
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        workflow = (SKILL_ROOT / "references" / "agent-workflow.md").read_text(encoding="utf-8")
        combined = skill + workflow
        for marker in (
            "排除目标经理自己的产品",
            "经理等权",
            "规模加权",
            "敢不敢和同事不一样",
            "不一样时有没有赚到钱",
            "永远分开",
            "主题限制调整",
            "反共识收益",
            "战役档案",
            "先手发现",
            "影子经理",
            "公司整体独立性",
        ):
            self.assertIn(marker, combined)

    def test_rarity_and_myth_checks_require_agent_judgment_with_evidence(self):
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        for marker in (
            "0–100",
            "一句可核实的理由",
            "甩锅跑路",
            "摘桃子",
            "藏尸体",
            "蹭业绩",
            "高位圈钱",
            "年底冲榜",
            "人设造假",
            "偷换尺子",
            "利益冲突",
        ):
            self.assertIn(marker, skill)

    def test_report_contract_forbids_internal_codes_and_naked_jargon(self):
        text = (SKILL_ROOT / "references" / "report-contract.md").read_text(encoding="utf-8")
        for marker in (
            "内部编号不得进入界面",
            "来源报告全名",
            "买入或加仓",
            "敢不敢和同事不一样",
            "不一样时有没有赚到钱",
            "中文后用括号补充专业词",
        ):
            self.assertIn(marker, text)

    def test_skill_routes_agents_to_a_complete_research_and_extraction_protocol(self):
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        protocol_path = SKILL_ROOT / "references" / "research-and-extraction.md"
        self.assertTrue(protocol_path.is_file())
        self.assertIn("research-and-extraction.md", skill)
        protocol = protocol_path.read_text(encoding="utf-8")
        for marker in (
            "先列问题，再找数据",
            "来源阶梯",
            "检索日志",
            "零结果",
            "报告期",
            "页码",
            "精确日期",
            "时间区间",
            "冲突账",
            "新闻不能证明买卖动机",
            "可用事实",
            "完成门槛",
        ):
            self.assertIn(marker, protocol)


if __name__ == "__main__":
    unittest.main()
