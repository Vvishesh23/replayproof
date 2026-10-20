# How ReplayProof works

Think of sequence numbers as numbered pages. Keeping page 4 is safe, but reading
past missing page 3 could make a report incomplete. The cursor says how far the
complete prefix extends; buffered pages have no analytical effect yet.

`SELECT * FROM streams WHERE id = :id FOR UPDATE` makes another writer for the
same stream wait until commit/rollback, across processes. Different streams lock
different rows. `UNIQUE(stream_id, sequence)` is the database's final identity
guard; `(stream_id, source_event_id)` prevents relabeling the same source print.

One transaction inserts the event and changes cursor/bars. Exceptions roll it all
back. Identity conflicts are returned from the service, allowing the audit write
to commit before the route returns 409. Retry hashing includes the normalized UTC
business payload and stream ID, never receive time.

The online reducer orders prints by timestamp and sequence inside each minute.
SQL independently uses row_number in both directions to select open and close;
SUM/MIN/MAX/COUNT compute the other fields. A lock protects the comparison from
simultaneous ingest. READ COMMITTED normally gives a fresh snapshot per statement;
the lock protocol prevents cooperating writers changing this stream between reads.
REPEATABLE READ would instead preserve a transaction snapshot but requires careful
retry handling under concurrent updates.

Indexes trade write cost/storage for efficient reads. The sequence unique index
supports prefix scans; the event-time index supports historical minute ranges.
Replay means resubmitting canonical events through normal ingestion, not directly
changing bars. Rebuild changes only the derived projection from retained source.

## Fifteen interview questions

1. Why no Python mutex? It cannot serialize independent worker processes.
2. Why lock before checking duplicates? Check and insert must share serialization.
3. Why two unique constraints? Sequence and source identifier are distinct identities.
4. Why not apply event 4 immediately? It would violate the contiguous-prefix contract.
5. Is the highest received sequence completeness? Only up to that number; no tail inference.
6. Are bars final? No; later sequence events can have earlier timestamps.
7. What chooses open? Earliest (event_time, sequence), not arrival order.
8. Why integer ticks? Exact arithmetic and explicit scale avoid float drift.
9. What if commit succeeds but response fails? Identical retry returns duplicate.
10. Why return rather than raise for conflicts? An exception inside the transaction would roll back the audit.
11. Can reconciliation share the reducer? That could repeat the same algorithmic defect.
12. Why lock during reconciliation? Multiple READ COMMITTED reads otherwise see changing state.
13. What bottlenecks? One hot stream serializes; minute recomputation revisits history.
14. Can SQL prove source truth? No; it proves projection consistency with retained events.
15. What if volume overflows bigint? PostgreSQL rejects the write; transaction rolls back, requiring operational attention.
