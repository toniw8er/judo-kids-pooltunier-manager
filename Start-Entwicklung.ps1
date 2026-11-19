param(
    [ValidateSet(10, 40, 100)][int]$Kinder = 40,
    [ValidateRange(1917, 2099)][int]$Jahr = 2026,
    [switch]$Neu
)
. (Join-Path $PSScriptRoot 'scripts\Environment.ps1')
$demoArguments = @('--count', "$Kinder", '--year', "$Jahr")
if ($Neu) { $demoArguments += '--fresh' }
& $uvExecutable run --locked python -m devtools.run @demoArguments
exit $LASTEXITCODE
