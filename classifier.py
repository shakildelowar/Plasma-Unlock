"""Statistical classification of wallet sizes.

Determines what constitutes a "large" wallet using quantitative methods
suited for heavy-tailed financial distributions.

Methods
-------
zscore      Standard z-score. Large if (x - mean) / std > threshold.
mad         Modified z-score using Median Absolute Deviation.
            Robust to outliers — default choice for token distributions.
iqr         Interquartile range fence. Large if x > Q3 + k * IQR.
percentile  Simple percentile cutoff (e.g. top 10%).
log_zscore  Log-transform then z-score. Handles power-law tails.
"""

from typing import Dict, Tuple

import numpy as np
import pandas as pd


def classify_wallets(
    wallet_amounts: Dict[str, float],
    method: str = "mad",
    threshold: float = 2.0,
) -> Tuple[pd.DataFrame, dict]:
    """
    Classify wallets as 'large' based on received unlock amounts.

    Parameters
    ----------
    wallet_amounts : dict
        {address: total_xpl_received}
    method : str
        Classification method (see module docstring).
    threshold : float
        Method-specific sensitivity parameter.

    Returns
    -------
    (df, stats) where df has columns [address, amount_xpl, is_large, z_score]
    and stats is a summary dict.
    """
    if not wallet_amounts:
        return pd.DataFrame(), {}

    df = pd.DataFrame(
        [{"address": a, "amount_xpl": v} for a, v in wallet_amounts.items()]
    )
    amounts = df["amount_xpl"].values.astype(float)

    cutoff = _compute_cutoff(amounts, method, threshold)
    df["is_large"] = df["amount_xpl"] >= cutoff

    # Attach a normalized score for ranking regardless of method
    df["z_score"] = _zscore(amounts)

    df = df.sort_values("amount_xpl", ascending=False).reset_index(drop=True)

    stats = _summary_stats(amounts, method, threshold, cutoff)
    stats["n_large"] = int(df["is_large"].sum())
    stats["n_total"] = len(df)
    stats["pct_large"] = (
        round(100.0 * stats["n_large"] / stats["n_total"], 2)
        if stats["n_total"]
        else 0.0
    )
    return df, stats


# ── Internal helpers ────────────────────────────────────────

def _zscore(x):
    mu, sigma = np.mean(x), np.std(x, ddof=1)
    if sigma == 0:
        return np.zeros_like(x)
    return (x - mu) / sigma


def _compute_cutoff(amounts: np.ndarray, method: str, threshold: float) -> float:
    if method == "zscore":
        return float(np.mean(amounts) + threshold * np.std(amounts, ddof=1))

    if method == "mad":
        median = np.median(amounts)
        mad = np.median(np.abs(amounts - median))
        if mad == 0:
            # Degenerate case: fall back to std-based estimate
            mad = np.std(amounts, ddof=1) * 0.6745
        return float(median + threshold * mad)

    if method == "iqr":
        q1, q3 = np.percentile(amounts, [25, 75])
        return float(q3 + threshold * (q3 - q1))

    if method == "percentile":
        return float(np.percentile(amounts, threshold))

    if method == "log_zscore":
        log_a = np.log1p(amounts)
        mu, sigma = np.mean(log_a), np.std(log_a, ddof=1)
        return float(np.expm1(mu + threshold * sigma))

    raise ValueError(f"Unknown classification method: {method!r}")


def _summary_stats(amounts, method, threshold, cutoff):
    return {
        "method": method,
        "threshold": threshold,
        "cutoff_xpl": round(float(cutoff), 2),
        "mean": round(float(np.mean(amounts)), 2),
        "median": round(float(np.median(amounts)), 2),
        "std": round(float(np.std(amounts, ddof=1)), 2),
        "min": round(float(np.min(amounts)), 2),
        "max": round(float(np.max(amounts)), 2),
        "q25": round(float(np.percentile(amounts, 25)), 2),
        "q75": round(float(np.percentile(amounts, 75)), 2),
    }
