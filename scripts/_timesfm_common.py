#!/usr/bin/env python3
"""
_timesfm_common.py — Motor compartido de TimesFM 2.5 (recursivo) para los
scripts forecast_ABC_estatal_TimesFM.py y forecast_DE_estatal_TimesFM.py.

Traducido y verificado a partir de forecast_ABCDE_estatal_TimesFM.ipynb — ver
ese notebook para el detalle de cómo se validó cada pieza (comparación byte a
byte contra el código fuente de timesfm==3.0.0, barrido manual de context/
layers/lr/log/point_channel por métrica, etc.). No se reimplementa nada aquí
que no estuviera ya probado en el notebook.
"""
import copy
import os
import ssl
import warnings

os.environ.setdefault('USE_TF', '0')
os.environ.setdefault('USE_TORCH', '1')

ssl._create_default_https_context = ssl._create_unverified_context  # proxy corporativo Netskope

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import requests
_orig_request = requests.Session.request
def _patched_request(self, *a, **kw):
    kw.setdefault('verify', False)
    return _orig_request(self, *a, **kw)
requests.Session.request = _patched_request  # huggingface_hub < 1.0 usa requests por debajo

try:
    import httpx

    def _unverified_httpx_client_factory():
        return httpx.Client(verify=False, follow_redirects=True, timeout=None)

    import huggingface_hub
    huggingface_hub.set_client_factory(_unverified_httpx_client_factory)
except (ImportError, AttributeError):
    pass  # huggingface_hub < 1.0 (sin httpx o sin set_client_factory) -- cubierto por el parche de arriba

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from sklearn.metrics import mean_absolute_percentage_error

import timesfm
from timesfm.torch import util as tfm_util

warnings.filterwarnings('ignore')

SEED = 11   # misma semilla que set_random_seed(11) en los scripts NP/LSTM


def load_timesfm_model(model_dir: str, repo_id: str = 'google/timesfm-2.5-200m-pytorch'):
    """Carga el checkpoint de TimesFM 2.5 desde `model_dir` (ver README/CLAUDE.md
    sobre dónde lo deja el instalador de v2) y lo compila. No intenta descargar
    nada -- eso es responsabilidad del instalador, no de este script.

    Devuelve (model, base_module, constantes_dict).
    """
    weights_path = os.path.join(model_dir, 'model.safetensors')
    if not os.path.exists(weights_path):
        raise FileNotFoundError(
            f'No se encontró el checkpoint de TimesFM 2.5 en "{model_dir}" '
            f'(falta {weights_path}). Este script no lo descarga automáticamente -- '
            f'debe dejarlo ahí el instalador de ForecastSEPE v2.'
        )

    model = timesfm.TimesFM_2p5_200M_torch(torch_compile=False)
    model.load_checkpoint(model_dir)

    model.compile(
        timesfm.ForecastConfig(
            max_context=1024,
            max_horizon=128,
            normalize_inputs=True,
            use_continuous_quantile_head=True,
            # False: por defecto este flag promedia la predicción con la que da
            # el modelo sobre la serie NEGADA (-serie) -- no tiene sentido para
            # datos económicos siempre positivos (ver notebook para el detalle).
            force_flip_invariance=False,
            infer_is_positive=True,
            fix_quantile_crossing=True,
        )
    )

    base_module = copy.deepcopy(model.model)

    consts = {
        'p':          model.model.p,             # 32  -- longitud de parche de entrada
        'o':          model.model.o,             # 128 -- longitud de parche de salida
        'q':          model.model.q,             # 10  -- canales de cuantil
        'aridx':      model.model.aridx,         # 5   -- canal de mediana (p50)
        'num_layers': len(model.model.stacked_xf),  # 20
    }
    return model, base_module, consts


def timesfm_forward_point(core_module, context_batch, mask_batch, horizon, point_channel):
    """Pronóstico puntual diferenciable para fine-tuning.

    context_batch: FloatTensor (B, ctx_len); ctx_len debe ser múltiplo de core_module.p.
    mask_batch: BoolTensor (B, ctx_len); True donde context_batch es relleno (no datos reales).
    horizon: int <= core_module.o (128).
    point_channel: 0 = media, 5 = mediana -- MISMO canal que luego usa recursive_forecast,
    para que no haya desajuste entre lo que se entrena y lo que se lee al predecir.
    Devuelve: FloatTensor (B, horizon).
    """
    p, o = core_module.p, core_module.o
    B, ctx_len = context_batch.shape
    assert ctx_len % p == 0, f'ctx_len ({ctx_len}) debe ser múltiplo de {p}'
    assert horizon <= o, f'horizon ({horizon}) debe ser <= {o}'

    patched_inputs = context_batch.reshape(B, -1, p)
    patched_masks  = mask_batch.reshape(B, -1, p)

    n_pts = torch.zeros(B, device=context_batch.device)
    mu    = torch.zeros(B, device=context_batch.device)
    sigma = torch.zeros(B, device=context_batch.device)
    patch_mu, patch_sigma = [], []
    for i in range(patched_inputs.shape[1]):
        (n_pts, mu, sigma), _ = tfm_util.update_running_stats(
            n_pts, mu, sigma, patched_inputs[:, i], patched_masks[:, i]
        )
        patch_mu.append(mu)
        patch_sigma.append(sigma)
    context_mu    = torch.stack(patch_mu, dim=1)
    context_sigma = torch.stack(patch_sigma, dim=1)

    normed_inputs = tfm_util.revin(patched_inputs, context_mu, context_sigma, reverse=False)
    normed_inputs = torch.where(patched_masks, 0.0, normed_inputs)

    (_, _, normed_outputs, _), _ = core_module(normed_inputs, patched_masks, decode_caches=None)

    renormed_outputs = tfm_util.revin(normed_outputs, context_mu, context_sigma, reverse=True)
    renormed_outputs = renormed_outputs.reshape(B, -1, o, core_module.q)

    return renormed_outputs[:, -1, :horizon, point_channel]


def pad_context_to_patch(ctx_arr, patch_len=32):
    """Rellena ctx_arr con ceros al PRINCIPIO hasta el siguiente múltiplo de
    patch_len (los datos reales quedan siempre al final). Devuelve (ctx_padded,
    mask) -- mask=True marca las posiciones de relleno."""
    L = len(ctx_arr)
    padded_len = ((L + patch_len - 1) // patch_len) * patch_len
    pad_amount = padded_len - L
    ctx_padded = np.concatenate([np.zeros(pad_amount, dtype=ctx_arr.dtype), ctx_arr])
    mask = np.concatenate([np.ones(pad_amount, dtype=bool), np.zeros(L, dtype=bool)])
    return ctx_padded, mask


def build_ft_windows(series, ctx, hor, step, patch_len=32):
    """Ternas (contexto rellenado, máscara, objetivo) por ventana deslizante."""
    windows = []
    for i in range(ctx, len(series) - hor + 1, step):
        ctx_arr, mask = pad_context_to_patch(series[i - ctx: i], patch_len)
        tgt_arr = series[i: i + hor]
        windows.append((ctx_arr, mask, tgt_arr))
    return windows


def make_ft_module(n_layers, base_module):
    """Copia profunda de `base_module` con solo las últimas `n_layers` capas de
    transformer + la cabeza de proyección puntual descongeladas."""
    ft_m = copy.deepcopy(base_module)
    for param in ft_m.parameters():
        param.requires_grad = False
    total = len(ft_m.stacked_xf)
    for i in range(total - n_layers, total):
        for param in ft_m.stacked_xf[i].parameters():
            param.requires_grad = True
    for param in ft_m.output_projection_point.parameters():
        param.requires_grad = True
    return ft_m


def run_ft_training(ft_m, lr, epochs, windows, point_channel, seed=SEED,
                     progress_range=None, progress_label=''):
    """Fine-tuning con AdamW, épocas FIJAS (sin early stopping).

    progress_range: tupla opcional (pct_inicio, pct_fin) -- si se da, se emite
    una línea PROGRESS: por época (interpolando el % dentro de ese rango) con
    el loss medio de esa época, para que se vea en la línea de estado de la
    app en vez de solo en el log del servidor. Sin esto, entrena en silencio
    (igual que antes).
    """
    trainable_p = [p for p in ft_m.parameters() if p.requires_grad]
    optimizer   = torch.optim.AdamW(trainable_p, lr=lr)
    torch.manual_seed(seed)
    ft_m.train()
    for epoch in range(1, epochs + 1):
        epoch_losses = []
        for ctx_arr, mask_arr, tgt_arr in windows:
            x = torch.tensor(ctx_arr, dtype=torch.float32).unsqueeze(0)
            m = torch.tensor(mask_arr, dtype=torch.bool).unsqueeze(0)
            y = torch.tensor(tgt_arr, dtype=torch.float32).unsqueeze(0)
            pred = timesfm_forward_point(ft_m, x, m, horizon=len(tgt_arr), point_channel=point_channel)
            loss = F.mse_loss(pred, y)
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(trainable_p, 1.0)
            optimizer.step()
            epoch_losses.append(loss.item())
        if progress_range is not None:
            lo, hi = progress_range
            pct = int(lo + (epoch / epochs) * (hi - lo))
            loss_medio = sum(epoch_losses) / len(epoch_losses)
            print(f'PROGRESS:{pct}:{progress_label} — época {epoch}/{epochs} (loss medio {loss_medio:.4f})', flush=True)
    ft_m.eval()
    return ft_m


def recursive_forecast(compiled_model, module, context, total_horizon, step, point_channel):
    """Pronóstico de `total_horizon` meses encadenando pasos de `step` meses:
    en cada paso predice `step` meses con todo el contexto disponible hasta ese
    momento (histórico real + lo ya predicho en pasos anteriores), y añade lo
    predicho al contexto del siguiente paso -- igual que decode() encadena
    bloques de 128 cuando el horizonte pedido supera output_patch_len, pero
    aquí con bloques de `step`.

    compiled_model: el objeto timesfm.TimesFM_2p5_200M_torch ya compilado.
    module: qué pesos usar (base_module para zero-shot, ft_model para fine-tuned).
    context: array 1D con el histórico real de partida (en la escala del modelo).
    Devuelve: (point_forecast, quantile_forecast), ambos en la escala del modelo.
    """
    compiled_model.model = module
    ctx = list(context)
    points, quants = [], []
    remaining = total_horizon
    while remaining > 0:
        h = min(step, remaining)
        _, quant_block = compiled_model.forecast(horizon=h, inputs=[np.array(ctx)])
        quant_block = quant_block[0]                 # (h, 10)
        point_block = quant_block[:, point_channel]   # (h,)
        points.append(point_block)
        quants.append(quant_block)
        ctx = ctx + list(point_block)
        remaining -= h
    return np.concatenate(points), np.concatenate(quants, axis=0)


def to_raw(x, log_transform):
    """Deshace la transformación del modelo (log, si log_transform=True) -- escala real."""
    return np.exp(x) if log_transform else x


def resolve_point_channel(metrica: str, params: dict) -> int:
    """POINT_CHANNEL efectivo para `metrica`: usa params['point_channel'] salvo
    que exista una excepción explícita en params['point_channel_overrides']
    (ver TIMESFM_DE_ESTATAL_PARAMS en config.py -- por ahora solo Contratos)."""
    overrides = params.get('point_channel_overrides', {})
    return overrides.get(metrica, params['point_channel'])


def resolve_ft_ctx_grid(metrica: str, params: dict) -> list:
    """FT_CTX_GRID efectivo para `metrica`: usa params['ft_ctx_grid'] (grid
    completo, para métricas aún sin validar) salvo que exista una entrada en
    params['ft_ctx_grid_overrides'] -- ahí se fija un único valor ya validado
    (ver TIMESFM_*_ESTATAL_PARAMS en config.py), y el bucle de grid search se
    reduce a un solo candidato sin necesidad de tocar su lógica."""
    overrides = params.get('ft_ctx_grid_overrides', {})
    return overrides.get(metrica, params['ft_ctx_grid'])


def run_timesfm_estatal_forecast(metrica: str, csv_path: str, params: dict, model_dir: str,
                                  f_end_override: str = None) -> dict:
    """Pipeline completo: carga de datos, selección automática de FT_CTX por
    backtest, fine-tuning final sobre el 100% del histórico, y pronóstico
    recursivo hasta el horizonte dinámico. Emite PROGRESS: por stdout.
    Devuelve el dict `result` en el formato documentado en CLAUDE.md.
    """
    import datetime as _dt

    log_transform = params['log_transform']
    fixed_lr      = params['lr']
    fixed_layers  = params['layers']
    point_channel = resolve_point_channel(metrica, params)
    ft_ctx_grid   = resolve_ft_ctx_grid(metrica, params)
    ft_hor        = params['ft_hor']
    ft_step       = params['ft_step']
    ft_epochs     = params['ft_epochs']
    recursive_step = params['recursive_step']
    val_months    = params['val_months']

    def progress(pct, msg):
        print(f'PROGRESS:{pct}:{msg}', flush=True)

    # 1. CARGA DE DATOS -------------------------------------------------------
    progress(5, f'Cargando datos de {metrica}...')
    df = pd.read_csv(csv_path, sep=';', na_values=["'-"])
    df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=True)
    df[metrica] = pd.to_numeric(df[metrica], errors='coerce')
    df = df.sort_values('Fecha').reset_index(drop=True)

    all_values       = df[metrica].values.astype(np.float32)
    all_values_model = np.log(all_values) if log_transform else all_values
    n = len(all_values)

    now = _dt.datetime.now().year
    f_end = f_end_override if f_end_override else f'{now + 3}-12'
    fecha_fin_pronostico  = pd.Timestamp(f_end + '-01')
    ultima_fecha_historico = df['Fecha'].iloc[-1]
    horizonte_meses = (
        (fecha_fin_pronostico.year  - ultima_fecha_historico.year)  * 12 +
        (fecha_fin_pronostico.month - ultima_fecha_historico.month)
    )

    if n < ft_ctx_grid[0] + val_months:
        raise ValueError(
            f'Histórico insuficiente ({n}m) para contexto={ft_ctx_grid[0]}m + validación={val_months}m'
        )

    # 2. CARGA DEL MODELO ------------------------------------------------------
    progress(10, 'Cargando modelo TimesFM 2.5...')
    model, base_module, consts = load_timesfm_model(model_dir)

    if horizonte_meses > model.forecast_config.max_horizon:
        raise ValueError(
            f'HORIZONTE_MESES ({horizonte_meses}) supera max_horizon '
            f'({model.forecast_config.max_horizon}) configurado en compile().'
        )

    # 3. SELECCIÓN AUTOMÁTICA DE FT_CTX (backtest, sin los últimos val_months) -
    backtest_context = all_values_model[:n - val_months]
    backtest_actual  = all_values[n - val_months:]

    best_ctx_mape = float('inf')
    ft_ctx        = ft_ctx_grid[0]
    grid_results  = []

    n_candidates = len(ft_ctx_grid)
    for ci, candidate_ctx in enumerate(ft_ctx_grid):
        slice_lo = 15 + int(ci / n_candidates * 45)
        slice_hi = 15 + int((ci + 1) / n_candidates * 45)
        progress(slice_lo, f'Backtest FT_CTX={candidate_ctx} ({ci + 1}/{n_candidates})...')

        ft_windows_bt = build_ft_windows(all_values_model[:-val_months], candidate_ctx, ft_hor, ft_step)
        ft_m_bt = make_ft_module(fixed_layers, base_module)
        ft_m_bt = run_ft_training(
            ft_m_bt, fixed_lr, ft_epochs, ft_windows_bt, point_channel,
            progress_range=(slice_lo, slice_hi),
            progress_label=f'Backtest FT_CTX={candidate_ctx} ({ci + 1}/{n_candidates})',
        )

        bt_point_model, _ = recursive_forecast(model, ft_m_bt, backtest_context, val_months,
                                                recursive_step, point_channel)
        bt_point = to_raw(bt_point_model, log_transform)
        mape_ctx = mean_absolute_percentage_error(backtest_actual, bt_point) * 100
        grid_results.append({'ft_ctx': candidate_ctx, 'mape': round(float(mape_ctx), 2)})
        print(f'  FT_CTX={candidate_ctx}: MAPE={mape_ctx:.2f}%', flush=True)

        if mape_ctx < best_ctx_mape:
            best_ctx_mape = mape_ctx
            ft_ctx        = candidate_ctx
        del ft_m_bt

    mape_fine_tuned = best_ctx_mape
    print(f'Mejor FT_CTX para {metrica}: {ft_ctx}  (MAPE {mape_fine_tuned:.2f}%)', flush=True)

    # 4. FINE-TUNING FINAL (100% del histórico) -------------------------------
    progress(65, f'Entrenando modelo final (FT_CTX={ft_ctx})...')
    ft_windows_final = build_ft_windows(all_values_model, ft_ctx, ft_hor, ft_step)
    ft_model_final = make_ft_module(fixed_layers, base_module)
    ft_model_final = run_ft_training(
        ft_model_final, fixed_lr, ft_epochs, ft_windows_final, point_channel,
        progress_range=(65, 90),
        progress_label='Entrenando modelo final',
    )

    # 5. PRONÓSTICO FINAL RECURSIVO --------------------------------------------
    progress(90, f'Generando pronóstico recursivo hasta {f_end} ({horizonte_meses} meses)...')
    forecast_dates = pd.date_range(
        ultima_fecha_historico + pd.DateOffset(months=1),
        periods=horizonte_meses, freq='MS'
    )

    forecast_point_model, forecast_quant_model = recursive_forecast(
        model, ft_model_final, all_values_model, horizonte_meses, recursive_step, point_channel
    )
    forecast_point = to_raw(forecast_point_model, log_transform)
    forecast_quant = to_raw(forecast_quant_model, log_transform)

    q_low, q_high = 1, 9   # p10, p90 (canal 0=media, 1..9=deciles 0.1..0.9)

    # 6. RESULT -----------------------------------------------------------------
    progress(96, 'Construyendo resultado...')
    historico = [
        {'fecha': row['Fecha'].strftime('%Y-%m'), 'valor': round(float(row[metrica])) if pd.notna(row[metrica]) else None}
        for _, row in df.iterrows()
    ]
    pronostico = [
        {'fecha': d.strftime('%Y-%m'), 'valor': round(float(v))}
        for d, v in zip(forecast_dates, forecast_point)
    ]
    intervalo_confianza = {
        'superior': [{'fecha': d.strftime('%Y-%m'), 'valor': round(float(v))}
                     for d, v in zip(forecast_dates, forecast_quant[:, q_high])],
        'inferior': [{'fecha': d.strftime('%Y-%m'), 'valor': round(float(v))}
                     for d, v in zip(forecast_dates, forecast_quant[:, q_low])],
    }

    result = {
        'metrica':             metrica,
        'modo':                'estatal',
        'modelo':              'TimesFM',
        'atributo':            None,
        'anio_inicio':         int(df['Fecha'].iloc[0].year),
        'historico':           historico,
        'pronostico':          pronostico,
        'intervalo_confianza': intervalo_confianza,
        'mape':                round(float(mape_fine_tuned), 2),
        'hiperparametros': {
            'ft_ctx': ft_ctx, 'ft_hor': ft_hor, 'layers': fixed_layers, 'lr': fixed_lr,
            'log_transform': log_transform, 'point_channel': point_channel,
            'recursive_step': recursive_step,
        },
    }
    return result


def run_timesfm_atributo_forecast(metrica: str, atributo: str, df: 'pd.DataFrame', grupos: list,
                                   params: dict, model_dir: str, f_end_override: str = None) -> dict:
    """Pipeline completo por grupo (modo atributo): para cada grupo, backtest
    con grid (FT_CTX x LOG_TRANSFORM, 4 combinaciones), fine-tuning final
    sobre el 100% de su historico, y pronostico recursivo. Emite PROGRESS:
    por stdout. Devuelve el dict `result` en el formato documentado en
    CLAUDE.md (modo atributo).

    `df` debe traer 'Fecha' ya parseada a datetime y las columnas de `grupos`
    ya numericas -- el entry point se encarga de la carga/limpieza del CSV y
    de aplicar el protocolo INPUT_REQUIRED si hay demasiadas columnas.

    A diferencia de run_timesfm_estatal_forecast, aqui LOG_TRANSFORM no se
    decide por el nombre de la metrica -- es una dimension mas del grid junto
    a FT_CTX, elegida por grupo (ver notebooks/forecast_ABCDE_atributo_TimesFM.ipynb
    para el detalle de por que hizo falta: un desglose puede tener una escala/
    estacionalidad muy distinta al agregado nacional).
    """
    import datetime as _dt
    import itertools

    fixed_lr           = params['lr']
    fixed_layers        = params['layers']
    point_channel       = resolve_point_channel(metrica, params)
    ft_ctx_grid         = params['ft_ctx_grid']
    log_transform_grid  = params['log_transform_grid']
    ft_hor              = params['ft_hor']
    ft_step             = params['ft_step']
    ft_epochs           = params['ft_epochs']
    recursive_step      = params['recursive_step']
    val_months          = params['val_months']

    def progress(pct, msg):
        print(f'PROGRESS:{pct}:{msg}', flush=True)

    progress(5, 'Cargando modelo TimesFM 2.5...')
    model, base_module, consts = load_timesfm_model(model_dir)

    now = _dt.datetime.now().year
    f_end = f_end_override if f_end_override else f'{now + 3}-12'
    fecha_fin_pronostico   = pd.Timestamp(f_end + '-01')
    ultima_fecha_historico = df['Fecha'].iloc[-1]
    horizonte_meses = (
        (fecha_fin_pronostico.year  - ultima_fecha_historico.year)  * 12 +
        (fecha_fin_pronostico.month - ultima_fecha_historico.month)
    )
    if horizonte_meses > model.forecast_config.max_horizon:
        raise ValueError(
            f'HORIZONTE_MESES ({horizonte_meses}) supera max_horizon '
            f'({model.forecast_config.max_horizon}) configurado en compile().'
        )

    q_low, q_high = 1, 9   # p10, p90 (canal 0=media, 1..9=deciles 0.1..0.9)
    forecast_dates = pd.date_range(
        ultima_fecha_historico + pd.DateOffset(months=1), periods=horizonte_meses, freq='MS'
    )

    series_out = {}
    mapes = []
    n_grupos = len(grupos)
    combos = list(itertools.product(ft_ctx_grid, log_transform_grid))

    for gi, grupo in enumerate(grupos):
        grupo_lo = 10 + int(gi / n_grupos * 85)
        grupo_hi = 10 + int((gi + 1) / n_grupos * 85)
        progress(grupo_lo, f'Grupo {gi + 1}/{n_grupos}: {grupo}...')

        all_values = df[grupo].values.astype(np.float32)
        n = len(all_values)

        if n < ft_ctx_grid[0] + val_months or np.isnan(all_values).all():
            print(f'  [AVISO] Histórico insuficiente o vacío para "{grupo}" -- se omite.', flush=True)
            continue

        backtest_actual = all_values[n - val_months:]

        best_mape  = float('inf')
        ft_ctx     = ft_ctx_grid[0]
        log_transform = log_transform_grid[0]

        for ci, (candidate_ctx, candidate_log) in enumerate(combos):
            slice_lo = grupo_lo + int(ci / len(combos) * (grupo_hi - grupo_lo) * 0.9)
            slice_hi = grupo_lo + int((ci + 1) / len(combos) * (grupo_hi - grupo_lo) * 0.9)
            label = f'{grupo}: FT_CTX={candidate_ctx}, LOG_TRANSFORM={candidate_log}'

            all_values_model = np.log(all_values) if candidate_log else all_values
            backtest_context = all_values_model[:n - val_months]

            ft_windows_bt = build_ft_windows(all_values_model[:-val_months], candidate_ctx, ft_hor, ft_step)
            ft_m_bt = make_ft_module(fixed_layers, base_module)
            ft_m_bt = run_ft_training(
                ft_m_bt, fixed_lr, ft_epochs, ft_windows_bt, point_channel,
                progress_range=(slice_lo, slice_hi), progress_label=label,
            )

            bt_point_model, _ = recursive_forecast(model, ft_m_bt, backtest_context, val_months,
                                                    recursive_step, point_channel)
            bt_point = to_raw(bt_point_model, candidate_log)
            mape_combo = mean_absolute_percentage_error(backtest_actual, bt_point) * 100
            print(f'  {label}: MAPE={mape_combo:.2f}%', flush=True)

            if mape_combo < best_mape:
                best_mape = mape_combo
                ft_ctx = candidate_ctx
                log_transform = candidate_log
            del ft_m_bt

        print(f'  Mejor combinación para "{grupo}": FT_CTX={ft_ctx}, LOG_TRANSFORM={log_transform} '
              f'(MAPE {best_mape:.2f}%)', flush=True)

        # Fine-tuning FINAL sobre el 100% del histórico de este grupo
        all_values_model = np.log(all_values) if log_transform else all_values
        ft_windows_final = build_ft_windows(all_values_model, ft_ctx, ft_hor, ft_step)
        ft_model_final = make_ft_module(fixed_layers, base_module)
        ft_model_final = run_ft_training(
            ft_model_final, fixed_lr, ft_epochs, ft_windows_final, point_channel,
            progress_range=(grupo_hi - 3, grupo_hi), progress_label=f'{grupo}: entrenamiento final',
        )

        forecast_point_model, forecast_quant_model = recursive_forecast(
            model, ft_model_final, all_values_model, horizonte_meses, recursive_step, point_channel
        )
        forecast_point = to_raw(forecast_point_model, log_transform)
        forecast_quant = to_raw(forecast_quant_model, log_transform)

        historico = [
            {'fecha': row['Fecha'].strftime('%Y-%m'), 'valor': round(float(row[grupo])) if pd.notna(row[grupo]) else None}
            for _, row in df.iterrows()
        ]
        pronostico = [
            {'fecha': d.strftime('%Y-%m'), 'valor': round(float(v))}
            for d, v in zip(forecast_dates, forecast_point)
        ]
        intervalo_confianza = {
            'superior': [{'fecha': d.strftime('%Y-%m'), 'valor': round(float(v))}
                         for d, v in zip(forecast_dates, forecast_quant[:, q_high])],
            'inferior': [{'fecha': d.strftime('%Y-%m'), 'valor': round(float(v))}
                         for d, v in zip(forecast_dates, forecast_quant[:, q_low])],
        }

        series_out[grupo] = {
            'historico': historico, 'pronostico': pronostico, 'intervalo_confianza': intervalo_confianza,
        }
        mapes.append(best_mape)
        del ft_model_final

    progress(96, 'Construyendo resultado...')
    result = {
        'metrica':     metrica,
        'modo':        'atributo',
        'modelo':      'TimesFM',
        'atributo':    atributo,
        'anio_inicio': int(df['Fecha'].iloc[0].year),
        'series':      series_out,
        'mape':        round(float(np.mean(mapes)), 2) if mapes else None,
    }
    return result
