# Backup and recovery continuation — 0.7.1

Implemented coordinated write-locked snapshots of three separate SQLite memories using
the backup API, manifest/hash/count/schema verification, exclusive non-overwriting
publication, isolated restore with forced safety stop, cleared heartbeat evidence and
restore audit records. Added CLI, isolated smoke fixture, storage exclusions and runbook.

Validation: 362 tests passed, zero failed/skipped. Fourteen new recovery cases include
actual CLI subprocesses, committed WAL content, blocked writers/active runner, snapshot
mutation, manifest/path/sidecar rejection, cleanup, exclusive destination reservation,
record preservation, forced stop and cleared heartbeat. Ruff/whitespace checks passed;
source and wheel distributions built. Existing Starlette/httpx TestClient deprecation
warning remains. Smoke output confirmed three memories verified, records preserved,
source control unchanged, restored stop ON and no existing operational data modified.

No source application controls are changed by backup. No actual user data is accessed,
backed up, uploaded, restored or switched over by this PR. Backups are not encrypted,
signed, scheduled or replicated. Hashes alone do not authenticate an untrusted bundle.
Interrupted publication lacks a completion marker; power-loss recovery is not certified.
Windows operational acceptance remains pending and is distinct from Linux test evidence.

External AI, semantic strategy validation, self-healing/promotion, automatic virtual
entries, continuous forward trial, collector supervision, demo orders, Android and
production deployment remain incomplete. This is a recovery milestone, not full platform
completion. Live-money trading remains disabled.
