# ReplayProof

Synthetic trade ingestion with durable gap buffering, transactional minute bars,
and an independent SQL reconciliation oracle. Verified natively on Windows and in
Docker against PostgreSQL 16.15: 24 tests, multi-process races, a two-worker HTTP
demo and durable restart.
See [actual check status](docs/VERIFICATION.md). No real feeds or trading logic.

With Docker Desktop running, start the project from this directory:

```powershell
docker compose up --build -d
```

Open the [ReplayProof dashboard](http://127.0.0.1:8000/).
The [interactive API documentation](http://127.0.0.1:8000/docs) remains available.
The source map and interview reading order are in [PROJECT_GUIDE.md](docs/PROJECT_GUIDE.md).

## Present the project

The dashboard is served by FastAPI itself, with no separate frontend service,
package manager, CDN, or external font dependency. It reads live PostgreSQL state.

- **Overview:** canonical-event counts, contiguous cursor, gap map, provisional
  candlestick/close-price charts and the latest independent SQL comparison.
- **Event explorer:** paginated source records, payload fingerprints, applied vs.
  buffered state, and filtering within the loaded page.
- **Reconciliation:** persisted comparison history, exact field differences, full
  checksums and JSON export.
- **Architecture:** a concise explanation of the transaction boundary and oracle.

Click **Run replay demo**, then **Start live demonstration**. A fresh `RPL_USD`
session applies sequences 1–16 and deliberately withholds 17. At the checkpoint,
95 records are stored, the cursor stays at 16, and 79 events remain buffered.
Choose **Inspect the gap on the dashboard** to show this state. Then choose
**Continue recovery → Recover sequence 17**. The walkthrough tests duplicate and
conflicting retries, applies all 96 events and reconciles 24 minute buckets.
All requests go through the normal API; existing streams stay intact. Browser
reload during the pause leaves the durable buffered session available for inspection.

The frontend creates no corruption endpoint and never enables development rebuild.
Its seeded scenario is separate from the CLI's original 40-event corruption demo.
Read-only stream/event/history endpoints are bounded. Charts display up to 60
retrieved minute buckets from the requested window; bars remain provisional.

![ReplayProof dashboard](artifacts/frontend/dashboard.png)

```mermaid
flowchart LR
    CLI[Seeded CLI / HTTP clients] --> API[FastAPI workers]
    API --> LOCK[PostgreSQL stream row lock]
    LOCK --> EVENTS[Immutable canonical events]
    LOCK --> PREFIX[Contiguous sequence cursor]
    PREFIX --> BARS[Provisional UTC minute bars]
    EVENTS --> SQL[Independent SQL oracle]
    BARS --> SQL
    SQL --> REPORT[Persisted diffs and digest]
```

## Native Windows start (verified)

Download the Windows x64 ZIP from [EDB's official PostgreSQL binaries page](https://www.enterprisedb.com/download-postgresql-binaries),
then extract it so `.tools\postgresql\pgsql\bin\postgres.exe` exists. This workspace
already has that extraction and a configured `.venv`. No Windows service, WSL or
Docker installation is required. Files stay under the ignored `.tools` directory.

For a fresh workspace, prepare Python 3.12 and run:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.lock
pip install --no-deps -e .
.\scripts\start-native.ps1 -DevRebuild
```

The last command starts PostgreSQL on loopback port 55432, migrates and starts two
API workers. API docs: http://127.0.0.1:8000/docs. In a second project terminal:

```powershell
$env:DATABASE_URL='postgresql+psycopg://replay:localonly@127.0.0.1:55432/replay'
$env:REPLAYPROOF_DEV_REBUILD='1'
.venv\Scripts\python.exe -m replayproof.cli demo --seed 2027
$env:REPLAYPROOF_TEST_DATABASE='1'
.venv\Scripts\python.exe -m pytest -q
```

Stop API with Ctrl+C. Stop only this database with
`.tools\postgresql\pgsql\bin\pg_ctl.exe -D .tools\pgdata -m fast -w stop`.
Its data persists. Local-only credentials are `replay` / `localonly`.

## Docker Compose start (verified)

Requires Docker Desktop with Linux containers and Compose. Host Python is optional
for this route. Credentials below are local-only. Run one API setup at a time;
both native and Docker examples use port 8000.

```powershell
docker compose up --build -d
docker compose exec -T -e REPLAYPROOF_TEST_DATABASE=1 api pytest -q
```

API docs: http://localhost:8000/docs. Compose applies migrations before starting
two API workers; PostgreSQL persists data in a named volume. Restart with
`docker compose restart api`; `docker compose down` preserves the database.

For the deliberate local incident demo, enable rebuild for both API and CLI:

```powershell
$env:REPLAYPROOF_DEV_REBUILD='1'
docker compose up -d --force-recreate api
docker compose exec -T api python -m replayproof.cli demo --seed 2027 --output artifacts/docker-demo
docker compose cp api:/app/artifacts/docker-demo artifacts/
$env:REPLAYPROOF_DEV_REBUILD='0'
docker compose up -d --force-recreate api
```

The CLI uses the same database as the API. It corrupts one bar directly through a
gated local helper; there is no corruption HTTP endpoint. Generated native evidence
is in `artifacts/demo/`, and Docker evidence in `artifacts/docker-demo/`. Both runs
produce the same final hashes. Native uses database port 55432; Compose uses 5432.

For the complete repeatable check, including restart and source/hash comparison,
run `.\scripts\verify-compose.ps1` with the local `.venv` prepared. It retains test
and incident output, restarts this project's containers and leaves rebuild disabled.

## Verification

Use a disposable database: tests create isolated stream IDs and retain evidence.

```powershell
alembic upgrade head
$env:REPLAYPROOF_TEST_DATABASE='1'
pytest -q
ruff check .
mypy replayproof
```

CI supplies PostgreSQL 16 and runs these commands. Tests use separate connections
via concurrent requests. A separate two-worker HTTP demo exercises process-shared
locking. A four-process integration test also verified one canonical event and
seven duplicate responses from independent interpreter/database pools.
The same lint/type/test gates passed inside Docker. Remote GitHub Actions has not
been run because this workspace has not been published to a GitHub repository.

## API example

Create with `POST /v1/streams` and `{"symbol":"SYNTH"}`. Submit to
`POST /v1/streams/{id}/events`:

```json
{"sequence":1,"source_event_id":"s-1","event_time":"2027-01-01T00:00:00Z","price_ticks":10001,"quantity":2,"schema_version":1}
```

Status returns cursor, highest seen, buffered count and bounded-by-high-watermark
gap ranges. Bars require aware `start` and `end`, at most 31 days; use `limit` and
`offset` pagination. Price scale is 10000. Open/close use (event_time, sequence).
Identical retries return `duplicate`; identity conflicts return 409 with a durable
audit entry. Reconciliation creates a stored report; report responses cap diffs
at 100 while persisted evidence retains the full list.

## Guarantees and limits

Source insert, cursor advancement and touched bars share one transaction and stream
row lock. A gap blocks projection until the normal ingest path fills it. An error
rolls back all changes. A committed request whose response is lost deduplicates on
retry. Reconciliation and rebuild serialize with ingest for a coherent comparison.

Five principal limits: hot streams serialize; recomputation and gap scans grow with
history; missing source events need external recovery; bars never become final;
there is no authentication or external truth source. Integer aggregate overflow
fails and rolls back rather than silently wrapping. Rebuild is denied by default.
Do not expose this local demo to the internet. See architecture and learning notes.

See [measured benchmark results](docs/BENCHMARK.md), the generated
[incident narrative](artifacts/demo/incident.md),
[before/after evidence](artifacts/demo/reconciliation_before.json), and
[matching replay hashes](artifacts/demo/digest_comparison.json).

## Five-minute interview walkthrough

Explain sequence 1,2,4 arriving and cursor stopping at 2; show the locked ingestion
transaction; explain historical event-time recomputation; contrast Python reducer
with SQL window oracle; then show generated incident diffs and repaired digest.
Be able to explain why retry safety is a database effect, not network delivery.

Resume bullets limited to the locally executed implementation and checks:

- Implemented PostgreSQL-serialized synthetic event ingestion with identity
  fingerprinting, durable gap buffering and atomic provisional OHLCV projections.
- Verified randomized replay and injected projection failures against an independent
  SQL oracle, producing reproducible reconciliation and repair evidence.
