# execution/client.py
import ccxt
import config
import time

class OKXClient:
    def __init__(self):
        self.exchange = ccxt.okx({
            "apiKey": config.API_KEY,
            "secret": config.SECRET_KEY,
            "password": config.PASSPHRASE,
            "enableRateLimit": True,
        })
        if config.MODE in ("demo", "paper"):
            self.exchange.set_sandbox_mode(True)
        else:
            self.exchange.set_sandbox_mode(False)

    def fetch_position(self, symbol):
        """Devuelve la posición activa para el símbolo o None."""
        try:
            positions = self.exchange.fetch_positions([symbol])
            for pos in positions:
                if float(pos.get("contracts", 0)) != 0:
                    return {
                        "side": pos["side"],
                        "contracts": float(pos["contracts"]),
                        "entry_price": float(pos["entryPrice"])
                    }
        except Exception:
            pass
        return None

    def has_open_position(self, symbol):
        return self.fetch_position(symbol) is not None

    def fetch_free_equity(self):
        """Saldo USDT disponible."""
        balance = self.exchange.fetch_balance()
        return balance.get("USDT", {}).get("free", 0.0)

    def fetch_ticker(self, symbol):
        return self.exchange.fetch_ticker(symbol)

    def place_market_order(self, symbol, side, contracts):
        """Coloca una orden de mercado (abre posición)."""
        params = {"tdMode": "isolated"}
        return self.exchange.create_order(symbol, "market", side, contracts, None, params)

    def place_take_profit(self, symbol, side, contracts, price):
        """Orden condicional de Take Profit (reduce only)."""
        params = {"tdMode": "isolated", "reduceOnly": True, "stopPrice": price}
        return self.exchange.create_order(symbol, "take_profit_market", side, contracts, None, params)

    def place_stop_loss(self, symbol, side, contracts, price):
        """Orden condicional de Stop Loss (reduce only)."""
        params = {"tdMode": "isolated", "reduceOnly": True, "stopPrice": price}
        return self.exchange.create_order(symbol, "stop_market", side, contracts, None, params)
