"""Read-only integration port. Deliberately contains no order_send implementation."""

from typing import Protocol


class MT5ReadPort(Protocol):
    ACCOUNT_TRADE_MODE_DEMO: int

    def account_info(self): ...
    def terminal_info(self): ...
    def symbols_get(self): ...


def demo_diagnostics(port: MT5ReadPort):
    account = port.account_info()
    terminal = port.terminal_info()
    if account is None or terminal is None or not terminal.connected:
        return {"demo_verified": False, "execution_allowed": False, "reason": "Disconnected"}
    if account.trade_mode != port.ACCOUNT_TRADE_MODE_DEMO:
        return {
            "demo_verified": False,
            "execution_allowed": False,
            "reason": "Real, contest, or unknown account rejected",
        }
    symbols = port.symbols_get()
    if symbols is None:
        return {
            "demo_verified": True,
            "execution_allowed": False,
            "reason": "Symbol metadata unavailable",
            "symbol_candidates": [],
        }
    candidates = [s.name for s in symbols if "XAUUSD" in s.name.upper() or "GOLD" in s.name.upper()]
    return {
        "demo_verified": True,
        "execution_allowed": False,
        "symbol_candidates": candidates,
        "reason": "Read-only; candidates require contract verification",
    }
