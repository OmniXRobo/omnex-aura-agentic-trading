# Operations and recovery

## Current environment

Development was performed on Linux with Python 3.12, Git and Node available. This is not
the user's Windows Server 2022 VPS. GitHub CLI, PostgreSQL, Flutter/Android SDK and the
Windows MT5 terminal were not available as verified runtime components. No external
repository was created, no provider API was called, and no broker order was submitted.

## Local security

Generate distinct high-entropy admin/viewer service tokens and set process environment
variables without logging them. No built-in default exists. Keep the API on loopback.
This release has bootstrap static-token authorization, not secure end-user registration,
MFA or a full identity provider. Do not expose it publicly. Add TLS/VPN, reverse-proxy
request limits, per-user sessions, rotation, rate limits and redacted structured logging
before remote use. `risk/preview` is a hypothetical calculation, never broker authorization.

Local administrator access can bypass SQLite triggers and safety state. Restrict data
directory ACLs to the service identity and backup operator. Use disk encryption. Avoid
shared Windows accounts for terminal and administration. Dependencies are locked for
this checkpoint, but supply-chain verification and a clean dependency audit remain gates.

## Windows deployment framework

`scripts/start-backend.ps1` creates a venv, installs the backend and starts loopback
Uvicorn. It is a bootstrap script, not a registered Windows service. Configure a tested
service wrapper for Python with absolute working/data paths, restricted identity,
secret environment, automatic restart/backoff and health checks. MT5 may require a
persistent interactive user session; validate actual VPS behavior after sign-out and
reboot. No service/reboot success is claimed here. ChatGPT need not stay open once the
backend is running under its own verified supervisor.

## Emergency stop

Run `python -m aura.safety --data-dir ABSOLUTE_DATA_DIRECTORY` from the same installed
environment. This persists the stop without using the API/orchestrator. Use the authenticated
admin route to clear it only for research tests. Clearing it cannot enable execution.
If database reads fail, eligibility blocks. A real executor will need a separately
supervised fail-closed stop and independent broker-side protective stops.

## Backup and restore

Before demo activation, implement and test encrypted scheduled backups and a separate
backup destination. For the current prototype stop all writers and workers, checkpoint
SQLite WAL, and copy all three database files together with the release version; or use
SQLite's online backup API per file while recording the consistency boundary. Do not copy
only a live main DB file while discarding its WAL. Never commit DBs. Test restore into an
isolated folder, verify schema version/record counts and turn the kill switch ON before
starting. Do not restore stale orders into an execution-enabled system. This checkpoint
has no broker execution, and automated backup scripts are not yet implemented.

## Source control handoff

Local branch: dev/m1-foundation. Target private repository: omnex-aura-agentic-trading.
The connected GitHub listing returned no accessible repositories; installed connector
operations do not include repository creation, and GitHub CLI is absent. Once authenticated
GitHub CLI is available, create the private repository without exposing credentials:

```bash
gh repo create omnex-aura-agentic-trading --private --source . --remote origin
git push -u origin dev/m1-foundation
```

Set up a main baseline and open a reviewed development PR before merging. Do not blindly
push this development branch to production. Confirm private visibility and configure branch
protection manually or with authenticated administration. CI must run remotely before it
is reported as passed. Backend CI YAML includes Linux/Windows, lint, tests, build and a
dependency-audit job. Android, release signing, advanced scanning and publishing jobs await
actual implementations and credentials.

## Rollback

Keep tagged source releases and version-associated database backups. Stop workers,
activate the kill switch, restore the reviewed source and compatible database backup,
run diagnostics/tests, then resume research only. Do not roll back against a broker
account until reconciliation has proven current external state. SQLite v1 schema creation
is idempotent; future schema evolution needs ordered migrations and compatibility tests.
