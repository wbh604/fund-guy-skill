import io
import importlib.util
import json
from contextlib import redirect_stderr
from http.client import RemoteDisconnected
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "skills" / "fund-manager-forensics" / "scripts" / "fetch_stock_ohlc.py"


class FakeResponse:
    def __init__(self, payload):
        self._stream = io.BytesIO(payload)
        self.read_sizes = []
        self.closed = False

    def read(self, size=-1):
        self.read_sizes.append(size)
        return self._stream.read(size)

    def close(self):
        self.closed = True


class CloseSpy(io.BytesIO):
    def __init__(self, payload=b""):
        super().__init__(payload)
        self.close_calls = 0

    def close(self):
        self.close_calls += 1
        super().close()


class RecordingOpener:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []
        self.response = None

    def __call__(self, request, *, timeout):
        self.calls.append((request, timeout))
        self.response = FakeResponse(self.payload)
        return self.response


class SequenceOpener:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []
        self.responses = []

    def __call__(self, request, *, timeout):
        self.calls.append((request, timeout))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        response = FakeResponse(outcome)
        self.responses.append(response)
        return response


def eastmoney_payload(rows=None, rc=0):
    if rows is None:
        rows = ["2024-01-05,20.10,21.00,21.50,19.80,1000"]
    return json.dumps({"rc": rc, "data": {"klines": rows}}).encode("utf-8")


def tencent_payload(symbol="hk01810", rows=None, code=0):
    if rows is None:
        rows = [["2024-01-05", "20.10", "21.00", "21.50", "19.80", "1000"]]
    return json.dumps(
        {"code": code, "msg": "", "data": {symbol: {"week": rows}}}
    ).encode("utf-8")


def normalized_row(**overrides):
    row = {
        "date": "2024-01-05",
        "open": 20.1,
        "close": 21.0,
        "high": 21.5,
        "low": 19.8,
        "volume": 1000.0,
    }
    row.update(overrides)
    return row


class StockOhlcTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue(MODULE_PATH.is_file(), f"missing {MODULE_PATH}")
        spec = importlib.util.spec_from_file_location("fetch_stock_ohlc", MODULE_PATH)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def test_market_secid_maps_supported_markets(self):
        self.assertEqual(self.module.market_secid("601012"), "1.601012")
        self.assertEqual(self.module.market_secid("300308"), "0.300308")
        self.assertEqual(self.module.market_secid("920001"), "0.920001")
        self.assertEqual(self.module.market_secid("01810"), "116.01810")

    def test_symbol_for_code_maps_all_supported_markets_strictly(self):
        self.assertEqual(self.module.symbol_for_code("601012"), "sh601012")
        self.assertEqual(self.module.symbol_for_code("300308"), "sz300308")
        self.assertEqual(self.module.symbol_for_code("920001"), "bj920001")
        self.assertEqual(self.module.symbol_for_code("01810"), "hk01810")
        for code in (
            "",
            "1234",
            "1234567",
            "ABC123",
            "１２３４５６",
            "123456",
            "00000",
            "hk01810",
        ):
            with self.subTest(code=code), self.assertRaises(ValueError):
                self.module.symbol_for_code(code)

    def test_route_table_is_read_only_and_identifies_current_markets(self):
        self.assertEqual(self.module.route_for_code("601012").market, "SSE")
        self.assertEqual(self.module.route_for_code("300308").market, "SZSE")
        self.assertEqual(self.module.route_for_code("920001").market, "BSE")
        self.assertEqual(self.module.route_for_code("01810").market, "HKEX")
        self.assertEqual(self.module.route_for_code("601012").volume_unit, "lots")
        self.assertEqual(self.module.route_for_code("920001").volume_unit, "lots")
        self.assertEqual(self.module.route_for_code("01810").volume_unit, "shares")
        with self.assertRaises(TypeError):
            self.module.ROUTES["OTHER"] = object()

    def test_market_secid_rejects_invalid_codes(self):
        for code in ("", "1234", "1234567", "ABC123", "１２３４５６", "123456", "00000"):
            with self.subTest(code=code), self.assertRaises(ValueError):
                self.module.market_secid(code)

    def test_parse_kline_row_returns_normalized_ohlc(self):
        self.assertEqual(
            self.module.parse_kline_row(
                "2024-01-05,20.10,21.00,21.50,19.80,1000"
            ),
            {
                "date": "2024-01-05",
                "open": 20.1,
                "close": 21.0,
                "high": 21.5,
                "low": 19.8,
                "volume": 1000.0,
            },
        )

    def test_parse_kline_row_rejects_invalid_dates_and_short_rows(self):
        for row in (
            "2024-02-30,20,21,22,19,1000",
            "2024/01/05,20,21,22,19,1000",
            "2024-01-05,20,21,22,19",
        ):
            with self.subTest(row=row), self.assertRaises(ValueError):
                self.module.parse_kline_row(row)

    def test_parse_kline_row_rejects_non_finite_and_invalid_prices(self):
        for row in (
            "2024-01-05,nan,21,22,19,1000",
            "2024-01-05,20,inf,22,19,1000",
            "2024-01-05,20,21,22,19,-1",
            "2024-01-05,0,21,22,19,1000",
            "2024-01-05,20,-1,22,19,1000",
            "2024-01-05,20,21,0,19,1000",
            "2024-01-05,20,21,22,0,1000",
        ):
            with self.subTest(row=row), self.assertRaises(ValueError):
                self.module.parse_kline_row(row)

    def test_parse_kline_row_rejects_inconsistent_ohlc_relationships(self):
        for row in (
            "2024-01-05,20,21,19,22,1000",
            "2024-01-05,23,21,22,19,1000",
            "2024-01-05,20,18,22,19,1000",
        ):
            with self.subTest(row=row), self.assertRaises(ValueError):
                self.module.parse_kline_row(row)

    def test_parse_tencent_row_uses_the_same_normalized_schema(self):
        self.assertEqual(
            self.module.parse_tencent_row(
                ["2024-01-05", "20.10", "21.00", "21.50", "19.80", "1000"]
            ),
            {
                "date": "2024-01-05",
                "open": 20.1,
                "close": 21.0,
                "high": 21.5,
                "low": 19.8,
                "volume": 1000.0,
            },
        )
        with self.assertRaises(ValueError):
            self.module.parse_tencent_row(["2024-01-05", "20", "21"])

    def test_parse_tencent_row_ignores_real_trailing_fields_after_ohlcv(self):
        self.assertEqual(
            self.module.parse_tencent_row(
                [
                    "2024-01-05",
                    "20.10",
                    "21.00",
                    "21.50",
                    "19.80",
                    "1000",
                    {"amount": "21.40"},
                ]
            ),
            normalized_row(),
        )

    def test_parse_entrypoints_classify_remote_data_errors(self):
        calls = (
            (self.module.parse_kline_row, ("not-a-kline-row",)),
            (self.module.parse_tencent_row, (["2024-01-05", "20"],)),
            (self.module.parse_eastmoney_response, ({"rc": 1},)),
            (
                self.module.parse_tencent_response,
                ({"code": 1, "data": {}}, "hk01810"),
            ),
        )
        for parser, args in calls:
            with self.subTest(parser=parser.__name__):
                with self.assertRaises(self.module.ProviderResponseError):
                    parser(*args)

    def test_expected_internal_data_validation_is_value_error_compatible(self):
        self.assertTrue(issubclass(self.module.DataValidationError, ValueError))
        self.assertTrue(issubclass(self.module.ProviderResponseError, ValueError))
        conflicting_rows = [
            normalized_row(),
            normalized_row(close=21.1),
        ]
        validations = (
            (self.module._parse_date, ("2024/01/05",)),
            (self.module._parse_number, ("not-a-number", "open")),
            (
                self.module._normalize_row,
                (["2024-01-05", "20", "21", "22", "19"],),
            ),
            (
                self.module._normalize_row,
                (["2024-01-05", "23", "21", "22", "19", "1000"],),
            ),
            (self.module._sort_and_deduplicate, (conflicting_rows,)),
            (
                self.module._normalize_mapping_row,
                ({**normalized_row(), "extra": "field"},),
            ),
        )
        for validator, args in validations:
            with self.subTest(validator=validator.__name__, args=args):
                with self.assertRaises(self.module.DataValidationError):
                    validator(*args)

    def test_parse_tencent_response_reads_only_week_for_all_supported_symbols(self):
        for symbol in ("sh601012", "sz300308", "bj920001", "hk01810"):
            payload = {
                "code": 0,
                "msg": "",
                "data": {
                    symbol: {
                        "prec": "20.10",
                        "qt": {},
                        "vcm": "",
                        "version": "1",
                        "week": [
                            [
                                "2024-01-05",
                                "20.10",
                                "21.00",
                                "21.50",
                                "19.80",
                                "1000",
                            ]
                        ],
                        "qfqweek": [],
                    }
                },
            }

            with self.subTest(symbol=symbol):
                self.assertEqual(
                    self.module.parse_tencent_response(payload, symbol),
                    [normalized_row()],
                )

        for symbol in ("sh300308", "sz601012", "bj601012", "hk601012", "xx601012"):
            with self.subTest(symbol=symbol), self.assertRaises(ValueError):
                self.module.parse_tencent_response({}, symbol)

    def test_parse_tencent_response_rejects_qfqweek_only_payload(self):
        payload = {
            "code": 0,
            "msg": "",
            "data": {
                "hk01810": {
                    "qfqweek": [
                        ["2024-01-05", "20.10", "21.00", "21.50", "19.80", "1000"]
                    ]
                }
            },
        }

        with self.assertRaisesRegex(ValueError, r"\.week"):
            self.module.parse_tencent_response(payload, "hk01810")

    def test_response_parsers_sort_and_fold_identical_duplicate_rows(self):
        east_rows = [
            "2024-01-12,22,23,24,21,2000",
            "2024-01-05,20,21,22,19,1000",
            "2024-01-05,20,21,22,19,1000",
        ]
        parsed = self.module.parse_eastmoney_response(
            json.loads(eastmoney_payload(east_rows))
        )
        self.assertEqual([row["date"] for row in parsed], ["2024-01-05", "2024-01-12"])
        self.assertEqual(parsed[0]["close"], 21.0)

        tx_rows = [
            ["2024-01-12", "22", "23", "24", "21", "2000"],
            ["2024-01-05", "20", "21", "22", "19", "1000"],
            ["2024-01-05", "20", "21", "22", "19", "1000"],
        ]
        parsed = self.module.parse_tencent_response(
            json.loads(tencent_payload(rows=tx_rows)), "hk01810"
        )
        self.assertEqual([row["date"] for row in parsed], ["2024-01-05", "2024-01-12"])

    def test_response_parsers_reject_conflicting_duplicate_dates(self):
        eastmoney = json.loads(
            eastmoney_payload(
                [
                    "2024-01-05,20,21,22,19,1000",
                    "2024-01-05,20,21.5,22,19,1000",
                ]
            )
        )
        with self.assertRaisesRegex(ValueError, "conflict"):
            self.module.parse_eastmoney_response(eastmoney)

        tencent = json.loads(
            tencent_payload(
                rows=[
                    ["2024-01-05", "20", "21", "22", "19", "1000"],
                    ["2024-01-05", "20", "21", "22", "19", "1001"],
                ]
            )
        )
        with self.assertRaisesRegex(ValueError, "conflict"):
            self.module.parse_tencent_response(tencent, "hk01810")

    def test_response_parsers_reject_provider_errors_and_empty_rows(self):
        invalid_eastmoney = (
            {"rc": 1, "data": {"klines": ["x"]}},
            {"rc": 0, "data": None},
            {"rc": 0, "data": {"klines": []}},
            {"rc": 0, "data": {"klines": "not-a-list"}},
        )
        for payload in invalid_eastmoney:
            with self.subTest(provider="eastmoney", payload=payload), self.assertRaises(ValueError):
                self.module.parse_eastmoney_response(payload)

        invalid_tencent = (
            {"code": 1, "data": {}},
            {"code": 0, "data": {}},
            {"code": 0, "data": {"hk01810": {"week": []}}},
            {"code": 0, "data": {"hk01810": {"week": "not-a-list"}}},
        )
        for payload in invalid_tencent:
            with self.subTest(provider="tencent", payload=payload), self.assertRaises(ValueError):
                self.module.parse_tencent_response(payload, "hk01810")

    def test_collects_and_deduplicates_all_trade_ledger_groups(self):
        report = {
            "trade_ledger": {
                "winners": [
                    {"code": "601012", "name": "隆基绿能"},
                    {"code": "300308", "name": "中际旭创"},
                ],
                "losers": [
                    {"code": "01810", "name": "小米集团-W"},
                    {"code": "601012", "name": "隆基绿能"},
                ],
                "manager_approved_candidates": [
                    {"code": "01810", "name": "小米集团-W"},
                    {"code": "000739", "name": "普洛药业"},
                ],
            }
        }
        self.assertEqual(
            self.module.collect_trade_ledger_stocks(report),
            [
                {"code": "601012", "name": "隆基绿能"},
                {"code": "300308", "name": "中际旭创"},
                {"code": "01810", "name": "小米集团-W"},
                {"code": "000739", "name": "普洛药业"},
            ],
        )

    def test_collect_rejects_conflicting_names_and_malformed_groups(self):
        conflict = {
            "trade_ledger": {
                "winners": [{"code": "601012", "name": "隆基绿能"}],
                "losers": [{"code": "601012", "name": "其他名称"}],
                "manager_approved_candidates": [],
            }
        }
        with self.assertRaises(ValueError):
            self.module.collect_trade_ledger_stocks(conflict)
        with self.assertRaises(ValueError):
            self.module.collect_trade_ledger_stocks({"trade_ledger": {"winners": {}}})

    def test_eastmoney_request_has_fixed_host_and_weekly_parameters(self):
        request = self.module.build_eastmoney_request("601012")
        parsed = urlparse(request.full_url)
        query = parse_qs(parsed.query)
        self.assertEqual(
            (parsed.scheme, parsed.netloc, parsed.path),
            ("https", "push2his.eastmoney.com", "/api/qt/stock/kline/get"),
        )
        self.assertEqual(query["secid"], ["1.601012"])
        self.assertEqual(query["klt"], ["102"])
        self.assertEqual(query["fqt"], ["1"])
        self.assertEqual(query["beg"], ["20170101"])
        self.assertEqual(query["end"], ["20500101"])
        self.assertEqual(query["lmt"], ["10000"])
        self.assertEqual(query["fields1"], [self.module.EASTMONEY_FIELDS1])
        self.assertEqual(query["fields2"], [self.module.EASTMONEY_FIELDS2])
        self.assertTrue(request.get_header("User-agent"))

    def test_beijing_request_uses_eastmoney_with_market_secid(self):
        request = self.module.build_eastmoney_request("920001")
        parsed = urlparse(request.full_url)
        self.assertEqual(parsed.netloc, "push2his.eastmoney.com")
        self.assertEqual(parse_qs(parsed.query)["secid"], ["0.920001"])

    def test_tencent_request_has_fixed_host_and_weekly_param_for_all_markets(self):
        expected = {
            "601012": "sh601012",
            "300308": "sz300308",
            "920001": "bj920001",
            "01810": "hk01810",
        }
        for code, symbol in expected.items():
            request = self.module.build_tencent_request(code)
            parsed = urlparse(request.full_url)
            with self.subTest(code=code):
                self.assertEqual(
                    (parsed.scheme, parsed.netloc, parsed.path),
                    ("https", "web.ifzq.gtimg.cn", "/appstock/app/fqkline/get"),
                )
                self.assertEqual(
                    parse_qs(parsed.query)["param"],
                    [f"{symbol},week,,,1000,"],
                )
        for code in ("1810", "hk01810", "01810.example.com", "123456"):
            with self.subTest(code=code), self.assertRaises(ValueError):
                self.module.build_tencent_request(code)

    def test_fetch_routes_a_shares_to_eastmoney_with_limits(self):
        opener = RecordingOpener(eastmoney_payload())
        result = self.module.fetch_stock_ohlc("601012", opener=opener)
        request, timeout = opener.calls[0]
        self.assertEqual(timeout, 15)
        self.assertEqual(opener.response.read_sizes, [self.module.MAX_RESPONSE_BYTES + 1])
        self.assertTrue(opener.response.closed)
        self.assertEqual(urlparse(request.full_url).netloc, "push2his.eastmoney.com")
        self.assertEqual(result["provider"], "东方财富")
        self.assertEqual(result["source"], self.module.EASTMONEY_ENDPOINT)
        self.assertEqual(result["secid"], "1.601012")
        self.assertEqual(result["adjustment"], "forward-adjusted")
        self.assertEqual(result["volume_unit"], "lots")
        self.assertEqual(len(opener.calls), 1)
        self.assertNotIn("symbol", result)
        self.assertNotIn("fallback_from", result)
        self.assertNotIn("fallback_reason", result)

    def test_a_share_provider_failures_fall_back_to_fixed_tencent_week(self):
        failures = (
            ("remote-disconnected", RemoteDisconnected("secret disconnect detail")),
            ("url-error", URLError("secret URL detail")),
            ("timeout", TimeoutError("secret timeout detail")),
            (
                "http-error",
                HTTPError(
                    "https://secret.example/response-body",
                    503,
                    "secret HTTP response body",
                    None,
                    None,
                ),
            ),
            ("invalid-payload", eastmoney_payload(rc=1)),
            ("empty-payload", eastmoney_payload(rows=[])),
        )
        for label, failure in failures:
            opener = SequenceOpener(
                [failure, tencent_payload(symbol="sh601012")]
            )
            try:
                with self.subTest(failure=label):
                    result = self.module.fetch_stock_ohlc("601012", opener=opener)
                    self.assertEqual(
                        [urlparse(call[0].full_url).netloc for call in opener.calls],
                        ["push2his.eastmoney.com", "web.ifzq.gtimg.cn"],
                    )
                    self.assertEqual([call[1] for call in opener.calls], [15, 15])
                    self.assertTrue(all(response.closed for response in opener.responses))
                    self.assertTrue(
                        all(
                            response.read_sizes == [self.module.MAX_RESPONSE_BYTES + 1]
                            for response in opener.responses
                        )
                    )
                    self.assertEqual(result["provider"], "腾讯证券")
                    self.assertEqual(result["source"], self.module.TENCENT_ENDPOINT)
                    self.assertEqual(result["symbol"], "sh601012")
                    self.assertEqual(result["secid"], "1.601012")
                    self.assertEqual(result["adjustment"], "unadjusted")
                    self.assertEqual(result["volume_unit"], "lots")
                    self.assertEqual(result["fallback_from"], "东方财富")
                    expected_type = (
                        "ProviderResponseError"
                        if isinstance(failure, bytes)
                        else type(failure).__name__
                    )
                    self.assertEqual(result["fallback_reason"], expected_type)
                    serialized = json.dumps(result, ensure_ascii=False)
                    self.assertNotIn("secret", serialized)
                    self.assertNotIn("response-body", serialized)
            finally:
                if isinstance(failure, HTTPError):
                    failure.close()

    def test_primary_http_error_closes_its_stream_and_exception_before_fallback(self):
        stream = CloseSpy(b"secret provider response body")
        primary_error = HTTPError(
            "https://eastmoney.invalid/private-body",
            503,
            "private response body",
            None,
            stream,
        )
        close_calls = []
        original_close = primary_error.close

        def record_close():
            close_calls.append(True)
            original_close()

        primary_error.close = record_close
        self.addCleanup(primary_error.close)
        opener = SequenceOpener(
            [primary_error, tencent_payload(symbol="sh601012")]
        )

        result = self.module.fetch_stock_ohlc("601012", opener=opener)

        self.assertEqual(result["provider"], "腾讯证券")
        self.assertEqual(result["fallback_reason"], "HTTPError")
        self.assertTrue(stream.closed)
        self.assertGreaterEqual(stream.close_calls, 1)
        self.assertTrue(close_calls)

    def test_a_share_fallback_uses_the_same_code_for_sse_szse_and_bse(self):
        cases = (
            ("601012", "sh601012", "1.601012"),
            ("300308", "sz300308", "0.300308"),
            ("920001", "bj920001", "0.920001"),
        )
        for code, symbol, secid in cases:
            opener = SequenceOpener(
                [RemoteDisconnected("disconnected"), tencent_payload(symbol=symbol)]
            )
            with self.subTest(code=code):
                result = self.module.fetch_stock_ohlc(code, opener=opener)
                self.assertEqual(result["symbol"], symbol)
                self.assertEqual(result["secid"], secid)
                self.assertIn(f"param={symbol}%2Cweek%2C%2C%2C1000%2C", opener.calls[1][0].full_url)

    def test_unclassified_eastmoney_parser_errors_propagate_without_fallback(self):
        failures = (
            ValueError("programmer value error"),
            TypeError("programmer type error"),
            AssertionError("programmer assertion error"),
        )
        for failure in failures:
            opener = SequenceOpener(
                [eastmoney_payload(), tencent_payload(symbol="sh601012")]
            )
            with self.subTest(error_type=type(failure).__name__):
                with patch.object(
                    self.module,
                    "parse_eastmoney_response",
                    side_effect=failure,
                ):
                    with self.assertRaises(type(failure)) as caught:
                        self.module.fetch_stock_ohlc("601012", opener=opener)
                self.assertIs(caught.exception, failure)
                self.assertEqual(len(opener.calls), 1)

    def test_unclassified_inner_helper_value_errors_never_fallback_or_aggregate(self):
        report = {
            "trade_ledger": {
                "winners": [{"code": "601012", "name": "隆基绿能"}],
                "losers": [],
                "manager_approved_candidates": [],
            }
        }

        def valid_fetch_result(code):
            return {
                "secid": "1.601012",
                "provider": "东方财富",
                "source": self.module.EASTMONEY_ENDPOINT,
                "adjustment": "forward-adjusted",
                "volume_unit": "lots",
                "rows": [normalized_row()],
            }

        for helper_name in ("_normalize_row", "_sort_and_deduplicate"):
            fetch_failure = ValueError(f"programmer error in {helper_name}")
            opener = SequenceOpener(
                [eastmoney_payload(), tencent_payload(symbol="sh601012")]
            )
            with self.subTest(helper=helper_name, boundary="provider"):
                with patch.object(
                    self.module,
                    helper_name,
                    side_effect=fetch_failure,
                ):
                    with self.assertRaises(ValueError) as caught:
                        self.module.fetch_stock_ohlc("601012", opener=opener)
                self.assertIs(caught.exception, fetch_failure)
                self.assertEqual(len(opener.calls), 1)

            contract_failure = ValueError(f"programmer error in {helper_name}")
            with self.subTest(helper=helper_name, boundary="contract"):
                with patch.object(
                    self.module,
                    helper_name,
                    side_effect=contract_failure,
                ):
                    with self.assertRaises(ValueError) as caught:
                        self.module.build_output(report, fetcher=valid_fetch_result)
                self.assertIs(caught.exception, contract_failure)

    def test_a_share_tencent_fallback_failure_raises_safe_provider_summary(self):
        fallback_error = HTTPError(
            "https://tencent.invalid/private-body",
            502,
            "private provider response body",
            None,
            None,
        )
        opener = SequenceOpener(
            [
                RemoteDisconnected("https://eastmoney.invalid/private-body"),
                fallback_error,
            ]
        )

        try:
            with self.assertRaises(self.module.ProviderFallbackError) as caught:
                self.module.fetch_stock_ohlc("601012", opener=opener)

            self.assertEqual(
                caught.exception.errors,
                {"东方财富": "RemoteDisconnected", "腾讯证券": "HTTPError"},
            )
            message = str(caught.exception)
            self.assertIn("东方财富=RemoteDisconnected", message)
            self.assertIn("腾讯证券=HTTPError", message)
            self.assertNotIn("://", message)
            self.assertNotIn("private", message.lower())
            self.assertNotIn("response body", message.lower())
            self.assertNotIn("private", repr(caught.exception).lower())
            self.assertIsNone(caught.exception.__context__)
            self.assertIsNone(caught.exception.__cause__)
        finally:
            fallback_error.close()

    def test_fetch_routes_five_digit_hk_to_tencent(self):
        opener = RecordingOpener(tencent_payload())
        result = self.module.fetch_stock_ohlc("01810", opener=opener)
        request, timeout = opener.calls[0]
        self.assertEqual(timeout, 15)
        self.assertEqual(urlparse(request.full_url).netloc, "web.ifzq.gtimg.cn")
        self.assertEqual(result["provider"], "腾讯证券")
        self.assertEqual(result["source"], self.module.TENCENT_ENDPOINT)
        self.assertEqual(result["symbol"], "hk01810")
        self.assertEqual(result["secid"], "116.01810")
        self.assertEqual(result["adjustment"], "unadjusted")
        self.assertEqual(result["volume_unit"], "shares")
        self.assertEqual(len(opener.calls), 1)
        self.assertNotIn("fallback_from", result)
        self.assertNotIn("fallback_reason", result)

    def test_fetch_rejects_responses_larger_than_eight_megabytes(self):
        opener = RecordingOpener(b"x" * (8 * 1024 * 1024 + 1))
        with self.assertRaises(self.module.ProviderFetchError) as caught:
            self.module.fetch_stock_ohlc("01810", opener=opener)
        self.assertEqual(caught.exception.provider, "腾讯证券")
        self.assertEqual(caught.exception.error_type, "ProviderResponseError")
        self.assertIsNone(caught.exception.__context__)
        self.assertIsNone(caught.exception.__cause__)
        self.assertEqual(len(opener.calls), 1)

    def test_fetch_api_does_not_accept_a_custom_endpoint(self):
        with self.assertRaises(TypeError):
            self.module.fetch_stock_ohlc(
                "601012", endpoint="http://169.254.169.254/latest/meta-data"
            )

    def test_default_redirect_handler_refuses_redirects(self):
        handler = self.module._NoRedirectHandler()
        self.assertIsNone(
            handler.redirect_request(None, None, 302, "Found", {}, "https://127.0.0.1")
        )

    def test_build_output_strictly_normalizes_injected_fetcher_rows(self):
        report = {
            "trade_ledger": {
                "winners": [{"code": "601012", "name": "隆基绿能"}],
                "losers": [],
                "manager_approved_candidates": [],
            }
        }

        def fetcher(code):
            return {
                "secid": "1.601012",
                "provider": "东方财富",
                "source": self.module.EASTMONEY_ENDPOINT,
                "adjustment": "forward-adjusted",
                "volume_unit": "lots",
                "rows": [
                    {
                        "date": "2024-01-05",
                        "open": "20.10",
                        "close": "21.00",
                        "high": "21.50",
                        "low": "19.80",
                        "volume": "1000",
                    }
                ],
            }

        output = self.module.build_output(report, fetcher=fetcher)
        self.assertEqual(output["series"]["601012"]["rows"], [normalized_row()])
        self.assertEqual(output["series"]["601012"]["volume_unit"], "lots")
        self.assertEqual(output["adjustment"], "forward-adjusted")

    def test_build_output_propagates_unclassified_fetcher_errors(self):
        report = {
            "trade_ledger": {
                "winners": [{"code": "601012", "name": "隆基绿能"}],
                "losers": [],
                "manager_approved_candidates": [],
            }
        }
        failures = (
            ValueError("unclassified value error"),
            TypeError("programmer type error"),
            AssertionError("programmer assertion error"),
        )
        for failure in failures:
            with self.subTest(error_type=type(failure).__name__):
                with self.assertRaises(type(failure)) as caught:
                    self.module.build_output(
                        report,
                        fetcher=lambda code, failure=failure: (_ for _ in ()).throw(failure),
                    )
                self.assertIs(caught.exception, failure)

    def test_build_output_uses_fixed_safe_summaries_for_expected_errors(self):
        report = {
            "trade_ledger": {
                "winners": [{"code": "601012", "name": "隆基绿能"}],
                "losers": [],
                "manager_approved_candidates": [],
            }
        }
        failures = (
            (
                self.module.ProviderFetchError("腾讯证券", "HTTPError"),
                "ProviderFetchError: 腾讯证券=HTTPError",
            ),
            (
                self.module.ProviderFallbackError("RemoteDisconnected", "HTTPError"),
                "ProviderFallbackError: 东方财富=RemoteDisconnected; 腾讯证券=HTTPError",
            ),
        )
        for failure, expected in failures:
            failure.args = ("secret https://provider.invalid private response body",)
            with self.subTest(error_type=type(failure).__name__):
                with self.assertRaises(self.module.BatchFetchError) as caught:
                    self.module.build_output(
                        report,
                        fetcher=lambda code, failure=failure: (_ for _ in ()).throw(failure),
                    )
                self.assertEqual(caught.exception.errors, {"601012": expected})
                rendered = " ".join(
                    (
                        str(caught.exception),
                        repr(caught.exception),
                        repr(caught.exception.errors),
                    )
                ).lower()
                self.assertNotIn("secret", rendered)
                self.assertNotIn("://", rendered)
                self.assertNotIn("response body", rendered)

    def test_invalid_injected_result_is_a_fixed_contract_error(self):
        report = {
            "trade_ledger": {
                "winners": [{"code": "601012", "name": "隆基绿能"}],
                "losers": [],
                "manager_approved_candidates": [],
            }
        }
        invalid = {
            "secid": "1.601012",
            "provider": "东方财富",
            "source": self.module.EASTMONEY_ENDPOINT,
            "adjustment": "unadjusted",
            "volume_unit": "lots",
            "rows": [normalized_row()],
        }

        with self.assertRaises(self.module.FetchResultContractError) as contract_error:
            self.module._validate_fetch_result("601012", invalid)
        self.assertEqual(str(contract_error.exception), "invalid fetch result contract")
        self.assertNotIn("adjustment", repr(contract_error.exception))
        self.assertIsNone(contract_error.exception.__context__)
        self.assertIsNone(contract_error.exception.__cause__)
        with self.assertRaises(self.module.BatchFetchError) as caught:
            self.module.build_output(report, fetcher=lambda code: invalid)
        self.assertEqual(
            caught.exception.errors,
            {"601012": "FetchResultContractError: invalid fetch result contract"},
        )

    def test_build_output_accepts_a_share_tencent_fallback_provenance(self):
        report = {
            "trade_ledger": {
                "winners": [{"code": "601012", "name": "隆基绿能"}],
                "losers": [],
                "manager_approved_candidates": [],
            }
        }

        def fetcher(code):
            return {
                "secid": "1.601012",
                "symbol": "sh601012",
                "provider": "腾讯证券",
                "source": self.module.TENCENT_ENDPOINT,
                "adjustment": "unadjusted",
                "volume_unit": "lots",
                "fallback_from": "东方财富",
                "fallback_reason": "RemoteDisconnected",
                "rows": [normalized_row()],
            }

        output = self.module.build_output(report, fetcher=fetcher)
        series = output["series"]["601012"]
        self.assertEqual(series["provider"], "腾讯证券")
        self.assertEqual(series["symbol"], "sh601012")
        self.assertEqual(series["fallback_from"], "东方财富")
        self.assertEqual(series["fallback_reason"], "RemoteDisconnected")
        self.assertEqual(output["adjustment"], "unadjusted")

    def test_build_output_rejects_mixed_or_unsafe_provenance_fields(self):
        report = {
            "trade_ledger": {
                "winners": [{"code": "601012", "name": "隆基绿能"}],
                "losers": [],
                "manager_approved_candidates": [],
            }
        }
        eastmoney = {
            "secid": "1.601012",
            "provider": "东方财富",
            "source": self.module.EASTMONEY_ENDPOINT,
            "adjustment": "forward-adjusted",
            "volume_unit": "lots",
            "rows": [normalized_row()],
        }
        tencent = {
            "secid": "1.601012",
            "symbol": "sh601012",
            "provider": "腾讯证券",
            "source": self.module.TENCENT_ENDPOINT,
            "adjustment": "unadjusted",
            "volume_unit": "lots",
            "fallback_from": "东方财富",
            "fallback_reason": "RemoteDisconnected",
            "rows": [normalized_row()],
        }
        invalid = (
            {**eastmoney, "symbol": "sh601012"},
            {**eastmoney, "fallback_from": "东方财富"},
            {**eastmoney, "fallback_reason": "RemoteDisconnected"},
            {key: value for key, value in tencent.items() if key != "symbol"},
            {**tencent, "symbol": "sz601012"},
            {key: value for key, value in tencent.items() if key != "fallback_from"},
            {key: value for key, value in tencent.items() if key != "fallback_reason"},
            {**tencent, "fallback_from": "腾讯证券"},
            {**tencent, "fallback_reason": "ValueError: private response body"},
            {**tencent, "source": self.module.EASTMONEY_ENDPOINT},
            {**tencent, "adjustment": "forward-adjusted"},
            {**tencent, "volume_unit": "shares"},
        )
        for result in invalid:
            with self.subTest(keys=tuple(result), result=result):
                with self.assertRaises(self.module.BatchFetchError):
                    self.module.build_output(report, fetcher=lambda code, result=result: result)

    def test_build_output_rejects_hk_fallback_fields_and_route_mixes(self):
        report = {
            "trade_ledger": {
                "winners": [{"code": "01810", "name": "小米集团-W"}],
                "losers": [],
                "manager_approved_candidates": [],
            }
        }
        tencent_hk = {
            "secid": "116.01810",
            "symbol": "hk01810",
            "provider": "腾讯证券",
            "source": self.module.TENCENT_ENDPOINT,
            "adjustment": "unadjusted",
            "volume_unit": "shares",
            "rows": [normalized_row()],
        }
        invalid = (
            {**tencent_hk, "fallback_from": "东方财富"},
            {**tencent_hk, "fallback_reason": "RemoteDisconnected"},
            {**tencent_hk, "volume_unit": "lots"},
            {**tencent_hk, "provider": "东方财富", "source": self.module.EASTMONEY_ENDPOINT},
            {**tencent_hk, "symbol": "sh01810"},
        )
        for result in invalid:
            with self.subTest(result=result):
                with self.assertRaises(self.module.BatchFetchError):
                    self.module.build_output(report, fetcher=lambda code, result=result: result)

    def test_build_output_collects_invalid_injected_rows_before_json_writing(self):
        report = {
            "trade_ledger": {
                "winners": [{"code": "601012", "name": "隆基绿能"}],
                "losers": [],
                "manager_approved_candidates": [],
            }
        }
        invalid_rows = (
            {**normalized_row(), "extra": object()},
            {key: value for key, value in normalized_row().items() if key != "volume"},
            normalized_row(date="2024-02-30"),
            normalized_row(open=float("nan")),
            normalized_row(close=0),
            normalized_row(volume=-1),
            normalized_row(low=22, high=21),
        )
        for row in invalid_rows:
            with self.subTest(row_keys=tuple(row)):
                def fetcher(code, invalid=row):
                    return {
                        "secid": "1.601012",
                        "provider": "东方财富",
                        "source": self.module.EASTMONEY_ENDPOINT,
                        "adjustment": "forward-adjusted",
                        "volume_unit": "lots",
                        "rows": [invalid],
                    }

                with self.assertRaises(self.module.BatchFetchError) as caught:
                    self.module.build_output(report, fetcher=fetcher)
                self.assertIn("601012", caught.exception.errors)

    def test_build_output_records_both_providers_and_series_sources(self):
        report = {
            "trade_ledger": {
                "winners": [{"code": "601012", "name": "隆基绿能"}],
                "losers": [{"code": "01810", "name": "小米集团-W"}],
                "manager_approved_candidates": [],
            }
        }

        def fetcher(code):
            if len(code) == 5:
                return {
                    "secid": "116.01810",
                    "symbol": "hk01810",
                    "provider": "腾讯证券",
                    "source": self.module.TENCENT_ENDPOINT,
                    "adjustment": "unadjusted",
                    "volume_unit": "shares",
                    "rows": [normalized_row()],
                }
            return {
                "secid": "1.601012",
                "provider": "东方财富",
                "source": self.module.EASTMONEY_ENDPOINT,
                "adjustment": "forward-adjusted",
                "volume_unit": "lots",
                "rows": [normalized_row()],
            }

        output = self.module.build_output(report, fetcher=fetcher, fetched_at="2026-08-10")
        self.assertEqual(output["fetched_at"], "2026-08-10")
        self.assertEqual(output["period"], "weekly")
        self.assertEqual(output["adjustment"], "mixed")
        self.assertEqual(
            output["source"]["providers"],
            [
                {
                    "provider": "东方财富",
                    "endpoint": self.module.EASTMONEY_ENDPOINT,
                    "adjustment": "forward-adjusted",
                    "volume_unit": "lots",
                },
                {
                    "provider": "腾讯证券",
                    "endpoint": self.module.TENCENT_ENDPOINT,
                    "adjustment": "unadjusted",
                    "volume_unit": "shares",
                },
            ],
        )
        self.assertEqual(output["series"]["601012"]["name"], "隆基绿能")
        self.assertEqual(output["series"]["601012"]["provider"], "东方财富")
        self.assertEqual(output["series"]["601012"]["adjustment"], "forward-adjusted")
        self.assertEqual(output["series"]["601012"]["volume_unit"], "lots")
        self.assertEqual(output["series"]["01810"]["source"], self.module.TENCENT_ENDPOINT)
        self.assertEqual(output["series"]["01810"]["adjustment"], "unadjusted")
        self.assertEqual(output["series"]["01810"]["volume_unit"], "shares")

    def test_provider_metadata_keeps_tencent_a_share_and_hk_units_separate(self):
        report = {
            "trade_ledger": {
                "winners": [{"code": "601012", "name": "隆基绿能"}],
                "losers": [{"code": "01810", "name": "小米集团-W"}],
                "manager_approved_candidates": [],
            }
        }

        def fetcher(code):
            if code == "601012":
                return {
                    "secid": "1.601012",
                    "symbol": "sh601012",
                    "provider": "腾讯证券",
                    "source": self.module.TENCENT_ENDPOINT,
                    "adjustment": "unadjusted",
                    "volume_unit": "lots",
                    "fallback_from": "东方财富",
                    "fallback_reason": "RemoteDisconnected",
                    "rows": [normalized_row()],
                }
            return {
                "secid": "116.01810",
                "symbol": "hk01810",
                "provider": "腾讯证券",
                "source": self.module.TENCENT_ENDPOINT,
                "adjustment": "unadjusted",
                "volume_unit": "shares",
                "rows": [normalized_row()],
            }

        output = self.module.build_output(report, fetcher=fetcher)
        self.assertEqual(
            output["source"]["providers"],
            [
                {
                    "provider": "腾讯证券",
                    "endpoint": self.module.TENCENT_ENDPOINT,
                    "adjustment": "unadjusted",
                    "volume_unit": "lots",
                },
                {
                    "provider": "腾讯证券",
                    "endpoint": self.module.TENCENT_ENDPOINT,
                    "adjustment": "unadjusted",
                    "volume_unit": "shares",
                },
            ],
        )

    def test_build_output_derives_hk_only_adjustment(self):
        report = {
            "trade_ledger": {
                "winners": [{"code": "01810", "name": "小米集团-W"}],
                "losers": [],
                "manager_approved_candidates": [],
            }
        }

        def fetcher(code):
            return {
                "secid": "116.01810",
                "symbol": "hk01810",
                "provider": "腾讯证券",
                "source": self.module.TENCENT_ENDPOINT,
                "adjustment": "unadjusted",
                "volume_unit": "shares",
                "rows": [normalized_row()],
            }

        output = self.module.build_output(report, fetcher=fetcher)
        self.assertEqual(output["adjustment"], "unadjusted")
        self.assertEqual(output["series"]["01810"]["volume_unit"], "shares")

    def test_build_output_rejects_injected_fetcher_adjustment_mismatches(self):
        report = {
            "trade_ledger": {
                "winners": [{"code": "601012", "name": "隆基绿能"}],
                "losers": [{"code": "01810", "name": "小米集团-W"}],
                "manager_approved_candidates": [],
            }
        }

        def fetcher(code):
            if len(code) == 5:
                return {
                    "secid": "116.01810",
                    "symbol": "hk01810",
                    "provider": "腾讯证券",
                    "source": self.module.TENCENT_ENDPOINT,
                    "adjustment": "forward-adjusted",
                    "volume_unit": "shares",
                    "rows": [normalized_row()],
                }
            return {
                "secid": "1.601012",
                "provider": "东方财富",
                "source": self.module.EASTMONEY_ENDPOINT,
                "adjustment": "unadjusted",
                "volume_unit": "lots",
                "rows": [normalized_row()],
            }

        with self.assertRaises(self.module.BatchFetchError) as caught:
            self.module.build_output(report, fetcher=fetcher)
        self.assertEqual(set(caught.exception.errors), {"601012", "01810"})
        for message in caught.exception.errors.values():
            self.assertEqual(
                message,
                "FetchResultContractError: invalid fetch result contract",
            )

    def test_build_output_rejects_injected_fetcher_volume_unit_mismatches(self):
        report = {
            "trade_ledger": {
                "winners": [{"code": "601012", "name": "隆基绿能"}],
                "losers": [{"code": "01810", "name": "小米集团-W"}],
                "manager_approved_candidates": [],
            }
        }

        def fetcher(code):
            if len(code) == 5:
                return {
                    "secid": "116.01810",
                    "symbol": "hk01810",
                    "provider": "腾讯证券",
                    "source": self.module.TENCENT_ENDPOINT,
                    "adjustment": "unadjusted",
                    "volume_unit": "lots",
                    "rows": [normalized_row()],
                }
            return {
                "secid": "1.601012",
                "provider": "东方财富",
                "source": self.module.EASTMONEY_ENDPOINT,
                "adjustment": "forward-adjusted",
                "volume_unit": "shares",
                "rows": [normalized_row()],
            }

        with self.assertRaises(self.module.BatchFetchError) as caught:
            self.module.build_output(report, fetcher=fetcher)
        self.assertEqual(set(caught.exception.errors), {"601012", "01810"})
        for message in caught.exception.errors.values():
            self.assertEqual(
                message,
                "FetchResultContractError: invalid fetch result contract",
            )

    def test_cli_writes_atomically_and_creates_parent_directory(self):
        report = {
            "trade_ledger": {
                "winners": [{"code": "601012", "name": "隆基绿能"}],
                "losers": [],
                "manager_approved_candidates": [],
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "report.json"
            output_path = Path(tmp) / "nested" / "stock-ohlc.json"
            report_path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")

            def fetcher(code):
                return {
                    "secid": "1.601012",
                    "provider": "东方财富",
                    "source": self.module.EASTMONEY_ENDPOINT,
                    "adjustment": "forward-adjusted",
                    "volume_unit": "lots",
                    "rows": [normalized_row()],
                }

            result = self.module.main(
                ["--report", str(report_path), "--output", str(output_path)],
                fetcher=fetcher,
                fetched_at="2026-08-10",
            )
            self.assertEqual(result, 0)
            self.assertTrue(output_path.is_file())
            self.assertEqual(json.loads(output_path.read_text())["series"]["601012"]["name"], "隆基绿能")
            self.assertEqual(list(output_path.parent.glob("*.tmp")), [])

    def test_cli_collects_all_stock_errors_and_does_not_write_partial_output(self):
        report = {
            "trade_ledger": {
                "winners": [
                    {"code": "601012", "name": "隆基绿能"},
                    {"code": "300308", "name": "中际旭创"},
                ],
                "losers": [{"code": "01810", "name": "小米集团-W"}],
                "manager_approved_candidates": [],
            }
        }
        calls = []

        def fetcher(code):
            calls.append(code)
            if code in {"601012", "01810"}:
                provider = "东方财富" if code == "601012" else "腾讯证券"
                raise self.module.ProviderFetchError(provider, "RemoteDisconnected")
            return {
                "secid": "0.300308",
                "provider": "东方财富",
                "source": self.module.EASTMONEY_ENDPOINT,
                "adjustment": "forward-adjusted",
                "volume_unit": "lots",
                "rows": [normalized_row()],
            }

        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "report.json"
            output_path = Path(tmp) / "stock-ohlc.json"
            report_path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
            stderr = io.StringIO()
            result = self.module.main(
                ["--report", str(report_path), "--output", str(output_path)],
                fetcher=fetcher,
                fetched_at="2026-08-10",
                stderr=stderr,
            )
            self.assertEqual(result, 1)
            self.assertEqual(calls, ["601012", "300308", "01810"])
            self.assertIn("601012", stderr.getvalue())
            self.assertIn("01810", stderr.getvalue())
            self.assertFalse(output_path.exists())

    def test_atomic_replace_failure_preserves_old_target_and_cleans_temp_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "stock-ohlc.json"
            output_path.write_text("old-content", encoding="utf-8")
            with patch.object(Path, "replace", side_effect=OSError("replace failed")):
                with self.assertRaises(OSError):
                    self.module.write_json_atomic(output_path, {"new": "content"})
            self.assertEqual(output_path.read_text(encoding="utf-8"), "old-content")
            self.assertEqual(list(output_path.parent.glob(f".{output_path.name}.*.tmp")), [])

    def test_cli_rejects_user_supplied_url_options(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.module.main(
                [
                    "--report",
                    "report.json",
                    "--output",
                    "stock-ohlc.json",
                    "--url",
                    "http://127.0.0.1",
                ]
            )


if __name__ == "__main__":
    unittest.main()
