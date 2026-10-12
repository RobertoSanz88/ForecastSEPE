# ForecastSEPE

Aplicación web para el **Observatorio de las Ocupaciones del SEPE** que permite generar pronósticos de series temporales del mercado laboral español a través de una interfaz web, sin necesidad de ejecutar notebooks Jupyter.

## Requisitos

- Windows 10/11
- Conexión de red (para la instalación inicial y para que Plotly.js se cargue vía CDN)
- Para usar el modelo TimesFM: se recomiendan al menos 8GB de RAM. Con 4GB funciona, pero muy lento (el *fine-tuning* del modelo compite por memoria con el resto de programas abiertos)

## Instalación

Descarga `INSTALAR_ForecastSEPE.bat` y ejecútalo **desde fuera de la carpeta del proyecto** (por ejemplo, desde Descargas, sin moverlo a ningún otro sitio).

El instalador se encarga de todo: Miniconda, Git, el propio repositorio, el entorno `NP-LSTM-XGBoost` y el entorno `timesfm_env` con el checkpoint de TimesFM 2.5 (~925MB). Si ya tienes algo instalado, lo detecta y lo salta.

Para actualizar a una versión más reciente, ejecuta el mismo instalador de nuevo — sin necesidad de mover ni volver a descargar nada.

## Lanzar la aplicación

**Opción A — Acceso directo (recomendado):**
Doble clic en el acceso directo **"ForecastSEPE"** que el instalador crea en el Escritorio.

**Opción B — Script bat:**
```
ForecastSEPE.bat
```
(dentro de la carpeta del proyecto). Detecta automáticamente los entornos instalados, abre el navegador y lanza el servidor.

**Opción C — Manual:**
```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8001
```
(usando el Python del entorno `NP-LSTM-XGBoost`). Luego abre http://localhost:8001 en el navegador.

## Uso

### Ruta A — CSV primero
1. Arrastra tu CSV al área de carga (o haz clic para seleccionar)
2. El sistema detecta automáticamente métrica y ámbito del nombre del fichero
3. Selecciona uno o más modelos
4. Pulsa **Ejecutar Pronóstico**

### Ruta B — Selección manual primero
1. Haz clic en la cajita de la métrica deseada
2. Selecciona el ámbito (Estatal / Por atributo)
3. La línea azul te muestra el nombre exacto que debe tener tu CSV
4. Prepara el CSV con ese nombre y arrástralo
5. Selecciona modelo y ejecuta

### Formato del nombre del CSV

```
{Métrica} desde {AñoInicio} {estatal|por {Atributo}}.csv
```

El horizonte de pronóstico no forma parte del nombre — se calcula automáticamente a partir de la fecha actual y del último registro del CSV.

Ejemplos válidos:
```
Parados desde 2010 estatal.csv
Afiliados desde 2015 por CCAA.csv
Contratos desde 2012 por provincias.csv
```

### Disponibilidad de modelos

| Modelo | Parados | Afiliados | Demandantes | Contratos | Personas Contratadas |
|--------|:-------:|:---------:|:-----------:|:---------:|:-------------------:|
| NeuralProphet (NP) | ✓ | ✓ | ✓ | ✓ | ✓ |
| LSTM | ✓ | ✓ | ✓ | — | — |
| XGBoost | — | — | — | ✓ | ✓ |
| TimesFM | ✓ | ✓ | ✓ | ✓ | ✓ |

### Ensemble
Si ejecutas dos o más modelos, se activa el botón **⚡ Calcular Ensemble** que promedia los pronósticos.

### Exportar Excel
El botón **⬇ Exportar Excel** genera un fichero `.xlsx` con dos hojas:
- **Histórico**: serie histórica del CSV
- **Pronóstico [Modelo]**: pronóstico con intervalos de confianza, una hoja por modelo

## Estructura

```
ForecastSEPE/
├── scripts/                 # Scripts de pronóstico (uno por métrica/ámbito/modelo)
├── backend/                 # FastAPI
│   └── main.py
├── frontend/                 # UI
│   └── index.html
├── notebooks/                # Desarrollo y validación de TimesFM
├── certs/                    # Certificado corporativo (Netskope), si hace falta
├── config.py                  # Hiperparámetros por modelo/métrica
├── models/                    # Checkpoint de TimesFM 2.5 (se crea al instalar, no versionado)
├── uploads/                   # CSVs temporales (no versionado)
├── .env                        # Variables opcionales (p.ej. TIMESFM_PYTHON_EXE manual)
├── requirements.txt
├── ForecastSEPE.bat
├── INSTALAR_ForecastSEPE.bat
└── CLAUDE.md                   # Documentación de arquitectura para Claude Code
```
