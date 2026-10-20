# Executed exploratory benchmarks

Native Windows 11 build 26100, AMD Ryzen 7 5800U (8 cores/16 threads),
16,442,789,888 bytes RAM, Python 3.12.14, PostgreSQL 16.15, two API workers,
HTTP concurrency 8, seed 2027. Same-host loopback HTTP/database. New streams
inside an existing migrated database, warmed connections; no controlled disk/cache
preconditioning. Hardware obtained with Windows CIM. Storage type not captured.

| Events per stream | Streams | Submission | events/s | p50 ms | p95 ms | p99 ms |
| --- | --- | --- | --- | --- | --- | --- |
| 1000 | 1 | ordered | 54.76 | 137.93 | 295.38 | 382.94 |
| 1000 | 1 | shuffled | 42.35 | 184.04 | 320.98 | 358.47 |
| 250 | 4 | ordered | 113.35 | 70.81 | 105.32 | 151.44 |
| 250 | 4 | shuffled | 136.77 | 52.26 | 114.81 | 157.77 |

All four runs: zero HTTP errors/conflicts; source counts and cursor verified,
independent SQL reconciliation matched, equal final digests within each workload.
Raw samples/reports: artifacts/benchmark-single-stream.json and
artifacts/benchmark-four-streams.json. Metrics measure full HTTP requests, not
isolated DB commit time. Ordered means submission order; concurrent arrival order
is not guaranteed.

These are single exploratory runs, not controlled scaling comparisons: per-stream
history differs, execution order warms caches and background laptop activity is
uncontrolled. Row-lock contention and repeated historical aggregation are explicit
design costs; measurements do not isolate their individual contributions.

Reproduce with the API running and DATABASE_URL pointing to its database:

    python -m replayproof.benchmark --count 1000 --streams 1 --concurrency 8 --api-workers 2 --url http://127.0.0.1:8000 --output artifacts/benchmark-single-stream.json
    python -m replayproof.benchmark --count 250 --streams 4 --concurrency 8 --api-workers 2 --url http://127.0.0.1:8000 --output artifacts/benchmark-four-streams.json

For a stronger study (NOT RUN), use equal 1000-event per-stream histories, 1/8
streams, concurrency 1/8, three repeats and seeds 2027–2029; record disk/cache state
and report variability. DB commit duration is not instrumented.
