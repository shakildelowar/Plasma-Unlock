"""Blockchain data fetching for Plasma XPL unlock tracking.

Supports two data collection modes:
  1. PlasmaScan API (Etherscan-compatible) — fast, requires address
  2. RPC block scanning — slower, no address needed (discovery mode)
"""

import time
import logging
from collections import defaultdict
from datetime import datetime, timezone

import requests
from web3 import Web3

import config

logger = logging.getLogger(__name__)


class PlasmaFetcher:
    """Fetches XPL wallet and transaction data from Plasma blockchain."""

    def __init__(self, rpc_url=None):
        url = rpc_url or config.RPC_URL
        self.w3 = Web3(Web3.HTTPProvider(url, request_kwargs={"timeout": 30}))
        if not self.w3.is_connected():
            raise ConnectionError(f"Cannot connect to Plasma RPC at {url}")
        self.api_url = config.PLASMASCAN_API_URL
        self.api_key = config.PLASMASCAN_API_KEY

    # ── Block / timestamp helpers ───────────────────────────

    def latest_block(self):
        return self.w3.eth.block_number

    def block_timestamp(self, block_num):
        return self.w3.eth.get_block(block_num)["timestamp"]

    def find_block_by_timestamp(self, target_ts, lo=0, hi=None):
        """Binary search for the first block at or after *target_ts*."""
        if hi is None:
            hi = self.w3.eth.block_number
        while lo < hi:
            mid = (lo + hi) // 2
            if self.block_timestamp(mid) < target_ts:
                lo = mid + 1
            else:
                hi = mid
        return lo

    def date_to_block(self, date_str):
        """Convert 'YYYY-MM-DD' to the nearest block number."""
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return self.find_block_by_timestamp(int(dt.timestamp()))

    # ── PlasmaScan API queries ──────────────────────────────

    def _api_get(self, params):
        if self.api_key:
            params["apikey"] = self.api_key
        time.sleep(config.API_DELAY_SEC)
        resp = requests.get(self.api_url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "1":
            return data.get("result", [])
        return []

    def get_normal_txs(self, address, start_block=0, end_block=99999999,
                       page=1, offset=10000):
        """Get normal (external) transactions for an address."""
        return self._api_get({
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": start_block,
            "endblock": end_block,
            "page": page,
            "offset": offset,
            "sort": "asc",
        })

    def get_internal_txs(self, address, start_block=0, end_block=99999999):
        """Get internal transactions for an address."""
        return self._api_get({
            "module": "account",
            "action": "txlistinternal",
            "address": address,
            "startblock": start_block,
            "endblock": end_block,
            "sort": "asc",
        })

    # ── RPC block scanning ──────────────────────────────────

    def scan_blocks(self, start_block, end_block, min_value_xpl=0,
                    progress_cb=None):
        """
        Scan a range of blocks for transactions above *min_value_xpl*.

        Returns a list of dicts:
            {from, to, value_wei, value_xpl, block, tx_hash, timestamp}
        """
        results = []
        min_wei = Web3.to_wei(min_value_xpl, "ether")
        total = end_block - start_block + 1

        for i, blk_num in enumerate(range(start_block, end_block + 1)):
            if progress_cb and i % 50 == 0:
                progress_cb(i, total)
            try:
                blk = self.w3.eth.get_block(blk_num, full_transactions=True)
            except Exception as exc:
                logger.debug("Block %d fetch failed: %s", blk_num, exc)
                continue
            for tx in blk.get("transactions", []):
                val = tx.get("value", 0)
                if val >= min_wei:
                    results.append({
                        "from": tx["from"].lower(),
                        "to": (tx.get("to") or "").lower(),
                        "value_wei": val,
                        "value_xpl": float(Web3.from_wei(val, "ether")),
                        "block": blk_num,
                        "tx_hash": (tx["hash"].hex()
                                    if isinstance(tx["hash"], bytes)
                                    else tx["hash"]),
                        "timestamp": blk["timestamp"],
                    })
        if progress_cb:
            progress_cb(total, total)
        return results

    # ── Balance queries ─────────────────────────────────────

    def get_balance(self, address):
        """Current XPL balance (float, in XPL)."""
        cs = Web3.to_checksum_address(address)
        return float(Web3.from_wei(self.w3.eth.get_balance(cs), "ether"))

    def get_balances(self, addresses):
        """Batch balance query. Returns {lowercase_addr: balance_xpl}."""
        out = {}
        for addr in addresses:
            try:
                out[addr.lower()] = self.get_balance(addr)
            except Exception as exc:
                logger.warning("Balance fetch failed for %s: %s", addr, exc)
                out[addr.lower()] = None
            time.sleep(config.API_DELAY_SEC)
        return out

    # ── Outbound transaction analysis ───────────────────────

    def get_outbound_txs(self, address, start_block=0, end_block=99999999):
        """
        Get all outbound transactions from an address in a block range.
        Returns list of {to, value_xpl, tx_hash, timestamp, block}.
        """
        txs = self.get_normal_txs(address, start_block, end_block)
        outbound = []
        addr_lower = address.lower()
        for tx in txs:
            if tx.get("from", "").lower() == addr_lower:
                val = int(tx.get("value", "0"))
                outbound.append({
                    "to": tx.get("to", "").lower(),
                    "value_xpl": float(Web3.from_wei(val, "ether")),
                    "tx_hash": tx.get("hash", ""),
                    "timestamp": int(tx.get("timeStamp", 0)),
                    "block": int(tx.get("blockNumber", 0)),
                })
        return outbound

    # ── Discovery helpers ───────────────────────────────────

    def discover_distributors(self, start_block, end_block,
                              min_value_xpl=100_000, top_n=10,
                              progress_cb=None):
        """
        Identify the top sender addresses in a block range.
        These are likely vesting or treasury contracts.

        Returns (top_senders_list, all_qualifying_txs).
        """
        txs = self.scan_blocks(
            start_block, end_block,
            min_value_xpl=min_value_xpl,
            progress_cb=progress_cb,
        )
        sender_totals = defaultdict(float)
        for tx in txs:
            sender_totals[tx["from"]] += tx["value_xpl"]

        ranked = sorted(sender_totals.items(), key=lambda x: -x[1])[:top_n]
        return ranked, txs
