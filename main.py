# main.py
import os
import time
import logging
from datetime import datetime

import config
from data.ohlcv import fetch_ohlcv
from strategy.engine import compute_signal_for_asset
from execution.client import OKXClient
from risk.sizing import calculate_contracts

os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
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
            df = fetch_ohlcv(asset, timeframe=config.TIMEFRAME, limit=limit)
            if df is not None and not df.empty:
                data[asset] = df
        except Exception as e:
            logger.error(f"Error fetching {asset}: {e}")
    return data

def compute_all_signals(data, assets):
    if "BTC/USDT:USDT" not in data or "ETH/USDT:USDT" not in data:
        return []
    df_btc = data["BTC/USDT:USDT"]
    df_eth = data["ETH/USDT:USDT"]
    signals = []
    for asset in assets:
        df_self = data.get(asset)
        if df_self is None or df_self.empty:
            continue
        sig = compute_signal_for_asset(df_self, df_btc, df_eth, config.SCORE_THRESHOLD)
        sig["asset"] = asset
        signals.append(sig)
    return signals

def select_best(signals):
    best = None
    best_abs = -1.0
    for sig in signals:
        if sig["signal"] == "none":
            continue
        s_abs = abs(sig["score"])
        if s_abs > best_abs:
            best_abs = s_abs
            best = sig
    return best

def execute_trade(client, signal, price, equity):
    if signal["signal"] == "long":
        sl_price = price - config.SL_ATR_MULT * signal["atr"]
    else:
        sl_price = price + config.SL_ATR_MULT * signal["atr"]

    contracts = calculate_contracts(
        client.exchange, signal["asset"], equity,
        config.RISK_PER_TRADE, price, sl_price, config.MAX_LEVERAGE
    )
    if contracts <= 0:
        logger.error("Contracts <= 0, aborting trade")
        return False

    side = "buy" if signal["signal"] == "long" else "sell"

    if config.MODE == "paper":
        logger.info(f"[PAPER] {signal['signal']} {contracts} {signal['asset']} @ {price}")
        return True

    # Orden market
    order = client.place_market_order(signal["asset"], side, contracts)
    if order is None:
        logger.error("Market order returned None")
        return False

    status = order.get("status")
    if status not in ("closed", "filled"):
        logger.error(f"Market order not filled. Status: {status}")
        return False

    time.sleep(1)  # breve espera para confirmación
    fill_price = order.get("price", price)

    if signal["signal"] == "long":
        tp_price = fill_price + config.TP_ATR_MULT * signal["atr"]
        sl_price = fill_price - config.SL_ATR_MULT * signal["atr"]
    else:
        tp_price = fill_price - config.TP_ATR_MULT * signal["atr"]
        sl_price = fill_price + config.SL_ATR_MULT * signal["atr"]

    tp_ok = client.place_take_profit(signal["asset"], side, contracts, tp_price)
    sl_ok = client.place_stop_loss(signal["asset"], side, contracts, sl_price)

    if not tp_ok or not sl_ok:
        logger.error("Failed to place TP/SL, but position may be open. Check manually.")
        return False

    logger.info(f"Trade executed: {signal['signal']} {contracts} {signal['asset']} @ {fill_price}")
    return True

def main():
    if config.MODE != "paper" and (not config.API_KEY or not config.SECRET_KEY or not config.PASSPHRASE):
        logger.error("Missing API credentials. Set environment variables.")
        return

    client = OKXClient()
    last_candle_time = None
    logger.info("Bot started in mode " + config.MODE.upper())

    while True:
        try:
            ref_df = fetch_ohlcv("BTC/USDT:USDT", timeframe=config.TIMEFRAME, limit=2)
            if ref_df is None or ref_df.empty:
                time.sleep(10)
                continue

            current_candle = ref_df.iloc[-1]["timestamp"]
            if current_candle == last_candle_time:
                time.sleep(10)
                continue
            last_candle_time = current_candle

            now_hour = datetime.utcnow().hour
            if not (config.TRADE_HOURS_START <= now_hour < config.TRADE_HOURS_END):
                logger.info("Outside trading hours")
                time.sleep(300)
                continue

            data = fetch_all_data(config.ASSETS, limit=200)
            if len(data) < len(config.ASSETS):
                logger.warning("Not all assets available")
                time.sleep(30)
                continue

            signals = compute_all_signals(data, config.ASSETS)
            best = select_best(signals)
            if not best or abs(best["score"]) < config.SCORE_THRESHOLD:
                continue

            logger.info(f"Best signal: {best['asset']} {best['signal']} score={best['score']:.4f}")

            if client.has_open_position(best["asset"]):
                logger.info("Position already open, skipping")
                continue

            equity = client.fetch_free_equity()
            ticker = client.fetch_ticker(best["asset"])
            if ticker is None:
                logger.error("Ticker not available")
                time.sleep(10)
                continue

            price = ticker["last"]

            if execute_trade(client, best, price, equity):
                with open("state.json", "a") as f:
                    f.write(f"{datetime.utcnow().isoformat()},{best['asset']},{best['signal']},{price}\n")

            time.sleep(10)

        except Exception as e:
            logger.exception("Unhandled exception in main loop")
            time.sleep(60)

if __name__ == "__main__":
    main()
