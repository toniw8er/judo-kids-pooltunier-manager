$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$uvCommand = Get-Command uv -ErrorAction SilentlyContinue
$uvExecutable = if ($uvCommand) { $uvCommand.Source } else { Join-Path $projectRoot '.tools\uv\uv.exe' }
if (-not (Test-Path -LiteralPath $uvExecutable)) { throw 'uv fehlt. Bitte uv installieren: https://docs.astral.sh/uv/getting-started/installation/' }
$env:UV_CACHE_DIR = Join-Path $projectRoot '.uv-cache'
# Projektlokales TEMP vermeidet inkompatible umgeleitete Windows-Temppfade beim Paketbau.
$env:TEMP = Join-Path $env:UV_CACHE_DIR 'temp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
