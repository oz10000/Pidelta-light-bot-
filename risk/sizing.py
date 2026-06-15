# risk/sizing.py
def get_step_size(exchange, symbol: str) -> float:
    """Obtiene el stepSize para la cantidad de contratos."""
    market = exchange.market(symbol)
    step = market.get("limits", {}).get("amount", {}).get("step")
    if step is None:
        step = market.get("precision", {}).get("amount")
    if step is None:
        step = 0.001   # valor seguro para SOL, ETH, BTC
    return float(step)

def calculate_contracts(exchange, symbol: str, equity: float, risk_per_trade: float,
                        entry_price: float, sl_price: float, max_leverage: int) -> float:
    """
    Calcula el número de contratos basado en el riesgo en USD.
    Fórmula: contracts = (equity * risk_per_trade) / abs(entry - sl)
    Luego aplica límites: apalancamiento máximo, max_qty del exchange, step size.
    """
    sl_distance = abs(entry_price - sl_price)
    if sl_distance <= 0:
        return 0.0

    risk_usd = equity * risk_per_trade
    contracts = risk_usd / sl_distance

    # Límite por apalancamiento
    max_contracts = (equity * max_leverage) / entry_price
    contracts = min(contracts, max_contracts)

    # Límite por cantidad máxima del exchange
    market = exchange.market(symbol)
    max_qty = market.get("limits", {}).get("amount", {}).get("max", float("inf"))
    contracts = min(contracts, max_qty)

    # Redondeo por step size
    step = get_step_size(exchange, symbol)
    contracts = round(contracts - (contracts % step), 6)
    return max(0.0, contracts)
