@echo off
setlocal enabledelayedexpansion
title ForecastSEPE - Observatorio SEPE
echo Starting ForecastSEPE (work - Netskope)...

REM --- Detect LAN IP (works on English and Spanish Windows, any IP range) ---
set HOST_IP=
for /f "tokens=2 delims=:" %%A in ('ipconfig ^| findstr /i "IPv4"') do (
    set _RAW=%%A
    set _IP=!_RAW: =!
    if not "!_IP!"=="127.0.0.1" if not defined HOST_IP set HOST_IP=!_IP!
)
if not defined HOST_IP (
    echo WARNING: Could not detect LAN IP - falling back to 127.0.0.1
    set HOST_IP=127.0.0.1
)
echo Detected IP: %HOST_IP%

set SSL_CERT_FILE=C:\Users\sgei044\certs\caadmin.netskope.crt
start cmd /k "cd /d "C:\Users\sgei044\Desktop\ML and IA with Python\ForecastSEPE" && set SSL_CERT_FILE=C:\Users\sgei044\certs\caadmin.netskope.crt && C:\Users\sgei044\NP-LSTM-XGBoost\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000"
timeout /t 5 /nobreak
start "" "http://%HOST_IP%:8000"
echo Ready at http://%HOST_IP%:8000
