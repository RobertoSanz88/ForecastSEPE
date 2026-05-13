#!/usr/bin/env python3
"""
forecast_DE_atributo_NP.py — Contratos / P. Contratadas por AtributoX — NeuralProphet
"""
import argparse
import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import NP_DE_ATRIBUTO_PARAMS

import math
import pandas as pd
import numpy as np
from sklearn.model_selection import ParameterGrid
from sklearn.metrics import mean_absolute_percentage_error, mean_absolute_error
from neuralprophet import NeuralProphet, set_random_seed, set_log_level

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

        metrica  = args.metrica
        atributo = args.atributo or 'CCAA'

        val_months = NP_DE_ATRIBUTO_PARAMS['val_months']
        FREQ_DATA  = 'MS'

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

        print(f'PROGRESS:8:Cargados {len(df_new)} meses | {len(df_new.columns)} grupos ({atributo})', flush=True)

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

        # --- PARÁMETROS DE ENTRENAMIENTO Y VALIDACIÓN ---
        # Sin CV rodante: el último año se reserva para comparar hiperparámetros entre sí.
        train_months = len(df_new) - val_months
        print(f'{train_months} meses de entrenamiento | {val_months} meses de validación')

        # Extraer lista de grupos ANTES de añadir la columna 'ds' para no incluirla como grupo
        grupos       = df_new.columns
        df_new['ds'] = df_new.index

        # Separar train y valid — Contratos no usa lags, por lo que valid es exactamente val_months filas
        train_data = df_new[:-val_months]
        valid_data = df_new[-val_months:]

        # Diccionarios de DataFrames por grupo (columnas: 'ds' + nombre del grupo)
        train_dataframes = {grupo: train_data[['ds', grupo]] for grupo in grupos}
        valid_dataframes = {grupo: valid_data[['ds', grupo]] for grupo in grupos}

        # 2. OPTIMIZACIÓN DE HIPERPARÁMETROS (Grid Search manual, validación en el último año)
        # ==================================================================================

        n_grupos = len(grupos)
        print(f'PROGRESS:10:Iniciando optimización de hiperparámetros para {n_grupos} grupos...', flush=True)

        best_params          = {}
        models_neuralprophet = {}
        forecasts_train      = {}
        forecasts_valid      = {}

        # Renombrar la columna del grupo a 'y' una sola vez, fuera del bucle de hiperparámetros
        for grupo in grupos:
            train_dataframes[grupo] = train_dataframes[grupo].rename(columns={grupo: 'y'})
            valid_dataframes[grupo] = valid_dataframes[grupo].rename(columns={grupo: 'y'})
            if 'ds' not in valid_dataframes[grupo].columns:
                valid_dataframes[grupo]['ds'] = valid_dataframes[grupo].index

        params_grid = NP_DE_ATRIBUTO_PARAMS['grid']

        for gi, (grupo, grupo_df) in enumerate(train_dataframes.items()):
            pct = 10 + int(gi / n_grupos * 52)
            print(f'PROGRESS:{pct}:Optimizando HP — {grupo} ({gi + 1}/{n_grupos})', flush=True)

            grid             = ParameterGrid(params_grid)
            model_parameters = pd.DataFrame(columns=['MAPE', 'Parameters'])

            for i, p in enumerate(grid, start=1):
                set_random_seed(11)
                model = NeuralProphet(
                    yearly_seasonality=True,
                    weekly_seasonality=False,
                    daily_seasonality=False,
                    growth=p['growth'],
                    n_changepoints=p['n_changepoints'],
                    seasonality_mode=p['seasonality_mode'],
                )
                model.fit(grupo_df, freq=FREQ_DATA, progress=False)

                # Predicción directa sobre los 12 meses de validación
                future         = model.make_future_dataframe(df=grupo_df, periods=val_months)
                valid_forecast = model.predict(future)

                # MAPE solo sobre filas con valor real (filtrar NaN del marcador SEPE "'-")
                y_true = valid_dataframes[grupo]['y'].values
                y_pred = valid_forecast['yhat1'].values
                valid_mask = ~np.isnan(y_true)
                mape = mean_absolute_percentage_error(y_true[valid_mask], y_pred[valid_mask]) * 100
                print(f'  [{grupo}] Combinación {i}/{len(grid)} — MAPE: {mape:.2f}%')
                model_parameters = pd.concat(
                    [model_parameters, pd.DataFrame({'MAPE': mape, 'Parameters': [p]})],
                    ignore_index=True
                )

            # Mejor combinación de hiperparámetros
            pars = model_parameters.sort_values(by='MAPE').reset_index(drop=True)
            best_params[grupo] = pars['Parameters'][0]

            # Reentrenar con los mejores hiperparámetros para obtener las predicciones de validación finales
            set_random_seed(11)
            model = NeuralProphet(
                yearly_seasonality=True,
                weekly_seasonality=False,
                daily_seasonality=False,
                **best_params[grupo]
            )
            model.fit(grupo_df, freq=FREQ_DATA, progress=False)
            models_neuralprophet[grupo] = model
            future                  = model.make_future_dataframe(df=grupo_df, periods=val_months)
            forecasts_valid[grupo]  = model.predict(future)
            forecasts_train[grupo]  = model.predict(grupo_df)
            print(f'Grupo completado: {grupo}')

        # Mejores hiperparámetros por grupo
        neuralprophet_best_params = pd.DataFrame(best_params).T

        # Cálculo de MAPE (%) y MAE en TRAIN y VALID
        mape_train_values = {}
        mape_valid_values = {}
        mae_valid_values  = {}

        for grupo in train_dataframes:
            y_true = train_dataframes[grupo]['y'].values
            y_pred = forecasts_train[grupo]['yhat1'].values
            mask   = ~np.isnan(y_true)
            mape_train_values[grupo] = mean_absolute_percentage_error(y_true[mask], y_pred[mask]) * 100

        for grupo in valid_dataframes:
            y_true = valid_dataframes[grupo]['y'].values
            y_pred = forecasts_valid[grupo]['yhat1'].values
            mask   = ~np.isnan(y_true)
            mape_valid_values[grupo] = mean_absolute_percentage_error(y_true[mask], y_pred[mask]) * 100
            mae_valid_values[grupo]  = mean_absolute_error(y_true[mask], y_pred[mask])

        mean_mape_train = pd.Series(mape_train_values).mean()
        mean_mape_valid = pd.Series(mape_valid_values).mean()
        mean_mae_valid  = pd.Series(mae_valid_values).mean()
        print(f'MAPE medio TRAIN ({atributo}): {mean_mape_train:.2f}%')
        print(f'MAPE medio VALID ({atributo}): {mean_mape_valid:.2f}%')
        print(f'MAE  medio VALID ({atributo}): {mean_mae_valid:,.0f} {metrica}')

        # 6. ENTRENAMIENTO FINAL Y PRONÓSTICO
        # ==================================================================================

        print(f'PROGRESS:62:Entrenando {n_grupos} modelos finales con hiperparámetros óptimos...', flush=True)

        # Dataset completo (train + valid) para el entrenamiento final
        df_new['ds'] = df_new.index
        trainvalid_dataframes = {grupo: df_new[['ds', grupo]] for grupo in grupos}

        models_neuralprophet = {}
        forecasts_results_np = {}

        for i, (grupo, grupo_df) in enumerate(trainvalid_dataframes.items(), start=1):
            pct = 62 + int(i / n_grupos * 33)
            print(f'PROGRESS:{pct}:Entrenando modelo final — {grupo} ({i}/{n_grupos})', flush=True)

            grupo_df = grupo_df.rename(columns={grupo: 'y'})

            model = NeuralProphet(
                yearly_seasonality=True,
                weekly_seasonality=False,
                daily_seasonality=False,
                growth=neuralprophet_best_params.loc[grupo, 'growth'],
                n_changepoints=neuralprophet_best_params.loc[grupo, 'n_changepoints'],
                seasonality_mode=neuralprophet_best_params.loc[grupo, 'seasonality_mode'],
            )
            set_random_seed(11)
            model.fit(grupo_df, freq=FREQ_DATA, progress=False)
            models_neuralprophet[grupo] = model

            # Predicción directa — sin recursividad porque n_lags=0
            future = model.make_future_dataframe(df=grupo_df, periods=HORIZONTE_MESES,
                                                 n_historic_predictions=False)
            forecast = model.predict(future)
            forecasts_results_np[grupo] = forecast['yhat1']
            print(f'Grupo {i}/{n_grupos} ({grupo}) completado')

        # Las fechas futuras se construyen dinámicamente desde el mes siguiente al último histórico
        forecasts_dates = pd.date_range(
            end=FECHA_FIN_PRONOSTICO,
            periods=HORIZONTE_MESES,
            freq='MS'
        ).to_list()

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
                for d, v in zip(forecasts_dates, forecasts_results_np[grupo].values)
            ]
            series_out[grupo] = {
                'historico':  historico,
                'pronostico': pronostico,
                'intervalo_confianza': None,
            }

        result = {
            'metrica':     metrica,
            'modo':        'atributo',
            'modelo':      'NP',
            'atributo':    atributo,
            'anio_inicio': anio_inicio,
            'series':      series_out,
        }

        print('RESULT:' + json.dumps(result, ensure_ascii=False), flush=True)

    except Exception as e:
        import traceback
        print(f'ERROR:{e}', flush=True)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
