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
