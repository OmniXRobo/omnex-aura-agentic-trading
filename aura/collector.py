"""Read-only MT5 collection. No order placement, login or provider APIs."""

import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from pydantic import ValidationError

from .market import TIMEFRAMES, Candle, Feed, GoldContract, Quote
from .market_store import MarketStore


class MarketDataError(RuntimeError):
    def __init__(self, message, code="market_data_error"):
        super().__init__(message)
        self.code = code


class ReadOnlyTerminal(Protocol):
    ACCOUNT_TRADE_MODE_DEMO: int

    def account_info(self): ...
    def terminal_info(self): ...
    def symbols_get(self): ...
    def symbol_info(self, symbol): ...
    def symbol_info_tick(self, symbol): ...
    def copy_rates_range(self, symbol, timeframe, date_from, date_to): ...


@dataclass(frozen=True)
class AccountBinding:
    login: int = field(repr=False)
    server: str = field(repr=False)

    def __post_init__(self):
        if isinstance(self.login, bool) or self.login <= 0 or not self.server:
            raise ValueError("Explicit account and server binding is required")


def _fields(obj, names):
    if obj is None:
        raise MarketDataError("Broker metadata unavailable")
    try:
        return {name: getattr(obj, name) for name in names}
    except AttributeError:
        raise MarketDataError("Broker metadata incomplete") from None


class Collector:
    def __init__(
        self,
        terminal: ReadOnlyTerminal,
        memory: MarketStore,
        feed: Feed,
        binding: AccountBinding,
        clock=None,
        time_policy=None,
    ):
        self.terminal, self.memory, self.feed, self.binding = terminal, memory, feed, binding
        self.time_policy = time_policy
        self.clock = clock or (lambda: int(time.time() * 1000))
        # Do not persist a claimed account before verifying the actual terminal.
        self.guard()
        try:
            self.memory.bind(feed, binding.login, binding.server)
        except ValueError:
            raise MarketDataError(
                "Stream belongs to another verified account; do not overwrite it",
                "stream_binding_conflict",
            ) from None

    def guard(self):
        try:
            account, terminal = self.terminal.account_info(), self.terminal.terminal_info()
            if account is None or terminal is None or not terminal.connected:
                raise MarketDataError(
                    "Terminal/account is disconnected or unavailable", "disconnected"
                )
            if account.trade_mode != self.terminal.ACCOUNT_TRADE_MODE_DEMO:
                raise MarketDataError("Only verified demo accounts are permitted", "not_demo")
            if account.server != self.binding.server:
                raise MarketDataError(
                    "Actual server does not match the configured server", "server_mismatch"
                )
            if account.login != self.binding.login:
                raise MarketDataError(
                    "Actual demo login does not match the configured login", "login_mismatch"
                )
        except MarketDataError:
            raise
        except Exception:
            raise MarketDataError(
                "Terminal identity cannot be read safely", "terminal_read_failed"
            ) from None

    def _call(self, method, *args):
        self.guard()
        try:
            value = method(*args)
        except Exception:
            raise MarketDataError("Native terminal read failed", "native_read_failed") from None
        self.guard()
        if value is None:
            raise MarketDataError("Broker data unavailable", "data_unavailable")
        return value

    def discover(self):
        symbols = self._call(self.terminal.symbols_get)
        return sorted(
            s.name
            for s in symbols
            if getattr(s, "currency_base", "") == "XAU"
            and getattr(s, "currency_profit", "") == "USD"
        )

    def contract(self, symbol):
        raw = self._call(self.terminal.symbol_info, symbol)
        values = _fields(raw, [key for key in GoldContract.model_fields if key != "symbol"])
        values["symbol"] = raw.name
        try:
            contract = GoldContract.model_validate(values)
        except ValidationError as error:
            fields = sorted({str(item["loc"][0]) for item in error.errors(include_input=False)})
            raise MarketDataError(
                "Invalid contract fields: " + ", ".join(fields), "contract_invalid"
            ) from None
        if contract.symbol != symbol:
            raise MarketDataError("Broker returned a different symbol")
        return contract

    def quote(self, symbol):
        raw = self._call(self.terminal.symbol_info_tick, symbol)
        data = _fields(raw, ["time_msc", "bid", "ask", "flags"])
        if self.time_policy is not None:
            try:
                normalized = self.time_policy.normalize(
                    data["time_msc"], self.clock(), self.binding.server, symbol
                )
            except ValueError:
                raise MarketDataError(
                    "Quote time policy expired or mismatched", "time_policy_invalid"
                ) from None
            data.update(
                raw_time_msc=data["time_msc"],
                time_msc=normalized,
                time_offset_seconds=self.time_policy.offset_seconds,
                time_policy=hashlib.sha256(self.time_policy.model_dump_json().encode()).hexdigest(),
            )
        try:
            quote = Quote(symbol=symbol, **data)
        except ValidationError:
            raise MarketDataError("Quote prices/timestamp are invalid", "quote_invalid") from None
        self._fresh(quote)
        return quote

    def _fresh(self, quote):
        now = self.clock()
        if self.time_policy is not None:
            try:
                self.time_policy.normalize(
                    quote.raw_time_msc, now, self.binding.server, quote.symbol
                )
            except ValueError:
                raise MarketDataError("Quote time policy expired", "time_policy_invalid") from None
        if quote.time_msc > now:
            raise MarketDataError("Quote timestamp is ahead of the VPS clock", "future_tick")
        if now - quote.time_msc > 5000:
            raise MarketDataError(
                "Quote is older than five seconds; check the symbol/feed and market session",
                "stale_tick",
            )

    def poll(self, symbol):
        try:
            contract = self.contract(symbol)
            quote = self.quote(symbol)
            self.guard()
            now = self.clock()
            self._fresh(quote)
            self.memory.bind_quote_time(self.feed, quote.time_offset_seconds, self.time_policy)
            self.memory.append(self.feed, contract, now)
            inserted = self.memory.append(self.feed, quote, now)
            self.memory.set_status(self.feed, "healthy", "Fresh demo quote collected", now)
            return {"inserted": inserted, "execution_allowed": False}
        except MarketDataError as error:
            self.memory.set_status(self.feed, "blocked", error.code, self.clock())
            raise
        except Exception:
            # Never echo broker exceptions: they may contain account details or credentials.
            self.memory.set_status(
                self.feed, "blocked", "Collection failed; data not eligible", self.clock()
            )
            raise MarketDataError(
                "Collection failed; check demo binding, metadata and freshness"
            ) from None

    def history(self, symbol, timeframe, start: datetime, end: datetime, page_bars=500,
                history_policy=None):
        if history_policy is None and (
            self.feed.source == "mt5_demo"
            or (self.time_policy is not None and self.time_policy.offset_seconds)
            or self.memory.quote_time_offset(self.feed) != 0
        ):
            raise MarketDataError(
                "An explicit dated candle policy is required; quote correction is insufficient",
                "history_time_unverified",
            )
        if timeframe not in TIMEFRAMES or not 1 <= page_bars <= 5000:
            raise ValueError("Invalid timeframe or page size")
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("Timezone-aware history boundaries are required")
        start_sec, end_sec = int(start.timestamp()), int(end.timestamp())
        now_sec = self.clock() // 1000
        if start_sec <= 0 or start_sec >= end_sec or end_sec > now_sec:
            raise ValueError("History range must be positive, ordered and not in the future")
        if end_sec - start_sec > 31 * 86400:
            raise ValueError("Import at most 31 days per request")
        offset, provenance = 0, {}
        if history_policy is not None:
            try:
                history_policy.require_scope(self.binding.server, symbol, timeframe,
                                             start_sec, end_sec, self.clock())
            except ValueError:
                raise MarketDataError("History policy scope or date interval is invalid",
                                      "history_time_policy_invalid") from None
            offset = history_policy.offset_seconds
            provenance = dict(time_offset_seconds=offset, time_policy=hashlib.sha256(
                history_policy.model_dump_json().encode()).hexdigest())
        self.contract(symbol)
        self.guard()
        self.memory.bind_history_time(self.feed, symbol, timeframe, start_sec, end_sec,
                                      offset, history_policy)
        seconds = TIMEFRAMES[timeframe]
        terminal_tf = getattr(self.terminal, "TIMEFRAME_" + timeframe)
        cursor, inserted, duplicate, open_skipped = start_sec, 0, 0, 0
        opens = set()
        try:
            while cursor < end_sec:
                page_end = min(cursor + page_bars * seconds, end_sec)
                raw = self._call(
                    self.terminal.copy_rates_range,
                    symbol,
                    terminal_tf,
                    datetime.fromtimestamp(cursor + offset, timezone.utc),
                    datetime.fromtimestamp(page_end - 1 + offset, timezone.utc),
                )
                batch = []
                for row in raw:
                    raw_opening = int(row["time"])
                    opening = raw_opening - offset
                    if opening < cursor or opening >= page_end:
                        raise MarketDataError("Broker returned a candle outside requested bounds")
                    candle = Candle(
                        symbol=symbol,
                        timeframe=timeframe,
                        open_time=opening,
                        **(dict(raw_open_time=raw_opening, **provenance) if history_policy else {}),
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        tick_volume=int(row["tick_volume"]),
                        spread_points=int(row["spread"]),
                        real_volume=int(row["real_volume"]),
                    )
                    if candle.close_time > min(end_sec, now_sec):
                        open_skipped += 1
                        continue
                    batch.append(candle)
                self.guard()
                for candle in batch:
                    opens.add(candle.open_time)
                    if self.memory.append(self.feed, candle, self.clock()):
                        inserted += 1
                    else:
                        duplicate += 1
                cursor = page_end
            ordered = sorted(opens)
            gaps = [
                {"after": a, "before": b, "seconds": b - a}
                for a, b in zip(ordered, ordered[1:])
                if b - a > seconds
            ]
            return {
                "inserted": inserted,
                "duplicates": duplicate,
                "open_bars_skipped": open_skipped,
                "potential_gaps": gaps,
                "completeness": "unverified",
                "time_offset_seconds": offset,
                "time_policy": provenance.get("time_policy"),
                "time_verification": "operator_attested" if history_policy else "fixture_default_utc",
                "execution_allowed": False,
            }
        except MarketDataError as error:
            self.memory.set_status(self.feed, "blocked", error.code, self.clock())
            raise
        except Exception:
            self.memory.set_status(
                self.feed, "blocked", "History import interrupted; retry safely", self.clock()
            )
            raise MarketDataError("History import failed; committed pages can be retried") from None
