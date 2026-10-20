# Project map

```text
replayproof/
  static/         local dashboard, charts and guided API-backed replay scenario
  api.py          synchronous HTTP routes and development rebuild gate
  contracts.py    strict identities, UTC normalization and canonical fingerprints
  db.py           PostgreSQL engine/session boundary
  models.py       SQL constraints, canonical events, bars and audit records
  service.py      stream lock, prefix application, reducer and independent SQL oracle
  synthetic.py    seeded synthetic trade fixtures
  cli.py          executable forensic incident and evidence writer
  devtools.py     explicitly gated local corruption helper
  benchmark.py    HTTP measurements with SQL/count verification
migrations/       Alembic schema history
tests/            unit, transaction, process-race and reconciliation checks
scripts/          native start, Compose verification and durable-state snapshots
artifacts/        generated incident, checksums, tests and benchmark evidence
docs/             decisions, invariants, limitations, learning notes and run evidence
compose.yaml      PostgreSQL, migration job and two-worker API
Dockerfile        Python 3.12 image with cached pinned dependency layer
requirements.lock tested dependency versions
.github/workflows/ci.yml  PostgreSQL-backed lint/type/test job
```

Start with README, then trace api.event -> service.ingest. The stream lock and
transaction define the consistency boundary. A sequence gap changes storage but
does not affect bars. Reconciliation selects first/last trades independently in
SQL, compares exact minute fields and persists the evidence. Rebuild replaces
only the derived rows under the same lock.

Design decisions and index tradeoffs: ARCHITECTURE_DECISIONS.md. Falsifiable
contracts: INVARIANTS.md. Interview explanations and 15 questions: LEARNING_NOTES.md.
Measured workload and limits: BENCHMARK.md. Actual passed/not-run split:
VERIFICATION.md. Resume bullets in README describe the implemented local work;
they make no public adoption, remote CI or production claims.
