$ErrorActionPreference = 'Stop'

$RepoZipUrl = 'https://github.com/superagenta110y/hood-link/archive/refs/heads/main.zip'
$InstallDir = Join-Path $env:USERPROFILE '.hoodlink'
$ZipPath = Join-Path $env:TEMP 'hood-link-main.zip'

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

Write-Host 'Downloading HoodLink...'
Invoke-WebRequest -Uri $RepoZipUrl -OutFile $ZipPath

$WorkDir = Join-Path $InstallDir 'hood-link-main'
if (Test-Path $WorkDir) {
  $listener = Get-NetTCPConnection -LocalPort 7878 -ErrorAction SilentlyContinue
  if ($listener) { Stop-Process -Id $listener.OwningProcess -Force -ErrorAction SilentlyContinue }
  Start-Sleep -Seconds 1
  Remove-Item -Recurse -Force $WorkDir
}
Expand-Archive -Path $ZipPath -DestinationPath $InstallDir -Force
Remove-Item $ZipPath -Force

$ServerDir = Join-Path $WorkDir 'server'
Set-Location $ServerDir

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  Write-Host 'Installing uv...'
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  $env:PATH = "$env:USERPROFILE\.local\bin;$env:PATH"
}

uv sync
Start-Process -FilePath 'uv' -ArgumentList @('run','uvicorn','hoodlink.main:app','--host','127.0.0.1','--port','7878')

$ExtensionDir = Join-Path $WorkDir 'extension'
Write-Host ""
Write-Host "HoodLink started."
Write-Host "  Dashboard : http://127.0.0.1:7878"
Write-Host "  Extension : $ExtensionDir"
Write-Host ""
Write-Host "To install the Chrome extension: open chrome://extensions/, enable Developer mode,"
Write-Host "then click 'Load unpacked' and select the extension folder above."
Write-Host ""
