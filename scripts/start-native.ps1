param([switch]$DevRebuild, [switch]$NoApi)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pgBin = Join-Path $projectRoot '.tools\postgresql\pgsql\bin'
$pgData = Join-Path $projectRoot '.tools\pgdata'
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath "$pgBin\pg_ctl.exe")) {
    throw 'Extract official PostgreSQL 16 Windows binaries under .tools\postgresql first. See README.'
}
if (!(Test-Path -LiteralPath $pythonExe)) {
    throw 'Create .venv and install requirements.lock plus the package first. See README.'
}
if (!(Test-Path -LiteralPath "$pgData\PG_VERSION")) {
    $passwordFile = Join-Path $projectRoot '.tools\pg-password.txt'
    Set-Content -LiteralPath $passwordFile -Value 'localonly' -NoNewline
    & "$pgBin\initdb.exe" -D $pgData -U replay "--pwfile=$passwordFile" --auth=scram-sha-256 --encoding=UTF8 --locale=C
    if ($LASTEXITCODE -ne 0) { throw 'initdb failed' }
}
& "$pgBin\pg_isready.exe" -h 127.0.0.1 -p 55432 -U replay
if ($LASTEXITCODE -ne 0) {
    & "$pgBin\pg_ctl.exe" -D $pgData -l "$projectRoot\.tools\postgres.log" -o '-h 127.0.0.1 -p 55432' -w start
    if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL start failed' }
}
$env:PGPASSWORD = 'localonly'
$existingDatabase = & "$pgBin\psql.exe" -h 127.0.0.1 -p 55432 -U replay -d postgres -At -c "SELECT 1 FROM pg_database WHERE datname='replay'"
if ($LASTEXITCODE -ne 0) { throw 'Database connection failed' }
if ($existingDatabase -ne '1') {
    & "$pgBin\createdb.exe" -h 127.0.0.1 -p 55432 -U replay replay
    if ($LASTEXITCODE -ne 0) { throw 'Database creation failed' }
}
$env:DATABASE_URL = 'postgresql+psycopg://replay:localonly@127.0.0.1:55432/replay'
$env:REPLAYPROOF_DEV_REBUILD = if ($DevRebuild) { '1' } else { '0' }
& $pythonExe -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Migration failed' }
if (!$NoApi) {
    & $pythonExe -m uvicorn replayproof.api:app --host 127.0.0.1 --port 8000 --workers 2
}
