#!/usr/bin/env python3
"""Validate the mandatory Deep Agent handoff without third-party packages."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
import sys
from typing import Any


MODULE_IDS = {f"M{index:02d}" for index in range(1, 46)}
PEOPLE_IDS = {f"P{index:02d}" for index in range(1, 25)}
REQUIRED_REVIEWERS = {
    "people_investigator",
    "alpha_forensic",
    "portfolio_detective",
    "institutional_skeptic",
    "chief_underwriter",
}
WORKING_REVIEWERS = REQUIRED_REVIEWERS - {"chief_underwriter"}
STATUSES = {"已证实", "估算", "未证明", "未发现可靠公开信息"}
TRADE_GROUPS = {"winners", "losers", "manager_approved"}
RARITY_GRADES = {"N", "R", "SR", "SSR", "UR"}
EXPOSURE_LEVELS = {"隐世", "圈内", "出圈", "明星", "顶流"}
CONFIDENCE_LEVELS = {"低", "中", "高"}


def nonempty_strings(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(
        isinstance(item, str) and item.strip() for item in value
    )


def validate_review(review: Any, path: str, errors: list[str]) -> None:
    if not isinstance(review, dict):
        errors.append(f"{path}: must be an object")
        return
    if review.get("status") not in STATUSES:
        errors.append(f"{path}.status: unsupported status")
    if not isinstance(review.get("conclusion"), str) or not review["conclusion"].strip():
        errors.append(f"{path}.conclusion: required")
    if not nonempty_strings(review.get("evidence_refs")):
        errors.append(f"{path}.evidence_refs: at least one source or search-log ref required")
    if review.get("reviewer") not in WORKING_REVIEWERS | {"chief_underwriter"}:
        errors.append(f"{path}.reviewer: unknown reviewer")


def validate_manager_rarity(rarity: Any, errors: list[str]) -> None:
    path = "manager_rarity"
    if not isinstance(rarity, dict):
        errors.append(f"{path}: required object")
        return
    for key in ("ability_grade", "card_rarity", "product_grade"):
        if rarity.get(key) not in RARITY_GRADES:
            errors.append(f"{path}.{key}: unsupported rarity grade")
    if rarity.get("exposure_level") not in EXPOSURE_LEVELS:
        errors.append(f"{path}.exposure_level: unsupported exposure level")
    if rarity.get("confidence") not in CONFIDENCE_LEVELS:
        errors.append(f"{path}.confidence: unsupported confidence")
    ability_score = rarity.get("ability_score")
    if type(ability_score) is not int or not 0 <= ability_score <= 100:
        errors.append(f"{path}.ability_score: integer 0-100 required")
    else:
        expected_grade = "SSR" if ability_score >= 85 else "SR" if ability_score >= 70 else "R" if ability_score >= 55 else "N"
        if rarity.get("ability_grade") != expected_grade:
            errors.append(f"{path}.ability_grade: expected {expected_grade} for score {ability_score}")
    scarcity_score = rarity.get("scarcity_score")
    if type(scarcity_score) is not int or not 0 <= scarcity_score <= 100:
        errors.append(f"{path}.scarcity_score: integer 0-100 required")
    for key in ("scarcity_reason", "punchline", "judgment", "counterevidence"):
        if not isinstance(rarity.get(key), str) or not rarity[key].strip():
            errors.append(f"{path}.{key}: required")
    if not nonempty_strings(rarity.get("evidence_refs")):
        errors.append(f"{path}.evidence_refs: at least one source required")
    evidence = rarity.get("evidence")
    if not isinstance(evidence, list) or len(evidence) < 3 or not all(
        isinstance(item, str) and item.strip() for item in evidence
    ):
        errors.append(f"{path}.evidence: at least three evidence lines required")


def _valid_optional_score(value: Any) -> bool:
    return value is None or (
        type(value) in (int, float) and 0 <= value <= 100
    )


def validate_independent_decision(decision: Any, errors: list[str]) -> None:
    path = "independent_decision"
    if not isinstance(decision, dict):
        errors.append(f"{path}: required object")
        return
    if "score" in decision:
        errors.append(f"{path}.score: must not merge thinking and alpha")
    if decision.get("status") not in STATUSES:
        errors.append(f"{path}.status: unsupported status")

    house = decision.get("house_consensus")
    if not isinstance(house, dict):
        errors.append(f"{path}.house_consensus: required object")
    else:
        if house.get("self_excluded") is not True:
            errors.append(f"{path}.house_consensus.self_excluded: must be true")
        for key in ("manager_equal", "aum_weighted"):
            if not _valid_optional_score(house.get(key)):
                errors.append(f"{path}.house_consensus.{key}: number 0-100 or null required")
        if not isinstance(house.get("conclusion"), str) or not house["conclusion"].strip():
            errors.append(f"{path}.house_consensus.conclusion: required")

    mandate = decision.get("mandate_adjustment")
    if not isinstance(mandate, dict):
        errors.append(f"{path}.mandate_adjustment: required object")
    else:
        if type(mandate.get("completed")) is not bool:
            errors.append(f"{path}.mandate_adjustment.completed: boolean required")
        if not isinstance(mandate.get("conclusion"), str) or not mandate["conclusion"].strip():
            errors.append(f"{path}.mandate_adjustment.conclusion: required")

    for key in ("thinking", "alpha"):
        item = decision.get(key)
        if not isinstance(item, dict):
            errors.append(f"{path}.{key}: required object")
            continue
        if not _valid_optional_score(item.get("score")):
            errors.append(f"{path}.{key}.score: number 0-100 or null required")
        if not isinstance(item.get("conclusion"), str) or not item["conclusion"].strip():
            errors.append(f"{path}.{key}.conclusion: required")

    for key in ("contrarian_alpha", "idea_origination", "shadow_manager", "company_independence"):
        if not isinstance(decision.get(key), str) or not decision[key].strip():
            errors.append(f"{path}.{key}: required")
    if not isinstance(decision.get("battles"), list):
        errors.append(f"{path}.battles: array required")
    missing_data = decision.get("missing_data")
    if decision.get("status") in {"未证明", "未发现可靠公开信息"} and not nonempty_strings(missing_data):
        errors.append(f"{path}.missing_data: required when evidence is insufficient")
    if not nonempty_strings(decision.get("evidence_refs")):
        errors.append(f"{path}.evidence_refs: required")


def validate_payload(payload: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["root: must be an object"]
    if payload.get("schema_version") != "1.0.0":
        errors.append("schema_version: expected 1.0.0")
    if payload.get("analysis_mode") != "deep":
        errors.append("analysis_mode: deep validator only accepts deep")
    if payload.get("agent_reviewed") is not True:
        errors.append("agent_reviewed: must be true")

    validate_manager_rarity(payload.get("manager_rarity"), errors)
    validate_independent_decision(payload.get("independent_decision"), errors)

    reviewers = payload.get("reviewers")
    if not isinstance(reviewers, dict):
        errors.append("reviewers: required object")
    else:
        missing = REQUIRED_REVIEWERS - set(reviewers)
        if missing:
            errors.append("reviewers: missing " + ", ".join(sorted(missing)))
        for reviewer in REQUIRED_REVIEWERS & set(reviewers):
            item = reviewers[reviewer]
            if not isinstance(item, dict) or item.get("reviewed") is not True:
                errors.append(f"reviewers.{reviewer}.reviewed: must be true")

    tenure = payload.get("manager_tenure")
    if not isinstance(tenure, dict):
        errors.append("manager_tenure: required object")
    else:
        if tenure.get("cut_complete") is not True:
            errors.append("manager_tenure.cut_complete: must be true")
        if not isinstance(tenure.get("current_manager"), str) or not tenure["current_manager"].strip():
            errors.append("manager_tenure.current_manager: required")
        if not isinstance(tenure.get("periods"), list) or not tenure["periods"]:
            errors.append("manager_tenure.periods: at least one period required")
        if not nonempty_strings(tenure.get("evidence_refs")):
            errors.append("manager_tenure.evidence_refs: required")

    modules = payload.get("module_reviews")
    if not isinstance(modules, dict):
        errors.append("module_reviews: required object")
    else:
        missing = MODULE_IDS - set(modules)
        extra = set(modules) - MODULE_IDS
        if missing:
            errors.append("module_reviews: missing " + ", ".join(sorted(missing)))
        if extra:
            errors.append("module_reviews: unknown " + ", ".join(sorted(extra)))
        for module_id in MODULE_IDS & set(modules):
            validate_review(modules[module_id], f"module_reviews.{module_id}", errors)

    people = payload.get("people_reviews")
    if not isinstance(people, dict):
        errors.append("people_reviews: required object")
    else:
        missing = PEOPLE_IDS - set(people)
        extra = set(people) - PEOPLE_IDS
        if missing:
            errors.append("people_reviews: missing " + ", ".join(sorted(missing)))
        if extra:
            errors.append("people_reviews: unknown " + ", ".join(sorted(extra)))
        for people_id in PEOPLE_IDS & set(people):
            validate_review(people[people_id], f"people_reviews.{people_id}", errors)

    trade_reviews = payload.get("trade_reviews")
    if not isinstance(trade_reviews, dict):
        errors.append("trade_reviews: required object")
    else:
        for group in sorted(TRADE_GROUPS):
            items = trade_reviews.get(group)
            if not isinstance(items, list) or not items:
                errors.append(f"trade_reviews.{group}: at least one item required")
                continue
            for index, item in enumerate(items):
                path = f"trade_reviews.{group}[{index}]"
                if not isinstance(item, dict):
                    errors.append(f"{path}: must be an object")
                    continue
                if not isinstance(item.get("name"), str) or not item["name"].strip():
                    errors.append(f"{path}.name: required")
                if item.get("status") not in STATUSES:
                    errors.append(f"{path}.status: unsupported status")
                if not nonempty_strings(item.get("evidence_refs")):
                    errors.append(f"{path}.evidence_refs: required")

    if not isinstance(payload.get("conflicts"), list):
        errors.append("conflicts: required array")

    verdict = payload.get("verdict")
    if not isinstance(verdict, dict):
        errors.append("verdict: required object")
    else:
        if type(verdict.get("buy_now")) is not bool:
            errors.append("verdict.buy_now: must be boolean")
        expected_label = "可以买" if verdict.get("buy_now") is True else "不能买"
        if verdict.get("label") != expected_label:
            errors.append(f"verdict.label: expected {expected_label}")
        for key in ("institutional_view", "sentence"):
            if not isinstance(verdict.get(key), str) or not verdict[key].strip():
                errors.append(f"verdict.{key}: required")
        for key in ("reasons", "flip_conditions", "evidence_refs"):
            if not nonempty_strings(verdict.get(key)):
                errors.append(f"verdict.{key}: non-empty string array required")
    return errors


def check_refs(payload, ledger):
    sources = {s["id"] for s in ledger["sources"]}
    modules = {"ledger:" + k for k in ledger.get("modules", {})}
    errors = []
    def walk(node, path):
        if isinstance(node, list):
            for i, item in enumerate(node):
                walk(item, f"{path}[{i}]")
        if not isinstance(node, dict):
            return
        if isinstance(node.get("evidence_refs"), list):
            matched = set()
            for ref in node["evidence_refs"]:
                if not isinstance(ref, str):
                    continue
                ids = set(re.findall(r"(?<![A-Za-z0-9])([A-Z][0-9]{2,})(?![A-Za-z0-9])", ref))
                if ref.startswith("ledger:"):
                    ids.add(ref)
                unknown = ids - sources - modules
                if unknown:
                    errors.append(f"{path}.evidence_refs: 来源不存在 {sorted(unknown)}")
                matched.update(ids & (sources | modules))
            if not matched and node.get("status") not in {"未证明", "未发现可靠公开信息"}:
                errors.append(f"{path}.evidence_refs: 缺少可定位的来源")
        for k, v in node.items():
            walk(v, f"{path}.{k}")
    walk(payload, "$")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("analysis", type=Path)
    parser.add_argument("--ledger", type=Path)
    args = parser.parse_args(argv)
    try:
        payload = json.loads(args.analysis.read_text(encoding="utf-8"))
        path = args.ledger or args.analysis.parent / "raw" / "evidence-ledger.json"
        ledger = json.loads(path.read_text(encoding="utf-8"))
        errors = validate_payload(payload) + check_refs(payload, ledger)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        print(json.dumps({"valid": False, "errors": [str(exc)]}, ensure_ascii=False))
        return 2
    print(json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
