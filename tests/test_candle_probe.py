"""Read-only broker candle evidence with bounded fixture data and no orders."""

import json

import pytest
from test_market_data import NOW, Terminal, bar

from aura.candle_probe import probe_candle_time
from aura.collector import AccountBinding

BINDING = AccountBinding(12345, "Fixture-Demo")


class ProbeTerminal(Terminal):
    def __init__(self, tick_offset=10800, candle_offset=10800):
        super().__init__()
        self.account.company = "Fixture broker"
        self.tick.time_msc += tick_offset * 1000
        self.bars = [bar(NOW // 1000 + candle_offset - i * 60) for i in (2, 1, 0)]
        self.position_calls = []
        self.switch_on_position = False
        self.range_empty = False

    def symbol_info_tick(self, symbol):
        result = super().symbol_info_tick(symbol)
        result.time_msc += 1
        return result

    def copy_rates_from_pos(self, symbol, timeframe, start, count):
        self.position_calls.append((symbol, timeframe, start, count))
        if self.switch_on_position:
            self.account.login = 67890
        return self.bars

    def copy_rates_range(self, *args):
        if self.range_empty:
            return []
        return super().copy_rates_range(*args)


def probe(port, **kwargs):
    return probe_candle_time(port, "XAUUSDm", BINDING, clock=lambda: NOW,
                             wait=lambda _: None, **kwargs)


@pytest.mark.parametrize("candle_offset", [0, 7200, 10800])
def test_c01_quote_and_candle_offsets_reported_independently(candle_offset):
    port = ProbeTerminal(candle_offset=candle_offset)
    report = probe(port)
    assert report["probe_completed"] and report["range_replays_match"]
    assert report["tick_timestamp_advanced"]
    assert report["tick_timestamps_nondecreasing"]
    assert len(report["samples"]) == 3
    first = report["samples"][0]
    assert first["raw_last_bar_minus_utc_bucket_seconds"] == candle_offset
    # Quote is just before its next minute boundary.
    assert first["raw_last_bar_minus_tick_bucket_seconds"] == candle_offset - 10800 + 60
    assert first["raw_tick_age_seconds"] < -10799
    assert report["execution_allowed"] is report["history_time_verified"] is False
    assert report["history_import_authorized"] is report["stream_modified"] is False
    assert "12345" not in json.dumps(report)
    assert all(call[2:] == (0, 5) for call in port.position_calls)


@pytest.mark.parametrize("field,value,error", [
    ("trade_mode", 2, "not_demo"), ("login", 67890, "account_mismatch"),
    ("server", "Other", "account_mismatch"),
])
def test_c02_wrong_identity_blocks_before_candle_reads(field, value, error):
    port = ProbeTerminal()
    setattr(port.account, field, value)
    report = probe(port)
    assert report["error"] == error and not report["probe_completed"]
    assert not port.position_calls


def test_c03_switch_during_read_discards_sample():
    port = ProbeTerminal()
    port.switch_on_position = True
    report = probe(port)
    assert report["error"] == "account_mismatch" and not report["samples"]
    assert not port.calls


@pytest.mark.parametrize("case", ["empty", "too_many", "unsorted", "invalid_ohlc", "duplicate"])
def test_c04_malformed_candles_never_pass(case):
    port = ProbeTerminal()
    if case == "empty":
        port.bars = []
    elif case == "too_many":
        port.bars *= 2
    elif case == "unsorted":
        port.bars.reverse()
    elif case == "invalid_ohlc":
        port.bars[0]["high"] = 1
    elif case == "duplicate":
        port.bars[1] = port.bars[0]
    report = probe(port)
    assert not report["probe_completed"] and not report["samples"]


def test_c05_range_disagreement_is_visible_not_authorization():
    port = ProbeTerminal()
    port.range_empty = True
    report = probe(port)
    assert report["probe_completed"] and not report["range_replays_match"]
    assert not report["history_time_verified"]


def test_c06_native_exception_is_sanitized():
    port = ProbeTerminal()

    def broken(*_):
        raise RuntimeError("secret account detail")

    port.copy_rates_from_pos = broken
    report = probe(port)
    assert report["error"] == "probe_read_failed"
    assert "secret" not in json.dumps(report)


@pytest.mark.parametrize("kwargs", [dict(samples=1), dict(samples=6), dict(samples=True),
    dict(interval=0), dict(interval=3), dict(timeframe="M2")])
def test_c07_probe_work_is_bounded(kwargs):
    with pytest.raises(ValueError):
        probe(ProbeTerminal(), **kwargs)


def test_c08_no_tick_advance_never_claims_verified_time():
    port = ProbeTerminal()
    port.symbol_info_tick = lambda _: port.tick
    report = probe(port)
    assert report["probe_completed"] and not report["tick_timestamp_advanced"]
    assert not report["history_time_verified"]


def test_c09_out_of_range_replay_rejected():
    port = ProbeTerminal()
    port.copy_rates_range = lambda *_: [bar(NOW // 1000 - 86400)]
    report = probe(port)
    assert report["error"] == "range_out_of_bounds" and not report["probe_completed"]


def test_c10_clock_regression_rejected():
    values = iter([NOW, NOW, NOW - 1])
    report = probe_candle_time(ProbeTerminal(), "XAUUSDm", BINDING,
                               clock=lambda: next(values), wait=lambda _: None)
    assert report["error"] == "clock_regression" and not report["probe_completed"]


def test_c11_cli_outputs_json_without_creating_database(tmp_path, monkeypatch, capsys):
    import sys

    from aura import diagnose

    port = ProbeTerminal()
    closed = []
    port.initialize = lambda **_: True
    port.shutdown = lambda: closed.append(True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "argv", ["diagnose", "--symbol", "XAUUSDm", "--candle-time-probe"])
    monkeypatch.setitem(sys.modules, "MetaTrader5", port)
    monkeypatch.setenv("AURA_MT5_TERMINAL_PATH", "fixture-terminal")
    monkeypatch.setenv("AURA_MT5_EXPECTED_LOGIN", "12345")
    monkeypatch.setenv("AURA_MT5_EXPECTED_SERVER", "Fixture-Demo")
    monkeypatch.setattr("aura.candle_probe.time.sleep", lambda _: None)
    diagnose.main()
    output = json.loads(capsys.readouterr().out)
    assert output["probe_completed"] and not output["history_import_authorized"]
    assert closed == [True]
    assert list(tmp_path.iterdir()) == []


def test_c12_probe_requires_explicit_identity(monkeypatch):
    import sys

    from aura import diagnose

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "argv", ["diagnose", "--symbol", "XAUUSDm", "--candle-time-probe"])
    monkeypatch.setenv("AURA_MT5_TERMINAL_PATH", "fixture-terminal")
    monkeypatch.delenv("AURA_MT5_EXPECTED_LOGIN", raising=False)
    monkeypatch.delenv("AURA_MT5_EXPECTED_SERVER", raising=False)
    with pytest.raises(SystemExit) as caught:
        diagnose.main()
    assert caught.value.code == 2
