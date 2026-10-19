@echo off
REM Crea ForecastSEPE.lnk en el Escritorio apuntando a ForecastSEPE.bat de esta
REM carpeta, con el icono de assets\icono_2.ico (opcional: si falta, se crea sin
REM icono). Valido en cualquier PC (desarrollo o trabajo): las rutas salen de la
REM ubicacion de este fichero y el Escritorio se resuelve con SpecialFolders, que
REM respeta la redireccion a OneDrive.
REM
REM Un .bat no puede crear un .lnk por si solo - se genera un .vbs temporal que
REM si sabe hacerlo via WScript.Shell (funciona en cualquier Windows sin tocar
REM politica de ejecucion, a diferencia de un script de PowerShell). Mismo
REM patron que crear_acceso_directo.bat de MCVLAnalyserSEPE.
setlocal
title ForecastSEPE - Crear acceso directo
cd /d "%~dp0"

set "TARGET=%~dp0ForecastSEPE.bat"
set "ICON=%~dp0assets\icono_2.ico"
set "VBS=%TEMP%\crear_acceso_forecastsepe.vbs"

echo.
echo  Creando acceso directo de ForecastSEPE en el Escritorio...
echo.

if not exist "%TARGET%" goto :sin_bat
if not exist "%ICON%" echo  [AVISO] No se encuentra assets\icono_2.ico. Se crea sin icono personalizado.

> "%VBS%" echo Set oWS = WScript.CreateObject("WScript.Shell")
>> "%VBS%" echo sLinkFile = oWS.SpecialFolders("Desktop") ^& "\ForecastSEPE.lnk"
>> "%VBS%" echo Set oLink = oWS.CreateShortcut(sLinkFile)
>> "%VBS%" echo oLink.TargetPath = "%TARGET%"
>> "%VBS%" echo oLink.WorkingDirectory = "%~dp0"
if exist "%ICON%" >> "%VBS%" echo oLink.IconLocation = "%ICON%,0"
>> "%VBS%" echo oLink.Description = "Lanza ForecastSEPE (pronosticos del Observatorio de las Ocupaciones)"
>> "%VBS%" echo oLink.Save

cscript //nologo "%VBS%"
set "RC=%errorlevel%"
del "%VBS%" >nul 2>&1
if not "%RC%"=="0" goto :error

echo.
echo  [OK] Acceso directo creado en el Escritorio: ForecastSEPE
echo.
pause
exit /b 0

:sin_bat
echo  [ERROR] No se encuentra ForecastSEPE.bat junto a este fichero.
echo          Ejecuta crear_acceso_directo.bat desde la carpeta de ForecastSEPE.
echo.
pause
exit /b 1

:error
echo  [ERROR] No se pudo crear el acceso directo.
echo.
pause
exit /b 1
