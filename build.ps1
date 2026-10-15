$ErrorActionPreference = 'Stop'
if ($env:GITHUB_RUN_NUMBER) {
    Set-Content -LiteralPath app_version.py -Value "VERSION = 'preview-$env:GITHUB_RUN_NUMBER-$env:GITHUB_RUN_ATTEMPT'" -Encoding utf8
}
python -m pip install -r requirements.txt pyinstaller==6.22.3
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
python -m PyInstaller --noconfirm --clean --windowed --onedir --name QuietPages --collect-all kokoro_onnx --collect-all espeakng_loader --collect-all phonemizer --collect-all sounddevice --collect-all pypdf --collect-all rapidocr_onnxruntime --collect-all pypdfium2 --collect-all pypdfium2_raw app.py
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
python package_notices.py
if ($LASTEXITCODE -ne 0) { throw 'Notice packaging failed' }
python collect_sources.py
if ($LASTEXITCODE -ne 0) { throw 'Source packaging failed' }
Compress-Archive -Path dist/QuietPages -DestinationPath dist/QuietPages-Windows-x64.zip -Force
$compiler = Get-Command makensis.exe -ErrorAction SilentlyContinue
if ($compiler) { $compilerPath = $compiler.Source }
else { $compilerPath = 'C:/Program Files (x86)/NSIS/makensis.exe' }
if (-not (Test-Path -LiteralPath $compilerPath)) { throw 'Install NSIS to build the Windows installer.' }
& $compilerPath installer.nsi
if ($LASTEXITCODE -ne 0) { throw 'Installer build failed' }
