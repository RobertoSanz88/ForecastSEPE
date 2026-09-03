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
        'growth'           : ['linear'], #, 'discontinuous'],
        'n_changepoints'   : [10], #, 20, 50],
        'seasonality_mode' : ['additive'], #, 'multiplicative'],

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
        'max_depth'       : [3], #, 5, 10],
        'learning_rate'   : [0.01], #, 0.1, 0.5],
        'n_estimators'    : [500], #, 1000, 2000],
        'colsample_bytree': [0.4], #, 0.7, 1],
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
