#!/usr/bin/env python3
"""
forecast_ABC_estatal_NP.py — Parados / Afiliados / Demandantes estatal — NeuralProphet
"""
import argparse
import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import NP_ABC_ESTATAL_PARAMS

import pandas as pd
import numpy as np
from sklearn.model_selection import ParameterGrid
from sklearn.metrics import mean_absolute_percentage_error, mean_absolute_error
from neuralprophet import NeuralProphet, set_log_level, set_random_seed

warnings.filterwarnings('ignore')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--metrica',  required=True)
    parser.add_argument('--modelo',   default='NP')
    parser.add_argument('--csv',      required=True)
    parser.add_argument('--atributo', default=None)
    parser.add_argument('--f_start',  type=str, default=None)
    parser.add_argument('--f_end',    type=str, default=None)
    args = parser.parse_args()

    try:
        # 1. CONFIGURACIÓN Y PREPARACIÓN DE DATOS
        # =========================================================================
        set_log_level('ERROR')
        set_random_seed(11)

        metrica = args.metrica

        train_months = NP_ABC_ESTATAL_PARAMS['cv']['train_months']
        val_months   = NP_ABC_ESTATAL_PARAMS['cv']['val_months']
        step_months  = NP_ABC_ESTATAL_PARAMS['cv']['step_months']

        # Carga y limpieza: NeuralProphet requiere columnas 'ds' (fecha) e 'y' (valor)
        df = pd.read_csv(args.csv, sep=';', na_values=["'-"])
        df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=True)
        df_np = df.rename(columns={'Fecha': 'ds', metrica: 'y'})
        df_np['y'] = pd.to_numeric(df_np['y'], errors='coerce')
        df_np = df_np.sort_values(by='ds').reset_index(drop=True)

        # Parámetros fijos del modelo
        NLAGS     = NP_ABC_ESTATAL_PARAMS['nlags']
        FREQ_DATA = 'MS'

        print(f'PROGRESS:8:Cargados {len(df_np)} meses de {metrica}', flush=True)

        # --- HORIZONTE DE PRONÓSTICO DINÁMICO ---
        import datetime as _dt
        now = _dt.datetime.now().year
        f_end = args.f_end if args.f_end else f'{now + 3}-12'
        FECHA_FIN_PRONOSTICO = pd.Timestamp(f_end + '-01')
        UltimaFechaHistorico = df_np['ds'].iloc[-1]
        HORIZONTE_MESES = (
            (FECHA_FIN_PRONOSTICO.year  - UltimaFechaHistorico.year)  * 12 +
            (FECHA_FIN_PRONOSTICO.month - UltimaFechaHistorico.month)
        )
        print(f"Último dato: {UltimaFechaHistorico.strftime('%Y-%m')}. "
              f"Horizonte de pronóstico: {HORIZONTE_MESES} meses (hasta {f_end}).")

        # --- ESPACIO DE BÚSQUEDA DE HIPERPARÁMETROS ---
        # growth: 'linear' para tendencia continua; 'discontinuous' permite saltos bruscos
        #   (útil para capturar shocks como el COVID-19 en la serie de parados)
        # n_changepoints: número de puntos de cambio de tendencia (más = más flexible)
        # seasonality_mode: 'additive' cuando la amplitud estacional es constante;
        #   'multiplicative' cuando crece o decrece proporcionalmente al nivel de la serie
        param_grid = NP_ABC_ESTATAL_PARAMS['grid']
        grid = list(ParameterGrid(param_grid))
        print(f'Total de combinaciones a evaluar: {len(grid)}')

        # 2. FUNCIÓN DE PREDICCIÓN RECURSIVA
        # =========================================================================

        def recursive_predict_np(model: NeuralProphet, df_history: pd.DataFrame, periods: int) -> pd.DataFrame:
            """
            Genera un pronóstico recursivo mes a mes con un modelo NeuralProphet con retardos.
            """
            n_lags    = model.n_lags
            last_date = df_history['ds'].iloc[-1]
            # Ventana deslizante con los últimos n_lags valores (reales al inicio, predichos después)
            recent_history = df_history.tail(n_lags)[['ds', 'y']].copy()

            rows = []
            for _ in range(periods):
                next_date = last_date + pd.DateOffset(months=1)

                # Añadir el paso futuro con y=None para que NeuralProphet genere la predicción
                df_step       = pd.DataFrame({'ds': [next_date], 'y': [None]})
                df_to_predict = pd.concat([recent_history, df_step], ignore_index=True)

                forecast_step = model.predict(df_to_predict)
                y_predicted   = forecast_step['yhat1'].iloc[-1]
                rows.append({'ds': next_date, 'yhat1': y_predicted})

                # Actualizar la ventana: descartar el más antiguo, añadir el recién predicho
                new_lag        = pd.DataFrame({'ds': [next_date], 'y': [y_predicted]})
                recent_history = pd.concat([recent_history.iloc[1:], new_lag], ignore_index=True)
                last_date      = next_date

            return pd.DataFrame(rows)

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
            while start + train_months + val_months <= len(df_np):

                # 3.1. Partir el histórico en entrenamiento y validación
                train_df = df_np.iloc[start : start + train_months].reset_index(drop=True)
                val_df   = df_np.iloc[start + train_months : start + train_months + val_months].reset_index(drop=True)

                print(f"  > Fold {fold}: "
                      f"Train {train_df['ds'].iloc[0].strftime('%Y-%m')} → {train_df['ds'].iloc[-1].strftime('%Y-%m')} | "
                      f"Val {val_df['ds'].iloc[0].strftime('%Y-%m')} → {val_df['ds'].iloc[-1].strftime('%Y-%m')}")

                # 3.2. Entrenar fold — epochs en modo automático (coherente con el modelo final)
                m_fold = NeuralProphet(
                    **params,
                    yearly_seasonality=True,
                    weekly_seasonality=False,
                    daily_seasonality=False,
                    n_lags=NLAGS
                )
                m_fold.fit(train_df, freq=FREQ_DATA)

                # 3.3. Pronóstico recursivo sobre el periodo de validación
                preds     = recursive_predict_np(m_fold, train_df, periods=val_months)
                fold_mape = mean_absolute_percentage_error(val_df['y'], preds['yhat1']) * 100
                fold_mae  = mean_absolute_error(val_df['y'], preds['yhat1'])
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

        # 5. ENTRENAMIENTO FINAL Y PRONÓSTICO RECURSIVO
        # =========================================================================

        print(f'PROGRESS:62:Entrenando el modelo final con hiperparámetros óptimos sobre todo el histórico...', flush=True)

        # epochs en modo automático (igual que en los folds de CV) para coherencia metodológica
        m_final = NeuralProphet(
            **best_params,
            yearly_seasonality=True,
            weekly_seasonality=False,
            daily_seasonality=False,
            n_lags=NLAGS,
            n_forecasts=1   # necesario para la predicción recursiva paso a paso
        )

        m_final.fit(df_np, freq=FREQ_DATA)

        print(f'PROGRESS:90:Generando pronóstico recursivo hasta {f_end} ({HORIZONTE_MESES} meses)...', flush=True)

        pronostico_recursivo = recursive_predict_np(m_final, df_np, periods=HORIZONTE_MESES)
        pronostico_recursivo.columns = ['Fecha', f'{metrica} Pronosticado']

        # RESULT
        print('PROGRESS:96:Construyendo resultado...', flush=True)

        col_pronostico = f'{metrica} Pronosticado'
        anio_inicio = df_np['ds'].iloc[0].year
        historico = [
            {'fecha': row['ds'].strftime('%Y-%m'), 'valor': round(float(row['y'])) if pd.notna(row['y']) else None}
            for _, row in df_np.iterrows()
        ]
        pronostico = [
            {'fecha': row['Fecha'].strftime('%Y-%m'), 'valor': round(float(row[col_pronostico]))}
            for _, row in pronostico_recursivo.iterrows()
        ]

        result = {
            'metrica':             metrica,
            'modo':                'estatal',
            'modelo':              'NP',
            'atributo':            None,
            'anio_inicio':         anio_inicio,
            'historico':           historico,
            'pronostico':          pronostico,
            'intervalo_confianza': None,
        }

        print('RESULT:' + json.dumps(result, ensure_ascii=False), flush=True)

    except Exception as e:
        import traceback
        print(f'ERROR:{e}', flush=True)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
