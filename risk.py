import MetaTrader5 as mt5

def validate_trade_inputs(config, side, volume, sl_distance, reward_risk):
    if side not in {"BUY", "SELL"}:
        raise ValueError("Side must be BUY or SELL.")
    if volume <= 0 or volume > config.max_volume:
        raise ValueError(f"Volume must be greater than 0 and no more than {config.max_volume} lots.")
    if sl_distance <= 0:
        raise ValueError("Stop-loss distance must be positive.")
    if reward_risk < 1:
        raise ValueError("Reward:risk must be at least 1.0.")
    if not config.execution_enabled:
        raise ValueError("Demo execution is disabled in configuration.")

def build_protected_market_request(adapter, side, volume, sl_distance, reward_risk):
    mt5m = adapter.mt5
    symbol = adapter.cfg.symbol
    info = adapter.symbol_info()
    tick = adapter.tick()

    # Round to broker's symbol precision and respect volume increments.
    digits = int(info.digits)
    step = float(info.volume_step)
    min_vol = float(info.volume_min)
    max_vol = min(float(info.volume_max), adapter.cfg.max_volume)
    volume = round(round(volume / step) * step, 8)
    if volume < min_vol or volume > max_vol:
        raise ValueError(f"Volume outside broker range ({min_vol}–{max_vol}, step {step}).")

    is_buy = side == "BUY"
    entry = float(tick.ask if is_buy else tick.bid)
    sl = entry - sl_distance if is_buy else entry + sl_distance
    tp_distance = sl_distance * reward_risk
    tp = entry + tp_distance if is_buy else entry - tp_distance
    entry, sl, tp = (round(x, digits) for x in (entry, sl, tp))

    # Validate direction relative to executable quote.
    if is_buy and not (sl < entry < tp):
        raise ValueError("Invalid BUY protection levels.")
    if not is_buy and not (tp < entry < sl):
        raise ValueError("Invalid SELL protection levels.")

    # SYMBOL_FILLING_* values are flags; ORDER_FILLING_* values are request enums.
    # Prefer IOC, then FOK when supported. RETURN is not permitted for Market
    # Execution symbols, so fail closed if no compatible policy is advertised.
    flags = int(getattr(info, "filling_mode", 0) or 0)
    if flags & getattr(mt5m, "SYMBOL_FILLING_IOC", 2):
        filling = mt5m.ORDER_FILLING_IOC
    elif flags & getattr(mt5m, "SYMBOL_FILLING_FOK", 1):
        filling = mt5m.ORDER_FILLING_FOK
    elif getattr(info, "trade_exemode", None) != getattr(mt5m, "SYMBOL_TRADE_EXECUTION_MARKET", 2):
        filling = mt5m.ORDER_FILLING_RETURN
    else:
        raise ValueError("Broker symbol does not advertise a compatible filling policy.")
    return {
        "action": mt5m.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": mt5m.ORDER_TYPE_BUY if is_buy else mt5m.ORDER_TYPE_SELL,
        "price": entry,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "magic": 26093001,
        "comment": "XAUUSD-Streamlit-Demo",
        "type_time": mt5m.ORDER_TIME_GTC,
        "type_filling": filling,
    }
