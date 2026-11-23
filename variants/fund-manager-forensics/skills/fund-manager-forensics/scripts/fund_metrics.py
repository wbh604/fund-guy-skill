from __future__ import annotations
from datetime import date, timedelta
from typing import Any, Dict, List

EVIDENCE_STATUSES = (
    "已证实",
    "估算",
    "未证明",
    "未发现可靠公开信息",
)

HOLDINGS_ENDPOINT = "https://fundf10.eastmoney.com/FundArchivesDatas.aspx"
NAV_ENDPOINT = "https://fund.eastmoney.com/pingzhongdata/{fund_code}.js"

FORENSICS_MODULES = (
    "tenure_segmentation",
    "manager_dependency",
    "basic_background",
    "career_stability",
    "workload",
    "personal_trivia",
    "regime_performance",
    "alpha_authenticity",
    "luck_test",
    "style_drift",
    "hotspot_lag",
    "trading_personality",
    "promise_ledger",
    "pressure_personality",
    "scale_curse",
    "strategy_capacity",
    "exit_pressure",
    "company_crowding",
    "synchronized_trading",
    "market_crowding",
    "independent_decision",
    "shadow_manager",
    "platform_alpha",
    "team_stability",
    "product_replication",
    "flow_impact",
    "holder_structure",
    "capital_tags",
    "capital_five_factors",
    "long_term_capital",
    "institutional_change",
    "post_manager_vote",
    "fund_flow_stability",
    "redemption_stampede",
    "pseudo_diversification",
    "ranking_anxiety",
    "special_returns",
    "tail_risk",
    "compliance",
    "core_scores",
    "alpha_type",
    "alpha_repeatability",
    "homepage_metrics",
    "evidence_grades",
    "hard_rules",
)

PEOPLE_FIELDS = (
    "career_path",
    "capability_formation",
    "investment_philosophy",
    "cognition",
    "decision_mechanism",
    "risk_personality",
    "conviction",
    "mistake_handling",
    "learning_ability",
    "independent_thinking",
    "emotional_stability",
    "integrity_consistency",
    "interest_alignment",
    "career_motivation",
    "platform_dependency",
    "key_person_risk",
    "manager_evolution_map",
    "behavioral_dna",
    "mistake_ledger",
    "idea_origination",
    "circle_of_competence",
    "manager_regime",
    "career_incentive_profile",
    "manager_underwriting_profile",
)

MODULE_TITLES = {
    "tenure_segmentation": "任期切割",
    "manager_dependency": "经理依赖度",
    "basic_background": "基础背调",
    "career_stability": "职业稳定性",
    "workload": "精力负荷",
    "personal_trivia": "人物花絮",
    "regime_performance": "牛熊照妖镜",
    "alpha_authenticity": "Alpha真实性",
    "luck_test": "运气检验",
    "style_drift": "风格漂移",
    "hotspot_lag": "热点滞后",
    "trading_personality": "交易人格",
    "promise_ledger": "承诺账本",
    "pressure_personality": "压力人格",
    "scale_curse": "规模诅咒",
    "strategy_capacity": "策略容量",
    "exit_pressure": "退出压力",
    "company_crowding": "公司内抱团",
    "synchronized_trading": "同步交易",
    "market_crowding": "市场拥挤",
    "independent_decision": "独立决策",
    "shadow_manager": "影子经理",
    "platform_alpha": "平台Alpha",
    "team_stability": "团队稳定",
    "product_replication": "产品复制",
    "flow_impact": "申赎冲击",
    "holder_structure": "持有人结构",
    "capital_tags": "九类资本标签",
    "capital_five_factors": "资本五要素",
    "long_term_capital": "长钱认可度",
    "institutional_change": "机构变化",
    "post_manager_vote": "换经理投票",
    "fund_flow_stability": "资金稳定",
    "redemption_stampede": "赎回踩踏",
    "pseudo_diversification": "伪分散",
    "ranking_anxiety": "排名焦虑",
    "special_returns": "特殊收益",
    "tail_risk": "尾部风险",
    "compliance": "合规",
    "core_scores": "核心评分",
    "alpha_type": "Alpha类型",
    "alpha_repeatability": "Alpha可复制率",
    "homepage_metrics": "首页指标",
    "evidence_grades": "证据等级",
    "hard_rules": "硬规则",
}

PEOPLE_TITLES = {
    "career_path": "职业路径",
    "capability_formation": "能力形成",
    "investment_philosophy": "投资哲学",
    "cognition": "认知方式",
    "decision_mechanism": "决策机制",
    "risk_personality": "风险人格",
    "conviction": "Conviction",
    "mistake_handling": "错误处理",
    "learning_ability": "学习能力",
    "independent_thinking": "独立思考",
    "emotional_stability": "情绪稳定",
    "integrity_consistency": "诚信一致",
    "interest_alignment": "利益一致",
    "career_motivation": "职业动机",
    "platform_dependency": "平台依赖",
    "key_person_risk": "Key Person Risk",
    "manager_evolution_map": "Manager Evolution Map",
    "behavioral_dna": "Behavioral DNA",
    "mistake_ledger": "Mistake Ledger",
    "idea_origination": "Idea Origination",
    "circle_of_competence": "Circle of Competence",
    "manager_regime": "Manager × Regime",
    "career_incentive_profile": "Career Incentive Profile",
    "manager_underwriting_profile": "Manager Underwriting Profile",
}


def metric(
    value: Any,
    conclusion: str,
    status: str,
    evidence_grade: str,
    evidence_ref: str,
) -> Dict[str, Any]:
    """Build one renderable metric with a strict evidence state."""

    if status not in EVIDENCE_STATUSES:
        raise ValueError(f"unsupported evidence status: {status}")

    return {
        "value": value,
        "conclusion": conclusion,
        "status": status,
        "evidence_grade": evidence_grade,
        "evidence_ref": evidence_ref,
    }


def empty_case() -> Dict[str, Any]:
    """Return the complete top-level schema for one fund-manager case file."""

    return {
        "meta": {},
        "fund": {},
        "verdict": {},
        "people": {},
        "independent_decision": {},
        "tenure": {},
        "performance_regimes": [],
        "alpha": {},
        "behavior": {},
        "battle_replays": [],
        "trade_ledger": {
            "winners": [],
            "losers": [],
            "manager_approved": [],
        },
        "capacity": {},
        "crowding": {},
        "platform": {},
        "flows": {},
        "holders": {},
        "capital_tags": {},
        "tail_risk": {},
        "compliance": {},
        "scores": {},
        "sources": [],
    }


def _suspected_unit_change(previous, current):
    """Quarantine split-like intervals, without claiming a verified corporate action."""
    q0, q1 = previous.get("shares"), current.get("shares")
    v0, v1 = previous.get("market_value"), current.get("market_value")
    if not all(x is not None and x > 0 for x in (q0, q1, v0, v1)):
        return False
    ratio = max(q1 / q0, q0 / q1)
    return abs(v1 / v0 - 1) <= 0.03 and any(
        abs(ratio / factor - 1) <= 0.002
        for factor in [n / 10 for n in range(12, 31)] + [4, 5, 10]
    )


def derive_trade_events(
    periods: List[Dict[str, Any]], change_threshold: float = 0.20
) -> List[Dict[str, Any]]:
    """Infer disclosure-period B/S events from reported share counts.

    ``B`` means first public disclosure in the observed window, not the actual
    trade date. ``B+`` and ``S`` require an absolute share-count move of at
    least ``change_threshold`` versus the latest disclosed count. ``EXIT`` is
    emitted only when a security disappears from a complete holdings report.
    """

    events: List[Dict[str, Any]] = []
    positions: Dict[str, Dict[str, Any]] = {}

    for snapshot in periods:
        period = snapshot["period"]
        is_complete = bool(snapshot.get("is_complete"))
        holdings = snapshot.get("holdings") or {}

        for code, holding in holdings.items():
            shares = float(holding["shares"])
            name = holding.get("name") or code
            previous = positions.get(code)

            if previous is None or not previous["active"]:
                events.append(
                    _trade_event(period, code, name, "B", shares, None, None)
                )
            else:
                previous_shares = previous["shares"]
                if previous_shares > 0 and not _suspected_unit_change(previous, holding):
                    change = (shares - previous_shares) / previous_shares
                    if change >= change_threshold:
                        events.append(
                            _trade_event(
                                period,
                                code,
                                name,
                                "B+",
                                shares,
                                previous_shares,
                                change,
                            )
                        )
                    elif change <= -change_threshold:
                        events.append(
                            _trade_event(
                                period,
                                code,
                                name,
                                "S",
                                shares,
                                previous_shares,
                                change,
                            )
                        )

            positions[code] = {**holding, "name": name, "shares": shares, "active": True}

        if is_complete:
            for code, previous in list(positions.items()):
                if previous["active"] and code not in holdings:
                    events.append(
                        _trade_event(
                            period,
                            code,
                            previous["name"],
                            "EXIT",
                            0.0,
                            previous["shares"],
                            -1.0,
                        )
                    )
                    previous["active"] = False
                    previous["shares"] = 0.0

    return events


def estimate_holding_pnl(periods: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Estimate disclosed-position price contribution for every observed stock."""

    observations: Dict[str, List[Dict[str, Any]]] = {}
    for period_index, snapshot in enumerate(periods):
        for code, holding in (snapshot.get("holdings") or {}).items():
            shares = holding.get("shares")
            market_value = holding.get("market_value")
            implied_price = None
            if shares and market_value is not None:
                implied_price = market_value / shares
            observations.setdefault(code, []).append(
                {
                    "period_index": period_index,
                    "period": snapshot["period"],
                    "report_date": snapshot.get("report_date"),
                    "name": holding.get("name") or code,
                    "shares": shares,
                    "market_value": market_value,
                    "weight_pct": holding.get("weight_pct"),
                    "implied_price": implied_price,
                }
            )

    event_map: Dict[str, List[Dict[str, Any]]] = {}
    for event in derive_trade_events(periods):
        event_map.setdefault(event["code"], []).append(event)

    outcomes: List[Dict[str, Any]] = []
    for code, stock_observations in observations.items():
        contributions: List[Dict[str, Any]] = []
        excluded = []
        for previous, current in zip(stock_observations, stock_observations[1:]):
            if _complete_absence_between(
                periods,
                code,
                previous["period_index"],
                current["period_index"],
            ):
                continue
            if (
                previous["implied_price"] is None
                or current["implied_price"] is None
                or previous["shares"] is None
                or current["shares"] is None
            ):
                continue
            if _suspected_unit_change(previous, current):
                excluded.append({"from": previous["period"], "to": current["period"], "reason": "疑似股本变动，暂不计入"})
                continue
            average_shares = (previous["shares"] + current["shares"]) / 2
            contribution = average_shares * (
                current["implied_price"] - previous["implied_price"]
            )
            contributions.append(
                {
                    "from": previous["period"],
                    "to": current["period"],
                    "estimated_pnl": round(contribution, 2),
                }
            )

        first = stock_observations[0]
        last = stock_observations[-1]
        weights = [
            item["weight_pct"]
            for item in stock_observations
            if item["weight_pct"] is not None
        ]
        outcomes.append(
            {
                "code": code,
                "name": last["name"],
                "first_disclosure": first["period"],
                "last_disclosure": last["period"],
                "disclosed_periods": len(stock_observations),
                "priced_intervals": len(contributions),
                "peak_weight_pct": max(weights) if weights else None,
                "estimated_pnl": round(
                    sum(item["estimated_pnl"] for item in contributions), 2
                ),
                "estimated": True,
                "status": "估算",
                "method": "报告期公允价值反推价格 × 相邻披露期平均股数；不是实际成交盈亏",
                "events": event_map.get(code, []),
                "intervals": contributions,
                "excluded_intervals": excluded,
            }
        )

    return sorted(outcomes, key=lambda item: abs(item["estimated_pnl"]), reverse=True)


def rank_trade_outcomes(
    periods: List[Dict[str, Any]], top_n: int = 10
) -> Dict[str, List[Dict[str, Any]]]:
    return _rank_outcomes(estimate_holding_pnl(periods), top_n)


def _rank_outcomes(outcomes, top_n):
    winners = sorted(
        (item for item in outcomes if item["estimated_pnl"] > 0),
        key=lambda item: item["estimated_pnl"],
        reverse=True,
    )[:top_n]
    losers = sorted(
        (item for item in outcomes if item["estimated_pnl"] < 0),
        key=lambda item: item["estimated_pnl"],
    )[:top_n]
    return {"winners": winners, "losers": losers}


def build_disclosure_price_series(
    periods: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """Build report-date RMB valuation prices from disclosed value and shares."""

    series: Dict[str, List[Dict[str, Any]]] = {}
    for snapshot in periods:
        for code, holding in (snapshot.get("holdings") or {}).items():
            shares = holding.get("shares")
            market_value = holding.get("market_value")
            if not shares or market_value is None:
                continue
            series.setdefault(code, []).append(
                {
                    "period": snapshot["period"],
                    "report_date": snapshot.get("report_date"),
                    "name": holding.get("name") or code,
                    "valuation_price_rmb": round(market_value / shares, 6),
                    "source": snapshot.get("source"),
                }
            )
    return series


def analyze_nav(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate drawdown and period-return facts from a unit-NAV series."""

    if not records:
        return {}
    points = sorted(records, key=lambda item: item["date"])
    peak_nav = float(points[0]["nav"])
    peak_date = points[0]["date"]
    max_drawdown = 0.0
    drawdown_peak_date = peak_date
    trough_date = peak_date

    for point in points:
        nav = float(point["nav"])
        if nav > peak_nav:
            peak_nav = nav
            peak_date = point["date"]
        drawdown = nav / peak_nav - 1
        if drawdown < max_drawdown:
            max_drawdown = drawdown
            drawdown_peak_date = peak_date
            trough_date = point["date"]

    monthly = _period_end_returns(points, key_length=7)
    quarterly = _quarter_end_returns(points)
    yearly = _period_end_returns(points, key_length=4, include_first=True)
    return {
        "start_date": points[0]["date"],
        "end_date": points[-1]["date"],
        "total_return_pct": round(
            (float(points[-1]["nav"]) / float(points[0]["nav"]) - 1) * 100,
            2,
        ),
        "max_drawdown_pct": round(max_drawdown * 100, 2),
        "drawdown_peak_date": drawdown_peak_date,
        "drawdown_trough_date": trough_date,
        "worst_month": min(monthly, key=lambda item: item["return_pct"], default=None),
        "worst_quarter": min(quarterly, key=lambda item: item["return_pct"], default=None),
        "yearly_returns": yearly,
    }


def _period_end_returns(
    points: List[Dict[str, Any]], key_length: int, include_first: bool = False
) -> List[Dict[str, Any]]:
    ends: Dict[str, Dict[str, Any]] = {}
    for point in points:
        ends[point["date"][:key_length]] = point
    ordered = list(ends.items())
    results = []
    previous_nav = float(points[0]["nav"]) if include_first else None
    for period, point in ordered:
        nav = float(point["nav"])
        if previous_nav is not None:
            results.append(
                {
                    "period": period,
                    "return_pct": round((nav / previous_nav - 1) * 100, 2),
                }
            )
        previous_nav = nav
    return results


def _quarter_end_returns(points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ends: Dict[str, Dict[str, Any]] = {}
    for point in points:
        nav_date = date.fromisoformat(point["date"])
        quarter = (nav_date.month - 1) // 3 + 1
        ends[f"{nav_date.year}Q{quarter}"] = point
    results = []
    previous_nav = None
    for period, point in ends.items():
        nav = float(point["nav"])
        if previous_nav is not None:
            results.append(
                {
                    "period": period,
                    "return_pct": round((nav / previous_nav - 1) * 100, 2),
                }
            )
        previous_nav = nav
    return results


def build_battle_replays(
    holdings: Dict[str, Any],
    trades: Dict[str, Any],
    historical_events: Dict[str, Any],
    stock_ohlc: Dict[str, Any],
    inception_date: str | None = None,
) -> List[Dict[str, Any]]:
    """Build honest event-window battle replays from audited local evidence."""

    replays = [
        _one_battle(holdings, item, historical_events, stock_ohlc, inception_date)
        for group in ("winners", "losers") for item in trades.get(group, [])
        if item.get("events") and stock_ohlc.get("series", {}).get(item["code"], {}).get("rows")
    ]
    return sorted(replays, key=lambda b: (b["start_date"], b["manager_actions"][0]["window_end"]))


def _one_battle(holdings, featured, historical_events, stock_ohlc, inception_date):
    periods = holdings.get("periods", [])
    period_indexes = {item["period"]: index for index, item in enumerate(periods)}
    report_dates = {item["period"]: item["report_date"] for item in periods}
    publications = [item for item in historical_events.get("events", [])
                    if item.get("category") == "基金披露" and item.get("published_at")
                    and holdings["fund_code"] in item.get("applies_to", {}).get("fund_codes", [])]
    action_labels = {
        "B": "首次公开披露持有",
        "B+": "披露持股明显增加",
        "S": "披露持股明显减少",
        "EXIT": "完整报告确认退出",
    }
    manager_actions = []
    for event in featured.get("events", []):
        period = event["period"]
        index = period_indexes[period]
        prior = next((p["report_date"] for p in reversed(periods[:index])
                      if p.get("is_complete") or featured["code"] in p.get("holdings", {})), None)
        window_start = (date.fromisoformat(prior) + timedelta(days=1)).isoformat() if prior else inception_date
        window_end = report_dates[period]
        sources = [p for p in publications if p.get("report_period") == period
                   and p["published_at"] >= window_end and (
                       p.get("holding_scope") == "full" or
                       (p.get("holding_scope") == "named" and event["event"] != "EXIT"
                        and featured["code"] in p["applies_to"].get("stock_codes", [])))]
        source = min(sources, key=lambda p: p["published_at"], default={})
        public_at = source.get("published_at")
        manager_actions.append(
            {
                **event,
                "action_label": action_labels.get(event["event"], "披露持仓变化"),
                "timeline_date": window_end,
                "time_precision": "period_window",
                "window_start": window_start,
                "window_end": window_end,
                "manager_clock": f"披露区间：{window_start or '起点未知'}至{window_end}",
                "public_clock": (
                    f"公众最早于{public_at}看到该报告"
                    if public_at
                    else "报告发布日期尚未入库，公众只能在报告公开后看到"
                ),
                "public_at": public_at,
                "source_url": source.get("source_url"),
                "source_title": source.get("source_title"),
                "basis": "相邻定期报告持股变化，只能定位到时间区间；报告期末不是成交日。",
            }
        )

    external_events = []
    start = manager_actions[0]["window_start"] or manager_actions[0]["window_end"]
    end = max(a["public_at"] or a["window_end"] for a in manager_actions)
    for item in historical_events.get("events", []):
        applies_to = item.get("applies_to", {})
        fund_codes = applies_to.get("fund_codes", [])
        stock_codes = applies_to.get("stock_codes", [])
        relevant = featured["code"] in stock_codes if stock_codes else holdings["fund_code"] in fund_codes
        if relevant and start <= item["event_date"] <= end:
            external_events.append(item)
    external_events.sort(key=lambda item: (item["event_date"], item["published_at"]))

    stock_series = stock_ohlc.get("series", {}).get(featured["code"], {})
    estimated_pnl = float(featured.get("estimated_pnl") or 0)
    sign = "+" if estimated_pnl >= 0 else "−"
    outcome_label = f"披露持仓区间估算 {sign}{abs(estimated_pnl) / 100000000:.2f}亿元"
    return {
            "id": "holding-" + featured["code"],
            "title": featured["name"] + "持仓回放",
            "stock_code": featured["code"],
            "stock_name": featured["name"],
            "start_date": start,
            "end_date": end,
            "verdict": f"{featured['disclosed_periods']}期报告披露持有，{outcome_label}。",
            "outcome_label": outcome_label,
            "estimated_pnl": estimated_pnl,
            "manager_clock": "经理动作只定位到相邻报告之间",
            "public_clock": "普通用户只能在定期报告公开后看到",
            "kline_available": bool(stock_series.get("rows")),
            "kline_source": stock_series.get("source") or stock_ohlc.get("source"),
            "kline_adjustment": stock_series.get("adjustment") or stock_ohlc.get("adjustment"),
            "manager_actions": manager_actions,
            "external_events": external_events,
            "search_log": historical_events.get("search_log", []),
        }


def _range_return(records: List[Dict[str, Any]], start: str, end: str) -> float | None:
    selected = [item for item in records if start <= item["date"] <= end]
    if len(selected) < 2:
        return None
    return round((selected[-1]["nav"] / selected[0]["nav"] - 1) * 100, 2)


def _complete_absence_between(
    periods: List[Dict[str, Any]],
    code: str,
    previous_index: int,
    current_index: int,
) -> bool:
    for snapshot in periods[previous_index + 1 : current_index]:
        if snapshot.get("is_complete") and code not in (snapshot.get("holdings") or {}):
            return True
    return False


def _trade_event(
    period: str,
    code: str,
    name: str,
    event: str,
    shares: float,
    previous_shares: float | None,
    change: float | None,
) -> Dict[str, Any]:
    return {
        "period": period,
        "code": code,
        "name": name,
        "event": event,
        "shares": shares,
        "previous_shares": previous_shares,
        "change_pct": None if change is None else round(change * 100, 2),
        "status": "估算",
        "basis": "定期报告披露持股变化",
    }
