@echo off
title ForecastSEPE 2.0 -- Instalador incremental (TimesFM)

echo.
echo  ============================================================
echo   ForecastSEPE 2.0 -- Instalador incremental
echo   Observatorio de las Ocupaciones - SEPE
echo  ============================================================
echo.
echo  Este script SOLO instala lo NUEVO de la version 2.0 (modelo
echo  TimesFM): no clona ni toca el repositorio ni el entorno
echo  NP-LSTM-XGBoost -- eso lo hace INSTALAR_ForecastSEPE.bat.
echo.
echo  Requisito: conda / Miniconda ya instalado (ejecuta antes
echo  INSTALAR_ForecastSEPE.bat si te falta).
echo.
echo  Instala:
echo    1. Entorno conda "timesfm_env"       - si no existe
echo    2. Checkpoint de TimesFM 2.5 (~925MB) - si no esta descargado
echo.
echo  Tiempo estimado: 5-15 minutos (depende de tu conexion).
echo.
echo  Pulsa una tecla para comenzar...
pause >nul

REM ====================================================================
REM  CONFIGURACION
REM ====================================================================
set PROJECT_DIR=%~dp0
set ENV_NAME=timesfm_env
set PYTHON_VER=3.11
set MODEL_DIR=%PROJECT_DIR%models\timesfm-2.5-200m-pytorch
set MODEL_REPO_URL=https://huggingface.co/google/timesfm-2.5-200m-pytorch/resolve/main

echo  Proyecto: %PROJECT_DIR%
echo.

REM ====================================================================
REM  PASO 1: LOCALIZAR CONDA (igual que INSTALAR_ForecastSEPE.bat)
REM ====================================================================
echo ============================================================
echo  [1/3] Comprobando conda...
echo ============================================================

set CONDA_EXE=
set CONDA_BASE=

where conda >nul 2>&1
if not errorlevel 1 (
    echo  [OK] conda encontrado en PATH
    goto :conda_done
)

if exist "%USERPROFILE%\Miniconda3\Scripts\conda.exe" (
    set CONDA_BASE=%USERPROFILE%\Miniconda3
    set CONDA_EXE=%USERPROFILE%\Miniconda3\Scripts\conda.exe
    goto :conda_done
)
if exist "%USERPROFILE%\miniconda3\Scripts\conda.exe" (
    set CONDA_BASE=%USERPROFILE%\miniconda3
    set CONDA_EXE=%USERPROFILE%\miniconda3\Scripts\conda.exe
    goto :conda_done
)
if exist "%USERPROFILE%\AppData\Local\anaconda3\Scripts\conda.exe" (
    set CONDA_BASE=%USERPROFILE%\AppData\Local\anaconda3
    set CONDA_EXE=%USERPROFILE%\AppData\Local\anaconda3\Scripts\conda.exe
    goto :conda_done
)
if exist "%USERPROFILE%\anaconda3\Scripts\conda.exe" (
    set CONDA_BASE=%USERPROFILE%\anaconda3
    set CONDA_EXE=%USERPROFILE%\anaconda3\Scripts\conda.exe
    goto :conda_done
)
if exist "C:\ProgramData\anaconda3\Scripts\conda.exe" (
    set CONDA_BASE=C:\ProgramData\anaconda3
    set CONDA_EXE=C:\ProgramData\anaconda3\Scripts\conda.exe
    goto :conda_done
)
if exist "C:\ProgramData\miniconda3\Scripts\conda.exe" (
    set CONDA_BASE=C:\ProgramData\miniconda3
    set CONDA_EXE=C:\ProgramData\miniconda3\Scripts\conda.exe
    goto :conda_done
)

echo.
echo  [ERROR] No se encontro conda/Miniconda.
echo          Ejecuta primero INSTALAR_ForecastSEPE.bat (paso 1),
echo          que instala Miniconda si hace falta.
echo.
goto :error_exit

:conda_done
if not defined CONDA_BASE (
    for /f "delims=" %%i in ('where conda 2^>nul') do set CONDA_EXE=%%i
    for /f "delims=" %%i in ('where conda 2^>nul') do set CONDA_BASE=%%~dpi..
)
echo  [OK] conda: %CONDA_BASE%
echo.

REM ====================================================================
REM  PASO 2: ENTORNO timesfm_env
REM ====================================================================
echo ============================================================
echo  [2/3] Comprobando entorno %ENV_NAME%...
echo ============================================================

call "%CONDA_BASE%\Scripts\activate.bat"

"%CONDA_EXE%" env list 2>nul | findstr /C:"%ENV_NAME%" >nul 2>&1
if not errorlevel 1 (
    echo  [INFO] El entorno %ENV_NAME% ya existe. Saltando creacion.
    goto :env_ready
)

echo  Creando entorno %ENV_NAME% (Python %PYTHON_VER%)...
"%CONDA_EXE%" create -n %ENV_NAME% python=%PYTHON_VER% -y --insecure
if errorlevel 1 (
    echo  [ERROR] No se pudo crear el entorno %ENV_NAME%.
    goto :error_exit
)
echo  [OK] Entorno creado.
echo.

echo  Instalando timesfm y dependencias...
call "%CONDA_BASE%\Scripts\activate.bat" %ENV_NAME%
pip install "timesfm[torch]==3.0.0" pandas numpy scikit-learn --trusted-host pypi.org --trusted-host files.pythonhosted.org --trusted-host pypi.python.org
if errorlevel 1 (
    echo  [AVISO] Algunos paquetes no se instalaron correctamente.
    echo          Revisa los mensajes anteriores.
) else (
    echo  [OK] timesfm instalado.
)

:env_ready
echo.

REM ====================================================================
REM  PASO 3: CHECKPOINT DE TimesFM 2.5
REM ====================================================================
echo ============================================================
echo  [3/3] Comprobando checkpoint de TimesFM 2.5...
echo ============================================================

REM Umbral de tamano minimo (bytes) para dar el checkpoint por bueno --
REM el real pesa ~925MB; cualquier cosa muy por debajo (p.ej. una pagina de
REM bloqueo del proxy corporativo en vez del fichero real) se descarta.
set MIN_SAFETENSORS_BYTES=500000000

set FSIZE=0
if exist "%MODEL_DIR%\model.safetensors" for %%A in ("%MODEL_DIR%\model.safetensors") do set FSIZE=%%~zA

if %FSIZE% GEQ %MIN_SAFETENSORS_BYTES% (
    echo  [INFO] El checkpoint ya existe en %MODEL_DIR% ^(%FSIZE% bytes^). Saltando descarga.
    goto :model_ready
)

if exist "%MODEL_DIR%\model.safetensors" (
    echo  [AVISO] Hay un model.safetensors en %MODEL_DIR% pero pesa muy poco
    echo          ^(%FSIZE% bytes^) -- no es el fichero real, se descarta y se
    echo          vuelve a intentar la descarga.
    del "%MODEL_DIR%\model.safetensors" >nul 2>&1
)

echo  [INFO] Descargando checkpoint (~925MB, puede tardar varios minutos)...
echo.

if not exist "%MODEL_DIR%" mkdir "%MODEL_DIR%"

echo  Descargando config.json...
curl -kL -o "%MODEL_DIR%\config.json" "%MODEL_REPO_URL%/config.json"
if errorlevel 1 (
    echo  [ERROR] curl fallo al descargar config.json.
    goto :model_download_failed
)

echo  Descargando model.safetensors (~925MB, paciencia)...
curl -kL -o "%MODEL_DIR%\model.safetensors" "%MODEL_REPO_URL%/model.safetensors"
if errorlevel 1 (
    echo  [ERROR] curl fallo al descargar model.safetensors.
    goto :model_download_failed
)

REM Verificar que lo descargado sea el fichero real, no una pagina de
REM bloqueo del proxy corporativo (Netskope) -- curl no distingue eso solo,
REM devuelve "exito" igualmente porque la peticion HTTP en si no falla.
set FSIZE=0
for %%A in ("%MODEL_DIR%\model.safetensors") do set FSIZE=%%~zA
if %FSIZE% LSS %MIN_SAFETENSORS_BYTES% (
    echo  [AVISO] La descarga se completo pero el fichero pesa solo %FSIZE%
    echo          bytes -- probablemente el proxy corporativo ha sustituido
    echo          el fichero real por una pagina de bloqueo/aviso.
    goto :model_download_failed
)

echo  [OK] Checkpoint descargado en %MODEL_DIR%.
goto :model_ready

:model_download_failed
echo.
echo  ------------------------------------------------------------
echo   Descarga automatica no disponible en esta red -- alternativa manual:
echo  ------------------------------------------------------------
echo    1. Abre en tu navegador normal (el que ya usas cada dia):
echo       https://huggingface.co/google/timesfm-2.5-200m-pytorch/tree/main
echo    2. Descarga los dos ficheros: config.json y model.safetensors
echo    3. Colocalos juntos en esta carpeta:
echo       %MODEL_DIR%
echo    4. Vuelve a ejecutar este instalador -- detectara que ya estan y
echo       no volvera a intentar la descarga automatica.
echo.
goto :error_exit

:model_ready
echo.

REM ====================================================================
REM  VERIFICACION
REM ====================================================================
echo ============================================================
echo  Verificando instalacion...
echo ============================================================
echo.

call "%CONDA_BASE%\Scripts\activate.bat" %ENV_NAME%
python -c "import timesfm; print('  [OK] timesfm', getattr(timesfm, '__version__', 'n/d'))" 2>nul
if errorlevel 1 echo  [AVISO] timesfm no disponible en %ENV_NAME%

if exist "%MODEL_DIR%\model.safetensors" (
    echo  [OK] Checkpoint presente en %MODEL_DIR%
) else (
    echo  [AVISO] Checkpoint no encontrado en %MODEL_DIR%
)

echo.
echo  ============================================================
echo   INSTALACION INCREMENTAL COMPLETADA
echo  ============================================================
echo.
echo  ForecastSEPE-v2-DEV.bat detecta este entorno automaticamente al
echo  arrancar -- no hace falta que edites nada mas a mano.
echo.
echo  Pulsa una tecla para cerrar esta ventana...
pause >nul
goto :eof

:error_exit
echo.
echo  La instalacion incremental no se pudo completar.
echo  Revisa los mensajes de error y vuelve a intentarlo.
echo.
echo  Pulsa una tecla para cerrar...
pause >nul
