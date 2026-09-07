# Hyperparameter grids — exact values from the 8 source notebooks.
# Each script imports only the constant(s) it needs:
#   from config import LSTM_ATRIBUTO_PARAMS

# ── LSTM ─────────────────────────────────────────────────────────────────────

# Parados o Afiliados mensual por AtributoX 2027-2029 LSTM_v2.ipynb
LSTM_ATRIBUTO_PARAMS = {
    'grid': {
        'lags'   : [6, 12],
        'units'  : [32, 64],
        'dropout': [0, 0.1],
    },
    'epochs': 100,          # fixed — not tuned in grid search
    'val_months': 12,
}

# Parados o Afiliados mensual estatal 2027-2029 LSTM_v2.ipynb
LSTM_ESTATAL_PARAMS = {
    'grid': {
        'lags'  : [2, 12, 18],
        'units' : [64, 128, 256],
        'epochs': [100, 200, 300],
    },
    # Validado empíricamente sobre 3 cortes temporales (abr-2026, dic-2025,
    # dic-2024): los tres hiperparámetros salen idénticos en Parados y
    # Afiliados (la única discrepancia, units=256 en el corte más reciente,
    # resultó ser ruido -- MAPE prácticamente igual a units=64 comparado
    # directamente). Se salta el grid search para estas dos métricas.
    # Demandantes no se ha probado -- usa el grid completo (fallback).
    'grid_overrides': {
        'Parados':   {'lags': [2], 'units': [64], 'epochs': [100]},
        'Afiliados': {'lags': [2], 'units': [64], 'epochs': [100]},
    },
    'cv': {
        'train_months': 96,
        'val_months'  : 36,
        'step_months' : 12,
    },
}

# ── NeuralProphet — ABC (Parados / Afiliados / Demandantes) ─────────────────

# Parados o Afiliados mensual por AtributoX 2027-2029 NP_v2.ipynb
NP_ABC_ATRIBUTO_PARAMS = {
    'grid': {
        'growth'           : ['linear', 'discontinuous'],
        'n_changepoints'   : [1, 10, 20],                      # NOTA: diferente del estatal [10,20,50]
        'seasonality_mode' : ['additive', 'multiplicative'],
    },
    'nlags'     : 2,
    'val_months': 12,
}

# Parados o Afiliados mensual estatal 2027-2029 NP_v2.ipynb
NP_ABC_ESTATAL_PARAMS = {
    'grid': {
        'growth'           : ['linear', 'discontinuous'],
        'n_changepoints'   : [10, 20, 50],
        'seasonality_mode' : ['additive', 'multiplicative'],
    },
    # Re-validado 2026-09-06 con prueba multi-semilla (3 semillas x 12
    # combinaciones x 4 folds, re-sembrando antes de cada fit) tras detectar
    # que el grid original (sin re-sembrar) daba resultados dependientes de
    # la posición de entrenamiento, no de los hiperparámetros reales -- ver
    # [[bug-np-recursive-seed-instability]]. Para Parados, cualquier
    # combinación con growth=discontinuous + n_changepoints=20 explota en
    # el fold que cruza el COVID (peor caso >40.000% MAPE) en 2 de las 3
    # semillas -- inestable de verdad, no mala suerte puntual. growth=linear
    # es sistemáticamente el más robusto (std 2-7 puntos, sin explosiones,
    # mediana 19-22% en las 6 combinaciones linear). Se fija
    # linear/10/additive: mejor peor-caso (21.69%) y menor varianza (std
    # 2.02) de las 12 combinaciones. Contratos pendiente de la misma prueba
    # antes de fijar nada ahí.
    #
    # Afiliados fijado 2026-09-07: el grid search de un solo corte/semilla no
    # bastaba -- picoteaba distinto ganador según el corte (dic-2024 dio
    # linear/10/additive con tendencia decreciente, claramente mal frente al
    # histórico real en subida). Diagnóstico: con n_changepoints=10 el modelo
    # no tiene changepoints cerca del final del histórico y extrapola con una
    # pendiente más vieja y suave que el crecimiento reciente real
    # (~524k/año) -- ver [[bug-np-recursive-seed-instability]] para el
    # patrón general de no fiarse de un solo grid search sin repetir. Con
    # linear/50/additive la tendencia es positiva y consistente en 3
    # semillas (+387k a +538k/año) y en 2 de los 3 cortes temporales
    # probados por el usuario (dic-2025 y el corte más reciente, MAPE ~3%
    # ambos), con MAPE de validación prácticamente igual al resto de
    # combinaciones (mediana 3.27% en la prueba multi-semilla).
    'grid_overrides': {
        'Parados':   {'growth': ['linear'], 'n_changepoints': [10], 'seasonality_mode': ['additive']},
        'Afiliados': {'growth': ['linear'], 'n_changepoints': [50], 'seasonality_mode': ['additive']},
    },
    'nlags': 2,
    'cv': {
        'train_months': 96,
        'val_months'  : 36,
        'step_months' : 12,
    },
}

# ── NeuralProphet — DE (Contratos / P. Contratadas) ─────────────────────────

# Contratos mensual por AtributoX 2027-2029 NP_v2.ipynb
NP_DE_ATRIBUTO_PARAMS = {
    'grid': {
        'growth'           : ['linear', 'discontinuous'],
        'n_changepoints'   : [10, 20, 50],
        'seasonality_mode' : ['additive', 'multiplicative'],
    },
    'nlags'     : 0,        # no autoregression for Contratos
    'val_months': 12,
}

# Contratos mensual estatal 2027-2029 NP_v2.ipynb
NP_DE_ESTATAL_PARAMS = {
    'grid': {
        'growth'           : ['linear', 'discontinuous'],
        'n_changepoints'   : [10, 20, 50],
        'seasonality_mode' : ['additive', 'multiplicative'],
    },
    # Fijado 2026-09-07 (tercera revisión). Tras revertir brevemente a
    # linear/10/multiplicative (ganador por MAPE de CV en la prueba
    # multi-semilla), se detectó que esa comprobación visual en la app se
    # había hecho con datos solo hasta 2024. Se vuelve a
    # discontinuous/10/multiplicative (mejor forma/tendencia visual en 2 de
    # 3 cortes) hasta repetir la comprobación con datos actualizados.
    'grid_overrides': {
        'Contratos': {'growth': ['discontinuous'], 'n_changepoints': [10], 'seasonality_mode': ['multiplicative']},
    },
    'nlags': 0,
    'cv': {
        'train_months': 96,
        'val_months'  : 36,
        'step_months' : 12,
    },
}

# ── XGBoost — DE ─────────────────────────────────────────────────────────────

# Contratos mensual por AtributoX 2027-2029 XGBoost_v2.ipynb
XGBOOST_ATRIBUTO_PARAMS = {
    'grid': {
        'max_depth'       : [3, 5, 10],
        'learning_rate'   : [0.01, 0.1, 0.5],
        'n_estimators'    : [500, 1000, 2000],
        'colsample_bytree': [0.4, 0.7, 1],
    },
    'reg': {
        'reg_lambda': 0,
        'reg_alpha'  : 10000,
        'gamma'      : 10000,
    },
    'val_months': 12,
}

# Contratos mensual estatal 2027-2029 XGBoost_v2.ipynb
XGBOOST_ESTATAL_PARAMS = {
    'grid': {
        'max_depth'       : [3, 5, 10],
        'learning_rate'   : [0.01, 0.1, 0.5],
        'n_estimators'    : [500, 1000, 2000],
        'colsample_bytree': [0.4, 0.7, 1],
    },
    # Validado empíricamente sobre 3 cortes temporales (abr-2026, dic-2025,
    # dic-2024): los cuatro hiperparámetros salen idénticos para Contratos
    # en los tres cortes. P. Contratadas no se ha probado -- fallback al
    # grid completo.
    'grid_overrides': {
        'Contratos': {'max_depth': [5], 'learning_rate': [0.01], 'n_estimators': [500], 'colsample_bytree': [0.4]},
    },
    'reg': {
        'reg_lambda': 0,
        'reg_alpha'  : 10000,
        'gamma'      : 10000,
    },
    'cv': {
        'train_months': 96,
        'val_months'  : 36,
        'step_months' : 12,
    },
}

# ── TimesFM 2.5 (recursivo) ──────────────────────────────────────────────────
# notebooks/forecast_ABCDE_estatal_TimesFM.ipynb — barrido manual completo
# (FT_CTX, capas, lr, log-transform, canal de punto media/mediana) por grupo
# de métrica. Validado empíricamente para Parados/Afiliados (grupo ABC) y
# Contratos (grupo DE); Demandantes y P. Contratadas heredan las reglas de su
# grupo pero no se han probado todavía.

# Parados o Afiliados mensual estatal — forecast_ABCDE_estatal_TimesFM.ipynb
TIMESFM_ABC_ESTATAL_PARAMS = {
    'log_transform':  False,
    'lr':             5e-6,
    'layers':         4,
    'point_channel':  5,          # mediana
    'ft_ctx_grid':    [24, 36],   # fallback para métricas sin validar (p.ej. Demandantes)
    # El FT_CTX óptimo es una propiedad estructural de la serie agregada
    # nacional (estacionalidad/tendencia) que no cambia con cada actualización
    # mensual de datos -- ya validado empíricamente, así que se fija por
    # métrica y se salta el grid search (mitad de coste de entrenamiento).
    'ft_ctx_grid_overrides': {'Parados': [24], 'Afiliados': [36]},
    'ft_hor':         12,         # igual a recursive_step, por coherencia entrenamiento/uso
    'ft_step':        3,
    'ft_epochs':      15,
    'recursive_step': 12,
    'val_months':     36,
}

# Contratos mensual estatal — forecast_ABCDE_estatal_TimesFM.ipynb
# Oscilaciones estacionales mucho más extremas en términos relativos (picos
# ~3-4x los valles) que el grupo ABC -- de ahí el log-transform y el lr mayor.
TIMESFM_DE_ESTATAL_PARAMS = {
    'log_transform':  True,
    'lr':             5e-5,
    'layers':         4,
    'point_channel':  5,          # mediana por defecto
    # Excepción SOLO para Contratos (no para todo el grupo, ver notebook): con
    # lr=5e-6 media/mediana empataban (21% ambas), pero con lr=5e-5 (el que
    # ganó) la media da 7.79% y la mediana 11.45% -- ya no empatan. Sin
    # validar para P. Contratadas, que se queda con la mediana por defecto.
    'point_channel_overrides': {'Contratos': 0},
    'ft_ctx_grid':    [24, 36],   # fallback para métricas sin validar (P. Contratadas)
    'ft_ctx_grid_overrides': {'Contratos': [36]},  # ver nota en TIMESFM_ABC_ESTATAL_PARAMS
    'ft_hor':         12,
    'ft_step':        3,
    'ft_epochs':      15,
    'recursive_step': 12,
    'val_months':     36,
}

# ── TimesFM 2.5 (recursivo) — ATRIBUTO ────────────────────────────────────────
# notebooks/forecast_ABCDE_atributo_TimesFM.ipynb -- a diferencia del estatal,
# aquí NO se fija FT_CTX por métrica: cada grupo de un desglose (provincia,
# sector, régimen...) puede tener una escala/estacionalidad muy distinta al
# agregado nacional -- confirmado con "Industria" (Parados por sector): con
# log=False salía ~19-20% de MAPE, con log=True ~11%, mientras que Agricultura
# (mismo CSV) necesitaba justo lo contrario. Por eso LOG_TRANSFORM entra en el
# grid junto a FT_CTX (2x2=4 combinaciones por grupo) en vez de decidirse por
# el nombre de la métrica. lr y point_channel se quedan fijos por regla ABC/DE
# -- se probó que solos no ayudan y combinados no generalizan de forma fiable.
#
# VAL_MONTHS=36 (no 12): con 12 el backtest solo ejercita un paso recursivo y
# es ciego a la deriva que solo aparece en pasos posteriores del pronóstico
# final ("efecto bola de nieve") -- confirmado también con "Industria": con
# VAL_MONTHS=12 el backtest daba buen MAPE pero el pronóstico final divergía.
# El MAPE reportado en atributo pasa a ser de los 3 años, no solo del primer
# año, como consecuencia de este cambio.

# Parados o Afiliados por atributo — forecast_ABCDE_atributo_TimesFM.ipynb
TIMESFM_ABC_ATRIBUTO_PARAMS = {
    'lr':               5e-6,
    'layers':           4,
    'point_channel':    5,           # mediana
    'ft_ctx_grid':      [24, 36],
    'log_transform_grid': [False, True],
    'ft_hor':           12,
    'ft_step':          3,
    'ft_epochs':        15,
    'recursive_step':   12,
    'val_months':       36,
}

# Contratos por atributo — forecast_ABCDE_atributo_TimesFM.ipynb
TIMESFM_DE_ATRIBUTO_PARAMS = {
    'lr':               5e-5,
    'layers':           4,
    'point_channel':    5,
    'point_channel_overrides': {'Contratos': 0},  # ver nota en TIMESFM_DE_ESTATAL_PARAMS
    'ft_ctx_grid':      [24, 36],
    'log_transform_grid': [False, True],
    'ft_hor':           12,
    'ft_step':          3,
    'ft_epochs':        15,
    'recursive_step':   12,
    'val_months':       36,
}
