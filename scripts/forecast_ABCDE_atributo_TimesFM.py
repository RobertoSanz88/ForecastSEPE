#!/usr/bin/env python3
"""
forecast_ABCDE_atributo_TimesFM.py — Parados/Afiliados/Demandantes (grupo ABC)
y Contratos/P. Contratadas (grupo DE) · por atributo · TimesFM 2.5 (recursivo)

Un único script para los dos grupos, igual que forecast_ABCDE_estatal_TimesFM.py
-- decide internamente qué hiperparámetros usar según el grupo de la métrica
recibida (ver config.py: TIMESFM_ABC_ATRIBUTO_PARAMS / TIMESFM_DE_ATRIBUTO_PARAMS).

Metodología completa (grid FT_CTX x LOG_TRANSFORM por grupo, VAL_MONTHS=36)
desarrollada y validada en notebooks/forecast_ABCDE_atributo_TimesFM.ipynb.
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import TIMESFM_ABC_ATRIBUTO_PARAMS, TIMESFM_DE_ATRIBUTO_PARAMS

import pandas as pd

from _timesfm_common import run_timesfm_atributo_forecast

# Igual que en forecast_ABCDE_estatal_TimesFM.py -- Contratos/P. Contratadas
# usan hiperparámetros distintos (lr mayor, excepción de point_channel).
DE_METRICS = {'contratos', 'p. contratadas'}

# TimesFM cuesta mucho más por grupo que NP/LSTM/XGBoost (hasta 4 fine-tunings
# de un modelo de 200M parámetros por grupo, no un ajuste ligero) -- con más
# de 10 grupos la duración estimada superaría las 5 horas, así que el límite
# antes de pedir un rango es mucho más bajo que el de esos otros modelos (53).
MAX_GRUPOS = 10


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
        metrica  = args.metrica
        atributo = args.atributo or 'CCAA'
        params = TIMESFM_DE_ATRIBUTO_PARAMS if metrica.strip().lower() in DE_METRICS else TIMESFM_ABC_ATRIBUTO_PARAMS

        # encoding='latin1' por los caracteres especiales en nombres de provincias/CCAA;
        # na_values=["'-"] convierte el marcador SEPE de dato confidencial en NaN.
        df = pd.read_csv(args.csv, sep=';', encoding='latin1', na_values=["'-"])
        df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=True)
        df = df.sort_values('Fecha').reset_index(drop=True)

        # ── Comprobación de número de columnas ──────────────────────────────
        n_datos = len(df.columns) - 1  # excluir Fecha
        if n_datos > MAX_GRUPOS:
            print(
                f'INPUT_REQUIRED:rango:Hay {n_datos} columnas. TimesFM solo permite un máximo '
                f'de {MAX_GRUPOS} grupos por ejecución (con más columnas la duración estimada '
                f'superaría las 5 horas). Introduce el rango [inicio-fin] (ej: [1-{MAX_GRUPOS}]):',
                flush=True,
            )
            rango = input()
            inicio, fin = map(int, rango.strip('[]').split('-'))
            df = df[[df.columns[0]] + list(df.columns[inicio:fin + 1])]
            print(f'PROGRESS:7:Seleccionadas {fin - inicio + 1} columnas: '
                  f'"{df.columns[1]}" → "{df.columns[-1]}"', flush=True)

        grupos = list(df.columns[1:])
        for g in grupos:
            df[g] = pd.to_numeric(df[g], errors='coerce')

        print(f'PROGRESS:8:Cargados {len(df)} meses | {len(grupos)} grupos ({atributo})', flush=True)

        # El checkpoint lo deja el instalador de ForecastSEPE v2 (no se descarga
        # aquí). Ruta configurable vía TIMESFM_MODEL_DIR en .env; por defecto,
        # relativa a la raíz del proyecto.
        model_dir = os.getenv('TIMESFM_MODEL_DIR') or str(
            Path(__file__).resolve().parent.parent / 'models' / 'timesfm-2.5-200m-pytorch'
        )

        result = run_timesfm_atributo_forecast(
            metrica=metrica,
            atributo=atributo,
            df=df,
            grupos=grupos,
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
