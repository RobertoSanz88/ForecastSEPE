#!/usr/bin/env python3
"""
forecast_ABC_estatal_LSTM.py — Parados / Afiliados / Demandantes estatal — LSTM (scalecast)
"""
import argparse
import json
import os
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import LSTM_ESTATAL_PARAMS

os.environ['TF_USE_LEGACY_KERAS'] = '1'

if sys.version_info < (3, 11):
    import typing
    from typing_extensions import Self, Unpack
    typing.Self = Self
    typing.Unpack = Unpack

import pandas as pd
import numpy as np
from sklearn.model_selection import ParameterGrid

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

        metrica = args.metrica

        train_months = LSTM_ESTATAL_PARAMS['cv']['train_months']
        val_months   = LSTM_ESTATAL_PARAMS['cv']['val_months']
        step_months  = LSTM_ESTATAL_PARAMS['cv']['step_months']

        # Carga, limpieza y ordenación cronológica
        df = pd.read_csv(args.csv, sep=';', na_values=["'-"])
        df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=True)
        df[metrica] = pd.to_numeric(df[metrica], errors='coerce')
        df = df.sort_values(by='Fecha').reset_index(drop=True)

        print(f'PROGRESS:8:Cargados {len(df)} meses de {metrica}', flush=True)

        # --- HORIZONTE DE PRONÓSTICO DINÁMICO ---
        import datetime as _dt
        now = _dt.datetime.now().year
        f_end = args.f_end if args.f_end else f'{now + 3}-12'
        FECHA_FIN_PRONOSTICO = pd.Timestamp(f_end + '-01')
        UltimaFechaHistorico = df['Fecha'].iloc[-1]
        HORIZONTE_MESES = (
            (FECHA_FIN_PRONOSTICO.year  - UltimaFechaHistorico.year)  * 12 +
            (FECHA_FIN_PRONOSTICO.month - UltimaFechaHistorico.month)
        )
        print(f"Último dato: {UltimaFechaHistorico.strftime('%Y-%m')}. "
              f"Horizonte de pronóstico: {HORIZONTE_MESES} meses (hasta {f_end}).")

        # --- ESPACIO DE BÚSQUEDA DE HIPERPARÁMETROS ---
        # lags: 2=corto plazo; 12=captura el ciclo anual completo; 18=año y medio
        #   (para Afiliados, 12 lags suele ser el óptimo por la fuerte estacionalidad)
        # units: tamaño de la capa LSTM (más unidades = más capacidad, más riesgo de sobreajuste)
        # epochs: iteraciones de entrenamiento sobre los datos
        lstm_params = LSTM_ESTATAL_PARAMS['grid']
        grid = list(ParameterGrid(lstm_params))
        print(f'Total de combinaciones a evaluar: {len(grid)}')

        # 3. OPTIMIZACIÓN DE HIPERPARÁMETROS (Grid Search con CV Manual)
        # ==================================================================================

        print(f'PROGRESS:10:Iniciando optimización de hiperparámetros ({len(grid)} combinaciones)...', flush=True)

        best_mape   = float('inf')
        best_mae    = float('inf')
        best_params = {}

        for ci, params in enumerate(grid):
            pct = 10 + int(ci / len(grid) * 52)
            print(f'PROGRESS:{pct}:Combinación {ci + 1}/{len(grid)}: {params}', flush=True)
            print(f'\n--- Modelo {ci + 1}/{len(grid)}: {params} ---')

            start          = 0
            fold           = 1
            all_fold_mapes = []
            all_fold_maes  = []

            # Ventana rodante: avanza step_months en cada iteración
            while start + train_months + val_months <= len(df):

                # 3.1. Seleccionar la ventana completa (train + val);
                #      scalecast reserva internamente los últimos val_months como test set
                trainval_df = df.iloc[start : start + train_months + val_months].reset_index(drop=True)

                print(f"  > Fold {fold}: "
                      f"{trainval_df['Fecha'].iloc[0].strftime('%Y-%m')} → "
                      f"{trainval_df['Fecha'].iloc[-1].strftime('%Y-%m')}")

                # 3.2. Configurar el Forecaster para este fold
                f = Forecaster(
                    y            = trainval_df[metrica],
                    current_dates= trainval_df['Fecha'],
                    future_dates = val_months,
                    test_length  = val_months,
                    metrics      = ['mae', 'mse', 'mape']
                )

                def forecaster(f):
                    f.add_ar_terms(params['lags'])
                    f.set_estimator('rnn')
                    f.manual_forecast(
                        layers_struct= [('LSTM', {'units': params['units'], 'activation': 'tanh'})],
                        epochs       = params['epochs'],
                        call_me      = 'lstm',
                    )

                # Pipeline de transformaciones previas al LSTM:
                # 1. DetrendTransform (poly_order=2): elimina la tendencia cuadrática de la serie.
                #    El LSTM aprende mejor patrones estacionarios; la tendencia la captura la regresión polinómica.
                # 2. DeseasonTransform: elimina la estacionalidad anual residual.
                #    El orden importa: primero detrend, luego deseason.
                # El Reverter aplica las transformaciones en orden inverso tras el pronóstico.
                transformer = Transformer(
                    transformers=[
                        ('DetrendTransform', {'poly_order': 2}),
                        'DeseasonTransform',
                    ],
                )

                reverter = Reverter(
                    reverters       = ['DeseasonRevert', 'DetrendRevert'],
                    base_transformer= transformer,
                )

                pipeline = Pipeline(
                    steps=[
                        ('Transform', transformer),
                        ('Forecast',  forecaster),
                        ('Revert',    reverter),
                    ]
                )

                f        = pipeline.fit_predict(f)
                exportado= f.export()

                # 3.3. Métricas del fold (TestSet = los últimos val_months de la ventana)
                fold_mape = exportado['model_summaries']['TestSetMAPE'].values[0] * 100
                fold_mae  = exportado['model_summaries']['TestSetMAE'].values[0]
                all_fold_mapes.append(fold_mape)
                all_fold_maes.append(fold_mae)
                print(f"    Fold {fold} — MAPE: {fold_mape:.2f}% | MAE: {fold_mae:,.0f} {metrica}")

                # 3.4. Avanzar la ventana
                start += step_months
                fold  += 1

            # 3.5. Métricas promedio de esta combinación
            current_mape = np.mean(all_fold_mapes)
            current_mae  = np.mean(all_fold_maes)
            print(f"\n  Promedio ({len(all_fold_mapes)} folds) — MAPE: {current_mape:.2f}% | MAE: {current_mae:,.0f} {metrica}")

            if current_mape < best_mape:
                best_mape   = current_mape
                best_mae    = current_mae
                best_params = params.copy()
                print(f"  *** Nuevo mejor modelo — MAPE: {best_mape:.2f}% | MAE: {best_mae:,.0f} {metrica} ***")

        print('\n========================================================')
        print('             OPTIMIZACIÓN FINALIZADA')
        print('========================================================')
        print(f'Mejor MAPE esperado ({HORIZONTE_MESES} meses): {best_mape:.2f}%')
        print(f'Mejor MAE esperado  ({HORIZONTE_MESES} meses): {best_mae:,.0f} {metrica}')
        print(f'Mejores hiperparámetros: {best_params}')

        # 5. ENTRENAMIENTO FINAL Y PRONÓSTICO
        # =========================================================================

        print(f'PROGRESS:62:Entrenando el modelo final con hiperparámetros óptimos sobre todo el histórico...', flush=True)

        # test_length=0: el LSTM final entrena sobre TODOS los datos históricos.
        # El MAPE esperado se reporta desde la CV (best_mape), no desde este modelo.
        f = Forecaster(
            y            = df[metrica],
            current_dates= df['Fecha'],
            future_dates = HORIZONTE_MESES,
            test_length  = 0,
            metrics      = ['mae', 'mse', 'mape']
        )

        def forecaster(f):
            f.add_ar_terms(best_params['lags'])
            f.set_estimator('rnn')
            f.manual_forecast(
                layers_struct= [('LSTM', {'units': best_params['units'], 'activation': 'tanh'})],
                epochs       = best_params['epochs'],
                call_me      = 'lstm',
            )

        transformer = Transformer(
            transformers=[
                ('DetrendTransform', {'poly_order': 2}),
                'DeseasonTransform',
            ],
        )

        reverter = Reverter(
            reverters       = ['DeseasonRevert', 'DetrendRevert'],
            base_transformer= transformer,
        )

        pipeline = Pipeline(
            steps=[
                ('Transform', transformer),
                ('Forecast',  forecaster),
                ('Revert',    reverter),
            ]
        )

        f        = pipeline.fit_predict(f)
        exportado= f.export()

        # lvl_fcsts contiene las predicciones en escala original (nivel),
        # tras revertir las transformaciones de detrend y deseason
        predictions = pd.DataFrame(exportado['lvl_fcsts']).set_index('DATE')
        predictions.rename_axis('Fecha', axis='index', inplace=True)

        # RESULT
        print('PROGRESS:96:Construyendo resultado...', flush=True)

        anio_inicio = df['Fecha'].iloc[0].year
        historico = [
            {'fecha': row['Fecha'].strftime('%Y-%m'), 'valor': round(float(row[metrica])) if pd.notna(row[metrica]) else None}
            for _, row in df.iterrows()
        ]
        pronostico = [
            {'fecha': d.strftime('%Y-%m'), 'valor': round(float(v))}
            for d, v in zip(predictions.index, predictions['lstm'])
        ]

        result = {
            'metrica':             metrica,
            'modo':                'estatal',
            'modelo':              'LSTM',
            'atributo':            None,
            'anio_inicio':         anio_inicio,
            'historico':           historico,
            'pronostico':          pronostico,
            'intervalo_confianza': None,
            'mape':                round(float(best_mape), 2),
        }

        print('RESULT:' + json.dumps(result, ensure_ascii=False), flush=True)

    except Exception as e:
        import traceback
        print(f'ERROR:{e}', flush=True)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
