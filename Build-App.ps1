param([string]$OutputDirectory = 'dist')

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$outputPath = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot $OutputDirectory))
if (-not $outputPath.StartsWith($PSScriptRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'Build-Ausgabe muss in einem Unterordner dieses Projekts liegen.'
}
. (Join-Path $PSScriptRoot 'scripts\Environment.ps1')
$packageName = 'PoolturnierManager'
$packagePath = [System.IO.Path]::GetFullPath((Join-Path $outputPath $packageName))
if (-not $packagePath.StartsWith($outputPath + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'Ungültiger Paketpfad.'
}
$runningPackage = Get-Process -Name $packageName -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -eq (Join-Path $packagePath "$packageName.exe") }
if ($runningPackage) {
    throw 'Die EXE in diesem Ausgabeordner läuft noch. Bitte die App schließen und den Build erneut starten.'
}
if (Test-Path -LiteralPath $packagePath) {
    # Windows PowerShell 5.1 ignoriert -Include zusammen mit -LiteralPath.
    $embeddedData = Get-ChildItem -LiteralPath $packagePath -File -Recurse -Force |
        Where-Object { $_.Extension -in '.sqlite3', '.db' }
    if ($embeddedData) {
        throw 'Im Paketordner liegen Wettkampfdaten. Bitte einen Ausgabeordner ohne Wettkampfdaten verwenden.'
    }
}
$workPath = [System.IO.Path]::GetFullPath((Join-Path (Join-Path $PSScriptRoot 'build') $packageName))
foreach ($generatedPath in @($packagePath, $workPath)) {
    if (-not $generatedPath.StartsWith($PSScriptRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw 'Buildpfad liegt außerhalb des Projekts.'
    }
    if (-not (Test-Path -LiteralPath $generatedPath)) { continue }
    # Übernommene Buildordner können auch schreibgeschützte Verzeichnisse enthalten.
    # Nur generierte Paket- und Zwischenordner vorbereiten.
    $packageItems = @(Get-Item -LiteralPath $generatedPath -Force) +
                    @(Get-ChildItem -LiteralPath $generatedPath -Force -Recurse)
    foreach ($item in $packageItems) {
        if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
            throw 'Der Buildordner enthält eine Verknüpfung. Bitte einen anderen Ausgabeordner wählen.'
        }
    }
    foreach ($item in $packageItems) {
        if ($item.Attributes -band [System.IO.FileAttributes]::ReadOnly) {
            $item.Attributes = $item.Attributes -band (-bnot [System.IO.FileAttributes]::ReadOnly)
        }
    }
}
# Fremde Programme im PATH können gleichnamige, inkompatible DLLs liefern (z. B. ICU).
# Mit sauberem Cache und auf die Laufzeit begrenztem PATH bündeln wir reproduzierbar.
$previousBuildPath = $env:PATH
$previousCachePath = $env:PYINSTALLER_CONFIG_DIR
$buildExitCode = 1
try {
    $env:PYINSTALLER_CONFIG_DIR = Join-Path $PSScriptRoot '.tools\pyinstaller-cache'
    $env:PATH = @((Join-Path $PSScriptRoot '.venv\Scripts'),
                  (Join-Path $env:SystemRoot 'System32'), $env:SystemRoot) -join [System.IO.Path]::PathSeparator
    & $uvExecutable run --locked --group build python -m PyInstaller --clean --noconfirm --onedir --windowed --name $packageName --collect-binaries ortools --distpath $outputPath --workpath build --specpath build --paths src scripts/entrypoint.py
    $buildExitCode = $LASTEXITCODE
}
finally {
    $env:PATH = $previousBuildPath
    $env:PYINSTALLER_CONFIG_DIR = $previousCachePath
}
if ($buildExitCode -ne 0) { exit $buildExitCode }
# Lizenztexte der tatsächlich verwendeten Pakete mit dem lokalen Testpaket ablegen.
$noticeFolder = Join-Path $packagePath 'Lizenztexte'
New-Item -ItemType Directory -Force -Path $noticeFolder | Out-Null
$packageFolders = Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot '.venv\Lib\site-packages') -Directory -Filter '*.dist-info'
foreach ($packageFolder in $packageFolders) {
    $files = Get-ChildItem -LiteralPath $packageFolder.FullName -File -Recurse | Where-Object { $_.Name -match '^(LICENSE|COPYING|NOTICE|METADATA)' }
    foreach ($file in $files) {
        $targetFolder = Join-Path $noticeFolder $packageFolder.Name
        New-Item -ItemType Directory -Force -Path $targetFolder | Out-Null
        Copy-Item -LiteralPath $file.FullName -Destination (Join-Path $targetFolder $file.Name) -Force
    }
}

