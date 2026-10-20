# Falsifiable contract

I1 Prefix: cursor is the greatest consecutive sequence from 1; future events have
no projection effect. Test: gap fill and multiple gaps.

I2 Idempotent: identical canonical retry preserves source and bar rows; divergent
sequence or reused source identity commits an audit conflict without replacement.
Test: duplicate/conflict and concurrent retry tests.

I3 Correct: integer OHLCV equals applied events grouped into UTC minutes, with
open/close ordered by (event_time, sequence). Test: historical/tied timestamps.

I4 Crash safety: source, cursor and bars commit together. Test: injected reducer
exception and retry after a successful commit with discarded response.

I5 Recovery: normal ingest of missing events applies the buffered prefix. No
recovery path writes source business fields. Test: gap fill.

I6 Reconciled: independent SQL expected rows equal every materialized row under
the stream lock. Test: changed, missing, extra rows and rebuild.

I7 Replay: equal canonical event sets produce byte-identical normalized bar JSON
and SHA-256 regardless of delivery order/retries. Stream ID is excluded from hash;
UTC ISO timestamps, sorted minute rows, fixed scale and integer fields are included.
Test: three seeded permutations and concurrent ingestion.

These describe the contracts and their tests. See VERIFICATION.md for the executed
native/Docker evidence and the separately identified unrun remote CI check.
