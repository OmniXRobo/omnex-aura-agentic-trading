"""Dated candle normalization, provenance and restart interpretation isolation."""

import json
import sqlite3
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
from test_market_data import FEED, NOW, Terminal, bar

from aura.collector import AccountBinding, Collector, MarketDataError
from aura.market import Candle, Feed
from aura.market_store import MarketStore
from aura.store import Store
from aura.time_policy import HistoryTimePolicy, load_history_policy

START, END = NOW // 1000 - 300, NOW // 1000


def policy(**changes):
    return HistoryTimePolicy(**(dict(
        server="Fixture-Demo", symbol="XAUUSDm", timeframe="M1", offset_seconds=10800,
        valid_from_utc=START, valid_to_utc=END, reviewed_at_msc=NOW,
        evidence="Fixture independent candle position/range and UTC review",
    ) | changes))


def setup(tmp_path, feed=FEED):
    memory, terminal = MarketStore(Store(tmp_path)), Terminal()
    terminal.bars = [bar(START + 10800 + i * 60) for i in range(5)]
    c = Collector(terminal, memory, feed, AccountBinding(12345, "Fixture-Demo"),
                  clock=lambda: NOW)
    return c, terminal, memory


def run(c, rule, start=START, end=END, page_bars=2):
    return c.history("XAUUSDm", "M1", datetime.fromtimestamp(start, timezone.utc),
                     datetime.fromtimestamp(end, timezone.utc), page_bars,
                     history_policy=rule)


def test_h01_shifted_query_and_raw_provenance_survive_restart(tmp_path):
    c, terminal, memory = setup(tmp_path)
    result = run(c, policy())
    assert result["inserted"] == 5 and result["time_verification"] == "operator_attested"
    assert int(terminal.calls[0][0].timestamp()) == START + 10800
    assert int(terminal.calls[0][1].timestamp()) == START + 120 - 1 + 10800
    assert result["potential_gaps"] == []
    restarted = MarketStore(Store(tmp_path))
    saved = restarted.events(FEED.key, "XAUUSDm", "candle")
    assert len(saved) == 5
    for item in saved:
        data = item["data"]
        assert data["raw_open_time"] - data["open_time"] == 10800
        assert data["time_policy"] == result["time_policy"]
        assert item["event_time"] == data["open_time"] * 1000
    with restarted.store.connect() as db:
        payload = db.execute("SELECT payload FROM history_time_policies").fetchone()[0]
        assert HistoryTimePolicy.model_validate_json(payload) == policy()
    c, _, _ = setup(tmp_path)
    assert run(c, policy())["duplicates"] == 5
    assert not memory.store.records("demo") and not memory.store.records("virtual")


@pytest.mark.parametrize("change", [dict(server="Other"), dict(symbol="Other"),
    dict(timeframe="M5"), dict(reviewed_at_msc=NOW + 1),
    dict(valid_from_utc=START + 60), dict(valid_to_utc=END - 60)])
def test_h02_scope_rejected_before_native_history_or_candle_claim(tmp_path, change):
    c, terminal, memory = setup(tmp_path)
    with pytest.raises(MarketDataError) as caught:
        run(c, policy(**change))
    assert caught.value.code == "history_time_policy_invalid"
    assert not terminal.calls
    with memory.store.connect() as db:
        assert db.execute("SELECT count(*) FROM history_time_bindings").fetchone()[0] == 0


@pytest.mark.parametrize("change", [dict(timeframe="D1"), dict(timeframe="M2"),
    dict(offset_seconds=True), dict(offset_seconds=10801), dict(valid_to_utc=START),
    dict(valid_from_utc=START - 32 * 86400), dict(reviewed_at_msc=(END - 1) * 1000)])
def test_h03_invalid_policy(change):
    with pytest.raises(ValidationError):
        policy(**change)


def test_h04_closed_bars_only_using_normalized_time(tmp_path):
    c, _, memory = setup(tmp_path)
    result = run(c, policy(), end=END - 30)
    assert result["inserted"] == 4 and result["open_bars_skipped"] == 1
    assert len(memory.events(FEED.key, "XAUUSDm", "candle")) == 4


def test_h05_offset_conflict_retained_after_failed_or_empty_import(tmp_path):
    c, terminal, _ = setup(tmp_path)
    terminal.bars = []
    assert run(c, policy())["inserted"] == 0
    c, terminal, _ = setup(tmp_path)
    with pytest.raises(MarketDataError) as caught:
        run(c, policy(offset_seconds=7200))
    assert caught.value.code == "history_time_conflict" and not terminal.calls


def test_h06_raw_overlap_cannot_be_reinterpreted_in_disjoint_utc_interval(tmp_path):
    c, _, _ = setup(tmp_path)
    run(c, policy())
    # Same raw transport range, different UTC interval and correction.
    start, end = START + 3600, END + 3600
    rule = policy(offset_seconds=7200, valid_from_utc=start, valid_to_utc=end,
                  reviewed_at_msc=NOW + 3600000)
    c.clock = lambda: NOW + 3600000
    with pytest.raises(MarketDataError) as caught:
        run(c, rule, start, end)
    assert caught.value.code == "history_time_conflict"


def test_h07_nonoverlapping_dated_offsets_allowed_without_guessing_DST(tmp_path):
    c, terminal, _ = setup(tmp_path)
    run(c, policy())
    start, end = START - 86400, END - 86400
    terminal.bars = [bar(start + 7200 + i * 60) for i in range(5)]
    rule = policy(offset_seconds=7200, valid_from_utc=start, valid_to_utc=end)
    assert run(c, rule, start, end)["inserted"] == 5


def test_h08_legacy_candles_not_silently_reinterpreted(tmp_path):
    c, terminal, memory = setup(tmp_path)
    terminal.bars = [bar(START)]
    run(c, None)
    with pytest.raises(MarketDataError) as caught:
        run(c, policy())
    assert caught.value.code == "history_time_conflict"
    assert len(memory.events(FEED.key, "XAUUSDm", "candle")) == 1


def test_h09_mt5_requires_explicit_policy_even_without_quote_correction(tmp_path):
    feed = Feed(broker="Equiti", source="mt5_demo", stream="history-test")
    c, terminal, _ = setup(tmp_path, feed)
    with pytest.raises(MarketDataError) as caught:
        run(c, None)
    assert caught.value.code == "history_time_unverified" and not terminal.calls
    assert run(c, policy())["inserted"] == 5


def test_h10_bad_page_does_not_persist_any_of_that_page(tmp_path):
    c, terminal, memory = setup(tmp_path)
    terminal.bars[1]["high"] = 1
    with pytest.raises(MarketDataError):
        run(c, policy())
    assert not memory.events(FEED.key, "XAUUSDm", "candle")


def test_h11_policy_and_bindings_append_only(tmp_path):
    c, _, memory = setup(tmp_path)
    run(c, policy())
    for table in ("history_time_policies", "history_time_bindings"):
        with pytest.raises(sqlite3.IntegrityError):
            with memory.store.connect() as db:
                db.execute(f"DELETE FROM {table}")


def test_h12_json_roundtrip_and_provenance_validation(tmp_path):
    path = tmp_path / "history.json"
    path.write_text(policy().model_dump_json())
    assert load_history_policy(path) == policy() and load_history_policy(None) is None
    data = dict(symbol="XAUUSDm", timeframe="M1", open_time=START,
                raw_open_time=START + 10800, time_offset_seconds=7200,
                open=3000, high=3002, low=2999, close=3001, tick_volume=1,
                spread_points=20, real_volume=0)
    with pytest.raises(ValidationError):
        Candle(**data)
    assert "12345" not in json.dumps(policy().model_dump())


def test_h13_competing_offset_claims_are_serialized(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    _, _, memory = setup(tmp_path)

    def claim(offset):
        try:
            memory.bind_history_time(FEED, "XAUUSDm", "M1", START, END, offset,
                                     policy(offset_seconds=offset))
            return "accepted"
        except MarketDataError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(claim, [10800, 7200]))
    assert sorted(outcomes) == ["accepted", "history_time_conflict"]
    with memory.store.connect() as db:
        assert db.execute("SELECT count(*) FROM history_time_bindings").fetchone()[0] == 1


def test_h14_windows_cli_import_uses_separate_history_policy(tmp_path, monkeypatch, capsys):
    import sys

    from aura import collect

    _, terminal, _ = setup(tmp_path / "fixture")
    closed = []
    terminal.initialize = lambda **_: True
    terminal.shutdown = lambda: closed.append(True)
    path = tmp_path / "policy.json"
    path.write_text(policy().model_dump_json())
    data_dir = tmp_path / "collected"
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "argv", ["collect", "--broker", "Equiti", "--symbol", "XAUUSDm",
        "--data-dir", str(data_dir), "--history-time-policy", str(path),
        "--history-from", datetime.fromtimestamp(START, timezone.utc).isoformat(),
        "--history-to", datetime.fromtimestamp(END, timezone.utc).isoformat()])
    monkeypatch.setitem(sys.modules, "MetaTrader5", terminal)
    monkeypatch.setenv("AURA_MT5_TERMINAL_PATH", "fixture-terminal")
    monkeypatch.setenv("AURA_MT5_EXPECTED_LOGIN", "12345")
    monkeypatch.setenv("AURA_MT5_EXPECTED_SERVER", "Fixture-Demo")
    collect.main()
    result = json.loads(capsys.readouterr().out)
    assert result["inserted"] == 5 and not result["execution_allowed"]
    assert closed == [True]
    memory = MarketStore(Store(data_dir))
    assert len(memory.events("mt5_demo:Equiti:demo-1", "XAUUSDm", "candle")) == 5
