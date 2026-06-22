# TalentPortal PowerShell Setup Script
Write-Host "=== TalentPortal Setup ===" -ForegroundColor Cyan

Write-Host "[1/4] Creating virtual environment..." -ForegroundColor Yellow
python -m venv venv

Write-Host "[2/4] Activating and installing dependencies..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1
pip install -r requirements.txt

Write-Host "[3/4] Initializing database (make sure PostgreSQL is running and .env is configured)..." -ForegroundColor Yellow
$env:FLASK_APP = "run.py"
flask db init
flask db migrate -m "initial schema"
flask db upgrade

Write-Host "[4/4] Seeding sample data..." -ForegroundColor Yellow
python seed.py

Write-Host ""
Write-Host "=== Setup Complete! ===" -ForegroundColor Green
Write-Host "Start the app: python run.py" -ForegroundColor White
Write-Host "URL: http://127.0.0.1:5000" -ForegroundColor White
Write-Host "Admin login: admin@talent.com / Admin1234" -ForegroundColor White
