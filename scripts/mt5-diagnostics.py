"""Run on Windows with the desired MT5 terminal already connected. Read-only."""

import json
import os
import sys

from aura.mt5 import demo_diagnostics

if sys.platform != "win32":
    raise SystemExit("Run this diagnostic on the Windows MT5 VPS")
import MetaTrader5 as mt5

path = os.environ.get("AURA_MT5_TERMINAL_PATH")
if not path:
    raise SystemExit("Set AURA_MT5_TERMINAL_PATH to the intended terminal64.exe")
if not mt5.initialize(path=path):
    raise SystemExit("MT5 initialization failed; check terminal installation and session")
try:
    print(json.dumps(demo_diagnostics(mt5), indent=2))
finally:
    mt5.shutdown()
