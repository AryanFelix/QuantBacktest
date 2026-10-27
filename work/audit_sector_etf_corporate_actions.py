"""Fetch Upstox corporate-action history for the six ETFs in the sector sleeve."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import upstox_quant as q


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "work" / "data" / "api_probes" / "sector_etf_corporate_actions_2026-10-26.json"
ASSETS = {
    "BANKBEES": "INF204KB15I9",
    "ITBEES": "INF204KB15V2",
    "AUTOBEES": "INF204KC1337",
    "PHARMABEES": "INF204KC1089",
    "PSUBNKBEES": "INF204KB16I7",
    "JUNIORBEES": "INF732E01045",
}

requests: list[dict] = []
for symbol, isin in ASSETS.items():
    try:
        actions = q.fetch_corporate_actions(isin)
        requests.append({
            "symbol": symbol,
            "isin": isin,
            "url": f"https://api.upstox.com/v2/fundamentals/{isin}/corporate-actions",
            "api_status": "success",
            "record_count": len(actions),
            "data": actions,
        })
    except Exception as exc:
        requests.append({
            "symbol": symbol,
            "isin": isin,
            "url": f"https://api.upstox.com/v2/fundamentals/{isin}/corporate-actions",
            "api_status": "error",
            "error": f"{type(exc).__name__}: {exc}",
        })

result = {
    "source_endpoint_template": "https://api.upstox.com/v2/fundamentals/{isin}/corporate-actions",
    "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
    "token_value_saved": False,
    "requests": requests,
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(
    f"requested={len(ASSETS)} success={sum(row['api_status'] == 'success' for row in requests)} "
    f"errors={sum(row['api_status'] == 'error' for row in requests)} "
    f"nonempty={sum(row.get('record_count', 0) > 0 for row in requests)} "
    f"events={sum(row.get('record_count', 0) for row in requests)} output={OUT}"
)
assert len(ASSETS) == 6 and len(set(ASSETS)) == 6
assert OUT.exists() and json.loads(OUT.read_text(encoding="utf-8")) == result
assert all(row["symbol"] in ASSETS for row in requests)
