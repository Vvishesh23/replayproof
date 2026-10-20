# Run from a terminal with access to Docker Desktop. Creates isolated test streams.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
$dockerExe = if ($dockerCommand) { $dockerCommand.Source } else { "$env:ProgramFiles\Docker\Docker\resources\bin\docker.exe" }
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $pythonExe)) { throw 'Set up the local .venv first (README).' }
$evidenceDir = Join-Path $projectRoot 'artifacts\docker-verification'
New-Item -ItemType Directory -Force $evidenceDir | Out-Null

function Invoke-Compose {
    param([string[]]$DockerArgs)
    & $dockerExe compose @DockerArgs
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose failed: $DockerArgs" }
}
function Wait-Api {
    $lastFailure = 'No readiness response'
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        try {
            $health = Invoke-RestMethod 'http://127.0.0.1:8000/health/ready' -TimeoutSec 2
            if ($health.status -eq 'ready') { return }
        } catch { $lastFailure = $_.Exception.Message }
        Start-Sleep -Seconds 1
    }
    throw "API readiness timeout: $lastFailure"
}

$env:REPLAYPROOF_DEV_REBUILD = '1'
Invoke-Compose @('up', '--build', '-d')
Wait-Api
Invoke-Compose @('exec', '-T', 'api', 'ruff', 'check', '.')
Invoke-Compose @('exec', '-T', 'api', 'mypy', 'replayproof')
Invoke-Compose @('exec', '-T', 'api', 'alembic', 'check')
Invoke-Compose @('exec', '-T', '-e', 'REPLAYPROOF_TEST_DATABASE=1', 'api', 'pytest', '-q') |
    Tee-Object -FilePath "$evidenceDir\pytest.txt"
Invoke-Compose @('exec', '-T', 'api', 'python', '-m', 'replayproof.cli', 'demo', '--seed', '2027', '--output', 'artifacts/docker-demo') |
    Tee-Object -FilePath "$evidenceDir\demo-transcript.txt"
Invoke-Compose @('cp', 'api:/app/artifacts/docker-demo', 'artifacts/')
$env:DATABASE_URL = 'postgresql+psycopg://replay:localonly@127.0.0.1:5432/replay'
& $pythonExe scripts/verify_durability.py capture --incident artifacts/docker-demo/incident.json --output-dir artifacts/docker-verification
if ($LASTEXITCODE -ne 0) { throw 'Durability capture failed' }
Invoke-Compose @('stop', 'api', 'db')
Invoke-Compose @('up', '-d')
Wait-Api
& $pythonExe scripts/verify_durability.py verify --incident artifacts/docker-demo/incident.json --output-dir artifacts/docker-verification
if ($LASTEXITCODE -ne 0) { throw 'Durability comparison failed' }
$env:REPLAYPROOF_DEV_REBUILD = '0'
Invoke-Compose @('up', '-d', '--force-recreate', 'api')
Wait-Api
$streamId = (Get-Content -Raw artifacts/docker-demo/incident.json | ConvertFrom-Json).stream_ids[0]
& $pythonExe -c "import httpx,sys; r=httpx.post('http://127.0.0.1:8000/v1/streams/'+sys.argv[1]+'/rebuild'); assert r.status_code == 404, r.text; print('PASS: dev rebuild inaccessible when disabled')" $streamId
if ($LASTEXITCODE -ne 0) { throw 'Disabled rebuild gate failed' }
Invoke-Compose @('ps', '--all')
Write-Output 'PASS: Compose build, migration, checks, tests, incident and durable restart. Rebuild disabled.'
