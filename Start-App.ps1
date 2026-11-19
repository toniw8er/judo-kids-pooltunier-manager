. (Join-Path $PSScriptRoot 'scripts\Environment.ps1')
& $uvExecutable run --locked python -m stadtmeisterschaft @args
exit $LASTEXITCODE
