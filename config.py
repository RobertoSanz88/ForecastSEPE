# Hyperparameter grids — exact values from the 8 source notebooks.
# Each script imports only the constant(s) it needs:
#   from config import LSTM_ATRIBUTO_PARAMS

# ── LSTM ─────────────────────────────────────────────────────────────────────

# Parados o Afiliados mensual por AtributoX 2027-2029 LSTM_v2.ipynb
LSTM_ATRIBUTO_PARAMS = {
    'grid': {
        'lags'   : [6],    # [6, 12],
        'units'  : [32],   # [32, 64],
        'dropout': [0.1],  # [0, 0.1],
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
        'n_changepoints'   : [1, 10, 20],          # NOTE: different from estatal [10,20,50]
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
        'growth'           : ['linear', 'discontinuous'],
        'n_changepoints'   : [10, 20, 50],
        'seasonality_mode' : ['additive', 'multiplicative'],
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
