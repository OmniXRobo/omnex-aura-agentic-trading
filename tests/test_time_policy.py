"""Time normalization remains explicit, scoped, expiring and fail-closed."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
from test_market_data import FEED, NOW, Terminal

from aura.collector import AccountBinding, Collector, MarketDataError
from aura.diagnose import report_terminal
from aura.market import Quote
from aura.market_store import MarketStore
from aura.store import Store
from aura.time_policy import QuoteTimePolicy, load_policy


def policy(**changes):
    return QuoteTimePolicy(**(dict(
        server="Fixture-Demo", symbol="XAUUSDm", offset_seconds=10800,
        verified_at_msc=NOW - 1000, expires_at_msc=NOW + 60000,
        evidence="Controlled fixture UTC comparison",
    ) | changes))


def collector(tmp_path, terminal, rule):
    memory = MarketStore(Store(tmp_path))
    return Collector(terminal, memory, FEED, AccountBinding(12345, "Fixture-Demo"),
                     clock=lambda: NOW, time_policy=rule), memory


def test_t01_corrected_quote_preserves_raw_time_after_restart(tmp_path):
    terminal = Terminal()
    terminal.tick.time_msc += 10800000
    c, memory = collector(tmp_path, terminal, policy())
    assert c.poll("XAUUSDm")["inserted"]
    restarted = MarketStore(Store(tmp_path))
    data = restarted.events(FEED.key, "XAUUSDm", "quote")[0]["data"]
    assert data["time_msc"] == NOW - 100
    assert data["raw_time_msc"] == terminal.tick.time_msc
    assert data["time_offset_seconds"] == 10800 and len(data["time_policy"]) == 64
    with restarted.store.connect("historical") as db:
        saved = db.execute("SELECT payload FROM quote_time_policies WHERE digest=?",
                           (data["time_policy"],)).fetchone()
        assert QuoteTimePolicy.model_validate_json(saved[0]) == policy()
    assert not c.poll("XAUUSDm")["inserted"]
    assert memory.store.records("demo") == memory.store.records("virtual") == []


@pytest.mark.parametrize("age,code", [(5001, "stale_tick"), (-1, "future_tick")])
def test_t02_correction_does_not_relax_freshness(tmp_path, age, code):
    terminal = Terminal()
    terminal.tick.time_msc = NOW + 10800000 - age
    c, memory = collector(tmp_path, terminal, policy())
    with pytest.raises(MarketDataError) as error:
        c.poll("XAUUSDm")
    assert error.value.code == code
    assert not memory.events(FEED.key, "XAUUSDm", "quote")


@pytest.mark.parametrize("change", [dict(server="Other-Demo"), dict(symbol="Other"),
    dict(expires_at_msc=NOW), dict(verified_at_msc=NOW + 1)])
def test_t03_wrong_or_expired_policy_blocks(tmp_path, change):
    c, memory = collector(tmp_path, Terminal(), policy(**change))
    with pytest.raises(MarketDataError) as error:
        c.poll("XAUUSDm")
    assert error.value.code == "time_policy_invalid"
    assert not memory.events(FEED.key, "XAUUSDm", "quote")


@pytest.mark.parametrize("change", [dict(offset_seconds=True), dict(offset_seconds=10801),
    dict(expires_at_msc=NOW + 86400000), dict(offset_seconds=100000)])
def test_t04_malformed_policy_rejected(change):
    with pytest.raises(ValidationError):
        policy(**change)


def test_t05_nonzero_quote_correction_never_applied_to_history(tmp_path):
    terminal = Terminal()
    c, memory = collector(tmp_path, terminal, policy())
    with pytest.raises(MarketDataError) as error:
        c.history("XAUUSDm", "M1", datetime.fromtimestamp(NOW / 1000 - 60, timezone.utc),
                  datetime.fromtimestamp(NOW / 1000, timezone.utc))
    assert error.value.code == "history_time_unverified"
    assert not terminal.calls and not memory.events(FEED.key, "XAUUSDm", "candle")


def test_t06_stream_cannot_change_offset_after_restart(tmp_path):
    terminal = Terminal()
    c, _ = collector(tmp_path, terminal, None)
    c.poll("XAUUSDm")
    terminal.tick.time_msc += 10800000
    c, memory = collector(tmp_path, terminal, policy())
    with pytest.raises(MarketDataError) as error:
        c.poll("XAUUSDm")
    assert error.value.code == "stream_time_conflict"
    assert len(memory.events(FEED.key, "XAUUSDm", "quote")) == 1


def test_t07_legacy_stream_not_reinterpreted(tmp_path):
    c, memory = collector(tmp_path, Terminal(), None)
    memory.append(FEED, c.quote("XAUUSDm"), NOW)
    with pytest.raises(MarketDataError):
        memory.bind_quote_time(FEED, 10800)


def test_t08_diagnostic_reports_both_ages_and_no_authority():
    terminal = Terminal()
    terminal.account.company = "Fixture"
    terminal.tick.time_msc += 10800000
    report = report_terminal(terminal, "XAUUSDm", 12345, "Fixture-Demo", NOW, policy())
    assert report["raw_tick_age_seconds"] == -10799.9
    assert report["tick_age_seconds"] == .1 and report["terminal_checks_passed"]
    assert report["history_time_verified"] is report["execution_allowed"] is False


def test_t09_raw_provenance_must_agree():
    with pytest.raises(ValidationError):
        Quote(symbol="XAUUSD", time_msc=NOW, raw_time_msc=NOW, time_offset_seconds=10800,
              bid=3000, ask=3001, flags=6)


def test_t10_policy_round_trip(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text(policy().model_dump_json())
    assert load_policy(path) == policy()
    assert load_policy(None) is None


def test_t11_history_still_blocked_when_policy_flag_omitted_on_restart(tmp_path):
    terminal = Terminal()
    terminal.tick.time_msc += 10800000
    c, _ = collector(tmp_path, terminal, policy())
    c.poll("XAUUSDm")
    restarted, _ = collector(tmp_path, terminal, None)
    with pytest.raises(MarketDataError) as error:
        restarted.history("XAUUSDm", "M1",
                          datetime.fromtimestamp(NOW / 1000 - 60, timezone.utc),
                          datetime.fromtimestamp(NOW / 1000, timezone.utc))
    assert error.value.code == "history_time_unverified"
    assert not terminal.calls
