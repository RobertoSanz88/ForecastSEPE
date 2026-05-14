#!/usr/bin/env python3
"""
forecast_ABC_atributo_LSTM.py — Parados/Afiliados/Demandantes por AtributoX — LSTM (scalecast)
"""
import argparse
import json
import os
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import LSTM_ATRIBUTO_PARAMS

os.environ['TF_USE_LEGACY_KERAS'] = '1'

if sys.version_info < (3, 11):
    import typing
    from typing_extensions import Self, Unpack
    typing.Self = Self
    typing.Unpack = Unpack

import math
import pandas as pd
import numpy as np
from sklearn.model_selection import ParameterGrid
from sklearn.metrics import mean_absolute_percentage_error, mean_absolute_error

from scalecast.Forecaster import Forecaster
from scalecast.Pipeline import Transformer, Reverter, Pipeline

warnings.filterwarnings('ignore')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--metrica',  required=True)
    parser.add_argument('--modelo',   default='LSTM')
    parser.add_argument('--csv',      required=True)
    parser.add_argument('--atributo', default=None)
    parser.add_argument('--f_start',  type=str, default=None)
    parser.add_argument('--f_end',    type=str, default=None)
    args = parser.parse_args()

    try:
        # 1. CONFIGURACIÓN Y PREPARACIÓN DE DATOS
        # =========================================================================

        metrica  = args.metrica
        atributo = args.atributo or 'CCAA'

        EPOCHS     = LSTM_ATRIBUTO_PARAMS['epochs']
        lstm_grid  = LSTM_ATRIBUTO_PARAMS['grid']

        df = pd.read_csv(args.csv, sep=';', encoding='latin1')
        df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=True)

        MAX_GRUPOS = 53
        n_datos = len(df.columns) - 1  # excluir Fecha
        if n_datos > MAX_GRUPOS:
            print(f'INPUT_REQUIRED:rango:Hay {n_datos} columnas. Introduce el rango [inicio-fin] (ej: [1-{MAX_GRUPOS}]):', flush=True)
            rango = input()
            inicio, fin = map(int, rango.strip('[]').split('-'))
            df = df[[df.columns[0]] + list(df.columns[inicio:fin + 1])]
            print(f'PROGRESS:7:Seleccionadas {fin - inicio + 1} columnas: "{df.columns[1]}" → "{df.columns[-1]}"', flush=True)

        df_new = df.set_index('Fecha', drop=True).sort_index()

        grupos = df_new.columns
        print(f'PROGRESS:8:Cargados {len(df_new)} meses | {len(grupos)} grupos ({atributo})', flush=True)

        # --- HORIZONTE DE PRONÓSTICO DINÁMICO ---
        import datetime as _dt
        now = _dt.datetime.now().year
        f_end = args.f_end if args.f_end else f'{now + 3}-12'
        FECHA_FIN_PRONOSTICO = pd.Timestamp(f_end + '-01')
        UltimaFechaHistorico = df_new.index[-1]
        HORIZONTE_MESES = (
            (FECHA_FIN_PRONOSTICO.year  - UltimaFechaHistorico.year)  * 12 +
            (FECHA_FIN_PRONOSTICO.month - UltimaFechaHistorico.month)
        )
        ultimo_str = UltimaFechaHistorico.strftime('%Y-%m')
        print(f'Último dato: {ultimo_str}. Horizonte de pronóstico: {HORIZONTE_MESES} meses (hasta {f_end}).')

        val_months = 12
        print(f'Validación: últimos {val_months} meses | Entrenamiento final: todos los datos')

        # --- ESPACIO DE BÚSQUEDA DE HIPERPARÁMETROS ---
        grid = list(ParameterGrid(lstm_grid))
        print(f'Combinaciones a evaluar por grupo: {len(grid)}')
        print(f'Total de modelos (grid x grupos): {len(grid) * len(grupos)}')

        # 2. OPTIMIZACIÓN DE HIPERPARÁMETROS
        # ==================================================================================

        n_grupos = len(grupos)
        print(f'PROGRESS:10:Iniciando optimización de hiperparámetros para {n_grupos} grupos...', flush=True)

        best_params       = {}
        mape_valid_values = {}
        mae_valid_values  = {}
        forecasts_valid   = {}

        for gi, grupo in enumerate(grupos):
            pct = 10 + int(gi / n_grupos * 50)
            print(f'PROGRESS:{pct}:Optimizando HP — {grupo} ({gi + 1}/{n_grupos})', flush=True)

            serie = df_new[grupo]

            best_mape_grupo   = float('inf')
            best_mae_grupo    = float('inf')
            best_params_grupo = {}
            best_val_series   = None

            for i, p in enumerate(grid, start=1):

                def forecaster(f, p=p):
                    f.add_ar_terms(p['lags'])
                    f.set_estimator('rnn')
                    f.manual_forecast(
                        layers_struct= [('LSTM', {'units': p['units'], 'activation': 'tanh', 'dropout': p['dropout']})],
                        epochs       = EPOCHS,
                        verbose      = 0,
                        call_me      = 'lstm',
                    )

                f = Forecaster(
                    y            = serie,
                    current_dates= df_new.index,
                    future_dates = val_months,
                    test_length  = val_months,
                    metrics      = ['mae', 'mse', 'mape'],
                )

                transformer = Transformer(
                    transformers=[('DetrendTransform', {'poly_order': 2}), 'DeseasonTransform'],
                )
                reverter = Reverter(
                    reverters       = ['DeseasonRevert', 'DetrendRevert'],
                    base_transformer= transformer,
                )
                pipeline = Pipeline(steps=[
                    ('Transform', transformer),
                    ('Forecast',  forecaster),
                    ('Revert',    reverter),
                ])

                f        = pipeline.fit_predict(f)
                exportado= f.export()

                mape = exportado['model_summaries']['TestSetMAPE'].values[0] * 100
                mae  = exportado['model_summaries']['TestSetMAE'].values[0]
                print(f'  [{grupo}] Combinación {i}/{len(grid)}: {p} — MAPE: {mape:.2f}%')

                if mape < best_mape_grupo:
                    best_mape_grupo   = mape
                    best_mae_grupo    = mae
                    best_params_grupo = p.copy()
                    val_df = pd.DataFrame(exportado['lvl_fcsts'])
                    val_df['DATE'] = pd.to_datetime(val_df['DATE'])
                    best_val_series = val_df.set_index('DATE')['lstm']

            best_params[grupo]       = best_params_grupo
            mape_valid_values[grupo] = best_mape_grupo
            mae_valid_values[grupo]  = best_mae_grupo
            forecasts_valid[grupo]   = best_val_series
            print(f'>>> Grupo completado: {grupo} — Mejor MAPE: {best_mape_grupo:.2f}% | Params: {best_params_grupo}\n')

        mean_mape_valid = pd.Series(mape_valid_values).mean()
        mean_mae_valid  = pd.Series(mae_valid_values).mean()
        print(f'MAPE medio VALID ({atributo}): {mean_mape_valid:.2f}%')
        print(f'MAE  medio VALID ({atributo}): {mean_mae_valid:,.0f} {metrica}')

        # 6. ENTRENAMIENTO FINAL Y PRONÓSTICO
        # ==================================================================================

        print(f'PROGRESS:62:Entrenando {n_grupos} modelos finales con hiperparámetros óptimos...', flush=True)

        forecasts_results_lstm = {}

        for i, grupo in enumerate(grupos, start=1):
            pct = 62 + int(i / n_grupos * 33)
            print(f'PROGRESS:{pct}:Entrenando modelo final — {grupo} ({i}/{n_grupos})', flush=True)

            serie = df_new[grupo]
            bp    = best_params[grupo]

            def forecaster(f, bp=bp):
                f.add_ar_terms(bp['lags'])
                f.set_estimator('rnn')
                f.manual_forecast(
                    layers_struct= [('LSTM', {'units': bp['units'], 'activation': 'tanh', 'dropout': bp['dropout']})],
                    epochs       = EPOCHS,
                    verbose      = 0,
                    call_me      = 'lstm',
                )

            f = Forecaster(
                y            = serie,
                current_dates= df_new.index,
                future_dates = HORIZONTE_MESES,
                test_length  = 0,
                metrics      = ['mae', 'mse', 'mape'],
            )

            transformer = Transformer(
                transformers=[('DetrendTransform', {'poly_order': 2}), 'DeseasonTransform'],
            )
            reverter = Reverter(
                reverters       = ['DeseasonRevert', 'DetrendRevert'],
                base_transformer= transformer,
            )
            pipeline = Pipeline(steps=[
                ('Transform', transformer),
                ('Forecast',  forecaster),
                ('Revert',    reverter),
            ])

            f        = pipeline.fit_predict(f)
            exportado= f.export()

            fcast_df = pd.DataFrame(exportado['lvl_fcsts'])
            fcast_df['DATE'] = pd.to_datetime(fcast_df['DATE'])
            forecasts_results_lstm[grupo] = fcast_df.set_index('DATE')['lstm']

            print(f'Grupo {i}/{n_grupos} ({grupo}) completado')

        # RESULT
        print('PROGRESS:96:Construyendo resultado...', flush=True)

        anio_inicio = df_new.index[0].year
        series_out = {}
        for grupo in grupos:
            historico = [
                {'fecha': d.strftime('%Y-%m'), 'valor': round(float(v))}
                for d, v in zip(df_new.index, df_new[grupo])
            ]
            pronostico = [
                {'fecha': d.strftime('%Y-%m'), 'valor': round(float(v))}
                for d, v in zip(
                    forecasts_results_lstm[grupo].index,
                    forecasts_results_lstm[grupo].values,
                )
            ]
            series_out[grupo] = {
                'historico':  historico,
                'pronostico': pronostico,
                'intervalo_confianza': None,
            }

        result = {
            'metrica':     metrica,
            'modo':        'atributo',
            'modelo':      'LSTM',
            'atributo':    atributo,
            'anio_inicio': anio_inicio,
            'series':      series_out,
            'mape':        round(float(mean_mape_valid), 2),
        }

        print('RESULT:' + json.dumps(result, ensure_ascii=False), flush=True)

    except Exception as e:
        import traceback
        print(f'ERROR:{e}', flush=True)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
