@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title ForecastSEPE — Instalador

echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║        ForecastSEPE — Instalador completo               ║
echo  ║        Observatorio de las Ocupaciones · SEPE            ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.
echo  Este script instala todo lo necesario para usar ForecastSEPE:
echo    1. Miniconda (Python)   — si no esta instalado
echo    2. Git                  — si no esta instalado
echo    3. Repositorio ForecastSEPE desde GitHub
echo    4. Entorno NP-LSTM-XGBoost con todas las dependencias
echo.
echo  No necesita permisos de administrador.
echo  Tiempo estimado: 30-45 minutos (primera instalacion).
echo.
pause

REM ====================================================================
REM  CONFIGURACION
REM ====================================================================
set "INSTALL_DIR=%USERPROFILE%\ForecastSEPE"
set "MINICONDA_DIR=%USERPROFILE%\Miniconda3"
set "GIT_DIR=%USERPROFILE%\PortableGit"
set "MINICONDA_URL=https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe"
set "GIT_URL=https://github.com/git-for-windows/git/releases/download/v2.47.1.windows.1/PortableGit-2.47.1-64-bit.7z.exe"
set "REPO_URL=https://github.com/RobertoSanz88/ForecastSEPE.git"
set "ENV_NAME=NP-LSTM-XGBoost"
set "PYTHON_VER=3.10"

REM ====================================================================
REM  PASO 1: MINICONDA
REM ====================================================================
echo.
echo ════════════════════════════════════════════════════════════
echo  [1/4] Comprobando Miniconda / Anaconda...
echo ════════════════════════════════════════════════════════════

set "CONDA_EXE="
set "CONDA_BASE="
set "CONDA_ACTIVATE="

REM Buscar conda en PATH
where conda >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%i in ('where conda') do set "CONDA_EXE=%%i"
    echo  [OK] conda encontrado en PATH: !CONDA_EXE!
    REM Derivar CONDA_BASE (2 niveles arriba de Scripts\conda.exe)
    for %%A in ("!CONDA_EXE!") do set "CONDA_BASE=%%~dpA.."
    goto :conda_ready
)

REM Buscar en ubicaciones comunes
for %%P in (
    "%USERPROFILE%\Miniconda3"
    "%USERPROFILE%\miniconda3"
    "%USERPROFILE%\AppData\Local\anaconda3"
    "%USERPROFILE%\anaconda3"
    "C:\ProgramData\anaconda3"
    "C:\ProgramData\miniconda3"
) do (
    if exist "%%~P\Scripts\conda.exe" (
        set "CONDA_BASE=%%~P"
        set "CONDA_EXE=%%~P\Scripts\conda.exe"
        echo  [OK] conda encontrado en: %%~P
        goto :conda_ready
    )
)

REM No encontrado — instalar Miniconda
echo  [INFO] conda no encontrado. Instalando Miniconda...
echo.
echo  Descargando Miniconda (~100 MB)...
echo  (Esto puede tardar unos minutos)
echo.

set "MINICONDA_INSTALLER=%TEMP%\Miniconda3-installer.exe"
curl -kL -o "%MINICONDA_INSTALLER%" "%MINICONDA_URL%"
if errorlevel 1 (
    echo.
    echo  [ERROR] No se pudo descargar Miniconda.
    echo          Comprueba tu conexion a internet.
    pause
    exit /b 1
)
echo  [OK] Miniconda descargado.
echo.
echo  Instalando Miniconda en %MINICONDA_DIR%...
echo  (Esto puede tardar 2-5 minutos, no cierres esta ventana)
echo.

start /wait "" "%MINICONDA_INSTALLER%" /S /InstallationType=JustMe /RegisterPython=0 /AddToPath=0 /D=%MINICONDA_DIR%
if errorlevel 1 (
    echo.
    echo  [ERROR] La instalacion de Miniconda fallo.
    pause
    exit /b 1
)

del "%MINICONDA_INSTALLER%" >nul 2>&1
set "CONDA_BASE=%MINICONDA_DIR%"
set "CONDA_EXE=%MINICONDA_DIR%\Scripts\conda.exe"
echo  [OK] Miniconda instalado en %MINICONDA_DIR%.

:conda_ready
REM Configurar activate
set "CONDA_ACTIVATE=%CONDA_BASE%\Scripts\activate.bat"
if not exist "%CONDA_ACTIVATE%" (
    echo  [ERROR] No se encuentra activate.bat en %CONDA_BASE%\Scripts\
    pause
    exit /b 1
)
echo.

REM ====================================================================
REM  PASO 2: GIT
REM ====================================================================
echo ════════════════════════════════════════════════════════════
echo  [2/4] Comprobando Git...
echo ════════════════════════════════════════════════════════════

set "GIT_EXE="

REM Buscar git en PATH
where git >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%i in ('where git') do set "GIT_EXE=%%i"
    echo  [OK] git encontrado en PATH: !GIT_EXE!
    goto :git_ready
)

REM Buscar Git Portable instalado previamente
if exist "%GIT_DIR%\bin\git.exe" (
    set "GIT_EXE=%GIT_DIR%\bin\git.exe"
    echo  [OK] Git Portable encontrado en: %GIT_DIR%
    goto :git_ready
)

REM No encontrado — instalar Git Portable
echo  [INFO] git no encontrado. Instalando Git Portable...
echo.
echo  Descargando Git Portable (~63 MB)...
echo.

set "GIT_INSTALLER=%TEMP%\PortableGit-installer.exe"
curl -kL -o "%GIT_INSTALLER%" "%GIT_URL%"
if errorlevel 1 (
    echo.
    echo  [ERROR] No se pudo descargar Git Portable.
    echo          Comprueba tu conexion a internet.
    pause
    exit /b 1
)
echo  [OK] Git Portable descargado.
echo.
echo  Descomprimiendo Git Portable en %GIT_DIR%...
echo  (Esto puede tardar 1-2 minutos)
echo.

REM PortableGit es un auto-extractor 7z — ejecutar con -o para destino y -y para no preguntar
"%GIT_INSTALLER%" -o"%GIT_DIR%" -y
if errorlevel 1 (
    echo.
    echo  [ERROR] No se pudo descomprimir Git Portable.
    pause
    exit /b 1
)

del "%GIT_INSTALLER%" >nul 2>&1
set "GIT_EXE=%GIT_DIR%\bin\git.exe"
echo  [OK] Git Portable instalado en %GIT_DIR%.

:git_ready
REM Configurar SSL para git (Netskope)
"%GIT_EXE%" config --global http.sslVerify false >nul 2>&1
echo.

REM ====================================================================
REM  PASO 3: CLONAR REPOSITORIO
REM ====================================================================
echo ════════════════════════════════════════════════════════════
echo  [3/4] Clonando repositorio ForecastSEPE...
echo ════════════════════════════════════════════════════════════

if exist "%INSTALL_DIR%\.git" (
    echo  [INFO] El repositorio ya existe en %INSTALL_DIR%.
    echo         Actualizando con git pull...
    cd /d "%INSTALL_DIR%"
    "%GIT_EXE%" pull
    echo  [OK] Repositorio actualizado.
) else (
    if exist "%INSTALL_DIR%" (
        echo  [AVISO] La carpeta %INSTALL_DIR% ya existe pero no es un repo git.
        echo          Se eliminara y clonara de nuevo.
        rmdir /s /q "%INSTALL_DIR%"
    )
    "%GIT_EXE%" clone "%REPO_URL%" "%INSTALL_DIR%"
    if errorlevel 1 (
        echo.
        echo  [ERROR] No se pudo clonar el repositorio.
        echo          Comprueba tu conexion a internet.
        pause
        exit /b 1
    )
    echo  [OK] Repositorio clonado en %INSTALL_DIR%.
)
echo.

REM ====================================================================
REM  PASO 4: CREAR ENTORNO
REM ====================================================================
echo ════════════════════════════════════════════════════════════
echo  [4/4] Creando entorno %ENV_NAME%...
echo ════════════════════════════════════════════════════════════
echo.
echo  Esto incluye NeuralProphet, TensorFlow, XGBoost, scalecast...
echo  Puede tardar 15-25 minutos la primera vez.
echo.

REM Activar conda base
call "%CONDA_ACTIVATE%"

REM Comprobar si el entorno ya existe
"%CONDA_EXE%" env list 2>nul | findstr /C:"%ENV_NAME%" >nul 2>&1
if not errorlevel 1 (
    echo  [INFO] El entorno '%ENV_NAME%' ya existe.
    echo         Saltando creacion. Para recrearlo, eliminalo primero con:
    echo         conda env remove -n %ENV_NAME%
    goto :entorno_ready
)

REM Crear entorno
echo  Creando entorno '%ENV_NAME%' (Python %PYTHON_VER%)...
"%CONDA_EXE%" create -n %ENV_NAME% python=%PYTHON_VER% -y --insecure
if errorlevel 1 (
    echo.
    echo  [ERROR] No se pudo crear el entorno.
    pause
    exit /b 1
)
echo  [OK] Entorno creado.
echo.

REM Activar entorno e instalar paquetes
call "%CONDA_ACTIVATE%" %ENV_NAME%

echo  Instalando paquetes...
if exist "%INSTALL_DIR%\requirements_entorno.txt" (
    pip install -r "%INSTALL_DIR%\requirements_entorno.txt" --trusted-host pypi.org --trusted-host files.pythonhosted.org --trusted-host pypi.python.org
) else if exist "%INSTALL_DIR%\requirements.txt" (
    pip install -r "%INSTALL_DIR%\requirements.txt" --trusted-host pypi.org --trusted-host files.pythonhosted.org --trusted-host pypi.python.org
) else (
    echo  [ERROR] No se encuentra requirements.txt en %INSTALL_DIR%
    pause
    exit /b 1
)

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
REM  PASO 5: VERIFICACION Y ACCESO DIRECTO
REM ====================================================================
echo ════════════════════════════════════════════════════════════
echo  Verificando instalacion...
echo ════════════════════════════════════════════════════════════

call "%CONDA_ACTIVATE%" %ENV_NAME%
echo.
python -c "import neuralprophet; print('  [OK] NeuralProphet', neuralprophet.__version__)" 2>nul || echo  [AVISO] NeuralProphet no disponible
python -c "import tensorflow; print('  [OK] TensorFlow', tensorflow.__version__)" 2>nul || echo  [AVISO] TensorFlow no disponible
python -c "import scalecast; print('  [OK] scalecast')" 2>nul || echo  [AVISO] scalecast no disponible
python -c "import xgboost; print('  [OK] XGBoost', xgboost.__version__)" 2>nul || echo  [AVISO] XGBoost no disponible
python -c "import fastapi; print('  [OK] FastAPI', fastapi.__version__)" 2>nul || echo  [AVISO] FastAPI no disponible
echo.

REM Crear acceso directo en escritorio
echo  Creando acceso directo en el Escritorio...
(
echo @echo off
echo cd /d "%INSTALL_DIR%"
echo call "%INSTALL_DIR%\ForecastSEPE.bat"
) > "%USERPROFILE%\Desktop\ForecastSEPE.bat"
echo  [OK] Acceso directo creado: ForecastSEPE.bat en el Escritorio.

echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║        INSTALACION COMPLETADA                            ║
echo  ╠══════════════════════════════════════════════════════════╣
echo  ║                                                          ║
echo  ║  Para usar ForecastSEPE:                                 ║
echo  ║    - Doble clic en ForecastSEPE.bat en el Escritorio     ║
echo  ║    - Se abrira el navegador automaticamente              ║
echo  ║                                                          ║
echo  ║  Para actualizar:                                        ║
echo  ║    - Ejecuta este instalador de nuevo                    ║
echo  ║    - Detectara que ya esta instalado y hara git pull     ║
echo  ║                                                          ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.
pause
