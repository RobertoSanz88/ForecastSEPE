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

REM --- Buscar Python del entorno timesfm_env (opcional -- modelo TimesFM) ---
set TIMESFM_PYTHON_EXE=

if exist "%USERPROFILE%\Miniconda3\envs\timesfm_env\python.exe" (
    set TIMESFM_PYTHON_EXE=%USERPROFILE%\Miniconda3\envs\timesfm_env\python.exe
)
if not defined TIMESFM_PYTHON_EXE if exist "%USERPROFILE%\miniconda3\envs\timesfm_env\python.exe" (
    set TIMESFM_PYTHON_EXE=%USERPROFILE%\miniconda3\envs\timesfm_env\python.exe
)
if not defined TIMESFM_PYTHON_EXE if exist "%USERPROFILE%\AppData\Local\anaconda3\envs\timesfm_env\python.exe" (
    set TIMESFM_PYTHON_EXE=%USERPROFILE%\AppData\Local\anaconda3\envs\timesfm_env\python.exe
)
if not defined TIMESFM_PYTHON_EXE if exist "%USERPROFILE%\anaconda3\envs\timesfm_env\python.exe" (
    set TIMESFM_PYTHON_EXE=%USERPROFILE%\anaconda3\envs\timesfm_env\python.exe
)
if not defined TIMESFM_PYTHON_EXE if exist "C:\ProgramData\anaconda3\envs\timesfm_env\python.exe" (
    set TIMESFM_PYTHON_EXE=C:\ProgramData\anaconda3\envs\timesfm_env\python.exe
)
if not defined TIMESFM_PYTHON_EXE if exist "C:\ProgramData\miniconda3\envs\timesfm_env\python.exe" (
    set TIMESFM_PYTHON_EXE=C:\ProgramData\miniconda3\envs\timesfm_env\python.exe
)
REM entorno creado con "python -m venv timesfm_env" directamente en la carpeta
REM de usuario (no via conda create, sin la carpeta "envs\" de por medio)
if not defined TIMESFM_PYTHON_EXE if exist "%USERPROFILE%\timesfm_env\python.exe" (
    set TIMESFM_PYTHON_EXE=%USERPROFILE%\timesfm_env\python.exe
)

if defined TIMESFM_PYTHON_EXE (
    echo  TimesFM: %TIMESFM_PYTHON_EXE%
) else (
    echo  TimesFM: entorno timesfm_env no encontrado -- ese modelo no estara disponible.
    echo           Ejecuta INSTALAR_ForecastSEPE_v2.bat si lo necesitas.
)

REM --- Lanzar uvicorn en ventana separada ---
REM El servidor escucha en 0.0.0.0 (accesible tambien via %HOST_IP% si hace
REM falta desde otro equipo), pero el navegador se abre con 127.0.0.1: el
REM proxy corporativo Netskope intercepta el trafico por IP de LAN y devuelve
REM 504, mientras que localhost/127.0.0.1 no pasa por ahi.
echo.
echo  Arrancando servidor DEV en http://127.0.0.1:8766 (LAN: http://%HOST_IP%:8766) ...
echo  (No cierres la ventana negra del servidor)
echo.

if defined SSL_CERT (
    start cmd /k "cd /d "%PROJECT_DIR%" && set SSL_CERT_FILE=%SSL_CERT% && set TIMESFM_PYTHON_EXE=%TIMESFM_PYTHON_EXE% && "%PYTHON_EXE%" -m uvicorn backend.main:app --host 0.0.0.0 --port 8766"
) else (
    start cmd /k "cd /d "%PROJECT_DIR%" && set TIMESFM_PYTHON_EXE=%TIMESFM_PYTHON_EXE% && "%PYTHON_EXE%" -m uvicorn backend.main:app --host 0.0.0.0 --port 8766"
)

REM --- Esperar y abrir navegador (localhost, no la IP de LAN -- ver nota arriba) ---
timeout /t 5 /nobreak >nul
start "" "http://127.0.0.1:8766"
echo  [OK] Navegador abierto en http://127.0.0.1:8766
echo.
echo  Si da 504 usando la IP de LAN, usa http://127.0.0.1:8766 (Netskope
echo  intercepta el trafico por IP en esta red).
echo  Para detener: cierra la ventana del servidor.
echo.
echo  Pulsa una tecla para cerrar esta ventana (el servidor sigue activo
echo  en su propia ventana negra aunque cierres esta)...
pause >nul
