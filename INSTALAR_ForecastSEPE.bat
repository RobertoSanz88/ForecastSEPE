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
echo.
echo  No necesita permisos de administrador.
echo  Tiempo estimado: 30-45 minutos (primera instalacion).
echo.
echo  Pulsa una tecla para comenzar la instalacion...
pause >nul

REM ====================================================================
REM  CONFIGURACION
REM ====================================================================
set INSTALL_DIR=%USERPROFILE%\ForecastSEPE
set MINICONDA_DIR=%USERPROFILE%\Miniconda3
set GIT_DIR=%USERPROFILE%\PortableGit
set MINICONDA_URL=https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe
set GIT_URL=https://github.com/git-for-windows/git/releases/download/v2.47.1.windows.1/PortableGit-2.47.1-64-bit.7z.exe
set REPO_URL=https://github.com/RobertoSanz88/ForecastSEPE.git
set ENV_NAME=NP-LSTM-XGBoost
set PYTHON_VER=3.10

REM ====================================================================
REM  PASO 1: MINICONDA
REM ====================================================================
echo.
echo ============================================================
echo  [1/4] Comprobando Miniconda / Anaconda...
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

REM ====================================================================
REM  PASO 2: GIT
REM ====================================================================
echo ============================================================
echo  [2/4] Comprobando Git...
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
if exist "%GIT_DIR%\bin\git.exe" (
    set GIT_EXE=%GIT_DIR%\bin\git.exe
    echo  [OK] Git Portable encontrado en: %GIT_DIR%
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
echo  Descomprimiendo Git Portable en %GIT_DIR%...
echo  (Esto puede tardar 1-2 minutos)
echo.

"%TEMP%\PortableGit-installer.exe" -o"%GIT_DIR%" -y
if errorlevel 1 (
    echo  [ERROR] No se pudo descomprimir Git Portable.
    goto :error_exit
)

del "%TEMP%\PortableGit-installer.exe" >nul 2>&1
set GIT_EXE=%GIT_DIR%\bin\git.exe
echo  [OK] Git Portable instalado en %GIT_DIR%.

:git_done
REM Configurar SSL para git (Netskope)
"%GIT_EXE%" config --global http.sslVerify false >nul 2>&1
echo  [OK] Git configurado (SSL bypass para Netskope).
echo.

REM ====================================================================
REM  PASO 3: CLONAR REPOSITORIO
REM ====================================================================
echo ============================================================
echo  [3/4] Clonando repositorio ForecastSEPE...
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
REM  PASO 4: CREAR ENTORNO
REM ====================================================================
echo ============================================================
echo  [4/4] Creando entorno %ENV_NAME%...
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

echo.

REM Crear acceso directo en escritorio
echo  Creando acceso directo en el Escritorio...
echo @echo off > "%USERPROFILE%\Desktop\ForecastSEPE.bat"
echo cd /d "%INSTALL_DIR%" >> "%USERPROFILE%\Desktop\ForecastSEPE.bat"
echo call "%INSTALL_DIR%\ForecastSEPE.bat" >> "%USERPROFILE%\Desktop\ForecastSEPE.bat"
echo  [OK] Acceso directo creado: ForecastSEPE.bat en el Escritorio.

echo.
echo  ============================================================
echo   INSTALACION COMPLETADA
echo  ============================================================
echo.
echo  Para usar ForecastSEPE:
echo    - Doble clic en ForecastSEPE.bat en el Escritorio
echo    - Se abrira el navegador automaticamente
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
