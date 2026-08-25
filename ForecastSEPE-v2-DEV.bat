@echo off
title ForecastSEPE 2.0-DEV - Observatorio SEPE (puerto 8766)
echo.
echo  ============================================================
echo   ForecastSEPE 2.0-DEV - Iniciando servidor...
echo  ============================================================
echo.

REM --- Directorio del proyecto (donde esta este .bat) ---
set PROJECT_DIR=%~dp0
echo  Proyecto: %PROJECT_DIR%

REM --- Detectar IP LAN (Windows espanol e ingles) ---
set HOST_IP=
for /f "tokens=2 delims=:" %%A in ('ipconfig ^| findstr /i "IPv4"') do (
    for /f "tokens=*" %%B in ("%%A") do (
        if not "%%B"=="127.0.0.1" if not defined HOST_IP set HOST_IP=%%B
    )
)
if not defined HOST_IP set HOST_IP=127.0.0.1
echo  IP detectada: %HOST_IP%

REM --- Buscar certificado Netskope ---
set SSL_CERT=
if exist "%PROJECT_DIR%certs\caadmin.netskope.crt" (
    set SSL_CERT=%PROJECT_DIR%certs\caadmin.netskope.crt
    goto :cert_done
)
if exist "%USERPROFILE%\certs\caadmin.netskope.crt" (
    set SSL_CERT=%USERPROFILE%\certs\caadmin.netskope.crt
    goto :cert_done
)
if exist "C:\ProgramData\Netskope\STAgent\data\nscacert.pem" (
    set SSL_CERT=C:\ProgramData\Netskope\STAgent\data\nscacert.pem
    goto :cert_done
)

:cert_done
if defined SSL_CERT (
    echo  Certificado Netskope: %SSL_CERT%
) else (
    echo  Sin certificado Netskope (no es necesario en todas las redes)
)

REM --- Buscar Python del entorno NP-LSTM-XGBoost ---
set PYTHON_EXE=

if exist "%USERPROFILE%\Miniconda3\envs\NP-LSTM-XGBoost\python.exe" (
    set PYTHON_EXE=%USERPROFILE%\Miniconda3\envs\NP-LSTM-XGBoost\python.exe
    goto :python_found
)

if exist "%USERPROFILE%\miniconda3\envs\NP-LSTM-XGBoost\python.exe" (
    set PYTHON_EXE=%USERPROFILE%\miniconda3\envs\NP-LSTM-XGBoost\python.exe
    goto :python_found
)

if exist "%USERPROFILE%\AppData\Local\anaconda3\envs\NP-LSTM-XGBoost\python.exe" (
    set PYTHON_EXE=%USERPROFILE%\AppData\Local\anaconda3\envs\NP-LSTM-XGBoost\python.exe
    goto :python_found
)

if exist "%USERPROFILE%\anaconda3\envs\NP-LSTM-XGBoost\python.exe" (
    set PYTHON_EXE=%USERPROFILE%\anaconda3\envs\NP-LSTM-XGBoost\python.exe
    goto :python_found
)

if exist "C:\ProgramData\anaconda3\envs\NP-LSTM-XGBoost\python.exe" (
    set PYTHON_EXE=C:\ProgramData\anaconda3\envs\NP-LSTM-XGBoost\python.exe
    goto :python_found
)

if exist "C:\ProgramData\miniconda3\envs\NP-LSTM-XGBoost\python.exe" (
    set PYTHON_EXE=C:\ProgramData\miniconda3\envs\NP-LSTM-XGBoost\python.exe
    goto :python_found
)

if exist "%USERPROFILE%\NP-LSTM-XGBoost\python.exe" (
    set PYTHON_EXE=%USERPROFILE%\NP-LSTM-XGBoost\python.exe
    goto :python_found
)

echo.
echo  [ERROR] No se encontro el entorno NP-LSTM-XGBoost.
echo          Ejecuta primero INSTALAR_ForecastSEPE.bat
echo.
pause
exit /b 1

:python_found
echo  Python: %PYTHON_EXE%

REM --- Lanzar uvicorn en ventana separada ---
echo.
echo  Arrancando servidor DEV en http://%HOST_IP%:8766 ...
echo  (No cierres la ventana negra del servidor)
echo.

if defined SSL_CERT (
    start cmd /k "cd /d "%PROJECT_DIR%" && set SSL_CERT_FILE=%SSL_CERT% && "%PYTHON_EXE%" -m uvicorn backend.main:app --host 0.0.0.0 --port 8766"
) else (
    start cmd /k "cd /d "%PROJECT_DIR%" && "%PYTHON_EXE%" -m uvicorn backend.main:app --host 0.0.0.0 --port 8766"
)

REM --- Esperar y abrir navegador ---
timeout /t 5 /nobreak >nul
start "" "http://%HOST_IP%:8766"
echo  [OK] Navegador abierto en http://%HOST_IP%:8766
echo.
echo  Para detener: cierra la ventana del servidor.
