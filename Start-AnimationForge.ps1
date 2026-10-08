param([int]$Port = 8794, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$repoRoot = $PSScriptRoot
$pythonExe = Join-Path $repoRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) { $pythonExe = (Get-Command python).Source }
& $pythonExe -c "import numpy, PIL"
if ($LASTEXITCODE -ne 0) { throw 'Animation Forge needs NumPy and Pillow in its Python environment. See docs/animation-forge.md.' }
$url = "http://127.0.0.1:$Port"
$running = $null
try { $running = Invoke-RestMethod "$url/api/health" -TimeoutSec 2 } catch { }
if ($running) {
    if ($running.app -ne 'other-animation-forge' -or [IO.Path]::GetFullPath($running.repo) -ne [IO.Path]::GetFullPath($repoRoot)) { throw "Port $Port is occupied by a different application." }
} else {
    if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) { throw "Port $Port is occupied. Choose another -Port." }
    $logDir = Join-Path $repoRoot '.forge/animation-forge'
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    $process = Start-Process -FilePath $pythonExe -ArgumentList @('"' + (Join-Path $repoRoot 'tools/animation_forge.py') + '"', '--port', $Port) -WorkingDirectory $repoRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDir 'server.log') -RedirectStandardError (Join-Path $logDir 'server-error.log') -PassThru
    Set-Content -LiteralPath (Join-Path $logDir 'server.pid') -Value $process.Id
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Milliseconds 300
        try { $running = Invoke-RestMethod "$url/api/health" -TimeoutSec 1; break } catch { }
        if ($process.HasExited) { throw "Server exited. Inspect $logDir/server-error.log" }
    }
    if (-not $running) { throw "Server did not become ready. Inspect $logDir/server-error.log" }
}
Write-Output "Animation Forge: $url"
if (-not $NoBrowser) { Start-Process $url }
