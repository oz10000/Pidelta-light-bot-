import ccxt
import config
import logging
import time
import re

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
        """Obtiene el modo de posición de la cuenta (net_mode o long_short_mode)."""
        if self._mode:
            return self._mode
        try:
            res = self.exchange.private_get_account_config()
            self._mode = res["data"][0]["posMode"]
        except Exception:
            self._mode = "long_short_mode"
        return self._mode

    def _pos_side(self, direction):
        """
        Determina posSide según el modo de la cuenta.
        - net_mode: no se envía posSide
        - long_short_mode: "long" o "short"
        """
        mode = self._get_mode()
        if mode == "net_mode":
            return None
        return "long" if direction == "long" else "short"

    def _generate_cl_ord_id(self, prefix, symbol):
        """
        Genera un clOrdId válido para OKX.
        Requisitos: solo alfanumérico, comienza con letra, máximo 32 caracteres.
        """
        # Limpiar símbolo: eliminar "/" y ":" para evitar caracteres inválidos
        clean_symbol = re.sub(r'[/:]', '_', symbol)
        # Base del ID: prefijo + símbolo + timestamp
        base = f"{prefix}_{clean_symbol}_{int(time.time() * 1000)}"
        # Asegurar que comienza con letra
        if not base[0].isalpha():
            base = f"p{base}"
        # Truncar a 32 caracteres si es necesario
        if len(base) > 32:
            base = base[:32]
        return base

    def fetch_balance(self):
        """Obtiene el saldo disponible en USDT."""
        return self.exchange.fetch_balance().get("USDT", {}).get("free", 0.0)

    def fetch_ticker(self, symbol):
        """Obtiene el ticker actual de un símbolo."""
        return self.exchange.fetch_ticker(symbol)

    def has_open_position(self, symbol):
        """Verifica si existe una posición abierta para el símbolo."""
        try:
            pos = self.exchange.fetch_positions([symbol])
            return any(float(p.get("contracts") or 0) != 0 for p in pos)
        except Exception:
            return False

    def place_market_order(self, symbol, side, size):
        """
        Coloca una orden de mercado.
        Incluye clOrdId para trazabilidad.
        """
        try:
            direction = "long" if side == "buy" else "short"
            pos_side = self._pos_side(direction)
            cl_ord_id = self._generate_cl_ord_id("mkt", symbol)

            params = {
                "tdMode": "isolated",
                "clOrdId": cl_ord_id,
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
            logger.error(f"place_market_order error: {e}")
            return None

    def place_take_profit(self, symbol, side, size, price):
        """
        Coloca una orden de Take Profit (orden condicional).
        """
        return self._place_trigger(
            symbol, side, size, price,
            "tpTriggerPx", "tpOrdPx",
            "tp"
        )

    def place_stop_loss(self, symbol, side, size, price):
        """
        Coloca una orden de Stop Loss (orden condicional).
        """
        return self._place_trigger(
            symbol, side, size, price,
            "slTriggerPx", "slOrdPx",
            "sl"
        )

    def _place_trigger(self, symbol, side, size, price, px_key, ord_key, prefix):
        """
        Coloca una orden condicional (TP o SL) en OKX.
        - px_key: "tpTriggerPx" o "slTriggerPx"
        - ord_key: "tpOrdPx" o "slOrdPx"
        - prefix: "tp" o "sl" para generar clOrdId
        """
        try:
            direction = "long" if side == "sell" else "short"
            pos_side = self._pos_side(direction)

            # Generar clOrdId válido para OKX
            cl_ord_id = self._generate_cl_ord_id(prefix, symbol)

            # Parámetros para orden condicional (TP/SL)
            params = {
                "tdMode": "isolated",
                "reduceOnly": True,
                "clOrdId": cl_ord_id,
                "ordType": "conditional",        # Obligatorio para TP/SL en OKX
                px_key: price,                    # tpTriggerPx o slTriggerPx
                ord_key: price,                   # tpOrdPx o slOrdPx
            }
            if pos_side:
                params["posSide"] = pos_side

            logger.debug(f"Colocando orden {prefix}: symbol={symbol}, side={side}, "
                         f"price={price}, clOrdId={cl_ord_id}")

            return self.exchange.create_order(
                symbol,
                "market",      # El tipo base no importa, los params definen la lógica
                side,
                size,
                None,
                params
            )
        except Exception as e:
            logger.error(f"Error en _place_trigger ({prefix}): {e}")
            return None
