"""Arkham Intelligence API integration for Plasma wallet tracking.

Arkham has confirmed Plasma chain integration (intel.arkm.com).
This module provides:
  - Entity lookup (labeled wallets: foundation, ecosystem, exchanges)
  - Transfer history for addresses on the Plasma chain
  - Portfolio/balance queries
"""

import time
import logging

import requests

import config

logger = logging.getLogger(__name__)

BASE = config.ARKHAM_API_URL
PLASMA_CHAIN = "plasma"


def _headers():
    h = {"Accept": "application/json"}
    if config.ARKHAM_API_KEY:
        h["API-Key"] = config.ARKHAM_API_KEY
    return h


def _get(path, params=None):
    url = f"{BASE}{path}"
    time.sleep(config.API_DELAY_SEC)
    try:
        resp = requests.get(url, params=params, headers=_headers(), timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        logger.warning("Arkham API request failed: %s %s — %s", path, params, exc)
        return None


def get_entity(entity_slug):
    """
    Look up an Arkham-labeled entity (e.g. 'plasma-foundation').

    Returns dict with addresses, labels, portfolio, etc.
    """
    return _get(f"/intelligence/entity/{entity_slug}")


def get_transfers(address, chain=PLASMA_CHAIN, limit=100, offset=0,
                  time_gte=None, time_lte=None):
    """
    Get token transfers for an address on the Plasma chain.

    Parameters
    ----------
    address : str
    chain : str
    limit : int
    time_gte / time_lte : str
        ISO 8601 timestamps for filtering, e.g. '2026-01-01T00:00:00Z'
    """
    params = {
        "base": address,
        "chain": chain,
        "limit": limit,
        "offset": offset,
    }
    if time_gte:
        params["timeGte"] = time_gte
    if time_lte:
        params["timeLte"] = time_lte
    return _get("/intelligence/transfers", params)


def get_portfolio(address, chain=PLASMA_CHAIN):
    """Get portfolio/balance for an address."""
    return _get(f"/intelligence/address/{address}/portfolio", {"chain": chain})


def search_entity(query):
    """Search Arkham entities by name (e.g. 'Plasma', 'Binance')."""
    return _get("/intelligence/search", {"query": query})


def get_top_holders(chain=PLASMA_CHAIN, limit=50):
    """
    Attempt to fetch top holders for native token on Plasma chain.
    May require specific API tier.
    """
    return _get("/intelligence/top-holders", {"chain": chain, "limit": limit})


def fetch_labeled_plasma_wallets():
    """
    Attempt to discover labeled Plasma wallets from Arkham.
    Tries known entity slugs for Plasma ecosystem.

    Returns dict of {address: label} for any wallets found.
    """
    wallets = {}
    slugs_to_try = [
        "plasma-foundation",
        "plasma",
        "plasma-ecosystem",
        "plasma-treasury",
    ]
    for slug in slugs_to_try:
        data = get_entity(slug)
        if data and isinstance(data, dict):
            # Arkham entity responses typically have an 'addresses' field
            for addr_info in data.get("addresses", []):
                addr = addr_info.get("address", "").lower()
                label = addr_info.get("arkhamLabel", slug)
                chain = addr_info.get("chain", "")
                if addr and chain in ("plasma", ""):
                    wallets[addr] = label
            # Also check 'portfolio' for addresses
            portfolio = data.get("portfolio", {})
            for chain_data in portfolio.get("chains", []):
                if chain_data.get("chain") == "plasma":
                    for token in chain_data.get("tokens", []):
                        addr = token.get("address", "").lower()
                        if addr:
                            wallets[addr] = slug

    # Also try search
    search_data = search_entity("plasma")
    if search_data and isinstance(search_data, list):
        for item in search_data:
            if "plasma" in item.get("name", "").lower():
                for addr_info in item.get("addresses", []):
                    addr = addr_info.get("address", "").lower()
                    if addr:
                        wallets[addr] = item.get("name", "unknown")

    return wallets
