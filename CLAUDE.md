# ForecastSEPE — CLAUDE.md

## Propósito
Aplicación web para el Observatorio de las Ocupaciones del SEPE que permite lanzar pronósticos de series temporales del mercado laboral español sin necesidad de ejecutar notebooks Jupyter. Los usuarios finales no tienen conocimientos de Python.

## Stack
- **Backend:** FastAPI + uvicorn (`backend/main.py`)
- **Frontend:** Single HTML file con CSS/JS vanilla (`frontend/index.html`)
- **Comunicación progreso:** Server-Sent Events (SSE)
- **Ejecución de modelos:** subprocess llamando a scripts `.py`
- **Gráficos:** Plotly.js vía CDN
- **Export:** openpyxl en backend

## Estructura
```
ForecastSEPE/
├── scripts/
│   ├── forecast_ABC_estatal_NP.py       # Parados/Afiliados/Demandantes · estatal · NP
│   ├── forecast_ABC_estatal_LSTM.py     # Parados/Afiliados/Demandantes · estatal · LSTM
│   ├── forecast_ABC_atributo_NP.py      # Parados/Afiliados/Demandantes · atributo · NP
│   ├── forecast_ABC_atributo_LSTM.py    # Parados/Afiliados/Demandantes · atributo · LSTM ✓
│   ├── forecast_DE_estatal_NP.py        # Contratos/P.Contratadas · estatal · NP
│   ├── forecast_DE_estatal_XGBoost.py   # Contratos/P.Contratadas · estatal · XGBoost
│   ├── forecast_DE_atributo_NP.py       # Contratos/P.Contratadas · atributo · NP
│   └── forecast_DE_atributo_XGBoost.py  # Contratos/P.Contratadas · atributo · XGBoost
├── backend/
│   └── main.py                          # FastAPI: endpoints, SSE, subprocess, Excel
├── frontend/
│   └── index.html                       # UI completa (HTML + CSS + JS)
├── uploads/                             # CSVs temporales (gitignored)
├── .env
├── requirements.txt
├── start.bat
└── README.md
```

Los scripts marcados ✓ están implementados con modelos reales. Los demás se
irán convirtiendo desde los notebooks en `Parados Contratos Afiliados 2027-2029/`.
Mientras tanto, `forecast_ABC_*.py` y `forecast_DE_*.py` (stubs fase 1) cubren
los casos no convertidos.

## Grupos de métricas y scripts

| Grupo | Métricas | Modelos | Scripts |
|-------|----------|---------|---------|
| ABC   | Parados, Afiliados, Demandantes | NP, LSTM | forecast_ABC_*_{NP,LSTM}.py |
| DE    | Contratos, P. Contratadas | NP, XGBoost | forecast_DE_*_{NP,XGBoost}.py |

**Regla:** XGBoost solo para DE. LSTM solo para ABC. NP para todos.

**SCRIPT_MAP en backend/main.py:** clave `(grupo, modo, modelo)` → nombre de fichero.

**Escalabilidad:** Para añadir un modelo nuevo (ej. TimesFM), crear:
- `forecast_ABC_estatal_TimesFM.py` + `forecast_ABC_atributo_TimesFM.py`
- `forecast_DE_estatal_TimesFM.py` + `forecast_DE_atributo_TimesFM.py`

Y añadir las 4 entradas al `SCRIPT_MAP` en `backend/main.py`.

## Formato del CSV de entrada

**Nombre del fichero (contiene la metadata histórica):**
```
{Métrica} desde {AñoInicio} {estatal|por {Atributo}}.csv
```

El horizonte de pronóstico NO forma parte del nombre. Se calcula automáticamente:
- `f_end` = diciembre del año actual + 3 (siempre fijo, p.ej. `"2029-12"` en 2026)
- `f_start` = mes siguiente al último registro de la columna Fecha del CSV cargado
- Ambos se pasan a los scripts como strings `"YYYY-MM"`

Ejemplos correctos:
```
Parados desde 2010 estatal.csv
Afiliados desde 2015 por CCAA.csv
Contratos desde 2012 por provincias.csv
```

**Estructura interna:**
- Primera columna: `Fecha` (fechas mensuales, formato YYYY-MM o MM/YYYY)
- Columnas siguientes: una por serie (una si estatal, una por atributo si por atributo)

## Protocolo de comunicación scripts → backend → frontend

Los scripts emiten por stdout:
```
PROGRESS:10:Mensaje de progreso...
PROGRESS:45:Entrenando — epoch 20/60...
RESULT:{json completo}
ERROR:Descripción del error
```

**Formato del RESULT para estatal:**
```json
{
  "metrica": "Parados", "modo": "estatal", "modelo": "NP",
  "atributo": null, "anio_inicio": 2010,
  "historico": [{"fecha": "2010-01", "valor": 4250000}],
  "pronostico": [{"fecha": "2025-01", "valor": 3980000}],
  "intervalo_confianza": {
    "superior": [{"fecha": "2025-01", "valor": 4100000}],
    "inferior": [{"fecha": "2025-01", "valor": 3860000}]
  }
}
```

**Formato del RESULT para atributo:**
```json
{
  "metrica": "Parados", "modo": "atributo", "modelo": "NP",
  "atributo": "CCAA", "anio_inicio": 2010,
  "series": {
    "Andalucía": {
      "historico": [...], "pronostico": [...],
      "intervalo_confianza": {"superior": [...], "inferior": [...]}
    }
  }
}
```

## Protocolo INPUT_REQUIRED (columnas interactivas)

Cuando el CSV tiene más de 53 columnas, el script emite:
```
INPUT_REQUIRED:rango:Hay N columnas. Introduce el rango [inicio-fin] (ej: [1-53]):
```
El backend reenvía `{"type":"input_required","job_id":"...","prompt":"..."}` al frontend
via SSE. El frontend muestra un modal, el usuario escribe el rango y se envía a:
```
POST /provide-input  {"job_id": "...", "value": "[1-53]"}
```
El backend escribe el valor al stdin del subprocess y el script continúa con `input()`.

## Endpoints FastAPI

```
GET  /               → sirve frontend/index.html
POST /upload-csv     → recibe CSV, parsea nombre, devuelve metadata
GET  /run-forecast   → SSE: lanza script, emite PROGRESS, RESULT, INPUT_REQUIRED
POST /provide-input  → recibe respuesta del usuario para INPUT_REQUIRED
POST /export-excel   → recibe datos, devuelve .xlsx
POST /cleanup-csv    → borra el CSV temporal
GET  /health         → {"status": "ok"}
```

## SSL corporativo (Netskope)
Este proyecto se ejecuta detrás de un proxy SSL corporativo. Ver `CLAUDE.md` del directorio padre para los workarounds necesarios si se hacen llamadas HTTP externas desde los scripts.

## Lanzar la app
```
start.bat           # Windows: usa entorno NP-LSTM-XGBoost, abre navegador, lanza uvicorn en :8000
"C:\Users\sgei044\NP-LSTM-XGBoost\python.exe" -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

## Dimensiones de UI
- **Header:** 72px de alto, logo 44px, título 24px, subtítulo 13px
- **Footer:** padding 14px 16px, botones con padding 10px 22px / font-size 13px

## Fase 2 — conversión de notebooks a scripts

Notebooks fuente: `Parados Contratos Afiliados 2027-2029/`
Convertidos uno a uno, validando con el usuario entre script y script.

| Script | Notebook origen | Estado |
|--------|----------------|--------|
| forecast_ABC_atributo_LSTM.py | Parados o Afiliados mensual por AtributoX 2027-2029 LSTM_v2.ipynb | ✓ real |
| forecast_ABC_atributo_NP.py | Parados o Afiliados mensual por AtributoX 2027-2029 NP_v2.ipynb | pendiente |
| forecast_ABC_estatal_NP.py | Parados o Afiliados mensual estatal 2027-2029 NP_v2.ipynb | pendiente |
| forecast_ABC_estatal_LSTM.py | Parados o Afiliados mensual estatal 2027-2029 LSTM_v2.ipynb | pendiente |
| forecast_DE_atributo_XGBoost.py | Contratos mensual por AtributoX 2027-2029 XGBoost_v2.ipynb | pendiente |
| forecast_DE_atributo_NP.py | Contratos mensual por AtributoX 2027-2029 NP_v2.ipynb | pendiente |
| forecast_DE_estatal_XGBoost.py | Contratos mensual estatal 2027-2029 XGBoost_v2.ipynb | pendiente |
| forecast_DE_estatal_NP.py | Contratos mensual estatal 2027-2029 NP_v2.ipynb | pendiente |
