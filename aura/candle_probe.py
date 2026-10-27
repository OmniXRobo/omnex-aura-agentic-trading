"""Bounded read-only candle time evidence. No database, policy creation or execution."""

import time
from datetime import datetime, timezone

from .collector import AccountBinding, MarketDataError
from .diagnose import report_terminal
from .market import TIMEFRAMES, Candle, Quote


def _candle(row, symbol, timeframe):
    return Candle(
        symbol=symbol, timeframe=timeframe, open_time=int(row["time"]),
        open=float(row["open"]), high=float(row["high"]), low=float(row["low"]),
        close=float(row["close"]), tick_volume=int(row["tick_volume"]),
        spread_points=int(row["spread"]), real_volume=int(row["real_volume"]),
    )


def probe_candle_time(port, symbol, binding: AccountBinding, timeframe="M1", samples=3,
                      interval=1.0, clock=None, wait=None):
    """Report raw numerical relationships, never declare a timezone verified."""
    if timeframe not in TIMEFRAMES or type(samples) is not int or not 2 <= samples <= 5:
        raise ValueError("Choose a supported timeframe and two to five samples")
    if not 0.2 <= interval <= 2:
        raise ValueError("Sample interval must be between 0.2 and two seconds")
    clock = clock or (lambda: int(time.time() * 1000))
    wait = wait or time.sleep
    result = dict(symbol=symbol, timeframe=timeframe, execution_allowed=False,
                  stream_modified=False, history_time_verified=False,
                  history_import_authorized=False, samples=[])

    def guard():
        account, terminal = port.account_info(), port.terminal_info()
        if account is None or terminal is None or not terminal.connected:
            raise MarketDataError("Terminal unavailable", "disconnected")
        if account.trade_mode != port.ACCOUNT_TRADE_MODE_DEMO:
            raise MarketDataError("Demo required", "not_demo")
        if (account.login, account.server) != (binding.login, binding.server):
            raise MarketDataError("Account changed or mismatched", "account_mismatch")

    def read(method, *args):
        guard()
        value = method(*args)
        guard()
        if value is None:
            raise MarketDataError("Data unavailable", "data_unavailable")
        return value

    try:
        guard()
        preflight = report_terminal(port, symbol, binding.login, binding.server, clock())
        if not (preflight.get("contract_valid") and preflight.get("account_stable")
                and preflight.get("quote_valid") and preflight.get("login_matches")
                and preflight.get("server_matches") and preflight.get("demo_verified")):
            return result | {"error": "terminal_preflight_failed", "probe_completed": False}
        terminal_tf = getattr(port, "TIMEFRAME_" + timeframe)
        seconds = TIMEFRAMES[timeframe]
        for index in range(samples):
            if index:
                wait(interval)
            guard()
            raw_tick = read(port.symbol_info_tick, symbol)
            quote = Quote(symbol=symbol, **{
                k: getattr(raw_tick, k) for k in ("time_msc", "bid", "ask", "flags")
            })
            raw = read(port.copy_rates_from_pos, symbol, terminal_tf, 0, 5)
            observed = clock()
            # Native operations may block: report timestamps before/after the range read.
            if not 1 <= len(raw) <= 5:
                raise MarketDataError("Expected one to five bars", "invalid_bar_count")
            bars = [_candle(row, symbol, timeframe) for row in raw]
            opens = [bar.open_time for bar in bars]
            if opens != sorted(set(opens)):
                raise MarketDataError("Unordered or duplicate candles", "invalid_bar_order")
            start, end = opens[0], opens[-1]
            replay_raw = read(
                port.copy_rates_range, symbol, terminal_tf,
                datetime.fromtimestamp(start, timezone.utc),
                datetime.fromtimestamp(end, timezone.utc),
            )
            if len(replay_raw) > 5:
                raise MarketDataError("Unexpected range response", "invalid_range_count")
            replay = [_candle(row, symbol, timeframe).open_time for row in replay_raw]
            if any(opening < start or opening > end for opening in replay):
                raise MarketDataError("Range outside requested bounds", "range_out_of_bounds")
            finished = clock()
            if finished < observed:
                raise MarketDataError("VPS clock moved backwards", "clock_regression")
            result["samples"].append(dict(
                observed_utc_msc=observed, finished_utc_msc=finished,
                raw_tick_time_msc=quote.time_msc,
                raw_tick_age_seconds=(observed - quote.time_msc) / 1000,
                raw_bar_open_times=opens,
                raw_last_bar_minus_utc_bucket_seconds=opens[-1] - (observed // 1000 // seconds) * seconds,
                raw_last_bar_minus_tick_bucket_seconds=opens[-1] - (quote.time_msc // 1000 // seconds) * seconds,
                range_replay_open_times=replay,
                range_replay_matches=opens == replay,
            ))
        guard()
        ticks = [item["raw_tick_time_msc"] for item in result["samples"]]
        result.update(
            probe_completed=True,
            tick_timestamps_nondecreasing=all(a <= b for a, b in zip(ticks, ticks[1:])),
            tick_timestamp_advanced=any(a < b for a, b in zip(ticks, ticks[1:])),
            range_replays_match=all(s["range_replay_matches"] for s in result["samples"]),
            interpretation="observations_only_no_timezone_or_DST_rule_inferred",
        )
        return result
    except MarketDataError as error:
        return result | {"error": error.code, "probe_completed": False}
    except Exception:
        # No native error text, account ID, credentials or raw exception input is emitted.
        return result | {"error": "probe_read_failed", "probe_completed": False}
