"""Sample data for offline testing and demonstration.

Generates realistic synthetic wallet data based on typical token unlock
distribution patterns (power-law with a few large recipients).

Usage
-----
    python main.py --sample --method mad --threshold 2.0
"""

import random
import hashlib


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


def get_sample_label(address):
    """Return a label for a sample address, if it matches a known pattern."""
    for key, label in SAMPLE_LABELS.items():
        test_addr = _make_addr(f"large_{key}_42")
        if address == test_addr:
            return label
    return None
