import sys
from pathlib import Path

import upstox_quant as quant


cache = quant.DATA_DIR / "expired"
expiries = sorted(
    path.name[len("monthly-") : -len("-option-contracts.json")]
    for path in cache.glob("monthly-*-option-contracts.json")
)
assert expiries
# shortcut: cached expiry files replace live discovery; missing contract candles still trigger API requests.
quant.fetch_expiries = lambda _underlying_key: expiries
sys.argv = [sys.argv[0], "monthly-options", *sys.argv[1:]]
quant.main()
