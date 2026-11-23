from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "skills" / "fund-manager-forensics" / "scripts" / "validate_agent_analysis.py"


def valid_analysis():
    seats = [
        "people_investigator",
        "alpha_forensic",
        "portfolio_detective",
        "institutional_skeptic",
    ]
    module_reviews = {}
    for index in range(1, 46):
        module_reviews[f"M{index:02d}"] = {
            "status": "已证实",
            "conclusion": f"模块 {index} 结论",
            "evidence_refs": ["A01"],
            "reviewer": seats[(index - 1) % len(seats)],
        }
    people_reviews = {}
    for index in range(1, 25):
        people_reviews[f"P{index:02d}"] = {
            "status": "已证实",
            "conclusion": f"People {index} 结论",
            "evidence_refs": ["B01"],
            "reviewer": "people_investigator",
        }
    return {
        "schema_version": "1.0.0",
        "analysis_mode": "deep",
        "agent_reviewed": True,
        "reviewers": {role: {"reviewed": True} for role in seats + ["chief_underwriter"]},
        "manager_tenure": {
            "cut_complete": True,
            "current_manager": "测试经理",
            "periods": [{"start": "2020-01-01", "end": None, "weight": 1.0}],
            "evidence_refs": ["A01"],
        },
        "manager_rarity": {
            "ability_score": 78,
            "ability_grade": "SR",
            "scarcity_score": 18,
            "scarcity_reason": "公开访谈多、公司长期重点宣传，已经没有明显信息差。",
            "exposure_level": "顶流",
            "card_rarity": "SR",
            "product_grade": "R",
            "confidence": "中",
            "punchline": "能力稀缺，信息差已经消失。",
            "judgment": "研究能力仍稀缺；明星效应、百亿规模与共同管理使产品不再具备小众信息差。",
            "evidence_refs": ["A01", "A02", "A03", "B02", "C02"],
            "evidence": [
                "合成记录：经理曾负责企业研究。",
                "合成记录：产品规模高，受市场关注。",
                "合成记录：共同管理期需单独评估。",
            ],
            "counterevidence": "公开数据不足以拆分个人Alpha、平台Alpha与共同管理贡献。",
        },
        "independent_decision": {
            "status": "未证明",
            "house_consensus": {
                "self_excluded": True,
                "manager_equal": None,
                "aum_weighted": None,
                "conclusion": "还缺同公司主动权益基金的逐季持仓。",
            },
            "mandate_adjustment": {
                "completed": False,
                "conclusion": "还缺产品合同主题限制。",
            },
            "thinking": {
                "score": None,
                "conclusion": "证据还不够，不能判断他是否长期和同事不同。",
            },
            "alpha": {
                "score": None,
                "conclusion": "证据还不够，不能判断分化后是否赚钱。",
            },
            "contrarian_alpha": "未完成",
            "battles": [],
            "idea_origination": "未证明",
            "shadow_manager": "未证明",
            "company_independence": "未证明",
            "missing_data": ["同公司主动权益基金至少20个季度持仓"],
            "evidence_refs": ["C01"],
        },
        "module_reviews": module_reviews,
        "people_reviews": people_reviews,
        "trade_reviews": {
            "winners": [{"name": "赢家", "status": "估算", "evidence_refs": ["A01"]}],
            "losers": [{"name": "输家", "status": "估算", "evidence_refs": ["A01"]}],
            "manager_approved": [{"name": "满意票", "status": "已证实", "evidence_refs": ["B01"]}],
        },
        "conflicts": [],
        "verdict": {
            "buy_now": False,
            "label": "不能买",
            "institutional_view": "驳回核心仓申请",
            "sentence": "不能买；风险补偿不够。",
            "reasons": ["风险没有补偿"],
            "flip_conditions": ["集中度下降"],
            "evidence_refs": ["A01"],
        },
    }


class AgentContractTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue(VALIDATOR.is_file(), f"missing {VALIDATOR}")

    def run_validator(self, payload):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "agent_analysis.json"
            (path.parent / "raw").mkdir()
            (path.parent / "raw" / "evidence-ledger.json").write_text(json.dumps({"sources": [{"id": s} for s in ("A01","A02","A03","B01","B02","C01","C02")]}))
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            return subprocess.run(
                ["python3", str(VALIDATOR), str(path)],
                text=True,
                capture_output=True,
                check=False,
            )

    def test_complete_deep_analysis_passes(self):
        result = self.run_validator(valid_analysis())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_unknown_reference_rejected_even_with_real_source(self):
        payload = valid_analysis()
        payload["verdict"]["evidence_refs"] = ["A01/Z99"]
        result = self.run_validator(payload)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Z99", result.stdout)

    def test_deep_gate_rejects_unreviewed_output(self):
        payload = valid_analysis()
        payload["agent_reviewed"] = False
        self.assertNotEqual(self.run_validator(payload).returncode, 0)

    def test_deep_gate_rejects_non_boolean_verdict(self):
        payload = valid_analysis()
        payload["verdict"]["buy_now"] = "maybe"
        self.assertNotEqual(self.run_validator(payload).returncode, 0)

    def test_deep_gate_requires_a_case_specific_verdict_sentence(self):
        payload = valid_analysis()
        payload["verdict"].pop("sentence")
        self.assertNotEqual(self.run_validator(payload).returncode, 0)

    def test_deep_gate_rejects_missing_module_people_evidence_and_tenure(self):
        mutations = []
        payload = valid_analysis(); payload["module_reviews"].pop("M45"); mutations.append(payload)
        payload = valid_analysis(); payload["people_reviews"].pop("P24"); mutations.append(payload)
        payload = valid_analysis(); payload["module_reviews"]["M01"]["evidence_refs"] = []; mutations.append(payload)
        payload = valid_analysis(); payload["manager_tenure"]["cut_complete"] = False; mutations.append(payload)
        for payload in mutations:
            self.assertNotEqual(self.run_validator(payload).returncode, 0)

    def test_deep_gate_requires_all_four_seats_and_chief(self):
        payload = valid_analysis()
        payload["reviewers"].pop("institutional_skeptic")
        self.assertNotEqual(self.run_validator(payload).returncode, 0)

    def test_deep_gate_requires_agent_judged_manager_rarity(self):
        payload = valid_analysis()
        payload.pop("manager_rarity")
        result = self.run_validator(payload)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("manager_rarity", result.stdout)

    def test_manager_rarity_requires_supported_grades_and_three_evidence_lines(self):
        mutations = []
        payload = valid_analysis(); payload["manager_rarity"]["ability_grade"] = "S+"; mutations.append(payload)
        payload = valid_analysis(); payload["manager_rarity"]["exposure_level"] = "网红"; mutations.append(payload)
        payload = valid_analysis(); payload["manager_rarity"]["confidence"] = "大概"; mutations.append(payload)
        payload = valid_analysis(); payload["manager_rarity"]["evidence"] = ["只有一条"]; mutations.append(payload)
        for payload in mutations:
            self.assertNotEqual(self.run_validator(payload).returncode, 0)

    def test_manager_rarity_requires_objective_score_and_agent_scarcity_reason(self):
        mutations = []
        payload = valid_analysis(); payload["manager_rarity"].pop("ability_score"); mutations.append(payload)
        payload = valid_analysis(); payload["manager_rarity"]["scarcity_score"] = 101; mutations.append(payload)
        payload = valid_analysis(); payload["manager_rarity"]["scarcity_reason"] = ""; mutations.append(payload)
        for payload in mutations:
            result = self.run_validator(payload)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("manager_rarity", result.stdout)

    def test_deep_gate_requires_separate_independent_thinking_and_alpha(self):
        payload = valid_analysis()
        payload.pop("independent_decision")
        self.assertNotEqual(self.run_validator(payload).returncode, 0)

        payload = valid_analysis()
        payload["independent_decision"]["score"] = 82
        result = self.run_validator(payload)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must not merge", result.stdout)

    def test_unproven_independence_requires_explicit_missing_data(self):
        payload = valid_analysis()
        payload["independent_decision"]["missing_data"] = []
        result = self.run_validator(payload)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing_data", result.stdout)


if __name__ == "__main__":
    unittest.main()
