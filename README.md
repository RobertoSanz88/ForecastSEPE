# ForecastSEPE

Aplicación web para el **Observatorio de las Ocupaciones del SEPE** que permite generar pronósticos de series temporales del mercado laboral español a través de una interfaz web, sin necesidad de ejecutar notebooks Jupyter.

## Requisitos

- Python 3.10 o superior
- Conexión de red (Plotly.js se carga vía CDN)

## Instalación

```bash
# Clonar el repositorio
git clone <url-del-repo>
cd ForecastSEPE

# Crear entorno virtual (recomendado)
python -m venv .venv
.venv\Scripts\activate          # Windows

# Instalar dependencias
pip install -r requirements.txt --trusted-host pypi.org --trusted-host files.pythonhosted.org
```

## Lanzar la aplicación

**Opción A — Script bat (Windows):**
```
start.bat
```
El script activa el entorno virtual si existe, abre el navegador automáticamente y lanza el servidor.

**Opción B — Manual:**
```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```
Luego abre http://localhost:8000 en el navegador.

## Uso

### Ruta A — CSV primero
1. Arrastra tu CSV al área de carga (o haz clic para seleccionar)
2. El sistema detecta automáticamente métrica, ámbito y horizonte del nombre del fichero
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
{Métrica} desde {AñoInicio} {estatal|por {Atributo}} {AñoPronostico}-{AñoFinal}.csv
```

Ejemplos válidos:
```
Parados desde 2010 estatal 2025-2028.csv
Afiliados desde 2015 por CCAA 2025-2028.csv
Contratos desde 2012 por provincias 2025-2028.csv
```

### Disponibilidad de modelos

| Modelo | Parados | Afiliados | Demandantes | Contratos | Personas Contratadas |
|--------|:-------:|:---------:|:-----------:|:---------:|:-------------------:|
| NeuralProphet (NP) | ✓ | ✓ | ✓ | ✓ | ✓ |
| LSTM | ✓ | ✓ | ✓ | — | — |
| XGBoost | — | — | — | ✓ | ✓ |

### Ensemble
Si ejecutas dos o más modelos, se activa el botón **⚡ Calcular Ensemble** que promedia los pronósticos.

### Exportar Excel
El botón **⬇ Exportar Excel** genera un fichero `.xlsx` con dos hojas:
- **Histórico**: serie histórica del CSV
- **Pronóstico [Modelo]**: pronóstico con intervalos de confianza, una hoja por modelo

## Estructura

```
ForecastSEPE/
├── scripts/          # Scripts de pronóstico (stubs en fase 1)
├── backend/          # FastAPI
│   └── main.py
├── frontend/         # UI
│   └── index.html
├── uploads/          # CSVs temporales (no versionar)
├── .env
├── requirements.txt
├── start.bat
└── CLAUDE.md         # Documentación de arquitectura para Claude Code
```

## Fase 2 — Modelos reales

Los scripts actuales en `scripts/` son **stubs** que generan datos sintéticos realistas para desarrollo y pruebas. En la fase 2 se implementarán:

- `forecast_ABC_*.py`: NeuralProphet real + LSTM vía scalecast
- `forecast_DE_*.py`: NeuralProphet real + XGBoost

El protocolo de comunicación (`PROGRESS:`, `RESULT:`, `ERROR:`) y la estructura de los ficheros no cambiarán, por lo que la arquitectura es directamente reutilizable.

## Entorno corporativo (Netskope SSL)

Si recibes errores SSL al instalar dependencias, usa:
```bash
pip install -r requirements.txt --trusted-host pypi.org --trusted-host files.pythonhosted.org
```
