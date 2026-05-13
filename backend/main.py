import asyncio
import csv
import io
import json
import logging
import os
import re
import subprocess
import sys
import threading
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import openpyxl
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger("forecastsepe")

load_dotenv()

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
SCRIPTS_DIR = Path(os.getenv("SCRIPTS_DIR", "scripts"))
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))
FRONTEND_DIR = Path("frontend")

UPLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI(title="ForecastSEPE")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ABC_METRICS = {"parados", "afiliados", "demandantes"}
DE_METRICS  = {"contratos", "p. contratadas"}

# (grupo, modo, modelo) → script filename
SCRIPT_MAP = {
    ("abc", "estatal",   "NP"):      "forecast_ABC_estatal_NP.py",
    ("abc", "estatal",   "LSTM"):    "forecast_ABC_estatal_LSTM.py",
    ("abc", "atributo",  "NP"):      "forecast_ABC_atributo_NP.py",
    ("abc", "atributo",  "LSTM"):    "forecast_ABC_atributo_LSTM.py",
    ("de",  "estatal",   "NP"):      "forecast_DE_estatal_NP.py",
    ("de",  "estatal",   "XGBoost"): "forecast_DE_estatal_XGBoost.py",
    ("de",  "atributo",  "NP"):      "forecast_DE_atributo_NP.py",
    ("de",  "atributo",  "XGBoost"): "forecast_DE_atributo_XGBoost.py",
}

# Jobs en curso esperando input del usuario: job_id → {"event": Event, "value": list}
_active_jobs: dict = {}


# ── helpers ────────────────────────────────────────────────────────────────────

def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def get_metric_group(metrica: str) -> str:
    m = metrica.lower().strip()
    if m in ABC_METRICS:
        return "abc"
    if m in DE_METRICS:
        return "de"
    raise ValueError(f"Métrica desconocida: {metrica}")


def read_last_csv_date(csv_path: Path) -> Optional[str]:
    """Return the last non-empty Fecha value as 'YYYY-MM', or None."""
    last_date = None
    try:
        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                fecha = (row.get("Fecha") or row.get("fecha") or "").strip()
                if fecha:
                    m = re.match(r"(\d{4}-\d{2})", fecha)
                    if m:
                        last_date = m.group(1)
    except Exception:
        pass
    return last_date


def next_month_str(ym: str) -> str:
    """Given 'YYYY-MM', return the following month as 'YYYY-MM'."""
    year, month = int(ym[:4]), int(ym[5:7])
    month += 1
    if month > 12:
        month = 1
        year += 1
    return f"{year:04d}-{month:02d}"


def parse_csv_filename(filename: str) -> dict:
    name = filename[:-4] if filename.lower().endswith(".csv") else filename
    pattern = r"^(.+?)\s+desde\s+(\d{4})\s+(estatal|por\s+(.+?))$"
    m = re.match(pattern, name, re.IGNORECASE)
    if not m:
        raise ValueError(
            f'Nombre no reconocido: "{filename}". '
            f'Formato: "Métrica desde AAAA estatal.csv" '
            f'o "Métrica desde AAAA por Atributo.csv"'
        )
    metrica    = m.group(1).strip()
    anio_inicio = int(m.group(2))
    modo_raw   = m.group(3).lower().strip()
    atributo   = m.group(4).strip() if m.group(4) else None
    modo       = "estatal" if modo_raw == "estatal" else "atributo"
    grupo      = get_metric_group(metrica)
    return {
        "metrica":    metrica,
        "anio_inicio": anio_inicio,
        "modo":       modo,
        "atributo":   atributo,
        "grupo":      grupo,
    }


# ── SSE streaming ──────────────────────────────────────────────────────────────

async def _stream_forecast(cmd: list):
    """
    Async generator que ejecuta el script en un thread y emite SSE.
    Soporta el protocolo INPUT_REQUIRED para columnas interactivas.
    """
    loop = asyncio.get_event_loop()
    q: asyncio.Queue = asyncio.Queue()
    job_id = str(uuid.uuid4())
    input_event = threading.Event()
    input_value_holder: list = []
    _active_jobs[job_id] = {"event": input_event, "value": input_value_holder}

    def emit(event: dict) -> None:
        loop.call_soon_threadsafe(q.put_nowait, event)

    def run_script() -> None:
        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            while True:
                raw_line = proc.stdout.readline()
                if not raw_line:
                    break
                line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                if not line:
                    continue

                if line.startswith("PROGRESS:"):
                    parts = line.split(":", 2)
                    pct = int(parts[1]) if len(parts) > 1 else 0
                    msg = parts[2] if len(parts) > 2 else ""
                    emit({"type": "progress", "percent": pct, "message": msg})

                elif line.startswith("RESULT:"):
                    try:
                        data = json.loads(line[7:])
                        emit({"type": "result", "data": data})
                    except json.JSONDecodeError as e:
                        emit({"type": "error", "message": f"JSON inválido en RESULT: {e}"})

                elif line.startswith("ERROR:"):
                    emit({"type": "error", "message": line[6:].strip()})

                elif line.startswith("INPUT_REQUIRED:"):
                    parts = line.split(":", 2)
                    input_type = parts[1] if len(parts) > 1 else "text"
                    prompt     = parts[2] if len(parts) > 2 else "Introduce un valor:"
                    emit({"type": "input_required", "job_id": job_id,
                          "input_type": input_type, "prompt": prompt})
                    # Espera con keepalives cada 20 s para que el SSE no caduque
                    max_wait_s = 300
                    elapsed    = 0
                    while not input_event.wait(timeout=20) and elapsed < max_wait_s:
                        emit({"type": "keepalive"})
                        elapsed += 20
                    if input_value_holder:
                        proc.stdin.write((input_value_holder[0] + "\n").encode("utf-8"))
                        proc.stdin.flush()
                    else:
                        proc.terminate()
                        emit({"type": "error",
                              "message": "Timeout esperando el rango de columnas del usuario."})
                        emit({"type": "done"})
                        return
                    input_event.clear()
                    input_value_holder.clear()

            proc.wait()
            if proc.returncode != 0:
                stderr = proc.stderr.read().decode("utf-8", errors="replace")[:500]
                emit({"type": "error",
                      "message": f"Error en script (código {proc.returncode}): {stderr}"})
            emit({"type": "done"})
        except Exception as e:
            logger.error("Error en run_script:\n%s", traceback.format_exc())
            emit({"type": "error", "message": str(e)})
            emit({"type": "done"})
        finally:
            _active_jobs.pop(job_id, None)

    thread = threading.Thread(target=run_script, daemon=True)
    thread.start()

    while True:
        try:
            event = await asyncio.wait_for(q.get(), timeout=300.0)
        except asyncio.TimeoutError:
            yield _sse({"type": "error", "message": "Timeout: el script tardó demasiado."})
            break
        yield _sse(event)
        if event["type"] in ("done", "error"):
            break

    thread.join(timeout=5)


# ── routes ─────────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    html_path = FRONTEND_DIR / "index.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Frontend no encontrado")
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    try:
        metadata = parse_csv_filename(file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    temp_path = UPLOAD_DIR / f"{uuid.uuid4()}.csv"
    temp_path.write_bytes(await file.read())

    now   = datetime.now().year
    f_end = f"{now + 3}-12"
    last_date = read_last_csv_date(temp_path)
    f_start   = next_month_str(last_date) if last_date else f"{now + 1}-01"

    return {
        "csv_path": str(temp_path),
        "filename": file.filename,
        "f_start":  f_start,
        "f_end":    f_end,
        **metadata,
    }


@app.get("/run-forecast")
async def run_forecast(
    metrica:  str = Query(...),
    modo:     str = Query(...),
    modelo:   str = Query(...),
    csv_path: str = Query(...),
    atributo: Optional[str] = Query(None),
):
    try:
        grupo = get_metric_group(metrica)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    script_name = SCRIPT_MAP.get((grupo, modo, modelo))
    if not script_name:
        raise HTTPException(status_code=400,
                            detail=f"No hay script para {grupo}/{modo}/{modelo}")

    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        raise HTTPException(status_code=500,
                            detail=f"Script no encontrado: {script_name}")

    csv_file = Path(csv_path)
    if not csv_file.exists():
        raise HTTPException(status_code=400, detail="CSV no encontrado en el servidor")

    now   = datetime.now().year
    f_end = f"{now + 3}-12"
    last_date = read_last_csv_date(csv_file)
    f_start   = next_month_str(last_date) if last_date else f"{now + 1}-01"

    cmd = [
        sys.executable, str(script_path.resolve()),
        "--metrica", metrica,
        "--modelo",  modelo,
        "--csv",     str(csv_file.resolve()),
        "--f_start", f_start,
        "--f_end",   f_end,
    ]
    if atributo:
        cmd += ["--atributo", atributo]

    return StreamingResponse(
        _stream_forecast(cmd),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


class ProvideInputRequest(BaseModel):
    job_id: str
    value:  str


@app.post("/provide-input")
async def provide_input(req: ProvideInputRequest):
    job = _active_jobs.get(req.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado o expirado")
    job["value"].append(req.value)
    job["event"].set()
    return {"ok": True}


class CleanupRequest(BaseModel):
    csv_path: str


@app.post("/cleanup-csv")
async def cleanup_csv(req: CleanupRequest):
    try:
        p = Path(req.csv_path)
        upload_root = str(UPLOAD_DIR.resolve())
        if p.exists() and str(p.resolve()).startswith(upload_root):
            p.unlink(missing_ok=True)
    except Exception:
        pass
    return {"ok": True}


class ForecastSerie(BaseModel):
    modelo: str
    pronostico: list
    ic_superior: Optional[list] = None
    ic_inferior: Optional[list] = None


class ExportRequest(BaseModel):
    metrica:   str
    modo:      str
    atributo:  Optional[str] = None
    historico: list
    series:    list[ForecastSerie]


@app.post("/export-excel")
async def export_excel(req: ExportRequest):
    wb = openpyxl.Workbook()

    ws_h = wb.active
    ws_h.title = "Histórico"
    ws_h.append(["Fecha", req.metrica])
    for r in req.historico:
        ws_h.append([r.get("fecha"), r.get("valor")])

    for serie in req.series:
        safe_name = re.sub(r"[\\/*?:\[\]]", "_", serie.modelo)[:31]
        ws_p = wb.create_sheet(f"Pronóstico {safe_name}")
        headers = ["Fecha", req.metrica]
        if serie.ic_superior:
            headers += ["IC Superior", "IC Inferior"]
        ws_p.append(headers)
        for i, r in enumerate(serie.pronostico):
            row = [r.get("fecha"), r.get("valor")]
            if serie.ic_superior and i < len(serie.ic_superior):
                row.append(serie.ic_superior[i].get("valor"))
            if serie.ic_inferior and i < len(serie.ic_inferior):
                row.append(serie.ic_inferior[i].get("valor"))
            ws_p.append(row)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    safe_metrica = re.sub(r"[^\w]", "_", req.metrica)
    modelos_str  = "_".join(s.modelo for s in req.series)
    filename     = f"Pronostico_{safe_metrica}_{modelos_str}.xlsx"

    return Response(
        content=buf.read(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=HOST, port=PORT, reload=False)
