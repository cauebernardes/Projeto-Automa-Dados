@echo off
setlocal
cd /d "%~dp0" || exit /b 1
if not exist ".venv\Scripts\python.exe" (
  echo Ambiente virtual ausente na pasta de trabalho.
  pause
  exit /b 1
)
powershell.exe -NoProfile -Command "$port=Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1; if(!$port){exit 0}; $p=Get-CimInstance Win32_Process -Filter ('ProcessId='+$port.OwningProcess); $parent=Get-CimInstance Win32_Process -Filter ('ProcessId='+$p.ParentProcessId); $exe=Join-Path (Get-Location) '.venv\Scripts\python.exe'; if(($p.ExecutablePath -eq $exe -or $parent.ExecutablePath -eq $exe) -and $p.CommandLine -match 'streamlit run.+app\.py'){exit 10}; exit 11"
if errorlevel 11 (
  echo A porta 8501 esta ocupada por outro aplicativo.
  pause
  exit /b 1
)
if errorlevel 10 (
  start "" "http://127.0.0.1:8501"
  exit /b 0
)
".venv\Scripts\python.exe" -m streamlit run "app.py" --server.address 127.0.0.1 --server.port 8501 --browser.serverAddress 127.0.0.1
if errorlevel 1 (
  echo Falha ao iniciar o Streamlit. Confira a mensagem acima.
  pause
  exit /b 1
)
