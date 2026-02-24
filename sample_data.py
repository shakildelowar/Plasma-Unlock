"""Sample data for offline testing and demonstration.

Generates realistic synthetic wallet data based on typical token unlock
distribution patterns (power-law with a few large recipients).

Usage
-----
    python main.py --sample --method mad --threshold 2.0
"""

import random
import hashlib
from datetime import datetime, timedelta


def _make_addr(seed):
    """Generate a deterministic fake address from a seed."""
    h = hashlib.sha256(str(seed).encode()).hexdigest()
    return "0x" + h[:40]


# Labels for sample wallets (simulates what Arkham / on-chain labels provide)
SAMPLE_LABELS = {
    "ecosystem_fund": "Ecosystem Development Fund",
    "foundation": "Plasma Foundation",
    "team_vesting": "Team Vesting Contract",
    "investor_a": "Early Investor A",
    "investor_b": "Early Investor B",
    "treasury": "Protocol Treasury",
    "advisor_pool": "Advisor Pool",
    "community": "Community Rewards",
    "market_maker": "Market Maker",
    "exchange_hot": "Exchange Hot Wallet",
}


def generate_sample_wallets(n_wallets=80, seed=42):
    """
    Generate a realistic distribution of wallet unlock amounts.

    Returns dict of {address: amount_xpl} simulating January 2026 unlocks.
    The distribution follows a power-law pattern:
      - 3-5 very large wallets (5M-20M XPL each)
      - 8-12 medium wallets (500K-5M XPL)
      - Remaining are smaller recipients (10K-500K XPL)

    Total unlocked is ~88.89M XPL (matching monthly ecosystem unlock).
    """
    rng = random.Random(seed)
    wallets = {}

    # Large wallets (foundation/ecosystem tier)
    large_amounts = [
        18_500_000,   # ecosystem fund
        12_200_000,   # foundation
        9_800_000,    # team vesting tranche
        7_500_000,    # early investor A
        5_600_000,    # early investor B
    ]
    large_labels = list(SAMPLE_LABELS.keys())[:5]
    for i, (amount, label) in enumerate(zip(large_amounts, large_labels)):
        addr = _make_addr(f"large_{label}_{seed}")
        jitter = rng.uniform(0.95, 1.05)
        wallets[addr] = round(amount * jitter, 2)

    # Medium wallets
    medium_count = rng.randint(8, 12)
    medium_labels = list(SAMPLE_LABELS.keys())[5:]
    for i in range(medium_count):
        addr = _make_addr(f"medium_{i}_{seed}")
        amount = rng.uniform(500_000, 5_000_000)
        wallets[addr] = round(amount, 2)

    # Small wallets (fill remaining)
    current_total = sum(wallets.values())
    target_total = 88_888_889
    remaining = target_total - current_total
    small_count = n_wallets - len(wallets)

    if small_count > 0 and remaining > 0:
        # Distribute remaining with power-law-ish pattern
        raw = [rng.paretovariate(1.5) for _ in range(small_count)]
        raw_sum = sum(raw)
        for i, r in enumerate(raw):
            addr = _make_addr(f"small_{i}_{seed}")
            amount = max(10_000, remaining * r / raw_sum)
            wallets[addr] = round(amount, 2)

    return wallets


def generate_sample_balances(wallet_amounts, seed=42):
    """
    Generate simulated current balances for each wallet.

    Simulates various selling behaviors:
      - ~20% are heavy sellers (sold >75%)
      - ~25% are moderate sellers (sold 40-75%)
      - ~30% are light sellers (sold 10-40%)
      - ~25% are holders (sold <10%)
    """
    rng = random.Random(seed + 1)
    balances = {}

    for addr, received in wallet_amounts.items():
        roll = rng.random()
        if roll < 0.20:
            # Heavy seller
            pct_remaining = rng.uniform(0.05, 0.25)
        elif roll < 0.45:
            # Moderate seller
            pct_remaining = rng.uniform(0.25, 0.60)
        elif roll < 0.75:
            # Light seller
            pct_remaining = rng.uniform(0.60, 0.90)
        else:
            # Holder (may even have accumulated more)
            pct_remaining = rng.uniform(0.90, 1.10)

        balances[addr] = round(received * pct_remaining, 2)

    return balances


def generate_sample_timing(wallet_amounts, wallet_balances, seed=42):
    """
    Generate timing data for each wallet's unlock and selling activity.

    Returns dict of {address: timing_dict} where timing_dict has:
      - unlock_date: when the wallet received the unlock
      - unlock_block: block number of the unlock tx
      - unlock_tx_hash: transaction hash of the unlock
      - first_sell_date: when the wallet first sold (None if holder)
      - last_activity_date: most recent outbound transaction
      - num_sell_txs: number of individual sell transactions
      - sell_velocity_per_day: average XPL sold per day since first sell
      - days_since_unlock: days between unlock and now
      - days_active_selling: days between first sell and last activity
      - source: data source attribution
    """
    rng = random.Random(seed + 2)
    timing = {}

    # The main ecosystem unlock event was around Jan 25, 2026
    # But wallets received at slightly different times (batched distribution)
    unlock_base = datetime(2026, 1, 25, 14, 0, 0)
    now = datetime(2026, 2, 24, 12, 0, 0)
    base_block = 48_200_000

    for addr, received in wallet_amounts.items():
        balance = wallet_balances.get(addr, received)
        sold = max(0, received - balance)
        pct_sold = (sold / received * 100) if received > 0 else 0

        # Unlock happened in a ~3 day window (Jan 24-27)
        unlock_offset_hours = rng.uniform(-24, 48)
        unlock_dt = unlock_base + timedelta(hours=unlock_offset_hours)
        block_offset = int(unlock_offset_hours * 3600 / 2)  # ~2s blocks
        unlock_block = base_block + block_offset

        tx_hash = "0x" + hashlib.sha256(
            f"unlock_{addr}_{seed}".encode()
        ).hexdigest()

        days_since = (now - unlock_dt).total_seconds() / 86400

        # Determine selling timeline based on behavior
        first_sell_date = None
        last_activity = unlock_dt
        num_sell_txs = 0
        sell_velocity = 0.0
        days_selling = 0

        if pct_sold >= 75:
            # Heavy seller: started selling within hours, many txs
            delay_hours = rng.uniform(0.5, 12)
            first_sell_date = unlock_dt + timedelta(hours=delay_hours)
            # Still selling recently
            last_activity = now - timedelta(hours=rng.uniform(1, 48))
            num_sell_txs = rng.randint(15, 45)
            days_selling = (last_activity - first_sell_date).total_seconds() / 86400
            sell_velocity = sold / max(days_selling, 0.5)
        elif pct_sold >= 40:
            # Moderate seller: started within a few days
            delay_days = rng.uniform(1, 5)
            first_sell_date = unlock_dt + timedelta(days=delay_days)
            last_activity = now - timedelta(days=rng.uniform(0.5, 7))
            num_sell_txs = rng.randint(8, 20)
            days_selling = (last_activity - first_sell_date).total_seconds() / 86400
            sell_velocity = sold / max(days_selling, 0.5)
        elif pct_sold >= 10:
            # Light seller: started after a week or so, sporadic
            delay_days = rng.uniform(5, 15)
            first_sell_date = unlock_dt + timedelta(days=delay_days)
            last_activity = now - timedelta(days=rng.uniform(2, 14))
            num_sell_txs = rng.randint(2, 10)
            days_selling = (last_activity - first_sell_date).total_seconds() / 86400
            sell_velocity = sold / max(days_selling, 0.5)
        else:
            # Holder: no sell activity (last activity = unlock or minor movement)
            last_activity = unlock_dt + timedelta(hours=rng.uniform(0, 24))
            num_sell_txs = 0
            days_selling = 0
            sell_velocity = 0.0

        # Source attribution
        label = get_sample_label(addr)
        if label:
            source = f"Arkham Intel ({label})"
        elif received >= 1_000_000:
            source = "PlasmaScan API + Plasma RPC"
        else:
            source = "Plasma RPC (block scan)"

        timing[addr] = {
            "unlock_date": unlock_dt.strftime("%Y-%m-%d %H:%M UTC"),
            "unlock_block": unlock_block,
            "unlock_tx_hash": tx_hash,
            "first_sell_date": first_sell_date.strftime("%Y-%m-%d %H:%M UTC") if first_sell_date else None,
            "last_activity_date": last_activity.strftime("%Y-%m-%d %H:%M UTC"),
            "num_sell_txs": num_sell_txs,
            "sell_velocity_per_day": round(sell_velocity, 2),
            "days_since_unlock": round(days_since, 1),
            "days_active_selling": round(days_selling, 1),
            "label": label,
            "source": source,
        }

    return timing


def get_sample_label(address):
    """Return a label for a sample address, if it matches a known pattern."""
    for key, label in SAMPLE_LABELS.items():
        test_addr = _make_addr(f"large_{key}_42")
        if address == test_addr:
            return label
    return None
