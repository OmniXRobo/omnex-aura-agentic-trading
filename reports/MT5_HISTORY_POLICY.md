# M2 dated historical timestamp policy — 0.4.4

Implemented separate operator-attested candle policies for an exact server, symbol,
intraday timeframe and already observed UTC interval (maximum 31 days). Native range
requests add the explicit offset; returned candle openings subtract it. Raw/UTC times,
offset and policy digest persist with every policy-backed candle, and full policies are
append-only. No automatic timezone/DST inference or quote-policy reuse is implemented.
MT5 history imports now require an explicit policy, including offset zero; D1 policies
are rejected. Fixture history retains its UTC default.

Schema marker 6 adds durable interpretation claims and policy evidence. Immediate SQLite
transactions reject conflicting offsets over overlapping UTC OR raw transport intervals.
Claims persist through interruption/restart; legacy candles cannot be silently shifted.
Account bindings and historical events are preserved, and ordinary retries with the same
policy deduplicate. Claims are not automatically removed after failed/empty requests.

Validation: 246 tests passed, zero failed; Ruff passed; real HTTP/restart/independent safety
CLI smoke passed; v0.4.4 source distribution and wheel built. One preexisting Starlette/
httpx deprecation warning remains. The Windows import CLI is tested against a fake native
terminal. Actual Windows broker import/replay, comprehensive session/cost acceptance,
long-range dated evidence, DST conversion and lossless ticks remain pending. No broker
orders or external provider APIs were called. No screenshot/private broker data is committed.

The owner supplied recent successful probe evidence; this does not certify older history.
Next VPS action after review/merge: follow docs/MT5_HISTORY_TIME_POLICY.md, attest only the
small closed interval supported by the observation, import it, repeat with the same policy
and send the summary JSON. The full multi-agent/virtual/demo/dashboard milestones remain
pending. No live-money trading or demo execution interface was added.
