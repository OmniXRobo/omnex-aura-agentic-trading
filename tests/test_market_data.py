"""M2 fixture tests: no broker login, network or order submission."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from aura.api import create_app
from aura.collector import AccountBinding, Collector, MarketDataError
from aura.config import Settings
from aura.market import Candle, Feed, GoldContract, Quote
from aura.market_store import MarketStore
from aura.store import Store

NOW = 1700000400000
ADMIN = "a" * 40
VIEWER = "b" * 40
FEED = Feed(broker="Exness", source="fixture", stream="test-demo")
CONTRACT = dict(
    symbol="XAUUSDm",
    currency_base="XAU",
    currency_profit="USD",
    digits=2,
    point=0.01,
    trade_tick_size=0.01,
    trade_tick_value=1,
    trade_contract_size=100,
    volume_min=0.01,
    volume_max=100,
    volume_step=0.01,
    trade_stops_level=10,
    trade_freeze_level=0,
    trade_mode=4,
    filling_mode=1,
    swap_mode=1,
    swap_long=-2.0,
    swap_short=1.0,
)


def bar(opening, close=3001):
    return dict(
        time=opening,
        open=3000,
        high=3002,
        low=2999,
        close=close,
        tick_volume=50,
        spread=20,
        real_volume=0,
    )


class Terminal:
    ACCOUNT_TRADE_MODE_DEMO = 0
    TIMEFRAME_M1 = 1

    def __init__(self):
        self.account = NS(login=12345, server="Fixture-Demo", trade_mode=0)
        self.connected = True
        self.symbol = NS(
            name=CONTRACT["symbol"], **{k: v for k, v in CONTRACT.items() if k != "symbol"}
        )
        self.tick = NS(time_msc=NOW - 100, bid=3000, ask=3000.2, flags=6)
        self.bars = []
        self.calls = []
        self.after_read = None

    def account_info(self):
        return self.account

    def terminal_info(self):
        return NS(connected=self.connected)

    def symbols_get(self):
        return [
            self.symbol,
            NS(name="GOLDEUR", currency_base="XAU", currency_profit="EUR"),
            NS(name="GOLD-MINER", currency_base="STOCK", currency_profit="USD"),
        ]

    def symbol_info(self, symbol):
        return self.symbol

    def symbol_info_tick(self, symbol):
        if self.after_read:
            self.after_read()
        return self.tick

    def copy_rates_range(self, symbol, timeframe, date_from, date_to):
        assert date_from.utcoffset() == timedelta(0)
        assert date_to.utcoffset() == timedelta(0)
        self.calls.append((date_from, date_to))
        return [r for r in self.bars if date_from.timestamp() <= r["time"] <= date_to.timestamp()]

    def order_send(self, *_):
        pytest.fail("Market collection must never submit orders")


@pytest.fixture
def setup(tmp_path):
    store = Store(tmp_path)
    memory = MarketStore(store)
    terminal = Terminal()
    collector = Collector(
        terminal, memory, FEED, AccountBinding(12345, "Fixture-Demo"), clock=lambda: NOW
    )
    return collector, terminal, memory


def test_m2_01_contract_discovery_uses_currency_metadata(setup):
    collector, _, _ = setup
    assert collector.discover() == ["XAUUSDm"]
    assert collector.contract("XAUUSDm").trade_contract_size == 100


@pytest.mark.parametrize(
    "change",
    [
        dict(currency_profit="EUR"),
        dict(volume_min=200),
        dict(trade_tick_size=0),
        dict(point=0.1),
        dict(swap_short=float("nan")),
    ],
)
def test_m2_02_invalid_contracts(change):
    with pytest.raises(ValidationError):
        GoldContract(**(CONTRACT | change))


@pytest.mark.parametrize(
    "field,value",
    [("trade_mode", 1), ("trade_mode", 2), ("login", 67890), ("server", "Other-Demo")],
)
def test_m2_03_reject_wrong_account(setup, field, value):
    collector, terminal, memory = setup
    setattr(terminal.account, field, value)
    with pytest.raises(MarketDataError):
        collector.poll("XAUUSDm")
    assert memory.events(FEED.key, "XAUUSDm", "quote") == []
    assert memory.statuses(NOW)[0]["state"] == "blocked"


def test_m2_04_disconnect_and_account_switch_during_read(setup):
    collector, terminal, memory = setup
    terminal.connected = False
    with pytest.raises(MarketDataError):
        collector.poll("XAUUSDm")
    terminal.connected = True
    terminal.after_read = lambda: setattr(terminal.account, "login", 67890)
    with pytest.raises(MarketDataError):
        collector.poll("XAUUSDm")
    assert memory.events(FEED.key, "XAUUSDm", "quote") == []


@pytest.mark.parametrize(
    "change",
    [
        dict(time_msc=NOW - 5001),
        dict(time_msc=NOW + 1),
        dict(ask=2999),
        dict(bid=0),
        dict(ask=float("inf")),
    ],
)
def test_m2_05_invalid_or_stale_quote_blocked(setup, change):
    collector, terminal, memory = setup
    for key, value in change.items():
        setattr(terminal.tick, key, value)
    with pytest.raises(MarketDataError):
        collector.poll("XAUUSDm")
    assert memory.events(FEED.key, "XAUUSDm", "quote") == []


def test_m2_06_quote_dedupe_and_same_millisecond_changes(setup):
    collector, terminal, memory = setup
    assert collector.poll("XAUUSDm")["inserted"]
    assert not collector.poll("XAUUSDm")["inserted"]
    terminal.tick.bid = 3000.1
    assert collector.poll("XAUUSDm")["inserted"]
    assert len(memory.events(FEED.key, "XAUUSDm", "quote")) == 2
    restarted = MarketStore(Store(memory.store.directory))
    assert len(restarted.events(FEED.key, "XAUUSDm", "quote")) == 2
    assert memory.store.records("virtual") == memory.store.records("demo") == []


def test_m2_07_stream_cannot_mix_accounts(setup):
    collector, terminal, memory = setup
    with pytest.raises(ValueError, match="another account"):
        Collector(terminal, memory, FEED, AccountBinding(67890, "Fixture-Demo"))
    assert "12345" not in repr(collector.binding)
    assert "Fixture-Demo" not in repr(collector.binding)


def test_m2_08_feed_heartbeat_becomes_stale(setup):
    collector, _, memory = setup
    collector.poll("XAUUSDm")
    assert not memory.statuses(NOW)[0]["heartbeat_stale"]
    assert memory.statuses(NOW + 15001)[0]["heartbeat_stale"]
    assert not memory.statuses(NOW)[0]["execution_allowed"]


def test_m2_09_history_pages_utc_and_restart_deduplication(setup):
    collector, terminal, memory = setup
    terminal.bars = [bar(NOW // 1000 - 600 + i * 60) for i in range(10)]
    start = datetime.fromtimestamp(NOW // 1000 - 600, timezone.utc)
    end = datetime.fromtimestamp(NOW // 1000, timezone.utc)
    result = collector.history("XAUUSDm", "M1", start, end, page_bars=3)
    assert result["inserted"] == 10
    assert result["potential_gaps"] == []
    assert result["completeness"] == "unverified"
    assert len(terminal.calls) == 4
    assert collector.history("XAUUSDm", "M1", start, end)["duplicates"] == 10
    assert len(memory.events(FEED.key, "XAUUSDm", "candle")) == 10


def test_m2_10_open_bar_excluded_and_gaps_reported(setup):
    collector, terminal, memory = setup
    # History end is half a minute after the final open: that candle isn't closed.
    terminal.bars = [bar(NOW // 1000 - 180), bar(NOW // 1000 - 60)]
    result = collector.history(
        "XAUUSDm",
        "M1",
        datetime.fromtimestamp(NOW // 1000 - 180, timezone.utc),
        datetime.fromtimestamp(NOW // 1000 - 30, timezone.utc),
    )
    assert result["inserted"] == 1
    assert result["open_bars_skipped"] == 1
    terminal.bars = [bar(NOW // 1000 - 180), bar(NOW // 1000 - 60)]
    result = collector.history(
        "XAUUSDm",
        "M1",
        datetime.fromtimestamp(NOW // 1000 - 180, timezone.utc),
        datetime.fromtimestamp(NOW // 1000, timezone.utc),
    )
    assert result["potential_gaps"][0]["seconds"] == 120


def test_m2_11_history_revisions_preserved_latest_returned(setup):
    collector, terminal, memory = setup
    opening = NOW // 1000 - 60
    terminal.bars = [bar(opening)]
    start = datetime.fromtimestamp(opening, timezone.utc)
    end = datetime.fromtimestamp(NOW // 1000, timezone.utc)
    collector.history("XAUUSDm", "M1", start, end)
    terminal.bars = [bar(opening, 3002)]
    collector.history("XAUUSDm", "M1", start, end)
    result = memory.events(FEED.key, "XAUUSDm", "candle", timeframe="M1")
    assert len(result) == 1 and result[0]["data"]["close"] == 3002
    with memory.store.connect() as db:
        assert (
            db.execute("SELECT count(*) FROM market_events WHERE kind='candle'").fetchone()[0] == 2
        )


@pytest.mark.parametrize("case", ["naive", "reversed", "future", "too_long", "bad_timeframe"])
def test_m2_12_invalid_history_request(setup, case):
    collector, _, _ = setup
    start = datetime.fromtimestamp(NOW // 1000 - 60, timezone.utc)
    end = datetime.fromtimestamp(NOW // 1000, timezone.utc)
    timeframe = "M1"
    if case == "naive":
        start = start.replace(tzinfo=None)
    if case == "reversed":
        start = end + timedelta(seconds=1)
    if case == "future":
        end += timedelta(seconds=1)
    if case == "too_long":
        start -= timedelta(days=32)
    if case == "bad_timeframe":
        timeframe = "M2"
    with pytest.raises(ValueError):
        collector.history("XAUUSDm", timeframe, start, end)


def test_m2_13_invalid_batch_never_commits_partial_page(setup):
    collector, terminal, memory = setup
    opening = NOW // 1000 - 120
    terminal.bars = [bar(opening), bar(opening + 60)]
    terminal.bars[1]["high"] = 1
    with pytest.raises(MarketDataError):
        collector.history(
            "XAUUSDm",
            "M1",
            datetime.fromtimestamp(opening, timezone.utc),
            datetime.fromtimestamp(NOW // 1000, timezone.utc),
        )
    assert memory.events(FEED.key, "XAUUSDm", "candle") == []


def test_m2_14_missing_metadata_and_tick(setup):
    collector, terminal, _ = setup
    terminal.tick = None
    with pytest.raises(MarketDataError):
        collector.poll("XAUUSDm")
    terminal.symbol = None
    with pytest.raises(MarketDataError):
        collector.poll("XAUUSDm")


def test_m2_15_empty_history_finishes_without_claiming_completeness(setup):
    collector, terminal, _ = setup
    start = datetime.fromtimestamp(NOW // 1000 - 300, timezone.utc)
    end = datetime.fromtimestamp(NOW // 1000, timezone.utc)
    result = collector.history("XAUUSDm", "M1", start, end, page_bars=2)
    assert result["inserted"] == 0 and len(terminal.calls) == 3
    assert result["completeness"] == "unverified"


def test_m2_16_market_read_api_auth_and_query_limits(setup):
    collector, _, memory = setup
    collector.poll("XAUUSDm")
    with TestClient(create_app(Settings(memory.store.directory, ADMIN, VIEWER))) as client:
        params = {"feed": FEED.key, "symbol": "XAUUSDm"}
        headers = {"Authorization": "Bearer " + VIEWER}
        assert client.get("/v1/market/feeds").status_code == 401
        response = client.get("/v1/market/events", params=params, headers=headers)
        assert response.status_code == 200 and response.json()[0]["data"]["bid"] == 3000
        assert (
            client.get(
                "/v1/market/events", params=params | {"limit": 501}, headers=headers
            ).status_code
            == 422
        )
        assert (
            client.get(
                "/v1/market/events", params=params | {"kind": "order"}, headers=headers
            ).status_code
            == 422
        )
        assert client.post("/v1/market/events", json={}, headers=headers).status_code == 405
        assert client.get("/v1/status", headers=headers).json()["broker_execution_enabled"] is False


def test_m2_17_market_schema_upgrades_existing_foundation(tmp_path):
    store = Store(tmp_path)
    identifier = store.record("historical", "old_record", {"version": 1})
    MarketStore(store)
    MarketStore(Store(tmp_path))
    assert store.records("historical")[0]["id"] == identifier
    with store.connect() as db:
        assert [
            r[0] for r in db.execute("SELECT version FROM schema_version ORDER BY version")
        ] == [1, 2]


def test_m2_18_quote_and_candle_models_no_nan():
    with pytest.raises(ValidationError):
        Quote(symbol="X", time_msc=NOW, bid=float("nan"), ask=1, flags=0)
    with pytest.raises(ValidationError):
        Candle(
            symbol="X",
            timeframe="M1",
            open_time=1,
            open=3,
            high=1,
            low=2,
            close=3,
            tick_volume=0,
            spread_points=0,
            real_volume=0,
        )


def test_m2_19_interrupted_history_retries_without_duplicate_rows(setup, monkeypatch):
    collector, terminal, memory = setup
    opening = NOW // 1000 - 240
    terminal.bars = [bar(opening + i * 60) for i in range(4)]
    original = terminal.copy_rates_range
    calls = 0

    def disconnected(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("native connection lost")
        return original(*args)

    monkeypatch.setattr(terminal, "copy_rates_range", disconnected)
    start = datetime.fromtimestamp(opening, timezone.utc)
    end = datetime.fromtimestamp(NOW // 1000, timezone.utc)
    with pytest.raises(MarketDataError):
        collector.history("XAUUSDm", "M1", start, end, page_bars=2)
    assert len(memory.events(FEED.key, "XAUUSDm", "candle")) == 2
    monkeypatch.setattr(terminal, "copy_rates_range", original)
    result = collector.history("XAUUSDm", "M1", start, end, page_bars=2)
    assert result["inserted"] == result["duplicates"] == 2


def test_m2_20_broker_and_source_separation(setup):
    collector, terminal, memory = setup
    collector.poll("XAUUSDm")
    other = Feed(broker="Equiti", source="fixture", stream=FEED.stream)
    second = Collector(terminal, memory, other, collector.binding, clock=lambda: NOW)
    assert second.poll("XAUUSDm")["inserted"]
    assert len(memory.events(other.key, "XAUUSDm", "quote")) == 1
    assert len(memory.events(FEED.key, "XAUUSDm", "quote")) == 1


def test_m2_21_market_event_table_is_append_only(setup):
    import sqlite3

    collector, _, memory = setup
    collector.poll("XAUUSDm")
    for statement in ("DELETE FROM market_events", "UPDATE market_events SET payload='{}'"):
        with pytest.raises(sqlite3.IntegrityError):
            with memory.store.connect() as db:
                db.execute(statement)
