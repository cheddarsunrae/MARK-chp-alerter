$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot '.venv\Scripts\pythonw.exe'
$consolePython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$gui = Join-Path $PSScriptRoot 'chp_gui_crossplatform.py'

if (-not (Test-Path $gui)) {
    throw "CHP Alerter GUI not found: $gui"
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

Start-Process -FilePath $python -ArgumentList @($gui) -WorkingDirectory $PSScriptRoot
