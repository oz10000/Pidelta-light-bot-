# main.py
import time
import logging
from datetime import datetime
import config
from data.ohlcv import fetch_ohlcv
from signal.engine import compute_signal_for_asset
from execution.client import OKXClient
from risk.sizing import calculate_contracts

# Configuración de logging
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
    """Descarga OHLCV para todos los activos."""
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
    """Calcula señal para cada activo usando BTC y ETH como macro."""
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
    """Selecciona la señal con mayor |score| (ignorando 'none')."""
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
    """Ejecuta orden atómica: market → confirmación fill → TP/SL."""
    if signal["signal"] == "long":
        sl_price = price - config.SL_ATR_MULT * signal["atr"]
    else:
        sl_price = price + config.SL_ATR_MULT * signal["atr"]

    contracts = calculate_contracts(
        client.exchange, signal["asset"], equity, config.RISK_PER_TRADE,
        price, sl_price, config.MAX_LEVERAGE
    )
    if contracts <= 0:
        logger.error("Contratos inválidos, abortando trade")
        return False

    side = "buy" if signal["signal"] == "long" else "sell"

    if config.MODE == "paper":
        logger.info(f"[PAPER] {signal['signal']} {contracts} {signal['asset']} @ {price}")
        return True

    # 1. Orden market
    order = client.place_market_order(signal["asset"], side, contracts)
    if not order or order.get("status") not in ("closed", "filled"):
        logger.error("Orden market falló")
        return False

    # 2. Confirmar fill (pequeña pausa)
    time.sleep(1)
    fill_price = order.get("price", price)

    # 3. Calcular TP/SL y colocarlos
    if signal["signal"] == "long":
        tp_price = fill_price + config.TP_ATR_MULT * signal["atr"]
        sl_price = fill_price - config.SL_ATR_MULT * signal["atr"]
    else:
        tp_price = fill_price - config.TP_ATR_MULT * signal["atr"]
        sl_price = fill_price + config.SL_ATR_MULT * signal["atr"]

    client.place_take_profit(signal["asset"], side, contracts, tp_price)
    client.place_stop_loss(signal["asset"], side, contracts, sl_price)

    logger.info(f"Trade ejecutado: {signal['signal']} {contracts} {signal['asset']} @ {fill_price}")
    return True

def main():
    if config.MODE != "paper" and (not config.API_KEY or not config.SECRET_KEY or not config.PASSPHRASE):
        logger.error("Faltan credenciales de API. Configure las variables de entorno.")
        return

    client = OKXClient()
    last_candle_time = None
    logger.info("Bot iniciado en modo " + config.MODE.upper())

    while True:
        # Candle lock: obtener referencia de última vela (BTC)
        ref_df = fetch_ohlcv("BTC/USDT:USDT", timeframe=config.TIMEFRAME, limit=2)
        if ref_df is None or ref_df.empty:
            time.sleep(10)
            continue

        current_candle = ref_df.iloc[-1]["timestamp"]
        if current_candle == last_candle_time:
            time.sleep(10)
            continue
        last_candle_time = current_candle

        # Filtro horario
        now_hour = datetime.utcnow().hour
        if not (config.TRADE_HOURS_START <= now_hour < config.TRADE_HOURS_END):
            logger.info("Fuera de horario operativo")
            time.sleep(300)
            continue

        # Descargar datos de todos los activos
        data = fetch_all_data(config.ASSETS, limit=200)
        if len(data) < len(config.ASSETS):
            logger.warning("No se pudieron obtener todos los datos")
            time.sleep(30)
            continue

        # Calcular señales
        signals = compute_all_signals(data, config.ASSETS)
        best = select_best(signals)
        if not best or abs(best["score"]) < config.SCORE_THRESHOLD:
            continue

        logger.info(f"Mejor señal: {best['asset']} {best['signal']} score={best['score']:.4f}")

        # Verificar posición real en exchange
        if client.has_open_position(best["asset"]):
            logger.info("Ya hay posición abierta, no se abre otra")
            continue

        equity = client.fetch_free_equity()
        ticker = client.fetch_ticker(best["asset"])
        price = ticker["last"]

        if execute_trade(client, best, price, equity):
            # Registrar en state.json (solo log)
            with open("state.json", "a") as f:
                f.write(f"{datetime.utcnow().isoformat()},{best['asset']},{best['signal']},{price}\n")

        time.sleep(10)  # pequeña pausa para evitar ciclos muy rápidos

if __name__ == "__main__":
    main()
