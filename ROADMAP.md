# Milestone roadmap

| Milestone | Status | Remaining acceptance gate |
| --- | --- | --- |
| 1 Foundation | PR #1 merged; Linux/Windows CI and audit passed | Production DB/auth and actual Windows VPS service validation |
| 2 Market Data | Read-only collector, validated snapshots/history, API and fixtures implemented | Actual Windows MT5 connection, broker acceptance and lossless tick archive |
| 3 Trading Research | Not started | Indicators, strategies, backtest and statistical validation |
| 4 Multi-Agent AI | Local framework checkpoint only | OpenAI/Claude/Grok adapters, secure credentials, provider cost/failure tests |
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
