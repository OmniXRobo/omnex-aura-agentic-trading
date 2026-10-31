# Milestone roadmap

| Milestone | Status | Remaining acceptance gate |
| --- | --- | --- |
| 1 Foundation | PR #1 merged; Linux/Windows CI and audit passed | Production DB/auth and actual Windows VPS service validation |
| 2 Market Data | PR #2 merged; collector and Linux/Windows CI verified with fixtures | Actual Windows MT5 connection, broker acceptance and lossless tick archive |
| 3 Trading Research | PR #3 merged; baseline backtests plus chronological validation/holdout ledger implemented | Real datasets, macro/news, robust statistical/market stress and ML leakage controls |
| 4 Multi-Agent AI | Provider port, review workflow, durable quota/health and local/fake reliability tests implemented | Official OpenAI/Claude/Grok adapters, secure credentials, verified models and real API tests |
| 5 Virtual Autopilot | Persistent virtual market ledger implemented with fixtures | Accepted live-data observation, automated decisions, full lifecycle and supervised 2/3-day trial |
| 6 Self-Healing | Not started | Drift, isolated experiments, fresh OOS and shadow promotion/rollback |
| 7 MT5 Demo Autopilot | Not started / orders disabled | Owner demo activation, independent risk, reservation, reconciliation, fault recovery |
| 8 Dashboard and Android | Local authenticated operations dashboard implemented | Actual Windows browser acceptance, production auth/TLS, Flutter app and APK |
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

Owner VPS evidence confirmed four M1 candles imported and replayed as zero insertions /
four duplicates for the narrowly reviewed historical interval after PR #9. This does not
complete market-data acceptance: current quote collection, broader history, sessions and
lossless ticks remain pending. No screenshot/raw private data is committed.

M5 foundation (0.5.0): virtual.db sessions, decimal cost accounting, bid/ask market fills,
SL/TP on available quotes, atomic receipts/events and durable intent/position protection.
All strategy automation, production deployment and two-/three-day scheduling remain
pending. See docs/VIRTUAL_LEDGER.md for assumptions and remaining gates.

PR #10 is merged; the owner ran the v0.5.0 isolated virtual fixture successfully on the
Windows VPS. This is synthetic accounting/restart evidence, not forward performance.
The 0.5.1 consumer adds pinned source/contract/account interpretation, stale-gap audit,
durable cursors and receipt recovery. It observes/manages existing virtual positions
only; new entries and autonomous strategy/evaluation scheduling remain unimplemented.
Actual fresh quote collection and source-to-virtual VPS acceptance are still pending.

PR #11 is merged and its consumer fixture ran successfully on the owner VPS. The actual
feed was stale during the reported market closure; no new timestamp offset was inferred
or renewed. Fresh source-to-virtual observation remains pending when quoting resumes.

0.5.2 adds durable overlapping two-/three-day diagnostic plans, bounded index/catch-up,
immutable reports, accounting/quality metrics and foreground watch polling. Logical-clock
fixtures are not a real multi-day trial. Automatic strategy changes/promotion, process
supervision and actual 48/72-hour observation acceptance remain pending.

The owner prioritized a visible app before further registry work. The 0.6.0 batch adds
a packaged local dashboard, bounded authenticated summary API, admin stop-only control,
loopback launcher and dashboard/security tests. It displays real saved records with
explicit fixture/stale/empty states; no trading or provider functions are fabricated.
Managed browser preview cannot access the Python environment, so browser rendering is
unverified here. Actual Windows browser acceptance remains pending.

PR #12 is merged and the owner ran its logical-clock evaluator fixture successfully.
This does not count as real multi-day market performance. Operational collectors,
evaluators and service supervision are not started by the dashboard. External AI,
strategy registry/promotion, complete virtual entry automation and Android remain pending.

0.6.1 operations continuation: independent local queue/diagnostic runner, OS directory
lock, durable redacted polling heartbeat, bounded evaluator failures, absolute dashboard
data directory and optional current-user Windows logon task. Owner screenshots confirm
0.6.0 login and empty dashboard rendering. Full page interactions, actual persistent
feed mapping, Windows task/logon/reboot recovery and fresh quote consumption remain
pending. Collector/consumer supervision, backups, external AI, model registry, strategy
entry automation, demo orders and Android are not completed by this batch.

0.7.0 registry continuation: immutable research versions/parent lineage, historical
evidence reference digests, atomic append-only review requests/suspensions/archive,
optimistic concurrency/idempotency, authenticated API/local CLI and read-only Strategy
Laboratory view. This is a research registry only: evidence references are not strategy
validation, and champion/challenger selection, shadow execution, promotion/rollback and
automated self-healing remain pending. Owner VPS screenshot confirms the 0.6.1 runner
startup message; ongoing heartbeat, scheduled logon/reboot and collector acceptance are
not established by that screenshot. See docs/STRATEGY_REGISTRY.md.

0.7.1 recovery continuation: three-memory SQLite backup API snapshots under coordinated
write locks, bounded-format manifests with hashes/counts/schema checks, verification and
non-overwriting isolated restore with all emergency stops ON, cleared copied heartbeat
state and restoration audit. Windows fixture/real-data recovery, encrypted/off-site
backups, scheduling, retention and power-loss acceptance remain pending. Owner screenshot
confirms the 0.7.0 registry fixture succeeded on the VPS; it is not strategy performance
or new dashboard interaction acceptance. See docs/BACKUP_RECOVERY.md.

0.8.0 diagnostic continuation: immutable virtual evaluation triage with pinned policy,
source digests, atomic bounded cursor/audit, runner polling with bounded failure blocking,
local/API batch entry points and read-only Learning Review page. This is deterministic
evidence review only: no causal attribution, statistical drift, strategy changes,
challenger generation, promotion or risk changes. Backup compatibility includes schema
10. Owner screenshot confirms the 0.7.1 synthetic recovery fixture succeeded; actual
operational backup/restore and new browser/diagnostic VPS acceptance remain pending.
See docs/VIRTUAL_DIAGNOSTICS.md; full self-healing and remaining release gates are open.
