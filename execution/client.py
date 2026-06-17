def place_market_order(self, symbol, side, contracts):
    try:
        params = {
            "tdMode": "isolated",
            "posSide": "long" if side == "buy" else "short"
        }
        return self.exchange.create_order(symbol, "market", side, contracts, None, params)
    except Exception as e:
        logger.error(f"place_market_order error: {e}")
        return None

def place_take_profit(self, symbol, side, contracts, price):
    try:
        params = {
            "tdMode": "isolated",
            "reduceOnly": True,
            "stopPrice": price,
            "posSide": "long" if side == "sell" else "short"
        }
        return self.exchange.create_order(symbol, "take_profit_market", side, contracts, None, params)
    except Exception as e:
        logger.error(f"place_take_profit error: {e}")
        return None

def place_stop_loss(self, symbol, side, contracts, price):
    try:
        params = {
            "tdMode": "isolated",
            "reduceOnly": True,
            "stopPrice": price,
            "posSide": "long" if side == "sell" else "short"
        }
        return self.exchange.create_order(symbol, "stop_market", side, contracts, None, params)
    except Exception as e:
        logger.error(f"place_stop_loss error: {e}")
        return None
