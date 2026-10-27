"""Causal technical features; every index uses only its prefix."""

from math import sqrt


def sma(values, period):
    if period < 1:
        raise ValueError("Period must be positive")
    result = []
    total = 0.0
    for i, value in enumerate(values):
        total += value
        if i >= period:
            total -= values[i - period]
        result.append(total / period if i + 1 >= period else None)
    return result


def ema(values, period):
    """Seed with the first period's SMA, then apply alpha=2/(period+1)."""
    if period < 1:
        raise ValueError("Period must be positive")
    result = [None] * len(values)
    if len(values) < period:
        return result
    current = sum(values[:period]) / period
    result[period - 1] = current
    alpha = 2 / (period + 1)
    for i in range(period, len(values)):
        current += alpha * (values[i] - current)
        result[i] = current
    return result


def features(bars, fast_period, slow_period, volatility_period):
    closes = [bar.close for bar in bars]
    fast, slow = ema(closes, fast_period), ema(closes, slow_period)
    average = sma(closes, volatility_period)
    ranges, gains, losses = [], [], []
    for i, bar in enumerate(bars):
        previous = bars[i - 1].close if i else bar.open
        ranges.append(max(bar.high - bar.low, abs(bar.high - previous), abs(bar.low - previous)))
        change = bar.close - previous
        gains.append(max(change, 0))
        losses.append(max(-change, 0))
    atr = sma(ranges, volatility_period)
    avg_gain, avg_loss = sma(gains, volatility_period), sma(losses, volatility_period)
    output = []
    for i, bar in enumerate(bars):
        rsi = None
        if avg_gain[i] is not None:
            rsi = (
                50.0
                if avg_gain[i] == avg_loss[i] == 0
                else 100.0
                if avg_loss[i] == 0
                else 100 - 100 / (1 + avg_gain[i] / avg_loss[i])
            )
        std = (
            None
            if average[i] is None
            else sqrt(
                sum(
                    (value - average[i]) ** 2 for value in closes[i + 1 - volatility_period : i + 1]
                )
                / volatility_period
            )
        )
        output.append(
            {
                "open_time": bar.open_time,
                "fast_ema": fast[i],
                "slow_ema": slow[i],
                "sma": average[i],
                "atr_sma": atr[i],
                "rsi_sma": rsi,
                "bollinger_lower": None if std is None else average[i] - 2 * std,
                "bollinger_upper": None if std is None else average[i] + 2 * std,
            }
        )
    return output
