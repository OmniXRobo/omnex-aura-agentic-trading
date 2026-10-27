# Research backtest checkpoint (0.3.0)

This is an offline research laboratory, not the final adaptive autopilot, an approved
strategy, or a source of live investment instructions. It cannot call a broker or provider.
The M2 Windows MT5/broker connection still needs actual VPS acceptance. Synthetic
fixtures allow independent engineering tests while that environment is unavailable.

## Run the synthetic example

From the repository on Python 3.11/3.12 with the project environment installed:

```bash
python -m aura.research --request examples/backtest_fixture.json --data-dir ./data
```

On Windows use `.\.venv\Scripts\python.exe` instead of `python`.
The example contains generated sine-wave prices, NOT broker history. Do not interpret
its result as evidence of an investable edge. The command records request, parameters,
result and input hash in historical memory; virtual/demo/live trading memory is untouched.
It prints summary metrics, the source label, modeling assumptions and disabled execution/
promotion flags. Repeated identical requests have the same input hash and deterministic
results, but deliberately create separate research-run records.

The admin-only API offers `POST /v1/research/backtest` with the exact example JSON body.
The normal `/v1/memory/historical` endpoint exposes stored runs to authenticated readers.
No external AI/API credentials are needed for this offline path. The emergency stop may
remain ON while research runs; no execution capability is enabled by these calculations.

## Dataset contract

- Source must be fixture or user_supplied; neither asserts verified broker provenance.
- Symbol is XAUUSD, account/quote currency is USD and all costs are explicit USD assumptions.
- Supply at most 5,000 positive, finite bid-OHLC bars with explicit spread per bar.
- Each bar must be closed at the declared as_of boundary; bars must be ordered and
  non-overlapping. This validates declared dataset chronology, not source authenticity.
- The interval is explicit in seconds. Gaps are allowed; new entries are skipped if
  the next bar is not immediately adjacent to its signal bar.
- Ask is approximated as bid plus a CONSTANT spread within each bar. This is an explicit
  model, NOT a reconstructed executable bid/ask tick history. M2 broker candles cannot
  be assumed to satisfy it without independent preparation/validation.

## Causal technical features

Features return null during warmup. Every value uses only its own prefix. Prefix-invariance
regression tests compare the full series against truncated series to catch future leakage.

| Feature | Exact convention |
| --- | --- |
| SMA | Rolling arithmetic mean over the configured window |
| EMA | SMA seed after the first full period, then alpha=2/(period+1) |
| ATR_SMA | Rolling mean of true range; first previous price is the first bar open |
| RSI_SMA | Rolling arithmetic mean of gains/losses, NOT Wilder RSI; flat window=50 |
| Bollinger bands | SMA plus/minus 2 population standard deviations |

These are initial deterministic features, not calibrated ML predictions. Additional
indicators, multi-timeframe analysis, macro/news feeds, ML, and agent integration remain
pending. ATR/RSI conventions are named explicitly so results are not compared blindly
against broker chart indicators using different smoothing.

## Initial candidate strategies

`ema_cross_v1` proposes a direction only when fast/slow EMAs cross on a closed bar.
`channel_breakout_v1` compares a close with the preceding slow_period bars' highs/lows;
the current bar is excluded from that channel. Both require a valid prior volatility
estimate. These are deliberately simple baseline research candidates for future champion/
challenger comparisons; they are not the final continuously learning trading policy.

Parameters, dataset, source label and assumptions are hashed and stored with each run.
The result records engine version bar-research-v1. Source-control history must be retained
alongside each experiment; an input hash alone is not a model artifact or complete lineage.

## Entry, exit and costs

The previous CLOSED bar proposes a trade. Entry occurs at the NEXT bar's open, never
at the signal bar's already-known close. Only one position is modeled at a time. A
position closed within a bar cannot re-enter at that same bar's earlier open.

Long entry uses ask plus adverse slippage; short entry uses bid minus adverse slippage.
Long exits use bid; short exits use modeled ask. SL and TP are relative to the modeled
entry, based on prior ATR and configurable reward/risk. Adverse stop gaps fill at the
opening executable quote, not a magically guaranteed stop price. Favorable target gaps
receive only the target price before adverse slippage. If a bar can hit both SL and TP,
SL is assumed first. An open end-of-sample position is closed at the final executable
close. Intrabar exit timestamps are recorded as a bar-close UPPER BOUND, not a precise
broker fill time. A later tick simulator is required for real path/latency evidence.

Risk is at most 0.25% of current simulated equity per new trade. Size is rounded down to
volume step and bounded by supplied min/max; no minimum-size overshoot is forced. The
modeled stop budget includes exit slippage and roundtrip commission. Swap charges and
unbounded price gaps can exceed that modeled budget; the simulator does not cap losses
artificially. If remaining size is below the minimum, no trade is taken.

Commission is explicit roundtrip cost per lot. Swap uses signed cost per lot times the
number of UTC date boundaries through the exit-time upper bound. A positive cost is a
debit and a negative cost a credit. This is an approximation: broker rollover timing,
weekends/triple swaps, conversion rates, financing changes, and within-bar exit timing
are not modeled. Real observed broker costs are still an acceptance prerequisite.

A configurable CLOSED-TRADE drawdown threshold halts new entries. It is not an intrabar
maximum-equity-loss guarantee. There is no margin, leverage/liquidation, order rejection,
partial fill, trailing stop, order-book, market-hours, news blackout, or latency model
in this baseline. Those belong to later virtual/execution milestones. There is no
martingale, grid, position doubling or loss-recovery rule.

## Performance interpretation

Metrics include trade count, ending equity, net profit after supplied costs, win rate,
expectancy, profit factor and maximum closed-trade drawdown. Empty results use null
where a metric is undefined. Profit factor with gains but no losses is null with an
explicit unbounded flag; infinity/NaN is never emitted as JSON. Closed-trade drawdown
must not be presented as full intratrade mark-to-market drawdown.

All runs are labelled IN-SAMPLE RESEARCH. No walk-forward/OOS, confidence intervals,
Monte Carlo, macro/news validation, benchmark superiority or profitability claim is
made. Do not optimize on the eventual held-out set. Promotion eligibility and execution
are ALWAYS FALSE regardless of win rate, profit factor, or number of trades. External
LLMs will not be allowed to override this boundary in future milestones.

## Acceptance tests

`tests/test_research.py` maps test_m3_01 through test_m3_22 to feature math/warmup,
prefix invariance, dataset chronology, invalid costs/configuration, conservative fills,
gaps/slippage, risk rounding, swap approximation, no-trade behavior, single-position
handling, drawdown halting, metric edge cases, reproducibility, historical isolation,
channel construction, API authorization, nonpositive fill rejection and runnable fixtures.
This is engineering validation on synthetic data, not trading-strategy validation.
