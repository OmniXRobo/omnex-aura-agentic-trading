# Acceptance and test traceability

This checkpoint proves local foundation behavior only. Test IDs appear in function names
in tests/test_foundation.py. Parameterized scenarios increase the test count.

| ID | Criterion | Local automated evidence |
| --- | --- | --- |
| AC01 | No default admin secret; no repr leakage | test_ac01 |
| AC02 | Live/demo execution modes unavailable | test_ac02 |
| AC03 | API auth and admin/viewer isolation | test_ac03 |
| AC04 | Independent stop state survives restart | test_ac04 |
| AC05 | Historical/virtual/demo records isolated, no live writes | test_ac05 |
| AC06 | Database rejects audit update/delete | test_ac06 |
| AC07 | Kill switch defaults on; eligibility never authorizes execution | test_ac07 |
| AC08 | Risk rejects stop, size, spread, stale data, concurrency and news breaches | test_ac08 |
| AC09 | Reject nonfinite/invalid inputs and unknown proposal fields | test_ac09 |
| AC10 | Unavailable safety state fails closed | test_ac10 |
| AC11 | Queue deduplicates exact payload; rejects key collisions | test_ac11 |
| AC12 | Concurrent workers cannot claim the same leased job | test_ac12 |
| AC13 | Restart recovers expired job; stale worker cannot acknowledge | test_ac13 |
| AC14 | Retry and dead-letter behavior | test_ac14 |
| AC15 | Three independent local functions execute and persist evidence | test_ac15 |
| AC16 | Agent failure returns NO TRADE | test_ac16 |
| AC17 | MT5 fake port rejects real/contest/disconnected accounts | test_ac17 |
| AC18 | Missing account metadata rejects connection | test_ac18 |
| AC19 | Authenticated in-process research workflow and memory retrieval | test_ac19 |
| AC20 | No order route; mode injection rejected | test_ac20 |
| AC21 | Bounded job worker persists evidence and acknowledges | test_ac21 |
| AC22 | Valid sell geometry handled | test_ac22 |

## Required 11-category coverage plan

| Category | Current coverage | Remaining gate |
| --- | --- | --- |
| Unit | Configuration, risk, account diagnostics | Provider/strategy/simulation units |
| Integration | API + DB + orchestrator, worker + durable queue | PostgreSQL/provider/broker integration |
| System | Local process smoke test | Windows supervised deployment/reboot |
| Functional | Research run, safety toggle, read memory | Trading and dashboard workflows |
| Regression | Safety and input cases checked into source | Expand with every resolved defect |
| Performance | Not benchmarked | Tick-to-decision latency budgets |
| Load/stress | 8-worker queue claim correctness only | Sustained API/queue load, backpressure, resources |
| Security | Auth/RBAC, validation, append-only audit | Threat model, pentest, dependency and secret scans |
| Compatibility | Linux Python 3.12 locally; CI matrix written | Actual Windows/Python 3.11/3.12 runs |
| End-to-end | In-process backend workflow only | Real web/Android-to-demo workflow |
| User acceptance | Not performed | Owner executes signed checklist on demo |

All trading-specific validation from master section 18 remains pending except local
risk-failure, duplicate-job and restart-lease fixtures. Historical/walk-forward/OOS,
Monte Carlo, cost/regime/news stress, drift, actual broker disconnects, order duplicate
prevention, VPS reboot and strategy rollback must be separately implemented and run.

Full-project acceptance from master section 20 is NOT satisfied: providers, broker
connection, virtual autopilot, adaptive strategy evolution, dashboard, APK and deployment
have not been delivered. Local persistence and risk-boundary tests are a foundation.

## M2 market-data acceptance mapping

Tests in `tests/test_market_data.py` map to `test_m2_01` through `test_m2_21`:

| Test ID | Acceptance criterion |
| --- | --- |
| M2-01 | Gold discovery uses currency metadata; official symbol_info.name is mapped correctly |
| M2-02 | Invalid currency, tick/volume/point and swap metadata rejected |
| M2-03 | Real/contest and mismatched account/server are rejected |
| M2-04 | Disconnect/account switch during read cannot store a quote |
| M2-05 | Future/stale/crossed/nonfinite quotes rejected |
| M2-06 | Quote deduplication, same-ms changes and restart persistence |
| M2-07 | One feed stream cannot mix different accounts |
| M2-08 | Heartbeat freshness expires without collector updates |
| M2-09 | UTC history paging and repeat import deduplication |
| M2-10 | Open-bar exclusion and potential gap reporting |
| M2-11 | Candle revisions preserved; latest version read |
| M2-12 | Naive/reversed/future/oversized history requests rejected |
| M2-13 | Malformed page rejected before inserting its validated batch |
| M2-14 | Missing metadata/ticks fail closed |
| M2-15 | Empty history is bounded and never claimed complete |
| M2-16 | Market API authentication and read/query constraints |
| M2-17 | Schema v2 preserves foundation data and is repeatable |
| M2-18 | Quote/candle numeric/range validation |
| M2-19 | Interrupted history import safely resumes/deduplicates |
| M2-20 | Broker/source data remain separate |
| M2-21 | Market-event UPDATE/DELETE rejected by DB triggers |

Fixtures do not establish broker compatibility. The MT5 port has never been used to
submit an order. All original trading-specific statistical and execution acceptance
gates remain pending. PR #1 now supplies actual Windows/Linux backend CI evidence;
this does not prove Windows VPS/MT5 terminal integration.

## M3 research acceptance mapping

`tests/test_research.py` uses M3-01..M3-22 (28 parameterized scenarios). IDs cover:
feature math/warmup; causal prefix invariance; flat RSI/ATR/bands; dataset chronology;
configuration/cost rejection; next-bar and stop-first fills; long/short executable prices;
adverse gaps; risk rounding/cost budget; swap/exit-bound approximation; no-trade/minimum
volume; spread/gap rejection; one position and no backdated reentry; closed-trade drawdown
halt; metric edge cases; reproducible input hashes; historical-only persistence; causal
channel breakout; API authorization; invalid fill-price rejection; and fixture CLI execution.

These prove local research-engine behavior, not market profitability. Monte Carlo,
fresh out-of-sample/walk-forward evaluation, confidence intervals, macro/news input,
ML calibration and broker-data preparation remain pending. Backtest results always have
promotion_eligible=false and execution_allowed=false.

## M3 chronological-validation continuation

V01..V23 in `tests/test_validation.py` cover 28 scenarios: disjoint/ordered splits,
invalid size/gap/limits, fixed risk/cost policies across candidates, test-only entries
with causal warmup, final-data perturbation invariance of training selection, bounded
window exits, NO TRADE selection, seeded bootstrap/invalid inputs, restart-safe cached
replay, retuning/overlap/failure/concurrency protection, exploratory and legacy exposure
checks, corrupt-evidence fail-closed behavior, genuinely fresh future intervals,
admin API/409 behavior, CLI replay, disabled promotion and label/timeframe bypass rejection.

These tests do not establish market profitability or full ML leakage safety. Final
holdout protection operates within this persisted application workflow. IID-resampling
outputs remain research diagnostics. Live/provider/VPS acceptance gates are unchanged.

## M4 gateway acceptance mapping

G01..G24 in `tests/test_gateway.py` cover 31 scenarios: valid replies and durable usage;
transient retry/failover; timeout; executable-authority/schema rejection; malformed reply
handling; disabled/missing/input gates; rate/token/cost quota reservations; circuit
restart/recovery; cache TTL/model identity; provenance/usage bounds; sanitized errors;
atomic quotas; fallback context isolation; cancellation; three local perspectives with
NO TRADE; role failure/configuration; API authorization/server-owned routes; state/cache
failures; local adapter impersonation rejection; CLI behavior; bounded concurrency;
and explicit unknown-billing reporting.

These do not establish real API connectivity, independent multi-LLM analysis, genuine
billing enforcement or predictive ability. External adapters, keys, model access/pricing,
provider-specific tokenization, invoice reconciliation and all broker gates remain pending.

## MT5 diagnostic regression coverage

D01..D11 in tests/test_mt5_diagnostics.py cover 15 scenarios: wrong claimed login cannot
reserve a stream; server/demo/disconnect guards run before persistence; a verified
changed account cannot overwrite an existing stream; stale/future/invalid quote errors
are specific; contract errors identify field names without raw inputs; diagnosis is
read-only and hides account numbers; identity-vs-freshness issues are distinct; invalid
contract fields are visible; real accounts stop further symbol reads; account switches
are detected; native exception details are sanitized. Actual VPS quote collection still
requires operator-run diagnostics and a successful collection result.

Timestamp regression gate: `tests/test_time_policy.py` T01–T11 checks normalization,
provenance, persistence, strict five-second freshness, scope/expiry, history blocking,
and stream isolation. This is fixture evidence, not broker acceptance.

Candle timestamp evidence: `tests/test_candle_probe.py` C01–C12 checks independent
quote/candle relationships, bounded reads, identity checks, malformed data, range
disagreement, safe errors, clock regression and a Windows CLI fixture with no files
created. No fixture result verifies a broker timezone or authorizes history ingestion.

Dated history correction: `tests/test_history_time_policy.py` H01–H14 checks shifted
queries, persistent raw/UTC provenance, page replay, interval/scope gates, closed bars,
UTC/raw overlap conflicts, restart/legacy/concurrency protection, append-only evidence,
and the Windows CLI with a fake terminal. Actual broker import acceptance is pending.

Virtual foundation: `tests/test_virtual_ledger.py` V01–V18 covers bid/ask long/short
accounting, gap stops, restart and concurrent replay, risk/volume/geometry/news/stop/data
gates, rollover costs, immutable configuration, memory separation, durable drawdown halt,
isolated CLI behavior, transactional rollback and append-only input/event evidence.
Fixture evidence does not satisfy autonomous forward-trading or broker acceptance.

Quote consumer: `tests/test_virtual_consumer.py` CQ01–CQ19 covers source/contract/account
binding, corrected-time provenance/expiry, stale-gap and out-of-order dispositions,
heartbeat/reception gates, crash-after-commit recovery, concurrent/same-ms delivery,
existing virtual exit marking, isolated fixture and persisted-data observer CLI restart.
Fixture-backed demo-source emulation is not real broker connectivity or forward testing.

Virtual evaluation: `tests/test_virtual_evaluation.py` EV01–EV16 covers due/grace and
half-open boundaries, rolling lookbacks, cost accounting, restart/concurrent dedupe,
transactional failure recovery, missing/sparse observations, bounded index/catch-up,
clock regression, immutable plans/reports, source gaps, late evidence, checkpoint
integrity and isolated fixture/CLI behavior. Promotion/entry/execution stay false.
No fixture substitutes for a real supervised two-/three-day observation trial.

Dashboard: `tests/test_dashboard.py` DASH01–DASH10 covers public shell without secrets,
asset/security headers, auth, empty/seeded projections, viewer/admin restrictions,
stop-only action, unavailable safety state, fixture-directory protection, text-only
dynamic rendering, loopback launch and package/runtime version agreement. HTTP and
syntax checks do not substitute for actual Windows browser or Android acceptance.

## Operations runner continuation

OPS01–OPS10 (`tests/test_operations.py`) cover durable queue restart/idempotency under
an active stop, cross-process OS locking/release, stale/future heartbeat detection,
bounded/redacted evaluator failures, recovery, missing safety state, actual CLI startup,
admin/viewer path privacy, real evaluator report deduplication and abrupt-process restart.
Windows logon task registration, actual VPS recovery and collector supervision remain
manual pending acceptance gates.

## Research registry continuation

REG01–REG13 (`tests/test_registry.py`) cover immutable lineage/restart, exact replay,
concurrent revision conflicts, research-only review requests, reference integrity,
environment/type restrictions, suspension/archive, append-only persistence, atomic audit
rollback, prohibited inputs, authentication, dashboard projection, actual CLI startup,
bounded history and isolated fixture behavior. Browser/VPS acceptance, semantic strategy
evidence matching, shadow trials and promotion are separate pending gates.

## Backup/recovery continuation

BKP01–BKP14 (`tests/test_backup.py`) cover three-memory roundtrip, forced restored stop,
source preservation, heartbeat reset, committed WAL inclusion, runner/writer exclusion,
corruption and unexpected sidecar rejection, destination protection, missing/unsupported
safety/schema state, partial-failure cleanup, manifest traversal, actual CLI with spaced
paths, copy-time mutation, concurrent destination reservation and isolated fixture behavior.
Windows operational restore, encryption/off-site/scheduling and power-loss acceptance
remain separate pending gates.
