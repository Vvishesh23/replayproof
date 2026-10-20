# ReplayProof — Research check and differentiator analysis

## Recommendation

**Drop the original LedgerLock wallet-transfer clone as the lead portfolio project.** It is useful educationally but overlaps directly with multiple publicly accessible FastAPI/PostgreSQL financial ledger project examples.

**Build ReplayProof**, a PostgreSQL-backed, sequence-aware market-data ingestion service with idempotent retry handling, gap detection, durable buffering, a contiguous apply cursor, correct time-based 1-minute OHLCV projection, independent reconciliation, atomic repair and reproducible failure-injection case study. The domain matches the owner's quant experience; the technology demonstrates database and reliability fundamentals missing from the existing OCRFlow-focused backend resume. Do not represent it as unique or production-ready.

## GitHub landscape (illustrative, not exhaustive)

| Archetype | Public comparison | Findings | Implication |
|---|---|---|---|
| Wallet/ledger | https://github.com/vkr-vavilla/finledge | Python/FastAPI/PostgreSQL, double entry, retries and locking | LedgerLock is not visibly distinctive on concept alone |
| Ledger crash safety | https://github.com/alimekawi9/ledger | Fault-injection, concurrency and load testing | Even “reliability testing” alone is insufficient novelty |
| Order matching | https://github.com/tcs-codes/matching-engine | C++ matching, cancels, latency | Also a crowded finance portfolio direction |
| Market feed recovery | https://github.com/SionKang/feed-handler | Gap detection, replay | Can't claim feed gaps and replay are novel |
| Market feed advanced | https://github.com/anushkaadwivedii/resilient-market-data-engine | Packet validation, sequence recovery, reconstructed book | Don't use a simple feed handler as differentiator |
| Data reliability | https://github.com/mohilamin/data-pipeline-reliability-incident-lab | Synthetic failures, quality scorecards, replay and postmortems | Failure-demo is also not new on its own |
| Market streaming | https://github.com/athapar/market-streaming-platform | Kafka/Spark streaming, replay and reconciliation | Focus on bounded exact semantics over huge stack |

The differentiation goal is an **inspectable product of the engineering**, not a claim of first invention: a correct transactionally persisted state machine; deterministic multi-arrival replay, SQL-independent oracle, atomic recovery, and machine-readable incident evidence. The combination is still not guaranteed exclusive; public projects may share any portion of it.

## Relevance to hiring

Amazon's 2027 India new-grad description explicitly emphasizes coding and OOP, databases, ownership, resilient systems and testing. A strong backend project can show database and reliability capability, but **it cannot substitute for OA/DSA/CS fundamentals or guarantee shortlisting**.

Reference: https://www.amazon.jobs/en/jobs/10517895/software-development-engineer-intern-jan-2027-6-month-amazon-university-talent-acquisition

## Correctness sources

- PostgreSQL row-level locking and application consistency: https://www.postgresql.org/docs/current/applevel-consistency.html
- PostgreSQL `INSERT ... ON CONFLICT` race-safe uniqueness support: https://www.postgresql.org/docs/current/sql-insert.html
- Stripe's idempotency contract illustrates why same-key requests must be fingerprinted and replay responses need defined semantics: https://docs.stripe.com/api/idempotent_requests

## Do not confuse

- Exactly-once **database effect** inside one transactional Postgres database is not exactly-once network delivery or end-to-end distributed execution.
- Sequence continuity is not event-time completeness; OHLCV bars are provisional.
- An integrity checker that calls the same buggy reducer is not independent reconciliation.
- Fake p99, “10 million req/s”, 100% uptime, “production-grade”, unrun tests or a pretty dashboard are not evidence.
- ReplayProof's nominal 4–6 day scope is a target, not a guarantee. Correctness and learning may take longer.

## Should replace existing resume project only when

1. Working public repo with 30-second start and actual demo artifacts.
2. Real PostgreSQL-backed tests exercise duplicates, gaps, concurrent writes, timestamps and failure rollback.
3. Reconciliation detects injected corruption and an atomic rebuild repairs it.
4. Resume bullets reflect only implemented and verified behavior.
5. Owner can explain DB row locks, unique constraints, `READ COMMITTED`, transaction boundaries, indexes, retries, comparison oracle and performance tradeoffs independently.

## Conditional resume example — NOT for use yet

ReplayProof | Python, FastAPI, PostgreSQL, SQLAlchemy, Docker
- Designed a sequence-aware ingestion service with PostgreSQL-backed deduplication and durable gap buffering; atomically projected canonical source events into minute OHLCV bars under concurrent requests.
- Built an independent SQL reconciliation and replay workflow that detected injected projection corruption and restored matching state; verified correctness across randomized arrival orders and fault scenarios in [actual tests/run count].

**Remove or revise any phrase that has not been demonstrated.**
