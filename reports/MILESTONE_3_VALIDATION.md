# M3 continuation — chronological research validation (0.3.1)

PR #3 is confirmed merged. All Linux/Windows Python 3.11/3.12 jobs and dependency audits
for that PR passed. Actual Windows VPS/MT5 connectivity is still unverified.

## Implemented

- `aura/validation.py`: fixed-budget candidate search, expanding training prefixes,
  disjoint chronological test windows, a bar-count gap and separate final holdout.
- `aura/backtest.py`: entry inhibition before evaluation_start, causal prefix warmup,
  tracked exploratory exposure and conservative indexing of prior stored backtests.
- Transactional final-interval reservations, exact completed-request replay after restart,
  overlap/retuning protection and failed/concurrent run protection; new historical schema v3.
- Source/label/timeframe changes cannot bypass instrument/time holdout overlap checks.
- Seeded IID P/L resampling diagnostics, separate development/final results and always-disabled
  promotion/execution flags. No ML fit, market-data connection or trading permission added.
- Admin-only `/v1/research/validate`, CLI `aura.validate`, synthetic example and detailed guide.

## Verification

Final local suite: 132 passed, 0 failed (104 previous + 28 validation scenarios). Ruff,
backend HTTP/restart and independent-stop smoke, source/wheel builds are checked before
publishing. One existing Starlette TestClient deprecation warning. Evidence is recorded
in reports/junit.xml and reports/smoke.json. Remote CI for the new PR must be checked
separately; this report confirms only the preceding PR's completed remote checks.

## Limitations and safety

Chronology is validated on supplied bars, not independently authenticated broker data.
The bar-count gap is not a general label-horizon purging solution for future ML models.
The ledger protects persisted app workflows, not externally seen prices/local admin edits.
IID trade resampling ignores temporal correlation, selection bias and changing regimes;
it is not a calibrated future-return confidence claim. Window equity resets are explicit
and pooled P/L is not a compounded portfolio. Existing cost/fill/margin model limits remain.

All promotion and execution remain disabled. No credentials/secrets/personal data are
required or committed. No API provider or broker order/position-management function is
called. Synthetic results remain clearly labelled and do not prove an investable strategy.
This is further M3 engineering validation, not full master-spec completion.

## Next

Review the validation PR and run the synthetic example. Complete actual MT5 demo data
acceptance on the VPS, then add trustworthy dataset preparation, cost/regime stress,
macro/news and robust statistical validation. Provider integration still needs secure
credentials; continuous virtual/self-healing/autopilot milestones are not implemented.
