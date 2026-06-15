# signal/engine.py
import numpy as np
import pandas as pd
import math
from typing import Dict

# Parámetros fijos de la estrategia (no cambiar)
EMA_PERIOD = 20
ADX_PERIOD = 14
ATR_PERIOD = 14
CORR_WINDOW = 50
ADX_THRESHOLD = 25
SIGMOID_SCALE = 10.0

def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()

def atr(df: pd.DataFrame, period: int = ATR_PERIOD) -> pd.Series:
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"] - df["close"].shift()).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def adx(df: pd.DataFrame, period: int = ADX_PERIOD) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    atr_val = tr.rolling(period).mean()
    up = high.diff()
    down = low.diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    plus_di = 100 * pd.Series(plus_dm).rolling(period).mean() / atr_val
    minus_di = 100 * pd.Series(minus_dm).rolling(period).mean() / atr_val
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9)
    return dx.rolling(period).mean()

def compute_signal_for_asset(df_self: pd.DataFrame, df_btc: pd.DataFrame, df_eth: pd.DataFrame,
                             score_threshold: float = 0.15) -> Dict:
    """
    Retorna:
    {
        "signal": "long" | "short" | "none",
        "score": float,
        "atr": float,
        "adx": float
    }
    """
    # Micro: pendiente EMA20 / ATR
    ema20 = ema(df_self["close"], EMA_PERIOD)
    slope = ema20.iloc[-1] - ema20.iloc[-2]
    atr_val = atr(df_self).iloc[-1]
    micro = slope / atr_val if atr_val != 0 else 0.0

    # Régimen: ADX > 25
    adx_val = adx(df_self).iloc[-1]
    regime = 1.0 if adx_val > ADX_THRESHOLD else 0.0

    # Macro: alineación de pendientes BTC/ETH + correlación
    ema_btc = ema(df_btc["close"], EMA_PERIOD)
    ema_eth = ema(df_eth["close"], EMA_PERIOD)
    btc_slope = ema_btc.iloc[-1] - ema_btc.iloc[-2]
    eth_slope = ema_eth.iloc[-1] - ema_eth.iloc[-2]
    alignment = 1.0 if (btc_slope * eth_slope > 0) else 0.0
    if alignment == 0.0:
        macro = 0.0
    else:
        corr_btc = df_btc["close"].iloc[-CORR_WINDOW:].corr(df_self["close"].iloc[-CORR_WINDOW:])
        corr_eth = df_eth["close"].iloc[-CORR_WINDOW:].corr(df_self["close"].iloc[-CORR_WINDOW:])
        if pd.isna(corr_btc) or pd.isna(corr_eth):
            macro = 0.0
        else:
            mean_corr = (corr_btc + corr_eth) / 2.0
            macro = 1.0 / (1.0 + math.exp(-SIGMOID_SCALE * (mean_corr - 0.5)))

    raw_score = micro * regime * macro
    score = math.tanh(raw_score)

    if score > score_threshold:
        signal = "long"
    elif score < -score_threshold:
        signal = "short"
    else:
        signal = "none"

    return {
        "signal": signal,
        "score": score,
        "atr": atr_val,
        "adx": adx_val
    }
