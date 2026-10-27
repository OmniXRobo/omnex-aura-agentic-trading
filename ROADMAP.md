# Milestone roadmap

| Milestone | Status | Remaining acceptance gate |
| --- | --- | --- |
| 1 Foundation | Local checkpoint implemented; incomplete remotely | Private GitHub repo/PR, CI run, production DB/auth, Windows service validation |
| 2 Market Data | Read-only port and plan | Windows terminal diagnostics, demo credentials, timestamps, contract/tick/history ingestion |
| 3 Trading Research | Not started | Indicators, strategies, backtest and statistical validation |
| 4 Multi-Agent AI | Local framework checkpoint only | OpenAI/Claude/Grok adapters, secure credentials, provider cost/failure tests |
| 5 Virtual Autopilot | Not started | Cost-aware fills, accounting, 2/3-day durable schedule |
| 6 Self-Healing | Not started | Drift, isolated experiments, fresh OOS and shadow promotion/rollback |
| 7 MT5 Demo Autopilot | Not started / orders disabled | Owner demo activation, independent risk, reservation, reconciliation, fault recovery |
| 8 Dashboard and Android | Not started | Backend auth sessions, web UI, Flutter app, actual APK build |
| 9 Continuous Research | Not started | Authorized sources, licensing and isolated experimentation |
| 10 Release and Operations | Documentation/framework only | Full testing, supervised Windows recovery, backups, monitoring, signed release |

Next work: finish M1 deployment and GitHub gates, then implement M2 read-only ingestion
against recorded fixtures before testing the Windows connector. Research tasks can
continue without provider credentials. Do not enable demo execution while addressing
market-data integration.
