# risk/sizing.py
def get_step_size(exchange, symbol):
    market = exchange.market(symbol)
    step = market.get("limits", {}).get("amount", {}).get("step")
    if step is None:
        step = market.get("precision", {}).get("amount")
    if step is None:
        step = 0.001
    return float(step)

def calculate_contracts(exchange, symbol, equity, risk_per_trade, entry_price, sl_price, max_leverage):
    sl_distance = abs(entry_price - sl_price)
    if sl_distance <= 0:
        return 0.0
    risk_usd = equity * risk_per_trade
    contracts = risk_usd / sl_distance
    max_contracts = (equity * max_leverage) / entry_price
    contracts = min(contracts, max_contracts)
    market = exchange.market(symbol)
    max_qty = market.get("limits", {}).get("amount", {}).get("max", float("inf"))
    contracts = min(contracts, max_qty)
    step = get_step_size(exchange, symbol)
    contracts = round(contracts - (contracts % step), 6)
    return max(0.0, contracts)
