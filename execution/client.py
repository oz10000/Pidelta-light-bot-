# execution/client.py
import ccxt
import config
import logging

logger = logging.getLogger("PideltaBot")

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
        """Devuelve dict con posición o None. Protegido contra NoneType."""
        try:
            positions = self.exchange.fetch_positions([symbol])
            if not positions:
                return None
            for pos in positions:
                contracts = pos.get("contracts")
                if contracts is None:
                    continue
                if float(contracts) != 0:
                    return {
                        "side": pos.get("side", ""),
                        "contracts": float(contracts),
                        "entry_price": float(pos.get("entryPrice", 0.0))
                    }
        except Exception as e:
            logger.error(f"fetch_position error: {e}")
        return None

    def has_open_position(self, symbol):
        return self.fetch_position(symbol) is not None

    def fetch_free_equity(self):
        try:
            balance = self.exchange.fetch_balance()
            return balance.get("USDT", {}).get("free", 0.0)
        except Exception as e:
            logger.error(f"fetch_free_equity error: {e}")
            return 0.0

    def fetch_ticker(self, symbol):
        try:
            return self.exchange.fetch_ticker(symbol)
        except Exception as e:
            logger.error(f"fetch_ticker error: {e}")
            return None

    def place_market_order(self, symbol, side, contracts):
        try:
            params = {"tdMode": "isolated"}
            return self.exchange.create_order(symbol, "market", side, contracts, None, params)
        except Exception as e:
            logger.error(f"place_market_order error: {e}")
            return None

    def place_take_profit(self, symbol, side, contracts, price):
        try:
            params = {"tdMode": "isolated", "reduceOnly": True, "stopPrice": price}
            return self.exchange.create_order(symbol, "take_profit_market", side, contracts, None, params)
        except Exception as e:
            logger.error(f"place_take_profit error: {e}")
            return None

    def place_stop_loss(self, symbol, side, contracts, price):
        try:
            params = {"tdMode": "isolated", "reduceOnly": True, "stopPrice": price}
            return self.exchange.create_order(symbol, "stop_market", side, contracts, None, params)
        except Exception as e:
            logger.error(f"place_stop_loss error: {e}")
            return None
