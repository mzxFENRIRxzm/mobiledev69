param(
    [string]$NgrokPath = 'ngrok',
    [int]$GatewayPort = 5050,
    [switch]$ExposeDjangoAdmin,
    [switch]$SkipBuild
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $projectRoot 'backend'
$python = Join-Path $backendRoot '.venv\Scripts\python.exe'
$flutter = 'D:\flutter\bin\flutter.bat'
$logRoot = Join-Path $projectRoot '.local'

if (-not (Test-Path $python)) { throw "Backend Python was not found: $python" }
if (-not (Test-Path $flutter)) { throw "Flutter SDK was not found: $flutter" }
New-Item -ItemType Directory -Force -Path $logRoot | Out-Null

$busy = Get-NetTCPConnection -State Listen -LocalPort 8000,50000,$GatewayPort -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalAddress -in @('127.0.0.1','0.0.0.0') }
if ($busy) {
    $details = ($busy | Select-Object LocalPort,OwningProcess | Format-Table -AutoSize | Out-String).Trim()
    throw "THE_X or ngrok ports are already in use. Stop those processes first.`n$details"
}

$ngrokCommand = Get-Command $NgrokPath -ErrorAction Stop
$ngrokProcess = $null
$children = @()
try {
    $ngrokProcess = Start-Process -FilePath $ngrokCommand.Source `
        -ArgumentList @('http', "http://127.0.0.1:$GatewayPort") `
        -RedirectStandardOutput (Join-Path $logRoot 'tunnel-ngrok.out.log') `
        -RedirectStandardError (Join-Path $logRoot 'tunnel-ngrok.err.log') `
        -WindowStyle Hidden -PassThru

    $publicOrigin = $null
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        Start-Sleep -Milliseconds 500
        if ($ngrokProcess.HasExited) { throw 'ngrok stopped before creating a public endpoint.' }
        try {
            $tunnels = (Invoke-RestMethod 'http://127.0.0.1:4040/api/tunnels' -TimeoutSec 2).tunnels
            $publicOrigin = ($tunnels | Where-Object { $_.public_url -like 'https://*' } |
                Select-Object -First 1).public_url
            if ($publicOrigin) { break }
        } catch { }
    }
    if (-not $publicOrigin) { throw 'ngrok did not provide an HTTPS endpoint within 20 seconds.' }

    $publicUri = [Uri]$publicOrigin
    $env:PYTHONUTF8 = '1'
    $env:PUBLIC_SIGNUP_ENABLED = 'true'
    $env:DEMO_EMAIL_VERIFICATION_LINK = 'true'
    $env:DJANGO_EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    $env:DJANGO_ALLOWED_HOSTS = "localhost,127.0.0.1,$($publicUri.Host)"
    $env:FRONTEND_ORIGINS = $publicOrigin
    $env:FRONTEND_LOGIN_URL = "$publicOrigin/login"
    $env:OIDC_SITE_URL = $publicOrigin
    $env:TRUST_PROXY_HEADERS = 'true'

    if (-not $SkipBuild) {
        Push-Location (Join-Path $projectRoot 'frontend')
        try {
            & $flutter build web --no-wasm-dry-run --no-web-resources-cdn `
                --dart-define="API_URL=$publicOrigin" `
                --dart-define="FRONTEND_URL=$publicOrigin"
            if ($LASTEXITCODE -ne 0) { throw 'Flutter web build failed.' }
        } finally { Pop-Location }
    }

    Push-Location $backendRoot
    try {
        # bootstrap_dev only configures local demo fixtures while DEBUG is true.
        $env:DJANGO_DEBUG = 'true'
        & $python manage.py bootstrap_dev
        if ($LASTEXITCODE -ne 0) { throw 'Could not configure the OIDC client.' }
        $env:DJANGO_DEBUG = 'false'
        & $python manage.py collectstatic --noinput --clear
        if ($LASTEXITCODE -ne 0) { throw 'Django collectstatic failed.' }
    } finally { Pop-Location }

    $backend = Start-Process -FilePath $python `
        -ArgumentList @('manage.py','runserver','127.0.0.1:8000','--noreload') `
        -WorkingDirectory $backendRoot `
        -RedirectStandardOutput (Join-Path $logRoot 'tunnel-backend.out.log') `
        -RedirectStandardError (Join-Path $logRoot 'tunnel-backend.err.log') `
        -WindowStyle Hidden -PassThru
    $children += $backend

    $preview = Start-Process -FilePath $python `
        -ArgumentList @((Join-Path $projectRoot 'scripts\preview_web.py'),'--host','127.0.0.1','--port','50000') `
        -WorkingDirectory $projectRoot `
        -RedirectStandardOutput (Join-Path $logRoot 'tunnel-preview.out.log') `
        -RedirectStandardError (Join-Path $logRoot 'tunnel-preview.err.log') `
        -WindowStyle Hidden -PassThru
    $children += $preview

    $gatewayArgs = @((Join-Path $projectRoot 'scripts\tunnel_gateway.py'), '--port', "$GatewayPort")
    if ($ExposeDjangoAdmin) { $gatewayArgs += '--expose-django-admin' }
    $gateway = Start-Process -FilePath $python -ArgumentList $gatewayArgs `
        -WorkingDirectory $projectRoot `
        -RedirectStandardOutput (Join-Path $logRoot 'tunnel-gateway.out.log') `
        -RedirectStandardError (Join-Path $logRoot 'tunnel-gateway.err.log') `
        -WindowStyle Hidden -PassThru
    $children += $gateway

    $health = $null
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Milliseconds 500
        if ($children | Where-Object HasExited) { throw 'A THE_X local service stopped during startup.' }
        try {
            $health = Invoke-WebRequest "http://127.0.0.1:$GatewayPort/login" `
                -Headers @{ Host = $publicUri.Host } -TimeoutSec 2 -UseBasicParsing
            if ($health.StatusCode -eq 200) { break }
        } catch { }
    }
    if (-not $health -or $health.StatusCode -ne 200) { throw 'THE_X gateway did not become ready.' }

    Write-Host ''
    Write-Host "THE_X public URL: $publicOrigin" -ForegroundColor Green
    Write-Host 'Anyone with this URL can open the app without using the same Wi-Fi.'
    Write-Host 'Press Ctrl+C to close the public tunnel and all local services.' -ForegroundColor Yellow
    if (-not $ExposeDjangoAdmin) {
        Write-Host 'Django Admin is blocked on the public tunnel. Flutter /admin remains available.'
    }

    while ($true) {
        Start-Sleep -Seconds 1
        if ($ngrokProcess.HasExited -or ($children | Where-Object HasExited)) {
            throw 'ngrok or a THE_X local service stopped unexpectedly. Check .local/tunnel-*.log.'
        }
    }
} finally {
    foreach ($process in @($children) + @($ngrokProcess)) {
        if ($process -and -not $process.HasExited) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        }
    }
}
