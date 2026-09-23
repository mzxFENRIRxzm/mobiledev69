param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('backend', 'frontend')]
    [string]$Mode,
    [string]$LanIp = ''
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot

if (-not $LanIp) {
    $probe = New-Object System.Net.Sockets.UdpClient
    try {
        # UDP Connect selects the OS routing interface without sending data.
        $probe.Connect('1.1.1.1', 65530)
        $LanIp = $probe.Client.LocalEndPoint.Address.IPAddressToString
    } finally {
        $probe.Dispose()
    }
}

if (-not $LanIp) {
    throw 'No LAN IPv4 address found. Pass one with -LanIp, for example 192.168.1.43.'
}

$frontendOrigin = "http://${LanIp}:50000"
$backendOrigin = "http://${LanIp}:8000"
Write-Host "THE_X LAN URL: $frontendOrigin" -ForegroundColor Green

if ($Mode -eq 'backend') {
    Set-Location (Join-Path $projectRoot 'backend')
    $env:PUBLIC_SIGNUP_ENABLED = 'true'
    $env:PYTHONUTF8 = '1'
    $env:DJANGO_ALLOWED_HOSTS = "localhost,127.0.0.1,$LanIp"
    $env:FRONTEND_ORIGINS = $frontendOrigin
    $env:FRONTEND_LOGIN_URL = "$frontendOrigin/login"
    $env:OIDC_SITE_URL = $backendOrigin
    & .\.venv\Scripts\python.exe manage.py bootstrap_dev
    if ($LASTEXITCODE -ne 0) { throw 'Could not configure the OIDC client for LAN access.' }
    & .\.venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000
    exit $LASTEXITCODE
}

Set-Location (Join-Path $projectRoot 'frontend')
& 'D:\flutter\bin\flutter.bat' build web --no-wasm-dry-run --no-web-resources-cdn `
    --dart-define="API_URL=$backendOrigin" `
    --dart-define="FRONTEND_URL=$frontendOrigin" `
    --dart-define="ALLOW_INSECURE_LAN_STORAGE=true"
if ($LASTEXITCODE -ne 0) { throw 'Flutter web build failed.' }
Set-Location $projectRoot
uv run --python 3.12 --no-project scripts/preview_web.py --host 0.0.0.0 --port 50000
