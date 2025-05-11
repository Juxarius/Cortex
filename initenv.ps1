git pull

if (-not (Test-Path ".\venv\Scripts\Activate.ps1")) {
    Write-Output "Virtual environment not found. Creating one..."
    python -m venv .\venv
}

.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt