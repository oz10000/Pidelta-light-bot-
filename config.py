import os

MODE = "demo"  # paper | demo | live

ASSETS = [
    "BTC/USDT:USDT",
    "ETH/USDT:USDT",
    "SOL/USDT:USDT"
]

TIMEFRAME = "5m"

# Strategy
SCORE_THRESHOLD = 0.20
RISK_PER_TRADE = 0.02
MAX_LEVERAGE = 9

TP_ATR_MULT = 1.2
SL_ATR_MULT = 1.5

# Time filter UTC
TRADE_HOURS_START = 12
TRADE_HOURS_END = 16

# OKX credentials
API_KEY = os.getenv("OKX_API_KEY", "")
SECRET_KEY = os.getenv("OKX_SECRET", "")
PASSPHRASE = os.getenv("OKX_PASSPHRASE", "")
