# Verified backup and quarantined recovery — 0.7.1

This local CLI snapshots historical.db, virtual.db and demo.db without merging their
records. It uses SQLite's backup API, so committed data still in WAL files is included.
It never copies broker credentials, API environment files, terminal installations or
operating-system settings. Those need a separate protected operational recovery plan.

## First Windows acceptance check

After reviewing/merging the PR, stop the dashboard and operations runner using Ctrl+C in
their respective PowerShell windows. Stop any collector/evaluator/consumer processes too.
If a scheduled operations task was installed, stop that task before maintenance.
Then update and run the isolated fixture:

```powershell
cd C:\OMNEX-AURA
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
.\.venv\Scripts\python.exe -m aura.backup_fixture
```

Expected output: memories_verified 3, records_preserved true, restored_emergency_stop_active
true, original_control_unchanged true, backup_verified true, execution_allowed false.
This fixture only uses temporary synthetic databases and removes them afterward. It is
not an operational backup of your data and will not populate dashboard views.

## Create and verify a real local backup

Use the exact same data directory as the dashboard and collector. Keep writers stopped
during maintenance to avoid interrupting their database operations. The CLI rejects an
active operations directory lock, acquires write locks across all three memories before
reading any snapshot, and fails rather than bypassing a busy database. Dashboard access
is not needed. It does not disable or alter source safety controls.

```powershell
.\.venv\Scripts\python.exe -m aura.backup create --data-dir C:\OMNEX-AURA\data --destination C:\OMNEX-AURA-BACKUPS
```

The output reports a newly generated `aura-<backup-id>` directory. Copy that exact local
path into the verify command; replace the placeholder below:

```powershell
.\.venv\Scripts\python.exe -m aura.backup verify --backup C:\OMNEX-AURA-BACKUPS\aura-REPLACE_WITH_BACKUP_ID
```

The manifest records SHA-256, file sizes, supported schema versions and selected table
counts, plus the application version and snapshot time. Verification checks the exact
three-file memory set, SQLite integrity, required safety state and manifest metadata.
Unexpected WAL/journal/extra files or altered data reject the bundle. Do not edit it.
SHA-256 detects altered bytes relative to the manifest; it is not a signature authenticating
the backup against an attacker who can replace both the databases and the manifest.
Only use backups produced by a trusted installation.

Backups are explicitly **unencrypted**. Protect the destination with appropriate Windows
ACLs and encrypted storage before using private operational data. This milestone does
not implement encryption, automatic scheduling, off-site replication, retention deletion
or production disaster recovery. No backup task is installed automatically. Nothing is
uploaded. Never commit or publicly share backup databases or their manifests.

## Restore into a separate directory

Choose a destination that does not exist, outside the backup bundle. Existing directories,
even empty ones, are rejected. The active `C:\OMNEX-AURA\data` directory is never replaced.

```powershell
.\.venv\Scripts\python.exe -m aura.backup restore --backup C:\OMNEX-AURA-BACKUPS\aura-REPLACE_WITH_BACKUP_ID --destination C:\OMNEX-AURA-RESTORE-CHECK
```

Restore verifies the bundle, copies to staging, re-verifies the copied bytes, forces the
kill switch ON in every memory, appends restoration audit records, and clears copied
operations heartbeat rows. It preserves research/market/virtual/demo records and existing
job/lease evidence; it does not start workers or automatically replay pending work. Review
jobs, policies, fresh broker binding and source/account state before manually resuming
any collector or consumer. Copied policies do not gain a new validity period.

The new directory is reserved exclusively; files are published with exclusive creation
and `restore.json` is written last as a completion marker. The backup completion marker
is `manifest.json`. Interrupted copies can leave incomplete directories; absence of a
complete valid marker means they must not be used. Normal caught failures clean owned
partial files. No whole-directory atomic publication or power-loss durability acceptance
is claimed. Temporary `.incomplete-*` and `.restore-incomplete-*` folders are not backups.

Restore metadata records original backup identity and the newly modified safety/audit
state. The restored directory is an operational copy, not an unchanged backup bundle;
do not pass it to `backup verify` or edit the original manifest to match restored files.
The original bundle remains unchanged and independently verifiable.

For an isolated visual inspection, start only the dashboard against the restored folder,
on a different port if necessary:

```powershell
.\.venv\Scripts\python.exe -m aura.dashboard --data-dir C:\OMNEX-AURA-RESTORE-CHECK --port 8001 --open-browser
```

Use its own locally printed token. Inspect saved records and emergency stop. Stop this
inspection dashboard afterward. The normal source dashboard/runner can then be restarted
using their original explicit `--data-dir C:\OMNEX-AURA\data`. Keep the recovered copy
isolated until a deliberate operational recovery review; no automatic switchover exists.

## Current acceptance limits

Linux tests include actual backup/verify/restore subprocesses, WAL snapshot behavior,
blocked writers, active runner exclusion, corruption/manifest/path checks, copy-time
mutation, empty destination collision rejection, cleanup, preserved records, cleared
heartbeats and forced safety stop. Windows-specific permissions, operational data size,
disk-full/power-loss recovery and actual VPS restore acceptance remain pending.
Future schema versions beyond the current supported 1–10 set are rejected; migrations
require a separately reviewed compatibility update. Live-money trading remains disabled.

Version 0.8.0 adds schema 10 for virtual diagnostics; backup/restore preserves those
reports and their cursor. Older binaries reject the newer schema rather than guessing.
