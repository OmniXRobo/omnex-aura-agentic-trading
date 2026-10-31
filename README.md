# OMNEX AURA 0.5.2 — Durable virtual evaluation checkpoints

Demo-only research platform in development. Live execution is prohibited in V1.
This checkpoint is runnable locally; it is not an autonomous trading release.

## Run locally

Python 3.11 or 3.12:

```bash
python -m venv .venv
# Activate the virtual environment using your operating system's normal command.
python -m pip install -r requirements.lock
python -m pip install -e . --no-deps
# Configure AURA_ADMIN_TOKEN (32+ random characters) in the process environment.
python -m uvicorn aura.api:create_app --factory --host 127.0.0.1 --port 8080
```

On Windows use `scripts/start-backend.ps1` after configuring the service environment.
Environment files are ignored by Git but are not automatically loaded by this application.
Use a secret manager or process environment. Never paste keys into issues or commit them.
No AI or broker credentials are required for this local deterministic checkpoint.

`GET /health` is public. Other endpoints require `Authorization: Bearer <token>`.
Use distinct `AURA_ADMIN_TOKEN` and optional `AURA_VIEWER_TOKEN`. These are local
bootstrap service tokens, not a complete end-user login system.

| Method | Route | Purpose |
| --- | --- | --- |
| GET | /v1/status | Mode, safety state, unavailable provider status |
| GET | /v1/agents | All 15 roles with honest implementation status |
| POST | /v1/research/run | Execute 3 independent local tasks, save evidence |
| POST | /v1/risk/preview | Validate a caller-supplied hypothetical proposal |
| PUT | /v1/safety/kill-switch | Persist emergency-stop state (admin only) |
| GET | /v1/memory/{historical,virtual,demo} | Read separated local records |

Example research body:

```json
{"symbol":"XAUUSD","prices":[3000,3001,3002],"tick_age_seconds":1,"source":"fixture"}
```

This returns NO TRADE with evidence from simple sample statistics, a descriptive
sample label, and data-quality checks. These are not an ML model, validated market
classifier, live broker feed, or provider-backed AI predictions.

## Verify

```bash
python -m pytest -q --junitxml=reports/junit.xml
python -m ruff check aura tests
python -m build
```

Independent stop, even with the API closed:

```bash
python -m aura.safety --data-dir ./data
```

All paths must use the same absolute data directory on deployment. The kill switch
starts ON. Turning it off does not enable order execution: no order-send implementation
exists. Risk previews consume caller-supplied facts and cannot authorize a broker order.

See ARCHITECTURE.md, ROADMAP.md, ACCEPTANCE_CRITERIA.md, docs/MT5_DEMO_PLAN.md,
docs/OPERATIONS.md and reports/MILESTONE_1.md. The full input specification is preserved
in docs/MASTER_SPECIFICATION.md.

## Read-only market data (M2)

The Windows collector now verifies an explicitly bound demo account/server and validates
gold symbol contracts. It stores sampled fresh bid/ask quotes and paginated closed candles
in historical memory, with duplicate prevention and preserved candle revisions. This is
not a lossless tick feed. It does not generate tradeable signals or submit broker orders.
See [Windows setup](docs/MT5_READ_ONLY_SETUP.md) for exact local commands and limitations.
`GET /v1/market/feeds` and `/v1/market/events` provide authenticated read access.

Source is public by the owner's instruction. PR #1 was merged and its Linux/Windows CI
and dependency audit passed. The original M1 report is a historical checkpoint; current
progress is recorded in reports/MILESTONE_2.md. M2 still needs actual Windows/broker
acceptance. No provider credentials or broker passwords are required for fixture tests.

## Offline research (M3)

Run `python -m aura.research --request examples/backtest_fixture.json --data-dir ./data`
to exercise the synthetic research fixture. It tests causal technical features, two
baseline candidate strategies, next-bar fills and explicit cost assumptions. Admins
can also POST the same body to `/v1/research/backtest`. Results stay in historical memory
and always reject promotion/execution. See docs/RESEARCH_BACKTEST.md for model limitations.
PR #2 is merged and all its Windows/Linux CI and dependency checks passed; real Windows
MT5 connection verification is still pending. The research pipeline does not require
that connection or external provider credentials. This is a research checkpoint, not
full M3 completion or an adaptive trading release.

## Chronological validation (M3 continuation)

Run `python -m aura.validate --request examples/validation_fixture.json --data-dir ./data`
for a synthetic expanding-window experiment with a separately reserved final holdout.
The admin API is `/v1/research/validate`. Exact retries replay saved evidence; retuning
on overlapping final intervals is blocked. Previously explored backtest intervals cannot
be called an unseen holdout. See docs/CHRONOLOGICAL_VALIDATION.md for the boundary details,
IID-bootstrap limitations and scope. All promotion/execution remains disabled. PR #3 is
merged and all its Linux/Windows CI and dependency-audit jobs passed.

## Provider-independent review gateway (M4 checkpoint)

`python -m aura.review --request examples/review_fixture.json --data-dir ./data` runs
three deterministic local review perspectives. The admin API is `/v1/research/review`;
authenticated users can inspect `/v1/providers/status`. The gateway adds bounded retries,
timeouts, declared failover routes, schema/provenance checks, durable quota reservations,
circuit health and short-lived caching. External provider adapters/credentials remain
unimplemented; status reports that explicitly. No paid API is called and no model
agreement enables trading. See docs/AGENT_GATEWAY.md for limits and tests. PR #4's Linux/
Windows CI and dependency audits passed; this is not full M4 or deployment completion.

## Read-only MT5 troubleshooting

If collection reports an account/stream mismatch or a vague data failure, use
`python -m aura.diagnose --symbol XAUUSD` on the Windows VPS with the same expected
terminal/login/server environment. The diagnostic performs no stream/database writes
and reveals identity match booleans, contract failures and quote age instead of the
login number. See docs/MT5_TROUBLESHOOTING.md. The collector verifies identity before
saving a new binding; existing bindings are never silently overwritten.

Quote timestamp correction is optional, scoped and expires within 24 hours. See
[MT5 timestamp policy](docs/MT5_TIME_POLICY.md). No offset is inferred automatically.

Use the [candle time probe](docs/MT5_CANDLE_TIME_PROBE.md) to gather bounded raw
quote/candle comparisons without changing stream bindings or authorizing imports.

MT5 history now requires an explicit [dated candle policy](docs/MT5_HISTORY_TIME_POLICY.md).
Quote corrections alone never authorize candle conversion.

The first [virtual market ledger](docs/VIRTUAL_LEDGER.md) provides atomic simulated
positions, cost accounting and restart-safe receipts. It is not autonomous autopilot.
Run `python -m aura.virtual_fixture` for an isolated synthetic smoke exercise.

The [quote consumer](docs/VIRTUAL_QUOTE_CONSUMER.md) validates persisted feed evidence
and resumes with idempotent ledger receipts. It cannot submit new entry intents.

The [virtual evaluator](docs/VIRTUAL_EVALUATION.md) creates restart-safe rolling two-/
three-day diagnostics. It never promotes strategies or enables trading.
