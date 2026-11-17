@echo off
rem Sentinelle Scolaire : lance l'API (port 8000) et le site (port 3000), puis ouvre le navigateur.
rem Fonctionne sans Internet ; l'assistant passe alors en mode hors ligne.
cd /d "%~dp0"
set "PY=python"
if exist "%~dp0..\..\..\.venv\Scripts\python.exe" set "PY=%~dp0..\..\..\.venv\Scripts\python.exe"

if not exist "%~dp0web\.next\BUILD_ID" (
  echo Premiere installation du site...
  pushd "%~dp0web"
  call npm install
  call npm run build
  popd
)

start "Sentinelle - API" cmd /k "cd /d "%~dp0api" && "%PY%" -m uvicorn main:app --port 8000"
start "Sentinelle - site" cmd /k "cd /d "%~dp0web" && npm start"
echo Ouverture du tableau de bord dans quelques secondes...
timeout /t 8 /nobreak >nul
start "" http://localhost:3000
