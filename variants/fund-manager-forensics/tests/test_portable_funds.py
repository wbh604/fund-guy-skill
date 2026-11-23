import json
from importlib import import_module
from pathlib import Path
import os
from hashlib import sha256
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile

from tests.test_agent_contract import valid_analysis

ROOT = Path(__file__).resolve().parents[1]
api = import_module("skills.fund-manager-forensics.scripts.fund_case")
installer = import_module("scripts.install_skill")


class PortableFundTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.folder = self.root / "research" / "unlisted"
        self.code = "000019"
        api.init(self.folder,self.code,"2025-01-27")
        self.m = api.read(self.folder/"case.json")
        self.m.update(management="active",subject="测试经理",report_date="2024-12-31",
                      managers=[{"name":"测试经理","start_date":"2024-05-01"}],identity_refs=["A01"])
        self.m["fund"].update(short_name="合成测试基金",share_class="C")
        self.put("case.json",self.m)
        self.ledger = api.read(self.folder/"raw/evidence-ledger.json")
        self.ledger["meta"]["evidence_cutoff"] = self.m["report_date"]
        self.ledger["sources"] = [{"id":k,"grade":k[0],"title":k+"测试文件","published_at":"2025-01-27","url":"https://example.org/report"} for k in ("A01","A02","A03","B01","B02","C01","C02")]
        self.put("raw/evidence-ledger.json",self.ledger)
        periods = []
        for day,period,up,down in [("2024-03-31","2024Q1",9999,2000),("2024-06-30","2024H1",1000,1000),("2024-12-31","2024FY",1200,800)]:
            periods.append({"report_date":day,"period":period,"is_complete":False,"holdings":{
              "000001":{"name":"赢家","shares":100,"market_value":up},
              "000002":{"name":"输家","shares":100,"market_value":down}}})
        self.put("raw/holdings-disclosed.json",{"fund_code":self.code,"periods":periods})
        self.a = valid_analysis()
        self.a.update(fund_code=self.code,as_of=self.m["as_of"])
        self.a["verdict"].update(buy_now=True,label="可以买",sentence="通过测试条件",reasons=["一","二","三"])
        self.put("agent_analysis.json",self.a)

    def put(self,name,value):
        (self.folder/name).write_text(api.dump(value),encoding="utf8")

    def test_unlisted_c_share_deep_can_reach_opposite_verdict(self):
        self.assertEqual(api.case_path(self.folder.parent,self.code),self.folder)
        r = api.build(self.folder,self.code,"deep")
        self.assertTrue(r["verdict"]["buy_now"])
        self.assertEqual(r["fund"]["share_class"],"C")
        self.assertEqual(r["meta"]["coverage"]["holding_periods"],2)
        self.assertEqual(r["trade_ledger"]["winners"][0]["estimated_pnl"],200)
        self.assertEqual(r["trade_ledger"]["losers"][0]["estimated_pnl"],-200)
        html = api.render(r)
        self.assertIn("合成测试基金",html)
        self.assertIn("测试经理",html)

    def test_refuses_wrong_share_date_manager_passive_and_future_evidence(self):
        for field,value in [("fund_code","000020"),("as_of","2025-01-28")]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.put("agent_analysis.json",{**self.a,field:value})
                api.build(self.folder,self.code,"deep")
        self.put("agent_analysis.json",self.a)
        for key,value in [("management","index"),("subject","另一位")]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.put("case.json",{**self.m,key:value})
                api.build(self.folder,self.code,"deep")
        self.put("case.json",self.m)
        self.ledger["sources"][0]["published_at"] = "2025-01-28"
        self.put("raw/evidence-ledger.json",self.ledger)
        with self.assertRaisesRegex(ValueError,"发布日"):
            api.build(self.folder,self.code,"deep")

    def test_duplicate_cutoffs_require_explicit_selection(self):
        second = self.folder.parent/self.code
        second.mkdir()
        (second/"case.json").write_text(api.dump(self.m))
        with self.assertRaisesRegex(ValueError,"多个"):
            api.case_path(self.folder.parent,self.code)
        self.assertEqual(api.case_path(self.folder.parent,self.code,"unlisted"),self.folder)

    def test_installed_zip_offline_renders_only_reviewed_synthetic_case(self):
        archive = installer.build_workbuddy_package(self.root/"dist")
        with ZipFile(archive) as z:
            z.extractall(self.root/"installed")
        skill = self.root/"installed"/"fund-manager-forensics"
        self.assertTrue((skill/"references/design.md").is_file())
        inventory = json.loads((skill/"PACKAGE-MANIFEST.json").read_text())["files"]
        for name, digest in inventory.items():
            self.assertEqual(sha256((skill/name).read_bytes()).hexdigest(), digest)
            self.assertEqual((skill/name).read_bytes(), (ROOT/"skills"/skill.name/name).read_bytes())
        target = self.folder
        command = [sys.executable,"-E","-s",str(skill/"scripts/fund_case.py"),self.code,"--workspace",str(target.parent)]
        env = {**os.environ,"PYTHONPATH":""}
        good = subprocess.run(command+["--mode","deep"],cwd=self.root,env=env,capture_output=True,text=True)
        self.assertEqual(good.returncode,0,good.stderr)
        html = (target/"report.html").read_text()
        self.assertIn("测试经理",html)
        self.assertIn("合成测试基金",html)
        bad = subprocess.run(command+["--mode","quick"],cwd=self.root,env=env,capture_output=True,text=True)
        self.assertNotEqual(bad.returncode,0)
        self.assertFalse((target/"quick.html").exists())
