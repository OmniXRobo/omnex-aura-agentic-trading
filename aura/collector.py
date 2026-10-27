"""Read-only MT5 collection. No order placement, login or provider APIs."""

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from .market import TIMEFRAMES, Candle, Feed, GoldContract, Quote
from .market_store import MarketStore


class MarketDataError(RuntimeError):
    pass


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
    ):
        self.terminal, self.memory, self.feed, self.binding = terminal, memory, feed, binding
        self.clock = clock or (lambda: int(time.time() * 1000))
        self.memory.bind(feed, binding.login, binding.server)

    def guard(self):
        account, terminal = self.terminal.account_info(), self.terminal.terminal_info()
        if account is None or terminal is None or not terminal.connected:
            raise MarketDataError("Terminal disconnected")
        if account.trade_mode != self.terminal.ACCOUNT_TRADE_MODE_DEMO:
            raise MarketDataError("Only verified demo accounts are permitted")
        if account.login != self.binding.login or account.server != self.binding.server:
            raise MarketDataError("Account binding changed")

    def _call(self, method, *args):
        self.guard()
        value = method(*args)
        self.guard()
        if value is None:
            raise MarketDataError("Broker data unavailable")
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
        contract = GoldContract.model_validate(values)
        if contract.symbol != symbol:
            raise MarketDataError("Broker returned a different symbol")
        return contract

    def quote(self, symbol):
        raw = self._call(self.terminal.symbol_info_tick, symbol)
        data = _fields(raw, ["time_msc", "bid", "ask", "flags"])
        quote = Quote(symbol=symbol, **data)
        quote.require_fresh(self.clock())
        return quote

    def poll(self, symbol):
        try:
            contract = self.contract(symbol)
            quote = self.quote(symbol)
            self.guard()
            now = self.clock()
            quote.require_fresh(now)
            self.memory.append(self.feed, contract, now)
            inserted = self.memory.append(self.feed, quote, now)
            self.memory.set_status(self.feed, "healthy", "Fresh demo quote collected", now)
            return {"inserted": inserted, "execution_allowed": False}
        except Exception:
            # Never echo broker exceptions: they may contain account details or credentials.
            self.memory.set_status(
                self.feed, "blocked", "Collection failed; data not eligible", self.clock()
            )
            raise MarketDataError(
                "Collection failed; check demo binding, metadata and freshness"
            ) from None

    def history(self, symbol, timeframe, start: datetime, end: datetime, page_bars=500):
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
        self.contract(symbol)
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
                    datetime.fromtimestamp(cursor, timezone.utc),
                    datetime.fromtimestamp(page_end - 1, timezone.utc),
                )
                batch = []
                for row in raw:
                    opening = int(row["time"])
                    if opening < cursor or opening >= page_end:
                        raise MarketDataError("Broker returned a candle outside requested bounds")
                    candle = Candle(
                        symbol=symbol,
                        timeframe=timeframe,
                        open_time=opening,
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
                "execution_allowed": False,
            }
        except Exception:
            self.memory.set_status(
                self.feed, "blocked", "History import interrupted; retry safely", self.clock()
            )
            raise MarketDataError("History import failed; committed pages can be retried") from None
