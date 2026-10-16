$ErrorActionPreference = 'Stop'
if (-not $env:RUNNER_TEMP) { throw 'Run installer lifecycle tests on the disposable CI Windows runner.' }
$testRoot = Join-Path $env:RUNNER_TEMP 'quiet-pages-installer-test'
$target = Join-Path $testRoot 'app'
$env:QUIET_PAGES_DATA = Join-Path $testRoot 'data'
New-Item -ItemType Directory -Force -Path $testRoot, $env:QUIET_PAGES_DATA | Out-Null
$process = Start-Process -FilePath 'dist/QuietPages-Setup-Windows-x64.exe' -ArgumentList @('/S', "/D=$target") -WindowStyle Hidden -Wait -PassThru
if ($process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath "$target/QuietPages.exe")) { throw 'Installer failed' }
$shortcut = Join-Path ([Environment]::GetFolderPath('StartMenu')) 'Programs/Talevoxa/Talevoxa.lnk'
if (-not (Test-Path -LiteralPath $shortcut)) { throw 'Start menu shortcut missing' }
if (-not (Test-Path 'HKCU:/Software/Microsoft/Windows/CurrentVersion/Uninstall/QuietPages')) { throw 'Uninstall registration missing' }
Set-Content -LiteralPath "$target/my-book.txt" -Value 'A user book must survive uninstall.'
$process = Start-Process -FilePath "$target/QuietPages.exe" -ArgumentList '--self-test' -WindowStyle Hidden -Wait -PassThru
if ($process.ExitCode -ne 0) {
    Get-Content -LiteralPath "$env:QUIET_PAGES_DATA/smoke-error.txt" -ErrorAction SilentlyContinue
    throw 'Installed app self-test failed'
}
Get-Content -LiteralPath "$env:QUIET_PAGES_DATA/smoke-test.txt"
# _?= runs the uninstaller in place, allowing this process to wait for completion.
$process = Start-Process -FilePath "$target/Uninstall.exe" -ArgumentList @('/S', "_?=$target") -WindowStyle Hidden -Wait -PassThru
if ($process.ExitCode -ne 0 -or (Test-Path -LiteralPath "$target/QuietPages.exe")) { throw 'Uninstall failed' }
if (-not (Test-Path -LiteralPath "$target/my-book.txt")) { throw 'Uninstall removed a user book' }
if (-not (Test-Path -LiteralPath "$env:QUIET_PAGES_DATA/kokoro-v1.0.onnx")) { throw 'Uninstall removed saved data' }
if (Test-Path -LiteralPath $shortcut) { throw 'Uninstall left the shortcut' }
Write-Output 'Installer, installed voices, OCR, cache replay and uninstall preservation passed.'
