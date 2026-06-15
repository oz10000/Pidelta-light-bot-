# config.py
import os

# Modo de ejecución: "paper", "demo", "live"
MODE = "demo"   # cambiar a "live" solo con fondos reales

# Activos para rotación (orden de prioridad)
ASSETS = ["SOL/USDT:USDT", "ETH/USDT:USDT", "BTC/USDT:USDT"]

# Trading
TIMEFRAME = "5m"
SCORE_THRESHOLD = 0.15
RISK_PER_TRADE = 0.02    # 2% del equity por operación
MAX_LEVERAGE = 9
TP_ATR_MULT = 1.2
SL_ATR_MULT = 1.5

# Horario operativo (UTC)
TRADE_HOURS_START = 8
TRADE_HOURS_END = 20

# Credenciales OKX (usar variables de entorno)
API_KEY = os.getenv("OKX_API_KEY", "")
SECRET_KEY = os.getenv("OKX_SECRET", "")
PASSPHRASE = os.getenv("OKX_PASSPHRASE", "")
