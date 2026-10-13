@echo off
title ForecastSEPE -- Instalador

echo.
echo  ============================================================
echo   ForecastSEPE -- Instalador completo
echo   Observatorio de las Ocupaciones - SEPE
echo  ============================================================
echo.
echo  Este script instala todo lo necesario para usar ForecastSEPE:
echo    1. Miniconda (Python)   - si no esta instalado
echo    2. Git                  - si no esta instalado
echo    3. Repositorio ForecastSEPE desde GitHub
echo    4. Entorno NP-LSTM-XGBoost con todas las dependencias
echo    5. Entorno timesfm_env (modelo TimesFM)
echo    6. Checkpoint de TimesFM 2.5 (~925MB)
echo.
echo  No necesita permisos de administrador.
echo  Tiempo estimado: 35-55 minutos (primera instalacion).
echo.
echo  Pulsa una tecla para comenzar la instalacion...
pause >nul

REM ====================================================================
REM  CONFIGURACION
REM ====================================================================
set INSTALL_DIR=%USERPROFILE%\ForecastSEPE
set MINICONDA_DIR=%USERPROFILE%\Miniconda3
set PORTABLE_GIT_DIR=%USERPROFILE%\PortableGit
set MINICONDA_URL=https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe
set GIT_URL=https://github.com/git-for-windows/git/releases/download/v2.47.1.windows.1/PortableGit-2.47.1-64-bit.7z.exe
set REPO_URL=https://github.com/RobertoSanz88/ForecastSEPE.git
set ENV_NAME=NP-LSTM-XGBoost
set PYTHON_VER=3.10
set TIMESFM_ENV_NAME=timesfm_env
set TIMESFM_PYTHON_VER=3.11
set MODEL_DIR=%INSTALL_DIR%\models\timesfm-2.5-200m-pytorch
set MODEL_REPO_URL=https://huggingface.co/google/timesfm-2.5-200m-pytorch/resolve/main
set MIN_SAFETENSORS_BYTES=500000000

REM ====================================================================
REM  PASO 1: MINICONDA
REM ====================================================================
echo.
echo ============================================================
echo  [1/6] Comprobando Miniconda / Anaconda...
echo ============================================================

set CONDA_EXE=
set CONDA_BASE=

REM Buscar conda en PATH
where conda >nul 2>&1
if not errorlevel 1 (
    echo  [OK] conda encontrado en PATH
    set CONDA_FOUND=1
    goto :conda_done
)

REM Buscar en Miniconda3
if exist "%USERPROFILE%\Miniconda3\Scripts\conda.exe" (
    set CONDA_BASE=%USERPROFILE%\Miniconda3
    set CONDA_EXE=%USERPROFILE%\Miniconda3\Scripts\conda.exe
    echo  [OK] conda encontrado en: %USERPROFILE%\Miniconda3
    goto :conda_done
)

REM Buscar en miniconda3 (minusculas)
if exist "%USERPROFILE%\miniconda3\Scripts\conda.exe" (
    set CONDA_BASE=%USERPROFILE%\miniconda3
    set CONDA_EXE=%USERPROFILE%\miniconda3\Scripts\conda.exe
    echo  [OK] conda encontrado en: %USERPROFILE%\miniconda3
    goto :conda_done
)

REM Buscar en AppData anaconda3
if exist "%USERPROFILE%\AppData\Local\anaconda3\Scripts\conda.exe" (
    set CONDA_BASE=%USERPROFILE%\AppData\Local\anaconda3
    set CONDA_EXE=%USERPROFILE%\AppData\Local\anaconda3\Scripts\conda.exe
    echo  [OK] conda encontrado en: %USERPROFILE%\AppData\Local\anaconda3
    goto :conda_done
)

REM Buscar en anaconda3
if exist "%USERPROFILE%\anaconda3\Scripts\conda.exe" (
    set CONDA_BASE=%USERPROFILE%\anaconda3
    set CONDA_EXE=%USERPROFILE%\anaconda3\Scripts\conda.exe
    echo  [OK] conda encontrado en: %USERPROFILE%\anaconda3
    goto :conda_done
)

REM Buscar en ProgramData anaconda3
if exist "C:\ProgramData\anaconda3\Scripts\conda.exe" (
    set CONDA_BASE=C:\ProgramData\anaconda3
    set CONDA_EXE=C:\ProgramData\anaconda3\Scripts\conda.exe
    echo  [OK] conda encontrado en: C:\ProgramData\anaconda3
    goto :conda_done
)

REM Buscar en ProgramData miniconda3
if exist "C:\ProgramData\miniconda3\Scripts\conda.exe" (
    set CONDA_BASE=C:\ProgramData\miniconda3
    set CONDA_EXE=C:\ProgramData\miniconda3\Scripts\conda.exe
    echo  [OK] conda encontrado en: C:\ProgramData\miniconda3
    goto :conda_done
)

REM No encontrado - instalar Miniconda
echo  [INFO] conda no encontrado. Instalando Miniconda...
echo.
echo  Descargando Miniconda (~100 MB)...
echo  (Esto puede tardar unos minutos)
echo.

curl -kL -o "%TEMP%\Miniconda3-installer.exe" "%MINICONDA_URL%"
if errorlevel 1 (
    echo  [ERROR] No se pudo descargar Miniconda.
    echo          Comprueba tu conexion a internet.
    goto :error_exit
)
echo  [OK] Miniconda descargado.
echo.
echo  Instalando Miniconda en %MINICONDA_DIR%...
echo  (Esto puede tardar 2-5 minutos, no cierres esta ventana)
echo.

start /wait "" "%TEMP%\Miniconda3-installer.exe" /S /InstallationType=JustMe /RegisterPython=0 /AddToPath=0 /D=%MINICONDA_DIR%
if errorlevel 1 (
    echo  [ERROR] La instalacion de Miniconda fallo.
    goto :error_exit
)

del "%TEMP%\Miniconda3-installer.exe" >nul 2>&1
set CONDA_BASE=%MINICONDA_DIR%
set CONDA_EXE=%MINICONDA_DIR%\Scripts\conda.exe
echo  [OK] Miniconda instalado en %MINICONDA_DIR%.

:conda_done
REM Si se encontro en PATH pero no tenemos CONDA_BASE, derivarlo
if not defined CONDA_BASE (
    for /f "delims=" %%i in ('where conda 2^>nul') do set CONDA_EXE=%%i
    for /f "delims=" %%i in ('where conda 2^>nul') do set CONDA_BASE=%%~dpi..
)

REM Verificar activate
if not exist "%CONDA_BASE%\Scripts\activate.bat" (
    echo  [ERROR] No se encuentra activate.bat en %CONDA_BASE%\Scripts\
    goto :error_exit
)
echo  [OK] activate.bat encontrado.
echo.

REM Aceptar Terms of Service de los canales por defecto de Anaconda --
REM necesario en conda >= 25.x para poder crear entornos sin preguntar
REM (conda create -y falla si no, con CondaToSNonInteractiveError).
REM Silencioso: en versiones de conda sin el subcomando "tos" simplemente
REM falla y se ignora, no rompe nada.
"%CONDA_EXE%" tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main --insecure >nul 2>&1
"%CONDA_EXE%" tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r --insecure >nul 2>&1
"%CONDA_EXE%" tos accept --override-channels --channel https://repo.anaconda.com/pkgs/msys2 --insecure >nul 2>&1

REM ====================================================================
REM  PASO 2: GIT
REM ====================================================================
echo ============================================================
echo  [2/6] Comprobando Git...
echo ============================================================

set GIT_EXE=

REM Buscar git en PATH
where git >nul 2>&1
if not errorlevel 1 (
    echo  [OK] git encontrado en PATH
    set GIT_EXE=git
    goto :git_done
)

REM Buscar Git Portable
if exist "%PORTABLE_GIT_DIR%\bin\git.exe" (
    set GIT_EXE=%PORTABLE_GIT_DIR%\bin\git.exe
    echo  [OK] Git Portable encontrado en: %PORTABLE_GIT_DIR%
    goto :git_done
)

REM No encontrado - instalar Git Portable
echo  [INFO] git no encontrado. Instalando Git Portable...
echo.
echo  Descargando Git Portable (~63 MB)...
echo.

curl -kL -o "%TEMP%\PortableGit-installer.exe" "%GIT_URL%"
if errorlevel 1 (
    echo  [ERROR] No se pudo descargar Git Portable.
    echo          Comprueba tu conexion a internet.
    goto :error_exit
)
echo  [OK] Git Portable descargado.
echo.
echo  Descomprimiendo Git Portable en %PORTABLE_GIT_DIR%...
echo  (Esto puede tardar 1-2 minutos)
echo.

"%TEMP%\PortableGit-installer.exe" -o"%PORTABLE_GIT_DIR%" -y
if errorlevel 1 (
    echo  [ERROR] No se pudo descomprimir Git Portable.
    goto :error_exit
)

del "%TEMP%\PortableGit-installer.exe" >nul 2>&1
set GIT_EXE=%PORTABLE_GIT_DIR%\bin\git.exe
echo  [OK] Git Portable instalado en %PORTABLE_GIT_DIR%.

:git_done
REM Configurar SSL para git (Netskope)
"%GIT_EXE%" config --global http.sslVerify false >nul 2>&1
echo  [OK] Git configurado (SSL bypass para Netskope).
echo.

REM ====================================================================
REM  PASO 3: CLONAR REPOSITORIO
REM ====================================================================
echo ============================================================
echo  [3/6] Clonando repositorio ForecastSEPE...
echo ============================================================

if exist "%INSTALL_DIR%\.git" (
    echo  [INFO] El repositorio ya existe en %INSTALL_DIR%.
    echo         Actualizando con git pull...
    cd /d "%INSTALL_DIR%"
    "%GIT_EXE%" pull
    echo  [OK] Repositorio actualizado.
    goto :repo_done
)

if exist "%INSTALL_DIR%" (
    echo  [AVISO] La carpeta %INSTALL_DIR% ya existe pero no es un repo git.
    echo          Se eliminara y clonara de nuevo.
    rmdir /s /q "%INSTALL_DIR%"
)

"%GIT_EXE%" clone "%REPO_URL%" "%INSTALL_DIR%"
if errorlevel 1 (
    echo  [ERROR] No se pudo clonar el repositorio.
    echo          Comprueba tu conexion a internet.
    goto :error_exit
)
echo  [OK] Repositorio clonado en %INSTALL_DIR%.

:repo_done
echo.

REM ====================================================================
REM  PASO 4: CREAR ENTORNO NP-LSTM-XGBoost
REM ====================================================================
echo ============================================================
echo  [4/6] Creando entorno %ENV_NAME%...
echo ============================================================
echo.
echo  Esto incluye NeuralProphet, TensorFlow, XGBoost, scalecast...
echo  Puede tardar 15-25 minutos la primera vez.
echo.

REM Activar conda base
call "%CONDA_BASE%\Scripts\activate.bat"

REM Comprobar si el entorno ya existe
"%CONDA_EXE%" env list 2>nul | findstr /C:"%ENV_NAME%" >nul 2>&1
if not errorlevel 1 (
    echo  [INFO] El entorno %ENV_NAME% ya existe. Saltando creacion.
    goto :entorno_ready
)

REM Crear entorno
echo  Creando entorno %ENV_NAME% (Python %PYTHON_VER%)...
"%CONDA_EXE%" create -n %ENV_NAME% python=%PYTHON_VER% -y --insecure
if errorlevel 1 (
    echo  [ERROR] No se pudo crear el entorno.
    goto :error_exit
)
echo  [OK] Entorno creado.
echo.

REM Activar entorno e instalar paquetes
call "%CONDA_BASE%\Scripts\activate.bat" %ENV_NAME%

echo  Instalando paquetes desde requirements.txt...
echo  (Esto es lo que mas tarda, paciencia...)
echo.
pip install -r "%INSTALL_DIR%\requirements.txt" --trusted-host pypi.org --trusted-host files.pythonhosted.org --trusted-host pypi.python.org
if errorlevel 1 (
    echo.
    echo  [AVISO] Algunos paquetes no se instalaron correctamente.
    echo          Revisa los mensajes anteriores.
) else (
    echo.
    echo  [OK] Paquetes instalados.
)

:entorno_ready
echo.

REM ====================================================================
REM  PASO 5: ENTORNO timesfm_env (modelo TimesFM)
REM ====================================================================
echo ============================================================
echo  [5/6] Creando entorno %TIMESFM_ENV_NAME% (modelo TimesFM)...
echo ============================================================
echo.

call "%CONDA_BASE%\Scripts\activate.bat"

"%CONDA_EXE%" env list 2>nul | findstr /C:"%TIMESFM_ENV_NAME%" >nul 2>&1
if not errorlevel 1 (
    echo  [INFO] El entorno %TIMESFM_ENV_NAME% ya existe. Saltando creacion.
    goto :timesfm_env_ready
)

echo  Creando entorno %TIMESFM_ENV_NAME% (Python %TIMESFM_PYTHON_VER%)...
"%CONDA_EXE%" create -n %TIMESFM_ENV_NAME% python=%TIMESFM_PYTHON_VER% -y --insecure
if errorlevel 1 (
    echo  [AVISO] No se pudo crear el entorno %TIMESFM_ENV_NAME%.
    echo          El resto de la app ^(NP/LSTM/XGBoost^) funcionara igual --
    echo          solo el modelo TimesFM no estara disponible.
    goto :timesfm_skip
)
echo  [OK] Entorno creado.
echo.

echo  Instalando timesfm y dependencias...
call "%CONDA_BASE%\Scripts\activate.bat" %TIMESFM_ENV_NAME%
pip install "timesfm[torch]==3.0.0" pandas numpy scikit-learn --trusted-host pypi.org --trusted-host files.pythonhosted.org --trusted-host pypi.python.org
if errorlevel 1 (
    echo  [AVISO] Algunos paquetes de timesfm no se instalaron correctamente.
    echo          Revisa los mensajes anteriores.
) else (
    echo  [OK] timesfm instalado.
)

:timesfm_env_ready
echo.

REM ====================================================================
REM  PASO 6: CHECKPOINT DE TimesFM 2.5
REM ====================================================================
echo ============================================================
echo  [6/6] Comprobando checkpoint de TimesFM 2.5...
echo ============================================================

REM Umbral de tamano minimo (bytes) para dar el checkpoint por bueno --
REM el real pesa ~925MB; cualquier cosa muy por debajo (p.ej. una pagina de
REM bloqueo del proxy corporativo en vez del fichero real) se descarta.
set FSIZE=0
if exist "%MODEL_DIR%\model.safetensors" for %%A in ("%MODEL_DIR%\model.safetensors") do set FSIZE=%%~zA

if %FSIZE% GEQ %MIN_SAFETENSORS_BYTES% (
    echo  [INFO] El checkpoint ya existe en %MODEL_DIR% ^(%FSIZE% bytes^). Saltando descarga.
    goto :timesfm_skip
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
    echo  [AVISO] curl fallo al descargar config.json.
    goto :model_download_failed
)

echo  Descargando model.safetensors (~925MB, paciencia)...
curl -kL -o "%MODEL_DIR%\model.safetensors" "%MODEL_REPO_URL%/model.safetensors"
if errorlevel 1 (
    echo  [AVISO] curl fallo al descargar model.safetensors.
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
goto :timesfm_skip

:model_download_failed
echo.
echo  ------------------------------------------------------------
echo   Descarga automatica del checkpoint no disponible en esta red.
echo   El resto de la app funcionara igual -- solo TimesFM no estara
echo   disponible hasta que lo descargues. Alternativa manual:
echo  ------------------------------------------------------------
echo    1. Abre en tu navegador normal (el que ya usas cada dia):
echo       https://huggingface.co/google/timesfm-2.5-200m-pytorch/tree/main
echo    2. Descarga los dos ficheros: config.json y model.safetensors
echo    3. Colocalos juntos en esta carpeta:
echo       %MODEL_DIR%
echo.

:timesfm_skip
echo.

REM ====================================================================
REM  VERIFICACION
REM ====================================================================
echo ============================================================
echo  Verificando instalacion...
echo ============================================================
echo.

call "%CONDA_BASE%\Scripts\activate.bat" %ENV_NAME%

python -c "import neuralprophet; print('  [OK] NeuralProphet', neuralprophet.__version__)" 2>nul
if errorlevel 1 echo  [AVISO] NeuralProphet no disponible

python -c "import tensorflow; print('  [OK] TensorFlow', tensorflow.__version__)" 2>nul
if errorlevel 1 echo  [AVISO] TensorFlow no disponible

python -c "import scalecast; print('  [OK] scalecast')" 2>nul
if errorlevel 1 echo  [AVISO] scalecast no disponible

python -c "import xgboost; print('  [OK] XGBoost', xgboost.__version__)" 2>nul
if errorlevel 1 echo  [AVISO] XGBoost no disponible

python -c "import fastapi; print('  [OK] FastAPI', fastapi.__version__)" 2>nul
if errorlevel 1 echo  [AVISO] FastAPI no disponible

call "%CONDA_BASE%\Scripts\activate.bat" %TIMESFM_ENV_NAME% 2>nul
python -c "import timesfm; print('  [OK] timesfm', getattr(timesfm, '__version__', 'n/d'))" 2>nul
if errorlevel 1 echo  [AVISO] timesfm no disponible en %TIMESFM_ENV_NAME%

if exist "%MODEL_DIR%\model.safetensors" (
    echo  [OK] Checkpoint de TimesFM presente en %MODEL_DIR%
) else (
    echo  [AVISO] Checkpoint de TimesFM no encontrado en %MODEL_DIR%
)

echo.

REM Crear acceso directo en escritorio -- resolver la ruta real via registro,
REM %USERPROFILE%\Desktop no es fiable si el Escritorio esta redirigido a OneDrive
echo  Creando acceso directo en el Escritorio...
set DESKTOP_DIR=
for /f "tokens=2,*" %%A in ('reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders" /v Desktop 2^>nul') do set "DESKTOP_DIR=%%B"
if not defined DESKTOP_DIR set DESKTOP_DIR=%USERPROFILE%\Desktop
if not exist "%DESKTOP_DIR%" mkdir "%DESKTOP_DIR%" >nul 2>&1

echo @echo off > "%DESKTOP_DIR%\ForecastSEPE.bat"
echo cd /d "%INSTALL_DIR%" >> "%DESKTOP_DIR%\ForecastSEPE.bat"
echo call "%INSTALL_DIR%\ForecastSEPE.bat" >> "%DESKTOP_DIR%\ForecastSEPE.bat"

if exist "%DESKTOP_DIR%\ForecastSEPE.bat" (
    echo  [OK] Acceso directo creado: %DESKTOP_DIR%\ForecastSEPE.bat
) else (
    echo  [AVISO] No se pudo crear el acceso directo en %DESKTOP_DIR%.
    echo          Puedes lanzar la app ejecutando directamente:
    echo          %INSTALL_DIR%\ForecastSEPE.bat
)

echo.
echo  ============================================================
echo   INSTALACION COMPLETADA
echo  ============================================================
echo.
echo  Para usar ForecastSEPE:
echo    - Doble clic en el acceso directo "ForecastSEPE" creado en el Escritorio
echo    - Se abrira el navegador automaticamente
echo    - ForecastSEPE.bat detecta solo los entornos (NP-LSTM-XGBoost y
echo      timesfm_env) que encuentre instalados -- no hace falta editar
echo      nada a mano.
echo.
echo  Para actualizar:
echo    - Ejecuta este instalador de nuevo
echo    - Detectara que ya esta instalado y hara git pull
echo.
echo  Pulsa una tecla para cerrar esta ventana...
pause >nul
goto :eof

:error_exit
echo.
echo  La instalacion no se pudo completar.
echo  Revisa los mensajes de error y vuelve a intentarlo.
echo.
echo  Pulsa una tecla para cerrar...
pause >nul
