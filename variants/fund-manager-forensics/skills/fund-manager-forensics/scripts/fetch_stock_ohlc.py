#!/usr/bin/env python3
"""Fetch validated weekly OHLC series for stocks named in a fund report."""

from __future__ import annotations

import argparse
from datetime import date, datetime
from http.client import RemoteDisconnected
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
from types import MappingProxyType
from typing import Any, Callable, NamedTuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


EASTMONEY_ENDPOINT = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
TENCENT_ENDPOINT = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
EASTMONEY_FIELDS1 = "f1,f2,f3,f4,f5,f6"
EASTMONEY_FIELDS2 = "f51,f52,f53,f54,f55,f56"
TIMEOUT_SECONDS = 15
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
USER_AGENT = "Fund-Manager-Forensics/stock-ohlc"

_ASCII_DIGITS = re.compile(r"[0-9]+\Z")
_EXCEPTION_TYPE_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_LEDGER_GROUPS = ("winners", "losers", "manager_approved", "manager_approved_candidates")
_ROW_FIELDS = ("date", "open", "close", "high", "low", "volume")
_ROW_FIELD_SET = frozenset(_ROW_FIELDS)
_TENCENT_PREFIX_BY_MARKET = MappingProxyType(
    {"SSE": "sh", "SZSE": "sz", "BSE": "bj", "HKEX": "hk"}
)
_NETWORK_ERRORS = (RemoteDisconnected, HTTPError, URLError, TimeoutError)


class Route(NamedTuple):
    market: str
    provider: str
    endpoint: str
    adjustment: str
    volume_unit: str
    secid_prefix: str
    code_length: int
    code_prefixes: tuple[str, ...]


ROUTES = MappingProxyType(
    {
        "SSE": Route(
            market="SSE",
            provider="东方财富",
            endpoint=EASTMONEY_ENDPOINT,
            adjustment="forward-adjusted",
            volume_unit="lots",
            secid_prefix="1",
            code_length=6,
            code_prefixes=("600", "601", "603", "605", "688", "689"),
        ),
        "SZSE": Route(
            market="SZSE",
            provider="东方财富",
            endpoint=EASTMONEY_ENDPOINT,
            adjustment="forward-adjusted",
            volume_unit="lots",
            secid_prefix="0",
            code_length=6,
            code_prefixes=("000", "001", "002", "003", "300", "301"),
        ),
        "BSE": Route(
            market="BSE",
            provider="东方财富",
            endpoint=EASTMONEY_ENDPOINT,
            adjustment="forward-adjusted",
            volume_unit="lots",
            secid_prefix="0",
            code_length=6,
            code_prefixes=("92",),
        ),
        "HKEX": Route(
            market="HKEX",
            provider="腾讯证券",
            endpoint=TENCENT_ENDPOINT,
            adjustment="unadjusted",
            volume_unit="shares",
            secid_prefix="116",
            code_length=5,
            code_prefixes=("0",),
        ),
    }
)


class BatchFetchError(RuntimeError):
    """Raised after all requested stocks were attempted and some failed."""

    def __init__(self, errors: dict[str, str]):
        self.errors = errors
        super().__init__(f"failed to fetch {len(errors)} stock(s)")


class DataValidationError(ValueError):
    """Expected remote or row data failed deterministic validation."""


class ProviderResponseError(ValueError):
    """A provider returned JSON, fields, or OHLC rows that violate its contract."""


class FetchResultContractError(ValueError):
    """An injected fetcher returned rows or provenance outside the local contract."""


class ProviderFetchError(RuntimeError):
    """Summarize one provider failure without retaining the original exception."""

    def __init__(self, provider: str, error_type: str):
        self.provider = provider
        self.error_type = error_type
        super().__init__(f"{provider}={error_type}")


class ProviderFallbackError(RuntimeError):
    """Summarize two provider failures without retaining provider error text."""

    def __init__(self, primary_error_type: str, fallback_error_type: str):
        self.errors = {
            "东方财富": primary_error_type,
            "腾讯证券": fallback_error_type,
        }
        super().__init__(
            "; ".join(f"{provider}={error_type}" for provider, error_type in self.errors.items())
        )


class _NoRedirectHandler(HTTPRedirectHandler):
    """Keep fixed-host requests from following provider-controlled redirects."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def route_for_code(code: str) -> Route:
    """Return the single allowlisted market/provider route for a strict stock code."""

    if not isinstance(code, str):
        raise ValueError("stock code must be a string")
    if not _ASCII_DIGITS.fullmatch(code):
        raise ValueError("stock code must be six ASCII digits or a five-digit HK code")
    if code == "00000":
        raise ValueError("invalid HK stock code")
    for route in ROUTES.values():
        if len(code) == route.code_length and code.startswith(route.code_prefixes):
            return route
    raise ValueError(f"unsupported stock code: {code}")


def market_secid(code: str) -> str:
    """Map a strict allowlisted stock code to its secid form."""

    route = route_for_code(code)
    return f"{route.secid_prefix}.{code}"


def symbol_for_code(code: str) -> str:
    """Map a strict allowlisted stock code to Tencent's fixed symbol form."""

    route = route_for_code(code)
    return f"{_TENCENT_PREFIX_BY_MARKET[route.market]}{code}"


def _parse_date(value: str) -> str:
    if not isinstance(value, str):
        raise DataValidationError("date must be a string")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise DataValidationError(f"invalid kline date: {value!r}") from None
    if parsed.strftime("%Y-%m-%d") != value:
        raise DataValidationError(f"invalid kline date format: {value!r}")
    return value


def _parse_number(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise DataValidationError(f"{field} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise DataValidationError(f"invalid {field}: {value!r}") from None
    if not math.isfinite(number):
        raise DataValidationError(f"{field} must be finite")
    return number


def _normalize_row(fields: list[Any]) -> dict[str, Any]:
    if len(fields) < 6:
        raise DataValidationError("kline row has fewer than six fields")
    row = {
        "date": _parse_date(fields[0]),
        "open": _parse_number(fields[1], "open"),
        "close": _parse_number(fields[2], "close"),
        "high": _parse_number(fields[3], "high"),
        "low": _parse_number(fields[4], "low"),
        "volume": _parse_number(fields[5], "volume"),
    }
    for field in ("open", "close", "high", "low"):
        if row[field] <= 0:
            raise DataValidationError(f"{field} must be positive")
    if row["volume"] < 0:
        raise DataValidationError("volume must not be negative")
    if row["low"] > row["high"]:
        raise DataValidationError("low must not exceed high")
    if not row["low"] <= row["open"] <= row["high"]:
        raise DataValidationError("open must be between low and high")
    if not row["low"] <= row["close"] <= row["high"]:
        raise DataValidationError("close must be between low and high")
    return row


def _normalize_mapping_row(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DataValidationError("normalized kline row must be an object")
    actual_fields = frozenset(value)
    if actual_fields != _ROW_FIELD_SET:
        missing = sorted(_ROW_FIELD_SET - actual_fields)
        extra = sorted(actual_fields - _ROW_FIELD_SET, key=str)
        raise DataValidationError(
            f"kline row fields mismatch; missing={missing}, extra={extra}"
        )
    return _normalize_row([value[field] for field in _ROW_FIELDS])


def parse_kline_row(value: str) -> dict[str, Any]:
    """Parse one Eastmoney comma-separated kline row."""

    try:
        if not isinstance(value, str):
            raise DataValidationError("Eastmoney kline row must be a string")
        return _normalize_row(value.split(","))
    except DataValidationError as exc:
        raise ProviderResponseError(str(exc)) from None


def parse_tencent_row(value: Any) -> dict[str, Any]:
    """Parse one Tencent kline array into the common OHLC schema."""

    try:
        if not isinstance(value, (list, tuple)):
            raise DataValidationError("Tencent kline row must be an array")
        return _normalize_row(list(value))
    except DataValidationError as exc:
        raise ProviderResponseError(str(exc)) from None


def _sort_and_deduplicate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_date: dict[str, dict[str, Any]] = {}
    for row in rows:
        row_date = row["date"]
        existing = by_date.get(row_date)
        if existing is not None and existing != row:
            raise DataValidationError(f"conflicting OHLCV rows for date {row_date}")
        by_date.setdefault(row_date, row)
    return [by_date[row_date] for row_date in sorted(by_date)]


def parse_eastmoney_response(payload: Any) -> list[dict[str, Any]]:
    """Validate and normalize an Eastmoney response object."""

    try:
        if not isinstance(payload, dict) or payload.get("rc") != 0:
            raise DataValidationError("Eastmoney response rc must equal 0")
        data = payload.get("data")
        klines = data.get("klines") if isinstance(data, dict) else None
        if not isinstance(klines, list) or not klines:
            raise DataValidationError("Eastmoney data.klines must be a non-empty list")
        return _sort_and_deduplicate([parse_kline_row(row) for row in klines])
    except DataValidationError as exc:
        raise ProviderResponseError(str(exc)) from None


def parse_tencent_response(payload: Any, symbol: str) -> list[dict[str, Any]]:
    """Validate and normalize a Tencent unadjusted weekly response object."""

    try:
        valid_symbol = False
        if isinstance(symbol, str) and re.fullmatch(
            r"(?:(?:sh|sz|bj)[0-9]{6}|hk[0-9]{5})", symbol
        ):
            code = symbol[2:]
            matching_route = next(
                (
                    route
                    for route in ROUTES.values()
                    if len(code) == route.code_length and code.startswith(route.code_prefixes)
                ),
                None,
            )
            valid_symbol = (
                matching_route is not None
                and _TENCENT_PREFIX_BY_MARKET[matching_route.market] == symbol[:2]
            )
        if not valid_symbol:
            raise DataValidationError("Tencent symbol must match a supported market stock code")
        if not isinstance(payload, dict) or payload.get("code") != 0:
            raise DataValidationError("Tencent response code must equal 0")
        data = payload.get("data")
        security = data.get(symbol) if isinstance(data, dict) else None
        rows = security.get("week") if isinstance(security, dict) else None
        if not isinstance(rows, list) or not rows:
            raise DataValidationError(
                "Tencent data.<symbol>.week must be a non-empty list"
            )
        return _sort_and_deduplicate([parse_tencent_row(row) for row in rows])
    except DataValidationError as exc:
        raise ProviderResponseError(str(exc)) from None


def _request(endpoint: str, query: dict[str, str]) -> Request:
    parsed = urlparse(endpoint)
    allowed = {
        (route_url.scheme, route_url.netloc, route_url.path)
        for route_url in (urlparse(route.endpoint) for route in ROUTES.values())
    }
    if (parsed.scheme, parsed.netloc, parsed.path) not in allowed or parsed.query:
        raise ValueError("network endpoint is not allowlisted")
    return Request(
        f"{endpoint}?{urlencode(query)}",
        headers={"User-Agent": USER_AGENT},
        method="GET",
    )


def build_eastmoney_request(code: str) -> Request:
    route = route_for_code(code)
    if route.endpoint != EASTMONEY_ENDPOINT:
        raise ValueError("Eastmoney fetches are restricted to A-share codes")
    return _request(
        route.endpoint,
        {
            "secid": market_secid(code),
            "klt": "102",
            "fqt": "1",
            "beg": "20170101",
            "end": "20500101",
            "lmt": "10000",
            "fields1": EASTMONEY_FIELDS1,
            "fields2": EASTMONEY_FIELDS2,
        },
    )


def build_tencent_request(code: str) -> Request:
    symbol = symbol_for_code(code)
    return _request(TENCENT_ENDPOINT, {"param": f"{symbol},week,,,1000,"})


def _default_opener(request: Request, *, timeout: int):
    return build_opener(_NoRedirectHandler()).open(request, timeout=timeout)


def _close_quietly(resource: Any) -> None:
    close = getattr(resource, "close", None)
    if callable(close):
        try:
            close()
        except Exception:
            pass


def _decode_json_body(body: bytes) -> Any:
    if len(body) > MAX_RESPONSE_BYTES:
        raise DataValidationError("HTTP response exceeds the 8MB limit")
    try:
        decoded = body.decode("utf-8")
        return json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise DataValidationError("provider returned invalid UTF-8 JSON") from None


def _read_json(request: Request, opener: Callable[..., Any]) -> Any:
    try:
        response = opener(request, timeout=TIMEOUT_SECONDS)
    except HTTPError as exc:
        _close_quietly(getattr(exc, "fp", None))
        _close_quietly(exc)
        raise
    try:
        body = response.read(MAX_RESPONSE_BYTES + 1)
    finally:
        _close_quietly(response)
    try:
        return _decode_json_body(body)
    except DataValidationError as exc:
        raise ProviderResponseError(str(exc)) from None


def fetch_stock_ohlc(code: str, opener: Callable[..., Any] | None = None) -> dict[str, Any]:
    """Fetch one stock from its market's fixed provider endpoint."""

    route = route_for_code(code)
    secid = market_secid(code)
    open_request = opener or _default_opener
    if route.market == "HKEX":
        symbol = symbol_for_code(code)
        provider_error_type: str | None = None
        try:
            payload = _read_json(build_tencent_request(code), open_request)
            rows = parse_tencent_response(payload, symbol)
        except _NETWORK_ERRORS as exc:
            provider_error_type = type(exc).__name__
        except ProviderResponseError as exc:
            provider_error_type = type(exc).__name__
        if provider_error_type is not None:
            safe_error = ProviderFetchError("腾讯证券", provider_error_type)
            raise safe_error from None
        return {
            "secid": secid,
            "symbol": symbol,
            "provider": route.provider,
            "source": route.endpoint,
            "adjustment": route.adjustment,
            "volume_unit": route.volume_unit,
            "rows": rows,
        }
    primary_error_type: str | None = None
    try:
        payload = _read_json(build_eastmoney_request(code), open_request)
        rows = parse_eastmoney_response(payload)
    except _NETWORK_ERRORS as exc:
        primary_error_type = type(exc).__name__
    except ProviderResponseError as exc:
        primary_error_type = type(exc).__name__
    if primary_error_type is not None:
        symbol = symbol_for_code(code)
        fallback_error_type: str | None = None
        try:
            fallback_payload = _read_json(build_tencent_request(code), open_request)
            fallback_rows = parse_tencent_response(fallback_payload, symbol)
        except _NETWORK_ERRORS as exc:
            fallback_error_type = type(exc).__name__
        except ProviderResponseError as exc:
            fallback_error_type = type(exc).__name__
        if fallback_error_type is not None:
            safe_error = ProviderFallbackError(primary_error_type, fallback_error_type)
            raise safe_error from None
        return {
            "secid": secid,
            "symbol": symbol,
            "provider": "腾讯证券",
            "source": TENCENT_ENDPOINT,
            "adjustment": "unadjusted",
            "volume_unit": "lots",
            "fallback_from": "东方财富",
            "fallback_reason": primary_error_type,
            "rows": fallback_rows,
        }
    return {
        "secid": secid,
        "provider": route.provider,
        "source": route.endpoint,
        "adjustment": route.adjustment,
        "volume_unit": route.volume_unit,
        "rows": rows,
    }


def collect_trade_ledger_stocks(report: Any) -> list[dict[str, str]]:
    """Collect unique code/name pairs from the three report ledger groups."""

    if not isinstance(report, dict):
        raise ValueError("report must be a JSON object")
    ledger = report.get("trade_ledger")
    if not isinstance(ledger, dict):
        raise ValueError("report.trade_ledger must be an object")

    stocks: dict[str, str] = {}
    for group_name in _LEDGER_GROUPS:
        group = ledger.get(group_name, [])
        if not isinstance(group, list):
            raise ValueError(f"trade_ledger.{group_name} must be a list")
        for index, item in enumerate(group):
            if not isinstance(item, dict):
                raise ValueError(f"trade_ledger.{group_name}[{index}] must be an object")
            code = item.get("code")
            name = item.get("name")
            market_secid(code)
            if not isinstance(name, str) or not name.strip():
                raise ValueError(f"trade_ledger.{group_name}[{index}].name is required")
            normalized_name = name.strip()
            if code in stocks and stocks[code] != normalized_name:
                raise ValueError(f"conflicting names for stock code {code}")
            stocks.setdefault(code, normalized_name)
    if not stocks:
        raise ValueError("trade ledger contains no supported stocks")
    return [{"code": code, "name": name} for code, name in stocks.items()]


def _normalize_fetch_result(code: str, result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise DataValidationError("fetcher result must be an object")
    rows = result.get("rows")
    if not isinstance(rows, list) or not rows:
        raise DataValidationError("fetcher result rows must be a non-empty list")
    route = route_for_code(code)
    if result.get("secid") != market_secid(code):
        raise DataValidationError("fetcher result secid does not match the stock code")
    core = {
        "provider": result.get("provider"),
        "source": result.get("source"),
        "adjustment": result.get("adjustment"),
        "volume_unit": result.get("volume_unit"),
    }
    fallback_fields = ("fallback_from", "fallback_reason")
    provenance_error = (
        "fetcher result provider/source/adjustment/volume_unit/symbol/fallback "
        "does not match a fixed market route"
    )
    if route.market == "HKEX":
        expected_core = {
            "provider": "腾讯证券",
            "source": TENCENT_ENDPOINT,
            "adjustment": "unadjusted",
            "volume_unit": "shares",
        }
        if (
            core != expected_core
            or result.get("symbol") != symbol_for_code(code)
            or any(field in result for field in fallback_fields)
        ):
            raise DataValidationError(provenance_error)
        provenance = {**expected_core, "symbol": symbol_for_code(code)}
    else:
        primary_core = {
            "provider": route.provider,
            "source": route.endpoint,
            "adjustment": route.adjustment,
            "volume_unit": route.volume_unit,
        }
        fallback_core = {
            "provider": "腾讯证券",
            "source": TENCENT_ENDPOINT,
            "adjustment": "unadjusted",
            "volume_unit": "lots",
        }
        if (
            core == primary_core
            and "symbol" not in result
            and not any(field in result for field in fallback_fields)
        ):
            provenance = primary_core
        elif (
            core == fallback_core
            and result.get("symbol") == symbol_for_code(code)
            and result.get("fallback_from") == "东方财富"
            and isinstance(result.get("fallback_reason"), str)
            and _EXCEPTION_TYPE_NAME.fullmatch(result["fallback_reason"])
        ):
            provenance = {
                **fallback_core,
                "symbol": symbol_for_code(code),
                "fallback_from": "东方财富",
                "fallback_reason": result["fallback_reason"],
            }
        else:
            raise DataValidationError(provenance_error)
    normalized = {
        "secid": market_secid(code),
        **provenance,
        "rows": _sort_and_deduplicate([_normalize_mapping_row(row) for row in rows]),
    }
    return normalized


def _validate_fetch_result(code: str, result: Any) -> dict[str, Any]:
    try:
        return _normalize_fetch_result(code, result)
    except DataValidationError:
        pass
    safe_error = FetchResultContractError("invalid fetch result contract")
    raise safe_error from None


def _safe_batch_error(exc: Exception) -> str:
    if isinstance(exc, ProviderFallbackError):
        return (
            "ProviderFallbackError: "
            f"东方财富={exc.errors['东方财富']}; 腾讯证券={exc.errors['腾讯证券']}"
        )
    if isinstance(exc, ProviderFetchError):
        return f"ProviderFetchError: {exc.provider}={exc.error_type}"
    if isinstance(exc, FetchResultContractError):
        return "FetchResultContractError: invalid fetch result contract"
    raise TypeError("unsupported batch error type")


def build_output(
    report: Any,
    *,
    fetcher: Callable[[str], dict[str, Any]] = fetch_stock_ohlc,
    fetched_at: str | None = None,
) -> dict[str, Any]:
    """Fetch every ledger stock, aggregating all per-stock failures."""

    stocks = collect_trade_ledger_stocks(report)
    series: dict[str, dict[str, Any]] = {}
    errors: dict[str, str] = {}
    for stock in stocks:
        code = stock["code"]
        try:
            fetched = _validate_fetch_result(code, fetcher(code))
            series[code] = {"name": stock["name"], **fetched}
        except (ProviderFetchError, ProviderFallbackError, FetchResultContractError) as exc:
            errors[code] = _safe_batch_error(exc)
    if errors:
        raise BatchFetchError(errors)

    adjustments = {item["adjustment"] for item in series.values()}
    providers = []
    provider_keys = set()
    for item in series.values():
        key = (
            item["provider"],
            item["source"],
            item["adjustment"],
            item["volume_unit"],
        )
        if key not in provider_keys:
            providers.append(
                {
                    "provider": item["provider"],
                    "endpoint": item["source"],
                    "adjustment": item["adjustment"],
                    "volume_unit": item["volume_unit"],
                }
            )
            provider_keys.add(key)
    return {
        "fetched_at": fetched_at or date.today().isoformat(),
        "period": "weekly",
        "adjustment": next(iter(adjustments)) if len(adjustments) == 1 else "mixed",
        "source": {"providers": providers},
        "series": series,
    }


def write_json_atomic(output_path: Path, payload: Any) -> None:
    """Write JSON through a same-directory temporary file and atomic replace."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.replace(output_path)
    except Exception:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise


def run(
    report_path: Path,
    output_path: Path,
    *,
    fetcher: Callable[[str], dict[str, Any]] = fetch_stock_ohlc,
    fetched_at: str | None = None,
) -> dict[str, Any]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    payload = build_output(report, fetcher=fetcher, fetched_at=fetched_at)
    write_json_atomic(output_path, payload)
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path, help="input report JSON path")
    parser.add_argument("--output", required=True, type=Path, help="output OHLC JSON path")
    return parser


def main(
    argv: list[str] | None = None,
    *,
    fetcher: Callable[[str], dict[str, Any]] = fetch_stock_ohlc,
    fetched_at: str | None = None,
    stderr=None,
) -> int:
    args = _parser().parse_args(argv)
    error_stream = stderr or sys.stderr
    try:
        run(args.report, args.output, fetcher=fetcher, fetched_at=fetched_at)
    except BatchFetchError as exc:
        print(str(exc), file=error_stream)
        for code, message in exc.errors.items():
            print(f"{code}: {message}", file=error_stream)
        return 1
    except (OSError, ValueError) as exc:
        print(f"stock OHLC collection failed: {exc}", file=error_stream)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
