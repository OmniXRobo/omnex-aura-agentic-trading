"""Read-only MT5 identity, metadata and tick diagnosis. Never creates/binds a stream."""

import argparse
import importlib
import json
import os
import sys
import time

from pydantic import ValidationError

from .market import GoldContract, Quote
from .time_policy import load_policy


def report_terminal(port, symbol, expected_login=None, expected_server=None, now_msc=None, time_policy=None):
    result = {"symbol": symbol, "execution_allowed": False, "stream_modified": False}
    try:
        account, terminal = port.account_info(), port.terminal_info()
        if account is None or terminal is None or not terminal.connected:
            return result | {"error": "disconnected", "demo_verified": False}
        result.update(
            demo_verified=account.trade_mode == port.ACCOUNT_TRADE_MODE_DEMO,
            company=account.company,
            server=account.server,
            login_matches=None if expected_login is None else account.login == expected_login,
            server_matches=None if expected_server is None else account.server == expected_server,
        )
        if not result["demo_verified"]:
            return result | {"error": "not_demo"}
        identity = (account.login, account.server, account.trade_mode)
        raw = port.symbol_info(symbol)
        if raw is None:
            result["contract_error"] = "symbol_unavailable"
        else:
            values = {k: getattr(raw, k, None) for k in GoldContract.model_fields if k != "symbol"}
            values["symbol"] = getattr(raw, "name", None)
            result["visible_in_market_watch"] = getattr(raw, "visible", None)
            try:
                contract = GoldContract.model_validate(values)
                result["contract_valid"] = contract.symbol == symbol
                result["contract_error"] = None if result["contract_valid"] else "symbol_mismatch"
            except ValidationError as error:
                result["contract_valid"] = False
                result["contract_invalid_fields"] = sorted(
                    {str(e["loc"][0]) for e in error.errors(include_input=False)}
                )
        tick = port.symbol_info_tick(symbol)
        now_msc = int(time.time() * 1000) if now_msc is None else now_msc
        try:
            quote = Quote(
                symbol=symbol,
                **{k: getattr(tick, k, None) for k in ("time_msc", "bid", "ask", "flags")},
            )
            result["raw_time_msc"] = quote.time_msc
            result["system_utc_msc"] = now_msc
            result["raw_tick_age_seconds"] = (now_msc - quote.time_msc) / 1000
            if time_policy is not None:
                try:
                    corrected = time_policy.normalize(
                        quote.time_msc, now_msc, account.server, symbol
                    )
                except ValueError:
                    return result | {"error": "time_policy_invalid", "terminal_checks_passed": False}
                quote = quote.model_copy(update={"time_msc": corrected})
                result["time_offset_seconds"] = time_policy.offset_seconds
                result["history_time_verified"] = False
            result["tick_age_seconds"] = (now_msc - quote.time_msc) / 1000
            result["quote_valid"] = True
            result["quote_fresh"] = 0 <= now_msc - quote.time_msc <= 5000
            result["spread"] = quote.ask - quote.bid
        except ValidationError:
            result["quote_valid"] = False
            result["quote_fresh"] = False
        after, terminal_after = port.account_info(), port.terminal_info()
        stable = (
            after is not None
            and terminal_after is not None
            and terminal_after.connected
            and (after.login, after.server, after.trade_mode) == identity
        )
        result["account_stable"] = stable
        result["terminal_checks_passed"] = bool(
            stable
            and result.get("contract_valid")
            and result.get("quote_fresh")
            and result["login_matches"] is True
            and result["server_matches"] is True
        )
        return result
    except Exception:
        return result | {"error": "terminal_read_failed", "terminal_checks_passed": False}


def main():
    parser = argparse.ArgumentParser(
        description="Read-only demo terminal diagnostics; no database writes"
    )
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--quote-time-policy", help="Reviewed local JSON policy; never auto-detected")
    args = parser.parse_args()
    try:
        time_policy = load_policy(args.quote_time_policy)
    except (OSError, ValueError):
        parser.error("Invalid quote time policy file")
    if sys.platform != "win32":
        parser.error("Run on the Windows MT5 VPS")
    path = os.getenv("AURA_MT5_TERMINAL_PATH", "")
    if not path:
        parser.error("Set the intended AURA_MT5_TERMINAL_PATH")
    login = os.getenv("AURA_MT5_EXPECTED_LOGIN", "")
    server = os.getenv("AURA_MT5_EXPECTED_SERVER", "")
    if login and not login.isdigit():
        parser.error("Expected login must be numeric; enter it only in the VPS environment")
    port = importlib.import_module("MetaTrader5")
    if not port.initialize(path=path):
        raise SystemExit("MT5 initialization failed")
    try:
        print(
            json.dumps(
                report_terminal(
                    port, args.symbol, int(login) if login else None, server or None,
                    time_policy=time_policy,
                ),
                indent=2,
                allow_nan=False,
            )
        )
    finally:
        port.shutdown()


if __name__ == "__main__":
    main()
