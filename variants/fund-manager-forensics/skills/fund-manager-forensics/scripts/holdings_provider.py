"""Optional provider candidates. Verify against filings before adopting."""
from __future__ import annotations
from datetime import date
from urllib.parse import urlencode
import re
from typing import Dict, List, Any
HOLDINGS_ENDPOINT="https://fundf10.eastmoney.com/FundArchivesDatas.aspx"

def fetch_holdings_history(
    fund_code: str,
    start_year: int,
    end_year: int,
) -> Dict[str, Any]:
    """Fetch disclosed holdings while preserving each report's disclosure scope."""

    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError as exc:  # pragma: no cover - depends on runtime packaging
        raise RuntimeError("fetch mode requires requests and beautifulsoup4") from exc

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": f"https://fundf10.eastmoney.com/ccmx_{fund_code}.html",
    }
    periods: List[Dict[str, Any]] = []

    for year in range(start_year, end_year + 1):
        params = {
            "type": "jjcc",
            "code": fund_code,
            "topline": "10000",
            "year": str(year),
            "month": "6,12",

        }
        response = requests.get(
            HOLDINGS_ENDPOINT,
            params=params,
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        content_match = re.search(r'content:"(.*)",arryear:', response.text, re.S)
        if content_match is None:
            raise RuntimeError(f"holdings payload missing for {year}")

        soup = BeautifulSoup(content_match.group(1), "html.parser")
        for box in soup.select(".boxitem"):
            report_match = re.search(
                r"截止至：\s*([0-9]{4}-[0-9]{2}-[0-9]{2})",
                box.get_text(" ", strip=True),
            )
            if report_match is None:
                continue
            report_date = report_match.group(1)
            month = int(report_date[5:7])
            complete_report = False  # Vendor candidates never prove a complete report.
            holdings: Dict[str, Dict[str, Any]] = {}

            rows = box.select("tbody tr")
            if not complete_report:
                rows = rows[:10]
            for row in rows:
                cells = [cell.get_text(" ", strip=True) for cell in row.select("td")]
                if len(cells) < 7:
                    continue
                code = cells[1].strip()
                holdings[code] = {
                    "name": cells[2].lstrip("*"),
                    "shares": _scaled_number(cells[-2], 10_000),
                    "market_value": _scaled_number(cells[-1], 10_000),
                    "weight_pct": _number(cells[-3].rstrip("%")),
                }

            periods.append(
                {
                    "period": _period_label(report_date),
                    "report_date": report_date,
                    "is_complete": complete_report,
                    "disclosure_scope": "complete" if complete_report else "top10",
                    "holdings": holdings,
                    "source": f"{HOLDINGS_ENDPOINT}?{urlencode(params)}",
                    "evidence_grade": "C",
                }
            )

    periods.sort(key=lambda item: item["report_date"])
    return {
        "fund_code": fund_code,
        "fetched_at": date.today().isoformat(),
        "methodology": {
            "quarterly": "仅前十大公开持仓，不据缺席判断退出",
            "semiannual_annual": "数据库候选，须核对法定全持仓原文后才可推断退出",
            "trade_dates": "B/S均为披露期推断，不是实际成交日",
        },
        "periods": periods,
    }


def is_full_report_available(report_date: str, as_of: date) -> bool:
    """Return whether a complete semiannual/annual portfolio is safely public."""

    period_end = date.fromisoformat(report_date)
    if period_end.month == 6:
        return as_of >= date(period_end.year, 8, 31)
    if period_end.month == 12:
        return as_of >= date(period_end.year + 1, 3, 31)
    return False


def _number(value: str) -> float | None:
    clean = value.replace(",", "").strip()
    if clean == "" or re.fullmatch(r"-+", clean):
        return None
    return float(clean)


def _scaled_number(value: str, scale: int) -> float | None:
    parsed = _number(value)
    return None if parsed is None else round(parsed * scale, 2)


def _period_label(report_date: str) -> str:
    year, month, _ = report_date.split("-")
    return {
        "03": f"{year}Q1",
        "06": f"{year}H1",
        "09": f"{year}Q3",
        "12": f"{year}FY",
    }[month]
