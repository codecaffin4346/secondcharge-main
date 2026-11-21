$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

if (-not (Test-Path "$Root\backend\.venv")) {
    Write-Host "Setting up the Python environment..."
    Set-Location "$Root\backend"
    uv venv --python 3.12 .venv
    uv pip install --python .venv\Scripts\python.exe -r requirements.txt
    Set-Location $Root
}

if (-not (Test-Path "$Root\frontend\node_modules")) {
    Write-Host "Installing web app dependencies..."
    Set-Location "$Root\frontend"
    npm ci
    Set-Location $Root
}

if (-not (Test-Path "$Root\backend\models\soh_models.joblib")) {
    Write-Host "Training models..."
    Set-Location "$Root\backend"
    & .venv\Scripts\python.exe -m app.ml.train
    Set-Location $Root
}

Set-Location "$Root\backend"
$Api = Start-Process -FilePath ".venv\Scripts\python.exe" -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" -PassThru -WindowStyle Hidden
Set-Location "$Root\frontend"
npm run build

try {
    Write-Host "SecondCharge running at http://localhost:3000"
    Write-Host "API docs: http://localhost:8000/docs"
    npx next start -H 127.0.0.1 -p 3000
}
finally {
    if ($Api -and -not $Api.HasExited) {
        Stop-Process -Id $Api.Id -Force
    }
}
