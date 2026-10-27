# Milestone 1 — local foundation checkpoint

Status: tested local checkpoint; milestone not complete for deployment.

## Implemented

- Preserved the full supplied master specification.
- Target architecture covering all 22 services and all 15 specialist roles.
- Python FastAPI backend with admin/viewer bearer authorization and strict configuration.
- Research-only/virtual configuration; no live or demo execution mode accepted.
- Three independent deterministic local tasks with evidence storage and explicit NO TRADE output.
- Separate historical, virtual and demo SQLite databases and schema v1 bootstrap.
- Append-only audit triggers; durable queue with idempotency, leases, retry/dead-letter handling.
- Independent emergency-stop command, default ON and durable across restart.
- Hypothetical risk validation with fail-closed safety reads, protective stop geometry,
  spread, data-age, news, position-count and risk-percent checks.
- Read-only injectable MT5 diagnostics and Windows diagnostic script; demo integration plan.
- Backend CI workflow, source package/wheel, Linux package pins and Windows startup script.
- Acceptance/test mapping, operations, deployment boundaries and roadmap.

## Verification actually executed

- pytest: **40 passed, 0 failed**, 1 dependency deprecation warning.
- Ruff: passed for backend, tests and Python scripts.
- Real loopback Uvicorn process/HTTP smoke test: passed.
- Backend process stop/restart with evidence persistence: passed.
- Independent CLI emergency stop while API closed: passed.
- Python source distribution and wheel builds: passed.
- GitHub Actions: not run remotely.

Machine-readable evidence: reports/junit.xml and reports/smoke.json.
The warning is Starlette TestClient announcing a future httpx-to-httpx2 transition;
current HTTP/API tests pass. Dependency/security audit has not been executed locally.

## Scope and limitations

This is a Linux local development environment, not the Windows VPS. SQLite is the local
foundation, not the final PostgreSQL deployment. Bootstrap static tokens are not a complete
user identity system. Durable jobs are manually processed by a bounded worker, not a
running continuous scheduler. Sample statistics are not validated trading strategies or
an ML classifier. Queue delivery is at least once; only identical enqueue requests are
deduplicated, not arbitrary broker orders. No order-submission capability exists.

Private GitHub repository creation/push/PR is pending: GitHub CLI is absent, repository
listing returned no accessible repositories, and the connected operations expose no
repository-creation action. Local source is committed on dev/m1-foundation. The source
checkpoint is preserved for handoff; no remote repository URL is claimed.

No OpenAI key was created: the required local key helper was unavailable. No provider
API calls were made. OpenAI/Claude/Grok adapters and credentials remain pending. Actual
MT5 connectivity, live ticks/history, demo order execution, research/backtesting, virtual
autopilot, adaptive learning, dashboard, Flutter/APK, external notifications, PostgreSQL,
Windows service registration/reboot recovery, TLS, backup automation and all release
acceptance gates remain pending. None is represented as working by this checkpoint.

## Safety and approvals

Live-money trading remains disabled. There is no broker order-send implementation and
no order API. Even clearing the kill switch or passing hypothetical research eligibility
cannot enable execution. No credentials/secrets were committed. Local data and env files
are ignored. Do not expose this bootstrap API publicly. Demo activation and deployment of
future executable trading changes require review; no such activation is requested now.

## Next tasks

Finish private source hosting/remote CI and production foundation gates. Implement M2
read-only broker metadata/tick/history ingestion with fixtures, then verify it on the
Windows VPS using an identified demo account. Keep all broker orders disabled throughout
M2. Add official provider adapters only after secure credentials are configured.
