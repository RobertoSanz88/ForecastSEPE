#!/usr/bin/env python3
"""
Reproduccion minima del Popen que hace backend/main.py, SIN FastAPI/uvicorn
de por medio -- para aislar si el cuelgue de TimesFM en la app es cosa de
Windows/Popen o de la maquinaria async/threading del backend.

Uso (con el MISMO python que arranca uvicorn, el de NP-LSTM-XGBoost):
    "<python de NP-LSTM-XGBoost>" scripts\\_debug_popen_repro.py "<python de timesfm_env>" "<csv>"

Ejemplo:
    "C:\\Users\\sgei044\\Miniconda3\\envs\\NP-LSTM-XGBoost\\python.exe" scripts\\_debug_popen_repro.py "C:\\Users\\sgei044\\timesfm_env\\python.exe" "Parados desde 2010 estatal.csv"
"""
import os
import subprocess
import sys
import time
from pathlib import Path

if len(sys.argv) < 3:
    print("Uso: _debug_popen_repro.py <python_timesfm_env> <csv>")
    sys.exit(1)

timesfm_python = sys.argv[1]
csv_path = sys.argv[2]
script_path = Path(__file__).parent / "forecast_ABCDE_estatal_TimesFM.py"

cmd = [
    timesfm_python, str(script_path.resolve()),
    "--metrica", "Parados",
    "--modelo", "TimesFM",
    "--csv", str(Path(csv_path).resolve()),
    "--f_end", "2029-12",
]
print("CMD:", cmd, flush=True)
print("Ejecutando con el mismo python que uvicorn:", sys.executable, flush=True)

_env = os.environ.copy()
_env["PYTHONIOENCODING"] = "utf-8"
_env.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

t0 = time.time()
proc = subprocess.Popen(
    cmd,
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    env=_env,
)
print(f"[{time.time()-t0:.1f}s] Popen lanzado, PID={proc.pid}. Leyendo stdout linea a linea...", flush=True)

while True:
    raw_line = proc.stdout.readline()
    if not raw_line:
        print(f"[{time.time()-t0:.1f}s] EOF en stdout (proceso terminado o pipe cerrado).", flush=True)
        break
    line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
    print(f"[{time.time()-t0:.1f}s] STDOUT> {line}", flush=True)

proc.wait()
print(f"[{time.time()-t0:.1f}s] returncode={proc.returncode}", flush=True)
stderr = proc.stderr.read().decode("utf-8", errors="replace")
if stderr:
    print("STDERR:\n" + stderr, flush=True)
