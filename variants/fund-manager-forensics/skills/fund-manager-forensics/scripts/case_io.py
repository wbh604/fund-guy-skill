"""Assemble only the supplied case directory; never import a showcase."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict
if __package__:
    from .fund_metrics import (MODULE_TITLES, PEOPLE_TITLES, empty_case, estimate_holding_pnl,
                               analyze_nav, build_battle_replays, _rank_outcomes, _range_return)
else:
    from fund_metrics import (MODULE_TITLES, PEOPLE_TITLES, empty_case, estimate_holding_pnl,
                              analyze_nav, build_battle_replays, _rank_outcomes, _range_return)


def build_case_from_cache(data_root: Path) -> Dict[str, Any]:
    """Assemble the single renderable case snapshot from audited local caches."""

    raw_root = data_root / "raw"
    def optional(name, default):
        path = raw_root / name
        return _read_json(path) if path.exists() else default
    current = _read_json(data_root / "case.json")
    ledger = _read_json(raw_root / "evidence-ledger.json")
    code = current["fund"]["code"]
    holdings = optional("holdings-disclosed.json", {"fund_code": code, "periods": []})
    nav = optional("nav-series.json", {"fund_code": code, "records": []})
    if any(d.get("fund_code") != current["fund"]["code"] for d in (holdings, nav, ledger["meta"])):
        raise ValueError("持仓、净值与报告份额代码不一致，已停止生成。")
    statements = optional("manager-statements.json", {})
    historical_events = optional("historical-events.json", {})
    stock_ohlc = optional("stock-ohlc.json", {})
    end = current["as_of"]
    if any(raw.get("fund_code") != code for raw in (statements,historical_events) if raw):
        raise ValueError("经理陈述或事件账与请求份额不一致。")
    if stock_ohlc.get("fund_code", code) != code:
        raise ValueError("行情索引与案例份额不符。")
    if any(row["date"] > end for row in nav["records"]):
        raise ValueError("净值超过研究截止日。")
    dates = [p["report_date"] for p in holdings["periods"]]
    if dates != sorted(set(dates)) or any(p["report_date"] > current["report_date"] or p.get("published_at", "") > end for p in holdings["periods"]):
        raise ValueError("持仓报告重复、顺序错乱或超出研究截面。")
    appointments = [i["start_date"] for i in current["managers"] if i["name"] == current["subject"]
                    and i["start_date"] <= end and (not i.get("end_date") or i["end_date"] >= end)]
    if not appointments:
        raise ValueError("研究日没有该经理的在任记录。")
    start = max(appointments)
    holdings = {**holdings, "periods":[p for p in holdings["periods"] if p["report_date"] >= start]}
    historical_events = {**historical_events,"events":[i for i in historical_events.get("events", [])
                         if i.get("published_at") and i["published_at"] <= end and i["event_date"] <= end]}
    modules = ledger["modules"]

    outcomes = estimate_holding_pnl(holdings["periods"])
    all_outcomes = {item["code"]: item for item in outcomes}
    trades = _rank_outcomes(outcomes, 10)
    manager_approved = []
    for approved_case in statements.get("explicit_named_stocks", []):
        if isinstance(approved_case, dict):
            refs = approved_case.get("evidence_refs", [])
            primary_refs = {s["id"] for s in ledger["sources"] if s.get("grade") in ("A","B")}
            if not (approved_case.get("manager_statement") and approved_case.get("code")
                    and isinstance(refs,list) and primary_refs.intersection(refs)):
                raise ValueError("经理点名需要股票代码、本人原话和该案的法定披露或正式访谈来源。")
            manager_approved.append(
                {
                    **approved_case,
                    "trade_record": all_outcomes.get(approved_case.get("code")),
                }
            )
    manager_approved_candidates = []
    for approved_case in statements.get("cases", []):
        manager_approved_candidates.append(
            {
                **approved_case,
                "trade_record": all_outcomes.get(approved_case["code"]),
            }
        )

    case = empty_case()
    case["meta"] = {
        "schema_version": "1.0",
        "case_type": "active_fund_manager_forensics",
        "holding_window_start": start,
        "demo": False,
        "evidence_cutoff": ledger["meta"]["evidence_cutoff"],
        "generated_at": ledger["meta"]["retrieved_at"],
        "coverage": {
            "modules": len(modules),
            "people_fields": len(ledger["people"]),
            "family_fields": len(ledger.get("family_background", {})),
            "holding_periods": len(holdings["periods"]),
        },
        "module_titles": MODULE_TITLES,
        "people_titles": PEOPLE_TITLES,
        "module_index": modules,
    }
    case["fund"] = {
        **current["fund"],
        "managers": current["managers"],
        "latest_snapshot": current.get("snapshot", {}),
        "latest_top_holdings": current.get("top_holdings", []),
        "history": {
            "first_disclosure": holdings["periods"][0]["report_date"] if holdings["periods"] else None,
            "last_disclosure": holdings["periods"][-1]["report_date"] if holdings["periods"] else None,
            "periods": len(holdings["periods"]),
            "complete_periods": sum(
                item["is_complete"] for item in holdings["periods"]
            ),
        },
    }
    case["verdict"] = {"only_for": current.get("only_for", [])}
    case["people"] = {
        "manager": current["subject"],
        "fields": ledger["people"],
        "family_background": ledger.get("family_background", {}),
    }
    case["tenure"] = modules.get("tenure_segmentation", {})
    case["performance_regimes"] = [{**r, "return_pct": _range_return(nav["records"], r["start"], r["end"])} for r in current.get("regimes", [])]
    case["alpha"] = _select_modules(
        modules,
        "manager_dependency",
        "alpha_authenticity",
        "luck_test",
        "alpha_type",
        "alpha_repeatability",
    )
    case["behavior"] = _select_modules(
        modules,
        "style_drift",
        "hotspot_lag",
        "trading_personality",
        "promise_ledger",
        "pressure_personality",
        "ranking_anxiety",
    )
    case["battle_replays"] = build_battle_replays(
        holdings,
        trades,
        historical_events,
        stock_ohlc,
        start,
    )
    case["trade_ledger"] = {
        "winners": trades["winners"],
        "losers": trades["losers"],
        "manager_approved": manager_approved,
        "manager_approved_candidates": manager_approved_candidates,
        "manager_approved_conclusion": statements.get("conclusion", "未提交经理点名记录"),
        "explicit_named_manager_stocks": len(manager_approved),
        "methodology": (
            "仅计本次任职后的披露。共管期属于团队。相邻两期平均股数 × 披露估值价差。疑似股本变化的区间暂不计入；"
            "这是估算，不是实际成交盈亏。仅从前十大消失不判定卖出。"
        ),
        "event_legend": {
            "B": "首次公开披露",
            "B+": "披露股数增加20%以上",
            "S": "披露股数减少20%以上",
            "EXIT": "完整持仓报告确认消失",
        },
    }
    case["capacity"] = _select_modules(
        modules, "scale_curse", "strategy_capacity", "exit_pressure"
    )
    case["crowding"] = _select_modules(
        modules,
        "company_crowding",
        "synchronized_trading",
        "market_crowding",
        "pseudo_diversification",
    )
    case["platform"] = _select_modules(
        modules,
        "independent_decision",
        "shadow_manager",
        "platform_alpha",
        "team_stability",
        "product_replication",
    )
    case["flows"] = {
        "flow_impact": modules.get("flow_impact", {}),
        "fund_flow_stability": modules.get("fund_flow_stability", {}),
        "redemption_stampede": modules.get("redemption_stampede", {}),
        "fund_company_proprietary": current.get("proprietary", {}),
    }
    case["holders"] = {
        "snapshot": current.get("holders", {}),
        "holder_structure": modules.get("holder_structure", {}),
        "institutional_change": modules.get("institutional_change", {}),
        "post_manager_vote": modules.get("post_manager_vote", {}),
    }
    case["capital_tags"] = {
        "tags": modules.get("capital_tags", {}),
        "five_factors": modules.get("capital_five_factors", {}),
        "long_term_capital": modules.get("long_term_capital", {}),
    }
    case["tail_risk"] = {
        **analyze_nav(nav["records"]),
        "basis": "单位净值变化，未还原分红，不等于投资者总回报",
        "metric": modules.get("tail_risk", {}),
    }
    case["compliance"] = modules.get("compliance", {})
    case["scores"] = modules.get("core_scores", {}).get("value", {})
    case["sources"] = ledger["sources"]
    return case


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _select_modules(
    modules: Dict[str, Dict[str, Any]], *module_ids: str
) -> Dict[str, Dict[str, Any]]:
    return {module_id: modules[module_id] for module_id in module_ids if module_id in modules}
