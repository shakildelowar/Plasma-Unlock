"""Selling behavior tracker and report generator.

Compares unlock amounts to current balances to determine which large wallets
are selling, holding, or accumulating.
"""

import pandas as pd

from fetcher import PlasmaFetcher


# ── Selling analysis ────────────────────────────────────────

def track_selling(fetcher: PlasmaFetcher, wallets_df: pd.DataFrame) -> pd.DataFrame:
    """
    For each large wallet, fetch current balance and compute selling metrics.

    Parameters
    ----------
    fetcher : PlasmaFetcher
    wallets_df : DataFrame with [address, amount_xpl, is_large]

    Returns
    -------
    DataFrame of large wallets with columns:
        address, amount_xpl, current_balance, amount_sold,
        pct_sold, remaining, behavior
    """
    large = wallets_df[wallets_df["is_large"]].copy()
    if large.empty:
        return large

    addresses = large["address"].tolist()
    balances = fetcher.get_balances(addresses)

    large["current_balance"] = large["address"].map(
        lambda a: balances.get(a.lower())
    )

    # If balance fetch failed (None), mark as unknown
    large["balance_known"] = large["current_balance"].notna()
    large["current_balance"] = large["current_balance"].fillna(0.0)

    large["amount_sold"] = (
        (large["amount_xpl"] - large["current_balance"]).clip(lower=0)
    )
    large["pct_sold"] = large.apply(
        lambda r: round(r["amount_sold"] / r["amount_xpl"] * 100, 2)
        if r["amount_xpl"] > 0 else 0.0,
        axis=1,
    )
    large["remaining"] = large["current_balance"]
    large["behavior"] = large["pct_sold"].apply(_classify_behavior)

    return large.sort_values("amount_sold", ascending=False).reset_index(drop=True)


def _classify_behavior(pct_sold: float) -> str:
    if pct_sold >= 75:
        return "heavy_seller"
    if pct_sold >= 40:
        return "moderate_seller"
    if pct_sold >= 10:
        return "light_seller"
    return "holder"


# ── Report generation ───────────────────────────────────────

def generate_report(tracking_df: pd.DataFrame, stats: dict) -> str:
    """Produce a plain-text summary report."""
    lines = []
    w = 72

    lines.append("=" * w)
    lines.append("  XPL WALLET UNLOCK TRACKER  —  SELLING BEHAVIOR REPORT")
    lines.append("=" * w)
    lines.append("")

    # ── Distribution statistics
    lines.append("DISTRIBUTION STATISTICS")
    lines.append("-" * 40)
    lines.append(f"  Total wallets analyzed : {stats['n_total']}")
    lines.append(f"  Large wallets found    : {stats['n_large']} ({stats['pct_large']}%)")
    lines.append(f"  Classification method  : {stats['method']}")
    lines.append(f"  Threshold parameter    : {stats['threshold']}")
    lines.append(f"  Cutoff value           : {stats['cutoff_xpl']:,.2f} XPL")
    lines.append(f"  Mean unlock amount     : {stats['mean']:,.2f} XPL")
    lines.append(f"  Median unlock amount   : {stats['median']:,.2f} XPL")
    lines.append(f"  Std deviation          : {stats['std']:,.2f} XPL")
    lines.append(f"  Min / Max              : {stats['min']:,.2f} / {stats['max']:,.2f} XPL")
    lines.append(f"  Q25 / Q75              : {stats['q25']:,.2f} / {stats['q75']:,.2f} XPL")
    lines.append("")

    if tracking_df.empty:
        lines.append("No large wallets found to track.")
        return "\n".join(lines)

    # ── Behavior summary
    behavior_counts = tracking_df["behavior"].value_counts()
    lines.append("SELLING BEHAVIOR SUMMARY")
    lines.append("-" * 40)
    for behavior, count in behavior_counts.items():
        label = behavior.replace("_", " ").title()
        lines.append(f"  {label:20s} : {count}")
    lines.append("")

    total_recv = tracking_df["amount_xpl"].sum()
    total_sold = tracking_df["amount_sold"].sum()
    total_rem = tracking_df["remaining"].sum()
    pct_s = total_sold / total_recv * 100 if total_recv else 0
    pct_r = total_rem / total_recv * 100 if total_recv else 0

    lines.append(f"  Total XPL received  : {total_recv:>20,.2f}")
    lines.append(f"  Total XPL sold      : {total_sold:>20,.2f}  ({pct_s:.1f}%)")
    lines.append(f"  Total XPL remaining : {total_rem:>20,.2f}  ({pct_r:.1f}%)")
    lines.append("")

    # ── Per-wallet detail table
    lines.append("LARGE WALLET DETAILS")
    lines.append("-" * w)
    hdr = (f"{'#':>3}  {'Address':>42}  {'Received':>14}  "
           f"{'Sold':>14}  {'%Sold':>6}  {'Status'}")
    lines.append(hdr)
    lines.append("-" * w)

    for idx, row in tracking_df.iterrows():
        addr = row["address"]
        short = f"{addr[:6]}...{addr[-4:]}" if len(addr) > 12 else addr
        note = "" if row.get("balance_known", True) else " *"
        lines.append(
            f"{idx + 1:>3}  {short:>42}  "
            f"{row['amount_xpl']:>14,.2f}  "
            f"{row['amount_sold']:>14,.2f}  "
            f"{row['pct_sold']:>5.1f}%  "
            f"{row['behavior'].replace('_', ' ').title()}{note}"
        )

    lines.append("")
    lines.append("  * = balance could not be verified")
    lines.append("=" * w)
    return "\n".join(lines)
