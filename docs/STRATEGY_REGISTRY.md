# Research strategy registry — 0.7.0

This is immutable research lineage and review-request tracking, not strategy execution,
champion selection, autonomous learning or validation approval. Descriptions are untrusted
text and are never evaluated as code. No state, metric or API response can enable entries,
broker orders or live trading.

## Windows acceptance

After reviewing/merging the PR, stop the dashboard and operations runner in their own
PowerShell windows using Ctrl+C. Update the project:

```powershell
cd C:\OMNEX-AURA
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
.\.venv\Scripts\python.exe -m aura.registry_fixture
```

The fixture should report two versions, replay_identical true, parent_state suspended,
child_state draft, emergency_stop_active true and execution_allowed false. It uses a new
temporary directory, removes it on exit and does not populate the operational dashboard.

Restart the dashboard with `--data-dir C:\OMNEX-AURA\data --open-browser` as before,
then the separate operations runner with the same directory. The new Strategy laboratory
page displays latest 20 saved versions and their research state. An empty registry is
expected until real research specifications are deliberately registered. Browser page
interaction and actual VPS fixture acceptance remain pending in this development report.

## Register a version locally

Save a reviewed JSON specification locally, containing:

```json
{
  "version_id": "research-gold-v1",
  "strategy_id": "research-gold",
  "parent_version": null,
  "symbol": "XAUUSD",
  "family": "breakout",
  "hypothesis": "Research hypothesis requiring independent validation",
  "entry_method": "Human-readable entry proposal; no executable expressions",
  "exit_method": "Human-readable protective stop and exit proposal",
  "cost_assumptions": "Measure spread, commission, slippage and swap per broker",
  "risk_percent": 0.25,
  "sizing": "fixed_risk_no_loss_recovery"
}
```

Register using `.\.venv\Scripts\python.exe -m aura.strategy --data-dir C:\OMNEX-AURA\data --spec C:\path\to\reviewed-spec.json`.
Inspect with `--show research-gold-v1` or `--list` instead of `--spec`.
Create a changed candidate with a new version_id and parent_version pointing to an existing
version of the same strategy. Existing specifications cannot be overwritten or deleted.
The risk value is a conservative research declaration, not a position-sizing authority.

An action JSON contains operation_id (unique), expected_revision (current revision),
action, reason (10–2000 characters), and optionally record_id. Apply with
`--version research-gold-v1 --action C:\path\to\reviewed-action.json`.

Supported actions:

- annotate: append a research note.
- attach_evidence: draft only; reference an existing historical backtest or validation record.
- request_review: draft only, after both record types have been referenced; state becomes review_requested.
- suspend: mark a research version suspended.
- archive: freeze its history; further changes require a child version.

All initial versions are draft. Suspended and review-requested specifications cannot gain
new evidence attachments; create a child version for revised research. At most 100 events
per version are supported. The API returns current state for exact operation retries;
reusing an ID with changed input, stale concurrent updates or contradictory versions fails.

Evidence links store record type and exact payload SHA-256. Reads and transitions reject
changed or missing references. This verifies the reference's integrity only: records are
NOT checked for semantic agreement with the strategy description, profitability, lineage
coverage, sample adequacy or fresh OOS performance. Synthetic records remain synthetic.
Having both types permits a review request only. No approval/promotion action exists.
No direct virtual/demo evidence references, champion pointer or live eligibility exists.
Historical OOS reservation and virtual evaluation engines remain unchanged.

## API and durability

Authenticated viewers/admins may GET `/v1/strategies?limit=20` (1–100) and
`/v1/strategies/{version_id}`. Lists omit event bodies; detail includes full history.
Only administrators may POST specifications to `/v1/strategies` or actions to
`/v1/strategies/{version_id}/actions`. Conflicts return 409; unsupported fields/actions
return 422. No mutation buttons are added to the dashboard in this milestone.

Specifications/events have SQLite append-only triggers. Version creation, optimistic
revision changes, unique operation IDs and audit writes share a transaction. Data remains
in historical.db, separate from virtual/demo memory. As with existing SQLite stores,
a local administrator can bypass these controls; this is not external tamper attestation.
No schema data is deleted on upgrade. Back up the persistent directory before operational
updates using the existing stopped-writer guidance. Automated backups remain pending.
