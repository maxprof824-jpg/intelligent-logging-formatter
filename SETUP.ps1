param([switch]$RebuildEnvironment)
$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
Set-Location -LiteralPath $taskRoot
$runtimeDir = Join-Path $taskRoot '.runtime'
$env:UV_CACHE_DIR = Join-Path $taskRoot '.cache\uv'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $runtimeDir 'python'
$env:UV_PYTHON_BIN_DIR = Join-Path $runtimeDir 'bin'
$env:UV_PYTHON_INSTALL_REGISTRY = '0'
$uvPath = Join-Path $runtimeDir 'uv\uv.exe'
if (-not (Test-Path -LiteralPath $uvPath)) {
    New-Item -ItemType Directory -Force (Split-Path $uvPath) | Out-Null
    $archivePath = Join-Path $runtimeDir 'uv.zip'
    Invoke-WebRequest -Uri 'https://github.com/astral-sh/uv/releases/download/0.12.13/uv-x86_64-pc-windows-msvc.zip' -OutFile $archivePath
    Expand-Archive -LiteralPath $archivePath -DestinationPath (Split-Path $uvPath) -Force
}
$pythonPath = Join-Path $taskRoot '.venv\Scripts\python.exe'
$createEnvironment = $RebuildEnvironment -or -not (Test-Path -LiteralPath $pythonPath)
if (-not $createEnvironment) {
    # A copied or moved venv can exist while its original base Python is missing.
    & $pythonPath -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)"
    if ($LASTEXITCODE -ne 0) {
        throw 'The existing virtual environment is unusable. Run powershell -NoProfile -ExecutionPolicy Bypass -File .\SETUP.ps1 -RebuildEnvironment to recreate it in this folder.'
    }
}
if ($createEnvironment) {
    & $uvPath python install 3.12.14 --no-bin --no-registry
    if ($LASTEXITCODE -ne 0) { throw 'Python installation failed' }
    # uv --clear replaces only this explicitly selected project virtual environment.
    & $uvPath venv --clear --python 3.12.14 (Join-Path $taskRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed' }
}
& $uvPath pip install --python $pythonPath 'torch==2.10.0' --index-url https://download.pytorch.org/whl/cu128
if ($LASTEXITCODE -ne 0) { throw 'CUDA PyTorch installation failed' }
if (Test-Path -LiteralPath (Join-Path $taskRoot 'requirements-lock.txt')) {
    & $uvPath pip install --python $pythonPath -r requirements-lock.txt
} else {
    & $uvPath pip install --python $pythonPath -r requirements.txt
}
if ($LASTEXITCODE -ne 0) { throw 'Training dependency installation failed' }
# Check the installed CUDA/BF16/NF4 stack before downloading ~8 GB of weights.
& $pythonPath doctor.py
if ($LASTEXITCODE -ne 0) { throw 'GPU verification failed. See reports\environment.json for details.' }
& $pythonPath -m unittest discover -p 'test_*.py'
if ($LASTEXITCODE -ne 0) { throw 'Application or model-download checks failed' }
& $pythonPath download_model.py
if ($LASTEXITCODE -ne 0) { throw 'Model download or checksum verification failed' }
if (-not (Test-Path -LiteralPath 'data\train.jsonl')) {
    & $pythonPath build_data.py
    if ($LASTEXITCODE -ne 0) { throw 'Dataset generation failed' }
}
if (Test-Path -LiteralPath 'runs\adapter-v2\adapter_model.safetensors') {
    $actual = (Get-FileHash -LiteralPath 'runs\adapter-v2\adapter_model.safetensors' -Algorithm SHA256).Hash.ToLower()
    if ($actual -ne '08a0f0d7c2c93dacb84fcdef97f1c2952c7a70551d260921c9782fa4bfa6dc9d') { throw 'Adapter checksum mismatch' }
    Write-Host 'Setup verified. Run RUN-DEMO.cmd.'
} else {
    Write-Host 'Environment verified. Download the tester release for the trained adapter, or run TRAIN-V2.cmd.'
}
