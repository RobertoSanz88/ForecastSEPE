@echo off
setlocal
title ForecastSEPE - Crear acceso directo

REM Crea ForecastSEPE.lnk en el Escritorio apuntando a ForecastSEPE.bat de esta
REM carpeta. Valido en cualquier PC (desarrollo o trabajo): las rutas salen de la
REM ubicacion de este fichero y el Escritorio se resuelve con la API de Windows,
REM que respeta la redireccion a OneDrive.
set "APP_DIR=%~dp0"
set "TARGET=%APP_DIR%ForecastSEPE.bat"
set "ICON=%APP_DIR%assets\icono_2.ico"

echo.
echo  Creando acceso directo de ForecastSEPE en el Escritorio...
echo.

if not exist "%TARGET%" goto :sin_bat
if not exist "%ICON%" echo  [AVISO] No se encuentra assets\icono_2.ico. Se crea sin icono personalizado.

REM Las rutas viajan en variables de entorno (no dentro del comando) para que
REM comillas o apostrofos en la ruta no rompan PowerShell.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$d=[Environment]::GetFolderPath('Desktop'); $s=(New-Object -COM WScript.Shell).CreateShortcut((Join-Path $d 'ForecastSEPE.lnk')); $s.TargetPath=$env:TARGET; $s.WorkingDirectory=$env:APP_DIR; if (Test-Path -LiteralPath $env:ICON) { $s.IconLocation=$env:ICON }; $s.Save(); Write-Host (' Ruta: ' + (Join-Path $d 'ForecastSEPE.lnk'))"
if errorlevel 1 goto :error

echo.
echo  [OK] Acceso directo creado en el Escritorio: ForecastSEPE.lnk
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
