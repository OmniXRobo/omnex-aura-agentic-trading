# Milestone roadmap

| Milestone | Status | Remaining acceptance gate |
| --- | --- | --- |
| 1 Foundation | PR #1 merged; Linux/Windows CI and audit passed | Production DB/auth and actual Windows VPS service validation |
| 2 Market Data | PR #2 merged; collector and Linux/Windows CI verified with fixtures | Actual Windows MT5 connection, broker acceptance and lossless tick archive |
| 3 Trading Research | PR #3 merged; baseline backtests plus chronological validation/holdout ledger implemented | Real datasets, macro/news, robust statistical/market stress and ML leakage controls |
| 4 Multi-Agent AI | Provider port, review workflow, durable quota/health and local/fake reliability tests implemented | Official OpenAI/Claude/Grok adapters, secure credentials, verified models and real API tests |
| 5 Virtual Autopilot | Not started | Cost-aware fills, accounting, 2/3-day durable schedule |
| 6 Self-Healing | Not started | Drift, isolated experiments, fresh OOS and shadow promotion/rollback |
| 7 MT5 Demo Autopilot | Not started / orders disabled | Owner demo activation, independent risk, reservation, reconciliation, fault recovery |
| 8 Dashboard and Android | Not started | Backend auth sessions, web UI, Flutter app, actual APK build |
| 9 Continuous Research | Not started | Authorized sources, licensing and isolated experimentation |
| 10 Release and Operations | Documentation/framework only | Full testing, supervised Windows recovery, backups, monitoring, signed release |

Repository visibility is public at the owner's explicit instruction, superseding the
original private preference. PR #1 established source hosting and verified the backend
on Linux/Windows with Python 3.11/3.12 in CI.

Next gate: verify the M2 collector on the actual Windows VPS using
docs/MT5_READ_ONLY_SETUP.md. Broker-connected runtime remains unverified here. Research
can continue with fixtures; no demo order execution is enabled.

M3 research fixtures may run before Windows broker acceptance. They must remain labelled
synthetic/in-sample and cannot promote a strategy or enable broker execution. See
reports/MILESTONE_3.md and docs/RESEARCH_BACKTEST.md for scope and evidence.

The M3 validation continuation adds expanding-window candidate selection, disjoint test
windows, a separately reserved final holdout, persistent exposure/reuse protection and
explicitly limited IID trade-resampling diagnostics. It does not complete statistical
strategy validation or enable promotion. See docs/CHRONOLOGICAL_VALIDATION.md.

PR #4 is merged and its Linux/Windows tests/builds and dependency audits passed. The M4
continuation implements only the provider-independent gateway and explicit local fallback;
real external providers remain disabled/unimplemented. See docs/AGENT_GATEWAY.md.

M2 timestamp continuation: scoped expiring quote corrections preserve raw time and policy
evidence. UTC remains default. Nonzero correction blocks historical imports pending
independent candle-time verification. Actual VPS acceptance remains pending.

PR #7 is merged; its Linux/Windows CI and dependency audits passed. A read-only candle
time probe now collects bounded position/range comparisons independently of quote
correction. Actual candle timing, DST rules and history acceptance remain unverified.

PR #8 is merged. M2 now supports operator-attested intraday history policies scoped to a
server/symbol/timeframe and a dated interval, with raw/UTC provenance and restart-safe
interpretation reservations. MT5 imports require explicit history evidence, including
offset-zero policies. D1 remains unsupported by this correction path. Actual VPS
import/replay acceptance, broader dated evidence and DST rules remain pending.
