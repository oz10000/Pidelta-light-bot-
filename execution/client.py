import ccxt
import config
import logging

logger = logging.getLogger("PideltaBot")


class OKXClient:
    """
    OKX Execution Adapter (OCA)

    Responsable único de:
    - Traducir intención → órdenes OKX válidas
    - Manejar posSide correctamente según modo de cuenta
    - Ejecutar TP/SL compatibles con CCXT OKX
    - Evitar errores 51000
    """

    # --------------------------------------------------------------
    # INIT
    # --------------------------------------------------------------
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

    # --------------------------------------------------------------
    # ACCOUNT MODE (SOURCE OF TRUTH)
    # --------------------------------------------------------------
    def get_account_mode(self):
        """
        Returns:
            - net_mode
            - long_short_mode
        """
        try:
            res = self.exchange.private_get_account_config()
            return res["data"][0]["posMode"]
        except Exception as e:
            logger.error(f"[OKX] account mode error: {e}")
            # fallback seguro
            return "long_short_mode"

    # --------------------------------------------------------------
    # POSITION STATE (SOURCE OF TRUTH)
    # --------------------------------------------------------------
    def fetch_position(self, symbol):
        try:
            positions = self.exchange.fetch_positions([symbol])

            for p in positions:
                size = float(p.get("contracts") or 0)

                if size != 0:
                    return {
                        "side": p.get("side"),  # long / short
                        "size": size,
                        "entry_price": float(p.get("entryPrice") or 0.0)
                    }

        except Exception as e:
            logger.error(f"[OKX] fetch_position error: {e}")

        return None

    def has_open_position(self, symbol):
        return self.fetch_position(symbol) is not None

    # --------------------------------------------------------------
    # BALANCE / TICKER
    # --------------------------------------------------------------
    def fetch_free_equity(self):
        try:
            balance = self.exchange.fetch_balance()
            return balance.get("USDT", {}).get("free", 0.0)
        except Exception as e:
            logger.error(f"[OKX] fetch_free_equity error: {e}")
            return 0.0

    def fetch_ticker(self, symbol):
        try:
            return self.exchange.fetch_ticker(symbol)
        except Exception as e:
            logger.error(f"[OKX] fetch_ticker error: {e}")
            return None

    # --------------------------------------------------------------
    # posSide RESOLUTION (CORE LOGIC)
    # --------------------------------------------------------------
    def _resolve_pos_side(self, account_mode, direction):
        """
        direction:
            - long
            - short
        """

        if account_mode == "net_mode":
            return None

        if account_mode == "long_short_mode":
            return "long" if direction == "long" else "short"

        return None

    # --------------------------------------------------------------
    # MARKET ORDER (OPEN / CLOSE)
    # --------------------------------------------------------------
    def place_market_order(self, symbol, direction, size):
        """
        direction:
            - long
            - short
        """

        try:
            self.validate_symbol(symbol)

            account_mode = self.get_account_mode()
            posSide = self._resolve_pos_side(account_mode, direction)

            params = {
                "tdMode": "isolated"
            }

            if posSide:
                params["posSide"] = posSide

            side = "buy" if direction == "long" else "sell"

            return self.exchange.create_order(
                symbol,
                "market",
                side,
                size,
                None,
                params
            )

        except Exception as e:
            logger.error(f"[OKX] place_market_order error: {e}")
            return None

    # --------------------------------------------------------------
    # TP / SL (OKX SAFE IMPLEMENTATION)
    # --------------------------------------------------------------
    def place_tp_sl(self, symbol, direction, size, tp_price=None, sl_price=None):
        """
        direction:
            - long
            - short
        """

        try:
            self.validate_symbol(symbol)

            account_mode = self.get_account_mode()
            posSide = self._resolve_pos_side(account_mode, direction)

            params = {
                "tdMode": "isolated"
            }

            if posSide:
                params["posSide"] = posSide

            # TAKE PROFIT
            if tp_price:
                params["tpTriggerPx"] = tp_price
                params["tpOrdPx"] = tp_price

            # STOP LOSS
            if sl_price:
                params["slTriggerPx"] = sl_price
                params["slOrdPx"] = sl_price

            # CCXT-compatible execution
            return self.exchange.create_order(
                symbol,
                "market",
                "sell" if direction == "long" else "buy",
                size,
                None,
                params
            )

        except Exception as e:
            logger.error(f"[OKX] place_tp_sl error: {e}")
            return None

    # --------------------------------------------------------------
    # SYMBOL VALIDATION (MULTI-ASSET SAFETY)
    # --------------------------------------------------------------
    SUPPORTED_SYMBOLS = {
        "BTC/USDT:USDT",
        "ETH/USDT:USDT",
        "SOL/USDT:USDT"
    }

    def validate_symbol(self, symbol):
        if symbol not in self.SUPPORTED_SYMBOLS:
            raise ValueError(f"[OKX] Unsupported symbol: {symbol}")
