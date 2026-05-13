#!/usr/bin/env python3
"""
forecast_DE_estatal_XGBoost.py — Contratos / P. Contratadas estatal — XGBoost
"""
import argparse
import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import XGBOOST_ESTATAL_PARAMS

import pandas as pd
import numpy as np
from sklearn.model_selection import ParameterGrid
from sklearn.metrics import mean_absolute_percentage_error, mean_absolute_error
from xgboost import XGBRegressor

warnings.filterwarnings('ignore')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--metrica',  required=True)
    parser.add_argument('--modelo',   default='XGBoost')
    parser.add_argument('--csv',      required=True)
    parser.add_argument('--atributo', default=None)
    parser.add_argument('--f_start',  type=str, default=None)
    parser.add_argument('--f_end',    type=str, default=None)
    args = parser.parse_args()

    try:
        # 1. CONFIGURACIÓN Y PREPARACIÓN DE DATOS
        # =========================================================================

        metrica = args.metrica

        train_months = XGBOOST_ESTATAL_PARAMS['cv']['train_months']
        val_months   = XGBOOST_ESTATAL_PARAMS['cv']['val_months']
        step_months  = XGBOOST_ESTATAL_PARAMS['cv']['step_months']
        REG_PARAMS   = XGBOOST_ESTATAL_PARAMS['reg']

        # Carga y ordenación cronológica
        df = pd.read_csv(args.csv, sep=';', na_values=["'-"])
        df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=True)
        df = df.sort_values(by='Fecha').reset_index(drop=True)

        # Feature engineering: XGBoost no es un modelo secuencial y no usa lags de la variable
        # objetivo. El único input son estas tres features temporales que capturan
        # estacionalidad (month, quarter) y tendencia de largo plazo (year).
        df['month']   = df['Fecha'].dt.month
        df['quarter'] = df['Fecha'].dt.quarter
        df['year']    = df['Fecha'].dt.year

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
        # max_depth: profundidad máxima de los árboles (más alto = más complejo)
        # learning_rate: tamaño del paso en el boosting (más bajo = más robusto, más lento)
        # n_estimators: número de árboles en el ensemble
        # colsample_bytree: fracción de features usadas por árbol (regularización implícita)
        param_grid = XGBOOST_ESTATAL_PARAMS['grid']
        grid = list(ParameterGrid(param_grid))
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

                # 3.1. Partir el histórico en entrenamiento y validación
                train_df = df.iloc[start : start + train_months].reset_index(drop=True)
                val_df   = df.iloc[start + train_months : start + train_months + val_months].reset_index(drop=True)

                print(f"  > Fold {fold}: "
                      f"Train {train_df['Fecha'].iloc[0].strftime('%Y-%m')} "
                      f"-> {train_df['Fecha'].iloc[-1].strftime('%Y-%m')} | "
                      f"Val {val_df['Fecha'].iloc[0].strftime('%Y-%m')} "
                      f"-> {val_df['Fecha'].iloc[-1].strftime('%Y-%m')}")

                # 3.2. Separar features y target; entrenar el fold
                X_train = train_df.drop(columns=['Fecha', metrica])
                y_train = train_df[metrica]
                X_valid = val_df.drop(columns=['Fecha', metrica])
                y_valid = val_df[metrica]

                m_fold = XGBRegressor(**params, **REG_PARAMS)
                m_fold.fit(X_train, y_train)

                # 3.3. Predicción directa sobre el periodo de validación
                preds     = m_fold.predict(X_valid)
                fold_mape = mean_absolute_percentage_error(y_valid, preds) * 100
                fold_mae  = mean_absolute_error(y_valid, preds)
                all_fold_mapes.append(fold_mape)
                all_fold_maes.append(fold_mae)
                print(f"    Fold {fold} - MAPE: {fold_mape:.2f}% | MAE: {fold_mae:,.0f} {metrica}")

                # 3.4. Avanzar la ventana
                start += step_months
                fold  += 1

            # 3.5. Métricas promedio de esta combinación
            current_mape = np.mean(all_fold_mapes)
            current_mae  = np.mean(all_fold_maes)
            print(f"\n  Promedio ({len(all_fold_mapes)} folds) - MAPE: {current_mape:.2f}% | MAE: {current_mae:,.0f} {metrica}")

            if current_mape < best_mape:
                best_mape   = current_mape
                best_mae    = current_mae
                best_params = params.copy()
                print(f"  *** Nuevo mejor modelo - MAPE: {best_mape:.2f}% | MAE: {best_mae:,.0f} {metrica} ***")

        print('\n========================================================')
        print('             OPTIMIZACIÓN FINALIZADA')
        print('========================================================')
        print(f'Mejor MAPE esperado ({HORIZONTE_MESES} meses): {best_mape:.2f}%')
        print(f'Mejor MAE esperado  ({HORIZONTE_MESES} meses): {best_mae:,.0f} {metrica}')
        print(f'Mejores hiperparámetros: {best_params}')

        # 5. ENTRENAMIENTO FINAL Y PRONÓSTICO
        # =========================================================================

        print(f'PROGRESS:62:Entrenando el modelo final con hiperparámetros óptimos sobre todo el histórico...', flush=True)

        X_train = df.drop(columns=['Fecha', metrica])
        y_train = df[metrica]

        m_final = XGBRegressor(**best_params, **REG_PARAMS)
        m_final.fit(X_train, y_train)

        print(f'PROGRESS:90:Generando pronóstico hasta {f_end} ({HORIZONTE_MESES} meses)...', flush=True)

        # Construir DataFrame de fechas futuras con sus features temporales.
        # IMPORTANTE: las features deben extraerse de df_futuro['Fecha'], no del histórico df,
        # para asignar los años/meses correctos al horizonte de pronóstico.
        df_futuro = pd.DataFrame({
            'Fecha': pd.date_range(
                start=UltimaFechaHistorico + pd.DateOffset(months=1),
                periods=HORIZONTE_MESES,
                freq='MS'
            )
        })
        df_futuro['month']   = df_futuro['Fecha'].dt.month
        df_futuro['quarter'] = df_futuro['Fecha'].dt.quarter
        df_futuro['year']    = df_futuro['Fecha'].dt.year
        df_futuro = df_futuro.set_index('Fecha')

        forecast = pd.DataFrame(
            m_final.predict(df_futuro),
            index=df_futuro.index,
            columns=[metrica]
        )

        # RESULT
        print('PROGRESS:96:Construyendo resultado...', flush=True)

        anio_inicio = df['Fecha'].iloc[0].year
        historico = [
            {'fecha': row['Fecha'].strftime('%Y-%m'), 'valor': round(float(row[metrica]))}
            for _, row in df.iterrows()
        ]
        pronostico = [
            {'fecha': d.strftime('%Y-%m'), 'valor': round(float(v))}
            for d, v in zip(forecast.index, forecast[metrica])
        ]

        result = {
            'metrica':              metrica,
            'modo':                 'estatal',
            'modelo':               'XGBoost',
            'atributo':             None,
            'anio_inicio':          anio_inicio,
            'historico':            historico,
            'pronostico':           pronostico,
            'intervalo_confianza':  None,
        }

        print('RESULT:' + json.dumps(result, ensure_ascii=False), flush=True)

    except Exception as e:
        import traceback
        print(f'ERROR:{e}', flush=True)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
