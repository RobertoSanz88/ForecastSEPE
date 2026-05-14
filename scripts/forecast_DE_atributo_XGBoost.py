#!/usr/bin/env python3
"""
forecast_DE_atributo_XGBoost.py — Contratos / P. Contratadas por AtributoX — XGBoost
"""
import argparse
import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import XGBOOST_ATRIBUTO_PARAMS

import math
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

        metrica  = args.metrica
        atributo = args.atributo or 'CCAA'

        REG_PARAMS = XGBOOST_ATRIBUTO_PARAMS['reg']
        val_months = XGBOOST_ATRIBUTO_PARAMS['val_months']

        # encoding='latin1' necesario por los caracteres especiales en nombres de provincias y CCAA
        # na_values=["'-"] convierte el marcador SEPE de dato confidencial en NaN
        df = pd.read_csv(args.csv, sep=';', encoding='latin1', na_values=["'-"])
        df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=True)

        # ── Comprobación de número de columnas ────────────────────────────────────────
        MAX_GRUPOS = 53
        n_datos = len(df.columns) - 1  # excluir Fecha
        if n_datos > MAX_GRUPOS:
            print(f'INPUT_REQUIRED:rango:Hay {n_datos} columnas. Introduce el rango [inicio-fin] (ej: [1-{MAX_GRUPOS}]):', flush=True)
            rango = input()
            inicio, fin = map(int, rango.strip('[]').split('-'))
            df = df[[df.columns[0]] + list(df.columns[inicio:fin + 1])]
            print(f'PROGRESS:7:Seleccionadas {fin - inicio + 1} columnas: "{df.columns[1]}" → "{df.columns[-1]}"', flush=True)

        df_new = df.set_index('Fecha', drop=True).sort_index()

        # Feature engineering: XGBoost no usa lags — el único input son estas tres
        # features temporales que capturan estacionalidad (month, quarter) y tendencia (year).
        df_new['month']   = df_new.index.month
        df_new['quarter'] = df_new.index.quarter
        df_new['year']    = df_new.index.year

        # Grupos = columnas del CSV (una por provincia, CCAA, sector, etc.) — sin las features
        grupos = [c for c in df_new.columns if c not in ('month', 'quarter', 'year')]
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
        print(f'Último dato: {ultimo_str}. Horizonte: {HORIZONTE_MESES} meses (hasta {f_end}).')

        # Sin CV rodante: el último año se reserva para comparar hiperparámetros entre sí.
        print(f'Validación: últimos {val_months} meses | Entrenamiento final: todos los datos')

        # --- MATRICES DE FEATURES (compartidas por todos los grupos) ---
        # XGBoost usa las mismas features temporales para todos los grupos;
        # solo cambia el vector y (target) en cada iteración del bucle.
        FEATURE_COLS = ['month', 'quarter', 'year']

        X_train = df_new[FEATURE_COLS].iloc[:-val_months]   # todo menos los últimos 12 meses
        X_valid = df_new[FEATURE_COLS].iloc[-val_months:]    # últimos 12 meses (validación)

        # Features para el horizonte de pronóstico futuro
        # IMPORTANTE: las features se extraen de las FECHAS FUTURAS, no del histórico,
        # para asignar los años/meses correctos al horizonte de pronóstico.
        forecasts_dates = pd.date_range(
            end=FECHA_FIN_PRONOSTICO, periods=HORIZONTE_MESES, freq='MS'
        )
        X_futuro = pd.DataFrame({
            'month'  : forecasts_dates.month,
            'quarter': forecasts_dates.quarter,
            'year'   : forecasts_dates.year,
        }, index=forecasts_dates)

        # --- ESPACIO DE BÚSQUEDA DE HIPERPARÁMETROS ---
        # max_depth: profundidad máxima de los árboles
        # learning_rate: tamaño del paso en el boosting
        # n_estimators: número de árboles en el ensemble
        # colsample_bytree: fracción de features por árbol (regularización implícita)
        param_grid = XGBOOST_ATRIBUTO_PARAMS['grid']
        grid = list(ParameterGrid(param_grid))
        print(f'Combinaciones a evaluar por grupo: {len(grid)}')
        print(f'Total de modelos (grid x grupos): {len(grid) * len(grupos)}')

        # 2. OPTIMIZACIÓN DE HIPERPARÁMETROS
        # ==================================================================================

        n_grupos = len(grupos)
        print(f'PROGRESS:10:Iniciando optimización para {n_grupos} grupos ({len(grid)} combinaciones cada uno)...', flush=True)

        best_params       = {}
        mape_valid_values = {}
        mae_valid_values  = {}
        forecasts_valid   = {}   # predicciones de validación del mejor modelo por grupo

        for gi, grupo in enumerate(grupos):
            pct = 10 + int(gi / n_grupos * 52)
            print(f'PROGRESS:{pct}:Optimizando HP — {grupo} ({gi + 1}/{n_grupos})', flush=True)

            y_train = df_new[grupo].iloc[:-val_months]
            y_valid = df_new[grupo].iloc[-val_months:]

            # Filtrar NaN del entrenamiento (valores confidenciales "'-" → NaN)
            train_mask = y_train.notna()
            X_train_g  = X_train[train_mask]
            y_train_g  = y_train[train_mask]

            best_mape_grupo   = float('inf')
            best_mae_grupo    = float('inf')
            best_params_grupo = {}
            best_val_preds    = None

            for i, p in enumerate(grid, start=1):
                model = XGBRegressor(**p, **REG_PARAMS)
                model.fit(X_train_g, y_train_g)
                preds = model.predict(X_valid)

                # MAPE solo sobre filas con valor real disponible en validación
                valid_mask = y_valid.notna()
                mape  = mean_absolute_percentage_error(y_valid[valid_mask], preds[valid_mask.values]) * 100
                mae   = mean_absolute_error(y_valid[valid_mask], preds[valid_mask.values])
                print(f'  [{grupo}] Combinación {i}/{len(grid)} — MAPE: {mape:.2f}%')

                if mape < best_mape_grupo:
                    best_mape_grupo   = mape
                    best_mae_grupo    = mae
                    best_params_grupo = p.copy()
                    best_val_preds    = preds.copy()

            best_params[grupo]       = best_params_grupo
            mape_valid_values[grupo] = best_mape_grupo
            mae_valid_values[grupo]  = best_mae_grupo
            forecasts_valid[grupo]   = best_val_preds
            print(f'>>> Grupo completado: {grupo} — Mejor MAPE: {best_mape_grupo:.2f}% | Params: {best_params_grupo}\n')

        mean_mape_valid = pd.Series(mape_valid_values).mean()
        mean_mae_valid  = pd.Series(mae_valid_values).mean()
        print(f'MAPE medio VALID ({atributo}): {mean_mape_valid:.2f}%')
        print(f'MAE  medio VALID ({atributo}): {mean_mae_valid:,.0f} {metrica}')

        # 6. ENTRENAMIENTO FINAL Y PRONÓSTICO
        # ==================================================================================

        print(f'PROGRESS:62:Entrenando {n_grupos} modelos finales con hiperparámetros óptimos...', flush=True)

        forecasts_results_xgb = {}

        X_all = df_new[FEATURE_COLS]   # features sobre todo el histórico

        for i, grupo in enumerate(grupos, start=1):
            pct = 62 + int(i / n_grupos * 33)
            print(f'PROGRESS:{pct}:Entrenando modelo final — {grupo} ({i}/{n_grupos})', flush=True)

            y_all = df_new[grupo]

            # Filtrar NaN del histórico completo antes de entrenar el modelo final
            mask = y_all.notna()

            model = XGBRegressor(**best_params[grupo], **REG_PARAMS)
            model.fit(X_all[mask], y_all[mask])

            forecast = model.predict(X_futuro)
            forecasts_results_xgb[grupo] = pd.Series(forecast, index=forecasts_dates)

            print(f'Grupo {i}/{n_grupos} ({grupo}) completado')

        # RESULT
        print('PROGRESS:96:Construyendo resultado...', flush=True)

        anio_inicio = df_new.index[0].year
        series_out = {}
        for grupo in grupos:
            historico = [
                {'fecha': d.strftime('%Y-%m'), 'valor': round(float(v)) if pd.notna(v) else None}
                for d, v in zip(df_new.index, df_new[grupo])
            ]
            pronostico = [
                {'fecha': d.strftime('%Y-%m'), 'valor': round(float(v))}
                for d, v in zip(
                    forecasts_results_xgb[grupo].index,
                    forecasts_results_xgb[grupo].values,
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
            'modelo':      'XGBoost',
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
