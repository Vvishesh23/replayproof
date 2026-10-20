# Architecture decisions

On 19 October the owner requested a presentation frontend, extending the original
backend-only brief. Static HTML/CSS/JavaScript is packaged with the Python module
and served from the same FastAPI origin. This adds no service, broker, framework
runtime, CDN, or deployment boundary. Bounded read endpoints expose recent streams,
canonical event pages and reconciliation history. The interactive scenario uses
normal ingestion/reconciliation only; development rebuild stays disabled.

One synchronous FastAPI process (or several workers) shares PostgreSQL 16. Each
stream is one synthetic instrument session starting at sequence 1. Price ticks
have scale 10000 ticks per price unit. All bars are provisional.

Every ingest transaction locks its stream row with SELECT FOR UPDATE before
checking identity, inserting a canonical event, or changing the cursor and bars.
Database unique constraints back both event identities. All application writers
must follow this protocol. READ COMMITTED is sufficient because reconciliation
and rebuild acquire the same lock before reading. Readers of status also lock
to obtain a coherent view. Conflicts commit their audit entry before HTTP 409.

The cursor advances only through a maximal contiguous prefix. Each touched minute
is recomputed from events at or below the new cursor, ordered by event time and
sequence. Historical timestamps may change old minutes. No time watermark exists.
This costs work proportional to affected minute history; it favors clarity over
throughput. Stream locks serialize a hot stream but independent streams proceed.

Canonical events have two unique indexes (stream, sequence) and (stream, source
ID), plus a (stream, event time) index for minute reads. Bars use a composite PK.
Source business fields have no update path. Database owners can bypass this;
there is no external source of truth or tamper-proof audit guarantee.

Reconciliation uses independent PostgreSQL window functions and aggregates;
it persists exact missing, extra and differing buckets. Rebuild atomically replaces
the projection under the stream lock. Unexpected errors roll back the whole
ingestion transaction. Lost responses are handled by identical retries.

Rejected alternatives: process mutexes do not coordinate workers; SQLite cannot
validate PostgreSQL locking; a broker adds another consistency boundary; incremental
OHLC boundary metadata complicates historical timestamps. Permanent gaps require
operator/source recovery; timestamps do not prove completeness. No auth or public
deployment is supplied. Dev rebuild is disabled by default.
