# M3 — offline research checkpoint (0.3.0)

PR #2 is confirmed merged. All its Linux/Windows Python 3.11/3.12 CI jobs and dependency
audits passed. Actual Windows MT5 broker acceptance still requires the VPS setup guide.

## Implemented

- `aura/features.py`: causal SMA, SMA-seeded EMA, ATR_SMA, RSI_SMA and Bollinger bands.
- `aura/backtest.py`: typed/capped datasets and configuration, EMA-cross and prior-channel
  baseline candidates, next-bar entries, explicit bid/ask-spread model, adverse slippage,
  stop-first intrabar policy, gaps, commission, approximate swap and risk-rounded sizing.
- Single simulated position; closed-trade drawdown entry halt; explicit end-of-sample exits.
- Metrics: net after supplied costs, expectancy, win rate, profit factor and closed-trade DD.
- Research requests/results/hash stored in historical memory, separate from virtual/demo.
- `aura/research.py`: offline CLI, plus admin-only `/v1/research/backtest` API route.
- Runnable synthetic fixture, exact model conventions, limits, acceptance mapping and roadmap.

## Verification

Local pytest: 104 passed, 0 failed (76 existing + 28 research scenarios). One existing
Starlette TestClient/httpx deprecation warning. Ruff passed for source/tests/scripts.
Real HTTP/process restart and independent emergency-stop smoke passed. Source and wheel
builds are run before publishing. Reports/junit.xml and reports/smoke.json contain evidence.
M3 remote CI status must be read from its PR; only M1/M2 CI is confirmed at report creation.

## Material limits

Data is explicitly synthetic or user-supplied. The current bar model assumes constant
within-bar spread and does not reconstruct full bid/ask tick paths. Intrabar fill time
is an upper bound. Swap is an approximation. Margin/liquidation, latency, partial fills,
order rejections, trailing stops, macro/news and real data quality gates are not implemented.
Drawdown is closed-trade only, not full marked-to-market risk. Baseline strategies are
reference research candidates, not the final adaptive/agentic policy. Source hashes help
reproduce requests but do not replace model lineage or validation artifacts.

No walk-forward/OOS/Monte Carlo/confidence-interval/profitability claim is made. M3 remains
a research checkpoint, not the full master milestone. Do not treat fixture results as
investment evidence or as permission to trade. No external provider API is called.

## Safety

Execution and promotion are always disabled in research results. No broker order/login/
amend/close function is introduced. No maturity, win rate or profitability score enables
trading. The emergency stop can stay ON during research. No broker credentials, API keys
or personal data are required or committed. Public source hosting remains owner-authorized.

## Next

Review PR #3 and run its offline fixture. Complete M2 actual Windows/demo data acceptance,
then build leakage-safe dataset preparation and fresh held-out/walk-forward evaluation.
Macro/news/provider integration still needs authorized sources/secure credentials. Keep
all order execution disabled while adding these components.
