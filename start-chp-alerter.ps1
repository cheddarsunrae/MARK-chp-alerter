$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot '.venv\Scripts\pythonw.exe'
$consolePython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$gui = Join-Path $PSScriptRoot 'mark_gui_entry.py'
$errorLog = Join-Path $PSScriptRoot 'runtime\mark-gui-error.log'

if (-not (Test-Path $gui)) {
    throw "MARK GUI entry point not found: $gui"
}

if (-not (Test-Path $python)) {
    Write-Host 'Python virtual environment not found. Creating it now...'
    py -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        throw 'Could not create the Python virtual environment.'
    }
}

if (-not (Test-Path $consolePython)) {
    throw "Virtual-environment Python not found: $consolePython"
}

& $consolePython -m pip install -r (Join-Path $PSScriptRoot 'requirements.txt')
if ($LASTEXITCODE -ne 0) {
    throw 'Dependency installation failed.'
}

if (-not (Test-Path (Join-Path $PSScriptRoot '.env'))) {
    Copy-Item (Join-Path $PSScriptRoot '.env.example') (Join-Path $PSScriptRoot '.env')
}

New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot 'runtime') | Out-Null
if (Test-Path $errorLog) {
    Remove-Item $errorLog -Force
}

$preflightFiles = @(
    (Join-Path $PSScriptRoot 'mark_gui_entry.py'),
    (Join-Path $PSScriptRoot 'chp_gui.py'),
    (Join-Path $PSScriptRoot 'mark_app.py'),
    (Join-Path $PSScriptRoot 'mark_backend.py')
)
& $consolePython -m py_compile @preflightFiles
if ($LASTEXITCODE -ne 0) {
    throw 'MARK GUI preflight failed. The Python error above identifies the broken file and line.'
}

Start-Process -FilePath $python -ArgumentList @($gui) -WorkingDirectory $PSScriptRoot
Start-Sleep -Milliseconds 800
if (Test-Path $errorLog) {
    Write-Host ''
    Write-Host 'MARK failed during startup:' -ForegroundColor Red
    Get-Content $errorLog
    throw "MARK GUI startup failed. See $errorLog"
}
