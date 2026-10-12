#!/usr/bin/env python3
"""
forecast_ABCDE_estatal_TimesFM.py — Parados/Afiliados/Demandantes (grupo ABC)
y Contratos/P. Contratadas (grupo DE) · estatal · TimesFM 2.5 (recursivo)

Un único script para los dos grupos: backend/main.py registra las dos
entradas de SCRIPT_MAP (("abc","estatal","TimesFM") y ("de","estatal","TimesFM"))
apuntando aquí; el script decide internamente qué hiperparámetros usar según
el grupo de la métrica recibida (ver config.py: TIMESFM_ABC_ESTATAL_PARAMS /
TIMESFM_DE_ESTATAL_PARAMS).

Metodología completa (barrido de FT_CTX, log-transform, capas/lr, canal de
punto media/mediana) desarrollada y validada en
notebooks/forecast_ABCDE_estatal_TimesFM.ipynb.
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import TIMESFM_ABC_ESTATAL_PARAMS, TIMESFM_DE_ESTATAL_PARAMS

from _timesfm_common import run_timesfm_estatal_forecast

# Igual que ABC_METRICS/DE_METRICS en backend/main.py -- Contratos/P. Contratadas
# usan hiperparámetros distintos (log-transform, lr mayor) por sus oscilaciones
# estacionales mucho más extremas (ver TIMESFM_DE_ESTATAL_PARAMS en config.py).
DE_METRICS = {'contratos', 'p. contratadas'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--metrica',  required=True)
    parser.add_argument('--modelo',   default='TimesFM')
    parser.add_argument('--csv',      required=True)
    parser.add_argument('--atributo', default=None)
    parser.add_argument('--f_start',  type=str, default=None)
    parser.add_argument('--f_end',    type=str, default=None)
    args = parser.parse_args()

    try:
        metrica = args.metrica
        params = TIMESFM_DE_ESTATAL_PARAMS if metrica.strip().lower() in DE_METRICS else TIMESFM_ABC_ESTATAL_PARAMS

        # El checkpoint lo deja el instalador de ForecastSEPE v2 (no se descarga
        # aquí). Ruta configurable vía TIMESFM_MODEL_DIR en .env; por defecto,
        # relativa a la raíz del proyecto.
        model_dir = os.getenv('TIMESFM_MODEL_DIR') or str(
            Path(__file__).resolve().parent.parent / 'models' / 'timesfm-2.5-200m-pytorch'
        )

        result = run_timesfm_estatal_forecast(
            metrica=metrica,
            csv_path=args.csv,
            params=params,
            model_dir=model_dir,
            f_end_override=args.f_end,
        )
        print('RESULT:' + json.dumps(result, ensure_ascii=False), flush=True)

    except Exception as e:
        import traceback
        print(f'ERROR:{e}', flush=True)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
