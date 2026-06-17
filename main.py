import os
import time
import logging
from datetime import datetime

import config
from data.ohlcv import fetch_ohlcv
from strategy.engine import compute_signal_for_asset
from execution.client import OKXClient
from risk.sizing import calculate_contracts
from utils.telemetry import log_event

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/trading.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("PideltaBot")


def fetch_all_data(assets, limit=200):
    data = {}

    for asset in assets:
        try:
            symbol = asset.replace(":USDT", "")
            df = fetch_ohlcv(symbol, timeframe=config.TIMEFRAME, limit=limit)

            if df is not None and not df.empty:
                data[asset] = df

        except Exception as e:
            logger.error(f"fetch error {asset}: {e}")

    return data


def compute_all_signals(data, assets):
    """
    Macro SIMÉTRICO REAL:
    cada activo usa los otros dos como contexto macro.
    """

    required = set(assets)
    if not required.issubset(set(data.keys())):
        return []

    df_btc = data["BTC/USDT:USDT"]
    df_eth = data["ETH/USDT:USDT"]
    df_sol = data["SOL/USDT:USDT"]

    macro_map = {
        "BTC/USDT:USDT": (df_eth, df_sol),
        "ETH/USDT:USDT": (df_btc, df_sol),
        "SOL/USDT:USDT": (df_btc, df_eth),
    }

    signals = []

    for asset in assets:
        df_self = data.get(asset)
        if df_self is None or df_self.empty:
            continue

        macro_a, macro_b = macro_map[asset]

        sig = compute_signal_for_asset(
            df_self,
            macro_a,
            macro_b,
            config.SCORE_THRESHOLD
        )

        sig["asset"] = asset
        signals.append(sig)

    return signals


def select_best(signals):
    best = None
    best_score = 0.0

    for s in signals:
        if s["signal"] == "none":
            continue

        if abs(s["score"]) > abs(best_score):
            best = s
            best_score = s["score"]

    return best


def execute_trade(client, signal, price, equity):
    side = "buy" if signal["signal"] == "long" else "sell"

    sl_price = (
        price - config.SL_ATR_MULT * signal["atr"]
        if signal["signal"] == "long"
        else price + config.SL_ATR_MULT * signal["atr"]
    )

    contracts = calculate_contracts(
        client.exchange,
        signal["asset"],
        equity,
        config.RISK_PER_TRADE,
        price,
        sl_price,
        config.MAX_LEVERAGE
    )

    if contracts <= 0:
        return False

    if config.MODE == "paper":
        logger.info(f"[PAPER] {signal}")
        return True

    order = client.place_market_order(signal["asset"], side, contracts)
    if not order:
        return False

    tp_price = (
        price + config.TP_ATR_MULT * signal["atr"]
        if signal["signal"] == "long"
        else price - config.TP_ATR_MULT * signal["atr"]
    )

    sl_price = (
        price - config.SL_ATR_MULT * signal["atr"]
        if signal["signal"] == "long"
        else price + config.SL_ATR_MULT * signal["atr"]
    )

    client.place_take_profit(signal["asset"], side, contracts, tp_price)
    client.place_stop_loss(signal["asset"], side, contracts, sl_price)

    logger.info(f"TRADE EXECUTED {signal}")
    return True


def main():
    client = OKXClient()

    last_candle = None

    while True:
        try:
            ref = fetch_ohlcv("BTC/USDT", config.TIMEFRAME, 2)
            candle_time = ref.iloc[-1]["timestamp"]

            if candle_time == last_candle:
                time.sleep(5)
                continue

            last_candle = candle_time

            hour = datetime.utcnow().hour
            if not (config.TRADE_HOURS_START <= hour < config.TRADE_HOURS_END):
                time.sleep(60)
                continue

            data = fetch_all_data(config.ASSETS)
            signals = compute_all_signals(data, config.ASSETS)

            best = select_best(signals)
            if not best or abs(best["score"]) < config.SCORE_THRESHOLD:
                continue

            if client.has_open_position(best["asset"]):
                continue

            equity = client.fetch_free_equity()
            ticker = client.fetch_ticker(best["asset"])

            price = ticker["last"]

            execute_trade(client, best, price, equity)

            time.sleep(5)

        except Exception as e:
            logger.error(f"loop error: {e}")
            time.sleep(30)


if __name__ == "__main__":
    main()
