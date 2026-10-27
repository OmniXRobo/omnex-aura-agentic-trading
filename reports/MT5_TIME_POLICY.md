# M2 timestamp continuation — 0.4.2

Implemented explicit server/symbol quote policies, maximum 24-hour validity, raw and
normalized timestamp provenance, append-only policy evidence and persistent stream-offset
isolation. UTC remains the default. Corrected quotes still reject future times and ages
above five seconds. Historical imports are blocked for nonzero-corrected streams, including
a restart that omits the policy flag. No account rebind or DB deletion is implemented.

Validation: 196 tests passed, zero failed; Ruff passed; HTTP/restart/independent safety CLI
smoke passed; source distribution and wheel built. One existing Starlette/httpx deprecation
warning remains. The migration test was updated to require schema marker 5 and verifies
existing foundation records survive repeated initialization.

Fixture evidence only: Windows MT5 is unavailable in the Linux development environment.
The reported VPS offsets are not proof of a documented broker timezone convention. Official
MetaQuotes documentation specifies UTC; these corrections require explicit operator review
of synchronized UTC and advancing quotes. Candle timestamp encoding, DST and dated history
conversion remain unverified. Default historical UTC imports are unchanged for streams with
no nonzero quote binding. This release does not complete broker acceptance, lossless tick
archiving, production operations, external AI providers or virtual/demo execution.

Next VPS step: review the PR, update code, follow docs/MT5_TIME_POLICY.md and send the new
read-only diagnostic JSON. Do not start collection unless terminal checks pass. No secrets,
account identifiers, native DBs or uploaded screenshots are committed. All execution stays
disabled; no broker order interface was added.
