from contextlib import contextmanager
from dataclasses import dataclass
import os
import json
import MetaTrader5 as mt5

class MT5Unavailable(RuntimeError):
    pass

@dataclass(frozen=True)
class MT5Config:
    login: int
    password: str
    server: str
    terminal_path: str
    symbol: str = "XAUUSD"
    execution_enabled: bool = False
    max_volume: float = 0.01
    max_positions: int = 1

    @classmethod
    def from_env(cls):
        login = os.getenv("MT5_LOGIN", "").strip()
        password = os.getenv("MT5_PASSWORD", "")
        server = os.getenv("MT5_SERVER", "").strip()
        terminal_path = os.getenv("MT5_TERMINAL_PATH", "").strip()
        if not all([login, password, server, terminal_path]):
            raise MT5Unavailable(
                "Missing MT5_LOGIN, MT5_PASSWORD, MT5_SERVER or MT5_TERMINAL_PATH. "
                "Set them in a local .env file. Do not commit credentials."
            )
        return cls(
            login=int(login), password=password, server=server,
            terminal_path=terminal_path,
            symbol=os.getenv("MT5_SYMBOL", "XAUUSD").strip(),
            execution_enabled=os.getenv("MT5_DEMO_EXECUTION_ENABLED", "false").lower() == "true",
            max_volume=float(os.getenv("MT5_MAX_VOLUME", "0.01")),
            max_positions=int(os.getenv("MT5_MAX_POSITIONS", "1")),
        )

class MT5Adapter:
    def __init__(self, config, mt5_module=None):
        self.cfg = config
        self.mt5 = mt5_module or mt5

    @contextmanager
    def session(self):
        if not self.mt5.initialize(
            path=self.cfg.terminal_path, login=self.cfg.login,
            password=self.cfg.password, server=self.cfg.server, timeout=60000
        ):
            raise MT5Unavailable(f"MT5 initialize failed: {self.mt5.last_error()}")
        try:
            if not self.mt5.symbol_select(self.cfg.symbol, True):
                raise MT5Unavailable(f"Cannot select symbol {self.cfg.symbol}: {self.mt5.last_error()}")
            yield
        finally:
            self.mt5.shutdown()

    def account_info(self):
        info = self.mt5.account_info()
        if info is None:
            raise MT5Unavailable(f"account_info failed: {self.mt5.last_error()}")
        return info

    def terminal_info(self):
        info = self.mt5.terminal_info()
        if info is None:
            raise MT5Unavailable(f"terminal_info failed: {self.mt5.last_error()}")
        return info

    def tick(self):
        tick = self.mt5.symbol_info_tick(self.cfg.symbol)
        if tick is None or not tick.bid or not tick.ask:
            raise MT5Unavailable(f"No usable tick for {self.cfg.symbol}: {self.mt5.last_error()}")
        return tick

    def symbol_info(self):
        info = self.mt5.symbol_info(self.cfg.symbol)
        if info is None:
            raise MT5Unavailable(f"symbol_info failed for {self.cfg.symbol}")
        return info

    def is_demo_account(self, account):
        return getattr(account, "trade_mode", None) == self.mt5.ACCOUNT_TRADE_MODE_DEMO

    def positions(self):
        positions = self.mt5.positions_get(symbol=self.cfg.symbol)
        if positions is None:
            raise MT5Unavailable(f"positions_get failed: {self.mt5.last_error()}")
        return list(positions)

    def submit_demo_order(self, request):
        if not self.cfg.execution_enabled:
            raise MT5Unavailable("Execution disabled. Set MT5_DEMO_EXECUTION_ENABLED=true only for a demo test.")
        account = self.account_info()
        if not self.is_demo_account(account):
            raise MT5Unavailable("Safety stop: connected account is not identified as a DEMO account.")
        if len(self.positions()) >= self.cfg.max_positions:
            raise MT5Unavailable("Position limit reached.")
        if request["volume"] > self.cfg.max_volume:
            raise MT5Unavailable("Requested volume exceeds MT5_MAX_VOLUME.")

        check = self.mt5.order_check(request)
        if check is None:
            raise MT5Unavailable(f"order_check returned no result: {self.mt5.last_error()}")
        # MT5 order_check retcode is not identical to order_send's success code;
        # surface details and fail closed unless the check reports success.
        if getattr(check, "retcode", None) != 0:
            raise MT5Unavailable(f"order_check rejected request: {check}")

        result = self.mt5.order_send(request)
        if result is None:
            raise MT5Unavailable(f"order_send returned no result: {self.mt5.last_error()}")
        if result.retcode != self.mt5.TRADE_RETCODE_DONE:
            raise MT5Unavailable(f"Broker did not confirm execution: {result}")
        # Reconcile actual position(s) and verify server-side SL/TP are present.
        positions = self.positions()
        matching = [p for p in positions if getattr(p, "symbol", None) == self.cfg.symbol]
        if not matching:
            raise MT5Unavailable("Order result reported success but no matching open position was found. Reconcile in MT5.")
        protected = any(float(getattr(p, "sl", 0) or 0) > 0 and float(getattr(p, "tp", 0) or 0) > 0 for p in matching)
        if not protected:
            raise MT5Unavailable("Position found but broker-side SL/TP could not be verified. Stop further trading and inspect MT5 immediately.")
        return {
            "retcode": result.retcode, "order": getattr(result, "order", None),
            "deal": getattr(result, "deal", None), "price": getattr(result, "price", None),
            "volume": getattr(result, "volume", None), "comment": getattr(result, "comment", None),
            "sl_tp_verified_on_open_position": protected,
        }
