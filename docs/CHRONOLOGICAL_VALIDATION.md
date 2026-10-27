# Chronological research validation (0.3.1)

This extends the M3 laboratory, not the broker execution path. PR #3's baseline passed
Linux/Windows CI; actual MT5 connection on the Windows VPS remains unverified. No
provider, market-data feed or broker credential is used by this validation runner.

## Run the explicitly synthetic example

```bash
python -m aura.validate --request examples/validation_fixture.json --data-dir ./data
```

On Windows use `.\.venv\Scripts\python.exe`. This generates a research report in
historical memory and prints its ID, fold count, diagnostics and final holdout result.
The supplied prices are deliberately synthetic trending bars, NOT broker observations.
The example's dates differ from the original backtest fixture so they do not claim
that a dataset already explored by that fixture is an unseen holdout.

Exact retries replay saved evidence without evaluating the holdout again. A changed
request that overlaps an already reserved final holdout is rejected. These restrictions
are deliberate: do not delete the ledger or change timestamps to tune on the holdout.
The authenticated admin API offers `POST /v1/research/validate` using the example JSON.
Both validation and exploratory backtest routes return HTTP 409 for protected-data
conflicts. Viewer tokens cannot launch either operation.

## Chronology and candidate selection

The final holdout is the last holdout_bars rows. Development folds use an expanding
training prefix, a gap of gap_bars rows, then a disjoint test window of test_bars rows.
Training expands by test_bars between folds and ends before the final holdout. A
max_folds cap bounds work; some development-tail rows may be training-only.

Every candidate evaluation receives only its training prefix. Candidate configuration
and minimum-trade thresholds are declared before evaluation. Candidates may differ in
strategy family, EMA/volatility windows, ATR stop multiplier or reward/risk; their costs,
capital, volume rules, risk budget, spread gate and drawdown policy must be identical.
A candidate is training-eligible only if it meets the minimum completed trade count,
has positive net training profit and did not hit the drawdown entry halt. The best net
training profit wins; ties break by stable configuration hash. If none qualifies, the
window returns NO TRADE. Positive training profit is not evidence of a real edge.

Each test uses a historical prefix for causal indicator warmup but disables all entries
before its test start. A signal from the immediately preceding closed bar may enter at
the test boundary. No warmup position is carried into the test. Each window starts with
fresh initial simulated equity and closes its position at its own end. This prevents
training positions/labels from crossing into test windows. Later walk-forward training
may use earlier fold outcomes once they have become historical observations, which is
normal chronological retraining. It never uses its own future test or final holdout.

Final candidate selection uses only the development prefix ending gap_bars before the
holdout. The chosen candidate is then evaluated once on the final window. Final holdout
trades remain separate from development summaries and bootstrap diagnostics.

A gap in supplied bars is not a universal ML-label purge. The current system has no
learned label horizons or fitted ML preprocessing. Future ML must add interval-aware
purging/embargo, leakage-safe transforms, feature/label lineage and independent approval.
Do not assume the current bar-count gap solves arbitrary ML leakage.

## Persistent holdout and exposure ledger

Historical schema v3 adds a validation ledger. A transaction reserves an instrument's
final time interval BEFORE evaluation; overlapping experiments are blocked even when
the source label, sampling interval, dataset label, parameters or random seed change.
Concurrent requests cannot evaluate the same reserved holdout. Failed/interrupted runs
retain their reservation and are not automatically retried. An exact completed request
replays its stored record after restart. A missing stored record fails closed.

Exploratory backtests record the time interval they evaluated. The runner indexes
legacy stored backtests before permitting a reservation; malformed old evidence blocks
validation rather than assuming the data is unseen. A final interval previously used
in exploratory backtesting is refused. Conversely, exploratory backtesting cannot
re-evaluate an already reserved final interval. All these checks use the same SQLite
write-transaction boundary, avoiding a reservation/exposure race.

The policy is intentionally conservative across sources and timeframes for XAUUSD.
Even a genuinely independent dataset over the same dates is refused until a human
research process establishes independence; there is no automatic bypass. Different
future final intervals can be used for later experiments. A prior final holdout may
become training history only for a later validation with a fresh reserved final interval.
Exploratory warmup outside its evaluated interval is not itself treated as a scored test.

This ledger controls the application's persisted research workflow. It cannot prove
that a human has never seen public prices or used another tool. Data provenance is
still fixture/user-supplied, and local administrators can modify their files or code.
Copying data into a new directory or falsifying dates would destroy this protection,
not create independent evidence. This is not a tamper-proof external audit system.

## Statistical diagnostic limits

Development test trades from independently reset windows are pooled for trade-count
and net-profit-sum diagnostics. This is NOT a compounded portfolio/equity curve. The
minimum test count only changes the evidence-status label; it never authorizes promotion.

A seeded IID closed-trade bootstrap samples those P/L observations with replacement.
It reports a 2.5%/97.5% empirical percentile range for mean trade profit and a 95th
percentile of simulated CLOSED-TRADE drawdown. Percentile indexing uses floor((N-1)*p).
The final holdout is excluded. Empty samples return an explicit no-data status.

This is resampling of observed synthetic/user-supplied outcomes, not Monte Carlo market
price generation or a calibrated future-profit confidence guarantee. It ignores serial
dependence, regimes, multiple testing, selection bias and model/data uncertainty. Small
samples remain weak even when an interval looks positive. Block bootstrap, robust
statistical comparisons, realistic costs, fresh broker data and market stress scenarios
remain further research requirements.

All previous bar-simulation limits still apply (constant within-bar spread, approximate
swap, bounded intrabar exit time, no margin/latency/partial-fill/trailing model). See
RESEARCH_BACKTEST.md. No macro/news input, adaptive model training, autonomous promotion,
continuous virtual scheduler, provider integration or broker execution is added here.

## Safety and evidence

Every result returns execution_allowed=false and promotion_eligible=false regardless
of selected candidate, number of trades, win rate, or resampling output. Historical,
virtual and demo evidence remain separate. The emergency stop may remain ON throughout.

Tests V01..V23 in tests/test_validation.py cover splits, invalid experiments, policy
coherence, warmup boundaries, final-price perturbation, test-entry chronology, no-trade
selection, deterministic resampling, persistent replay, retuning/overlap conflicts,
failed reservations, concurrent requests, raw/legacy exposure protection, fresh intervals,
authenticated APIs, CLI execution and source/timeframe relabelling rejection.
