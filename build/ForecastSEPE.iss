; Instalador de ForecastSEPE (opcion B: entornos conda + codigo como ficheros normales).
; Se compila con ISCC.exe. Las rutas de origen son parametrizables (/D...) para poder
; validar la sintaxis rapido con carpetas de mentira antes de la compilacion real.
;
;   ISCC.exe ForecastSEPE.iss                          -> compilacion real
;   ISCC.exe /DProyecto=... /DEntornoNP=... ForecastSEPE.iss   -> prueba

#ifndef Proyecto
  #define Proyecto   "C:\Users\rsanz\ForecastSEPE"
#endif
#ifndef EntornoNP
  #define EntornoNP  "C:\Users\rsanz\miniconda3\envs\NP-LSTM-XGBoost"
#endif
#ifndef EntornoTFM
  #define EntornoTFM "C:\Users\rsanz\miniconda3\envs\timesfm_env"
#endif
#ifndef Checkpoint
  #define Checkpoint "C:\Users\rsanz\ForecastSEPE\models\timesfm-2.5-200m-pytorch"
#endif
#ifndef Version
  #define Version    "2.0"
#endif
#ifndef Salida
  #define Salida     "C:\Users\rsanz\ForecastSEPE_build\out"
#endif

[Setup]
AppId={{8FA81C23-3195-43EB-8A28-BAA28CA2F6EA}
AppName=ForecastSEPE
AppVersion={#Version}
AppPublisher=Observatorio de las Ocupaciones (SEPE)
; Instalacion por usuario, sin permisos de administrador: la app escribe en su
; propia carpeta (uploads\, logs) y no puede hacerlo en Archivos de programa.
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\ForecastSEPE
DisableProgramGroupPage=yes
DisableDirPage=auto
OutputDir={#Salida}
OutputBaseFilename=ForecastSEPE_Setup_{#Version}
SetupIconFile={#Proyecto}\assets\icono_2.ico
UninstallDisplayIcon={app}\assets\icono_2.ico
Compression=lzma2/normal
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
; --- Codigo de la aplicacion (ficheros normales, se actualizan sin tocar el runtime) ---
Source: "{#Proyecto}\backend\*";  DestDir: "{app}\backend";  Flags: recursesubdirs createallsubdirs; Excludes: "__pycache__,*.pyc"
Source: "{#Proyecto}\scripts\*";  DestDir: "{app}\scripts";  Flags: recursesubdirs createallsubdirs; Excludes: "__pycache__,*.pyc,_debug_*"
Source: "{#Proyecto}\frontend\*"; DestDir: "{app}\frontend"; Flags: recursesubdirs createallsubdirs
Source: "{#Proyecto}\assets\*";   DestDir: "{app}\assets";   Flags: recursesubdirs createallsubdirs
Source: "{#Proyecto}\config.py";  DestDir: "{app}"
Source: "{#Proyecto}\requirements.txt"; DestDir: "{app}"
Source: "{#Proyecto}\ForecastSEPE.bat"; DestDir: "{app}"

; --- Runtime: los dos entornos conda, tal cual (el lanzador los detecta en runtime\) ---
Source: "{#EntornoNP}\*";  DestDir: "{app}\runtime\np_env";      Flags: recursesubdirs createallsubdirs; Excludes: "__pycache__,*.pyc"
Source: "{#EntornoTFM}\*"; DestDir: "{app}\runtime\timesfm_env"; Flags: recursesubdirs createallsubdirs; Excludes: "__pycache__,*.pyc"

; --- Checkpoint de TimesFM 2.5 ---
Source: "{#Checkpoint}\*"; DestDir: "{app}\models\timesfm-2.5-200m-pytorch"; Flags: recursesubdirs createallsubdirs

[Dirs]
Name: "{app}\uploads"

[Icons]
Name: "{autodesktop}\ForecastSEPE"; Filename: "{app}\ForecastSEPE.bat"; WorkingDir: "{app}"; IconFilename: "{app}\assets\icono_2.ico"; Comment: "Pronosticos del Observatorio de las Ocupaciones"
Name: "{userprograms}\ForecastSEPE"; Filename: "{app}\ForecastSEPE.bat"; WorkingDir: "{app}"; IconFilename: "{app}\assets\icono_2.ico"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\uploads"
Type: files; Name: "{app}\warnings.log"
