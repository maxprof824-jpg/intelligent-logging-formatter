param([string]$OutputDirectory)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Run SETUP-WINDOWS.cmd before training.'
}
if (-not $OutputDirectory) {
    # Preserve the shipped adapter and previous experiments.
    $OutputDirectory = 'runs/experiments/adapter-v2-' + [DateTime]::Now.ToString('yyyyMMdd-HHmmss-fff')
}
Write-Host ('Training output: ' + $OutputDirectory)
Write-Host 'Stop the demo with STOP-DEMO.cmd first so the GPU has enough memory.'
& $pythonPath -u train.py --data-dir data-v2 --max-length 4096 --output $OutputDirectory
if ($LASTEXITCODE -ne 0) { throw 'Training failed. The released adapter was not replaced.' }
Write-Host 'Training finished. To try this adapter, run:'
Write-Host ('.\.venv\Scripts\python.exe app_v2.py --adapter "' + $OutputDirectory + '"')
