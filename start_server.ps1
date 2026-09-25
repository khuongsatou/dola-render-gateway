$ErrorActionPreference = "Continue"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

$out = Join-Path $scriptDir 'server.log'
$err = Join-Path $scriptDir 'server.err.log'

Write-Host "Starting Dola Pool server..." -ForegroundColor Cyan

if (Test-Path $out) { Remove-Item $out -Force -ErrorAction SilentlyContinue }
if (Test-Path $err) { Remove-Item $err -Force -ErrorAction SilentlyContinue }

$hostAddr = if ($env:DOLA_HOST) { $env:DOLA_HOST } else { '0.0.0.0' }
$portAddr = if ($env:DOLA_PORT) { $env:DOLA_PORT } else { '8000' }

Start-Process -FilePath 'py.exe' -ArgumentList '-3','-m','uvicorn','server:app','--host',$hostAddr,'--port',$portAddr -WorkingDirectory $scriptDir -RedirectStandardOutput $out -RedirectStandardError $err -WindowStyle Normal

Start-Sleep -Seconds 3
Write-Host "Server running at http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "Admin dashboard available at http://127.0.0.1:8000/web" -ForegroundColor Yellow
