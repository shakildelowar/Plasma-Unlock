"""Configuration for Plasma XPL Unlock Tracker."""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Network ─────────────────────────────────────────────────
CHAIN_ID = 9745
RPC_URL = os.getenv("PLASMA_RPC_URL", "https://rpc.plasma.to")
PLASMASCAN_API_URL = os.getenv("PLASMASCAN_API_URL", "https://plasmascan.to/api")
PLASMASCAN_API_KEY = os.getenv("PLASMASCAN_API_KEY", "")

# ── Token ───────────────────────────────────────────────────
XPL_DECIMALS = 18
XPL_SYMBOL = "XPL"

# ── Date Range (January 2026 unlocks) ──────────────────────
UNLOCK_START = "2026-01-01"
UNLOCK_END = "2026-01-31"

# ── Classification Defaults ────────────────────────────────
# Methods: "zscore", "mad", "iqr", "percentile", "log_zscore"
#   zscore     — large if z-score > threshold (e.g. 1.0 = 1 std above mean)
#   mad        — large if modified z-score (MAD) > threshold (robust to outliers)
#   iqr        — large if amount > Q3 + threshold * IQR
#   percentile — large if amount > threshold-th percentile
#   log_zscore — log-transform then z-score (for heavy-tailed distributions)
DEFAULT_METHOD = "mad"
DEFAULT_THRESHOLD = 2.0

# ── Rate Limiting ──────────────────────────────────────────
API_DELAY_SEC = 0.25
RPC_BATCH_SIZE = 50

# ── Known Addresses ────────────────────────────────────────
_raw = os.getenv("VESTING_CONTRACTS", "")
VESTING_CONTRACTS = [a.strip() for a in _raw.split(",") if a.strip()]
