import ccxt
import config
import logging

logger = logging.getLogger("OKXClient")


class OKXClient:

    def __init__(self):
        self.exchange = ccxt.okx({
            "apiKey": config.API_KEY,
            "secret": config.SECRET_KEY,
            "password": config.PASSPHRASE,
            "enableRateLimit": True,
        })

        self._mode = None

    def _get_mode(self):
        if self._mode:
            return self._mode

        try:
            res = self.exchange.private_get_account_config()
            self._mode = res["data"][0]["posMode"]
        except Exception:
            self._mode = "long_short_mode"

        return self._mode

    def _pos_side(self, direction):
        mode = self._get_mode()

        if mode == "net_mode":
            return None

        return "long" if direction == "long" else "short"

    def fetch_balance(self):
        return self.exchange.fetch_balance().get("USDT", {}).get("free", 0.0)

    def fetch_ticker(self, symbol):
        return self.exchange.fetch_ticker(symbol)

    def has_open_position(self, symbol):
        try:
            pos = self.exchange.fetch_positions([symbol])
            return any(float(p.get("contracts") or 0) != 0 for p in pos)
        except:
            return False

    def place_market_order(self, symbol, side, size):
        try:
            direction = "long" if side == "buy" else "short"
            pos_side = self._pos_side(direction)

            params = {"tdMode": "isolated"}
            if pos_side:
                params["posSide"] = pos_side

            return self.exchange.create_order(
                symbol,
                "market",
                side,
                size,
                None,
                params
            )
        except Exception as e:
            logger.error(e)
            return None

    def place_take_profit(self, symbol, side, size, price):
        return self._place_trigger(symbol, side, size, price, "tpTriggerPx", "tpOrdPx")

    def place_stop_loss(self, symbol, side, size, price):
        return self._place_trigger(symbol, side, size, price, "slTriggerPx", "slOrdPx")

    def _place_trigger(self, symbol, side, size, price, px_key, ord_key):
        try:
            direction = "long" if side == "sell" else "short"
            pos_side = self._pos_side(direction)

            params = {
                "tdMode": "isolated",
                "reduceOnly": True,
                px_key: price,
                ord_key: price,
            }

            if pos_side:
                params["posSide"] = pos_side

            return self.exchange.create_order(
                symbol,
                "market",
                side,
                size,
                None,
                params
            )

        except Exception as e:
            logger.error(e)
            return None
