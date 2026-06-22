@echo off
echo === TalentPortal Setup ===

echo [1/4] Creating virtual environment...
python -m venv venv

echo [2/4] Activating and installing dependencies...
call venv\Scripts\activate.bat
pip install -r requirements.txt

echo [3/4] Initializing database migrations...
flask db init
flask db migrate -m "initial schema"
flask db upgrade

echo [4/4] Seeding sample data...
python seed.py

echo.
echo === Setup Complete! ===
echo Run the app with: venv\Scripts\activate && flask run
echo Or:               venv\Scripts\activate && python run.py
echo.
echo App will start at: http://127.0.0.1:5000
echo Admin login:       admin@talent.com / Admin1234
pause
