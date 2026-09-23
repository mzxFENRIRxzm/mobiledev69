param(
    [string]$NgrokPath = 'ngrok',
    [int]$GatewayPort = 5050,
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 50000,
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

function Find-FreePort([int]$preferred, [int[]]$reserved) {
    for ($candidate = $preferred; $candidate -lt [Math]::Min($preferred + 100, 65536); $candidate++) {
        if ($candidate -in $reserved) { continue }
        $listeners = Get-NetTCPConnection -State Listen -LocalPort $candidate -ErrorAction SilentlyContinue
        if ($listeners) { continue }
        $probe = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $candidate)
        try {
            $probe.Start()
            return $candidate
        } catch [System.Net.Sockets.SocketException] {
            continue
        } finally {
            $probe.Stop()
        }
    }
    throw "No free local port found from $preferred through $([Math]::Min($preferred + 99, 65535))."
}

$gatewayBusy = Get-NetTCPConnection -State Listen -LocalPort $GatewayPort -ErrorAction SilentlyContinue
if ($gatewayBusy) {
    $details = ($gatewayBusy | Select-Object LocalPort,OwningProcess | Format-Table -AutoSize | Out-String).Trim()
    throw "Gateway port $GatewayPort is already in use. Choose another with -GatewayPort.`n$details"
}
# A terminated PowerShell host can leave the Store edition of ngrok running.
# Its old tunnel cannot serve traffic when this gateway port is vacant.
$staleNgrok = @(Get-CimInstance Win32_Process -Filter "Name = 'ngrok.exe'" |
    Where-Object { $_.CommandLine -like "*http http://127.0.0.1:$GatewayPort*" })
foreach ($process in $staleNgrok) {
    Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
}
if ($staleNgrok.Count -gt 0) { Write-Host "Closed $($staleNgrok.Count) stale ngrok tunnel(s) on port $GatewayPort." }
$BackendPort = Find-FreePort $BackendPort @($GatewayPort)
$FrontendPort = Find-FreePort $FrontendPort @($GatewayPort, $BackendPort)
Write-Host "THE_X local ports: backend $BackendPort, preview $FrontendPort, gateway $GatewayPort"

$ngrokCommand = Get-Command $NgrokPath -ErrorAction Stop
$ngrokExecutable = $ngrokCommand.Source
# The Microsoft Store command alias starts a launcher, whose child can outlive Ctrl+C.
if ($ngrokExecutable -like '*\Microsoft\WindowsApps\ngrok.exe') {
    $ngrokPackage = Get-AppxPackage -Name ngrok.ngrok -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($ngrokPackage) {
        $installedExecutable = Join-Path $ngrokPackage.InstallLocation 'ngrok.exe'
        if (Test-Path $installedExecutable) { $ngrokExecutable = $installedExecutable }
    }
}
$ngrokProcess = $null
$ngrokWorkerIds = @()
$existingNgrokIds = @(Get-CimInstance Win32_Process -Filter "Name = 'ngrok.exe'" |
    Select-Object -ExpandProperty ProcessId)
$children = @()
try {
    $ngrokProcess = Start-Process -FilePath $ngrokExecutable `
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
    # Store installations can create another ngrok.exe even when started by
    # its installed executable. Track that process as well as Start-Process's PID.
    $ngrokWorkerIds = @(Get-CimInstance Win32_Process -Filter "Name = 'ngrok.exe'" |
        Where-Object { $_.ProcessId -notin $existingNgrokIds -and
            $_.CommandLine -like "*http http://127.0.0.1:$GatewayPort*" } |
        Select-Object -ExpandProperty ProcessId)

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
        & $python manage.py collectstatic --noinput --clear --verbosity 0
        if ($LASTEXITCODE -ne 0) { throw 'Django collectstatic failed.' }
    } finally { Pop-Location }

    $backend = Start-Process -FilePath $python `
        -ArgumentList @('manage.py','runserver',"127.0.0.1:$BackendPort",'--noreload') `
        -WorkingDirectory $backendRoot `
        -RedirectStandardOutput (Join-Path $logRoot 'tunnel-backend.out.log') `
        -RedirectStandardError (Join-Path $logRoot 'tunnel-backend.err.log') `
        -WindowStyle Hidden -PassThru
    $children += $backend

    $preview = Start-Process -FilePath $python `
        -ArgumentList @((Join-Path $projectRoot 'scripts\preview_web.py'),'--host','127.0.0.1','--port',"$FrontendPort") `
        -WorkingDirectory $projectRoot `
        -RedirectStandardOutput (Join-Path $logRoot 'tunnel-preview.out.log') `
        -RedirectStandardError (Join-Path $logRoot 'tunnel-preview.err.log') `
        -WindowStyle Hidden -PassThru
    $children += $preview

    $gatewayArgs = @((Join-Path $projectRoot 'scripts\tunnel_gateway.py'),
        '--port', "$GatewayPort", '--backend-port', "$BackendPort", '--frontend-port', "$FrontendPort")
    if ($ExposeDjangoAdmin) { $gatewayArgs += '--expose-django-admin' }
    $gateway = Start-Process -FilePath $python -ArgumentList $gatewayArgs `
        -WorkingDirectory $projectRoot `
        -RedirectStandardOutput (Join-Path $logRoot 'tunnel-gateway.out.log') `
        -RedirectStandardError (Join-Path $logRoot 'tunnel-gateway.err.log') `
        -WindowStyle Hidden -PassThru
    $children += $gateway

    $health = $null
    $discovery = $null
    $expectedIssuer = "$publicOrigin/openid"
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Milliseconds 500
        if ($children | Where-Object HasExited) { throw 'A THE_X local service stopped during startup.' }
        try {
            $health = Invoke-WebRequest "http://127.0.0.1:$GatewayPort/login" `
                -Headers @{ Host = $publicUri.Host } -TimeoutSec 2 -UseBasicParsing
            $discovery = Invoke-RestMethod "http://127.0.0.1:$GatewayPort/openid/.well-known/openid-configuration" `
                -Headers @{ Host = $publicUri.Host } -TimeoutSec 2
            if ($health.StatusCode -eq 200 -and $discovery.issuer -eq $expectedIssuer) { break }
        } catch { }
    }
    if (-not $health -or $health.StatusCode -ne 200 -or $discovery.issuer -ne $expectedIssuer) {
        throw "THE_X gateway or OIDC provider did not become ready. Expected issuer: $expectedIssuer; received: $($discovery.issuer). Check .local/tunnel-*.log."
    }

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
    $ngrokWorkerIds += @(Get-CimInstance Win32_Process -Filter "Name = 'ngrok.exe'" |
        Where-Object { $_.ProcessId -notin $existingNgrokIds -and
            $_.CommandLine -like "*http http://127.0.0.1:$GatewayPort*" } |
        Select-Object -ExpandProperty ProcessId)
    $serviceIdsToStop = @(@($children) + @($ngrokProcess) |
        Where-Object { $_ } | ForEach-Object Id) + $ngrokWorkerIds
    foreach ($serviceId in ($serviceIdsToStop | Select-Object -Unique)) {
        & taskkill.exe /PID $serviceId /T /F 2>$null | Out-Null
    }
}
