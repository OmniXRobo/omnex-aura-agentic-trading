# M2 candle timestamp evidence probe — 0.4.3

Added `aura.diagnose --candle-time-probe` and `aura/candle_probe.py`: three raw tick/candle
samples, five recent bars per sample, inclusive numerical-range replay and independent
quote/candle bucket comparisons. Demo identity is checked around each native read. The
probe emits no account identifier, creates no database, changes no stream and never
creates a correction policy or authorizes history ingestion. No execution interface added.

Validation: 221 tests passed, zero failed; Ruff passed; HTTP/restart/independent safety CLI
smoke passed; source/wheel built as 0.4.3. One preexisting Starlette/httpx deprecation warning
remains. Tests include Windows CLI emulation with a fake terminal and no generated files;
this is not a real Windows broker connection. PR #7 was verified merged with all ten
push/PR Linux/Windows and dependency checks successful before starting this change.

Limitations: numerical range consistency does not prove UTC or historical DST. Native
calls have no hard timeout. Current bars may change between reads and sessions may be
sparse. All timing relationships are observations only. Real VPS output, independent
candle-time review, dated historical conversion and broker acceptance remain pending.
The nonzero quote-offset history block remains active. Real external AI providers,
autonomous virtual execution, dashboard/Android and production operations remain separate
pending milestones. No API credentials or broker orders were used.

See docs/MT5_CANDLE_TIME_PROBE.md for exact VPS steps and C01–C12 acceptance mapping in
ACCEPTANCE_CRITERIA.md. Next evidence required: actual Equiti XAUUSD probe JSON.
