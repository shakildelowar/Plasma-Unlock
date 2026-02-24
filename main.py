#!/usr/bin/env python3
"""
XPL Wallet Unlock Tracker
=========================
Tracks large XPL wallets that had their first unlocks in January 2026,
determines which are selling, and how much they have left to sell.

"Large" is defined quantitatively using configurable statistical methods
(MAD, z-score, IQR, percentile, log-normal z-score).

Usage
-----
    # Discovery mode — scan blocks to find unlock recipients automatically
    python main.py --discover --min-value 50000

    # Scan known vesting contracts
    python main.py --contracts 0xABC...,0xDEF...

    # Track a pre-built wallet list
    python main.py --wallets-file wallets.txt

    # Tune classification sensitivity
    python main.py --discover --method zscore --threshold 1.5

    # Save results to JSON
    python main.py --discover --output results.json

    # Offline demo with synthetic data (no RPC/API needed)
    python main.py --sample

    # Generate HTML dashboard and Excel report
    python main.py --sample --dashboard --excel
"""

import argparse
import json
import sys
from collections import defaultdict

import config
from fetcher import PlasmaFetcher
from classifier import classify_wallets
from tracker import track_selling, generate_report
from sample_data import generate_sample_wallets, generate_sample_balances, generate_sample_timing
from dashboard import generate_dashboard
from export_excel import export_excel


def parse_args():
    p = argparse.ArgumentParser(
        description="Track large XPL wallet unlocks and selling behavior.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Date range
    p.add_argument("--start-date", default=config.UNLOCK_START,
                   help="Start of unlock window (YYYY-MM-DD)")
    p.add_argument("--end-date", default=config.UNLOCK_END,
                   help="End of unlock window (YYYY-MM-DD)")

    # Data source
    src = p.add_mutually_exclusive_group()
    src.add_argument("--contracts", type=str, default="",
                     help="Comma-separated vesting contract addresses")
    src.add_argument("--discover", action="store_true",
                     help="Auto-discover distributors by scanning blocks")
    src.add_argument("--wallets-file", type=str, default="",
                     help="File with wallet addresses to track (one per line)")
    src.add_argument("--sample", action="store_true",
                     help="Run with synthetic sample data (no RPC needed)")

    # Scan parameters
    p.add_argument("--min-value", type=float, default=10_000,
                   help="Min XPL per tx to consider an unlock (default: 10000)")
    p.add_argument("--scan-days", type=int, default=0,
                   help="If >0, narrow scan to ±N days around the 25th")
    p.add_argument("--top-n", type=int, default=10,
                   help="Top N distributors to show in discovery mode")

    # Classification
    p.add_argument("--method", default=config.DEFAULT_METHOD,
                   choices=["zscore", "mad", "iqr", "percentile", "log_zscore"],
                   help="Statistical method for 'large' classification")
    p.add_argument("--threshold", type=float, default=config.DEFAULT_THRESHOLD,
                   help="Method-specific threshold")

    # Network
    p.add_argument("--rpc-url", type=str, default="",
                   help="Override Plasma RPC endpoint")

    # Output
    p.add_argument("--output", type=str, default="",
                   help="Save results to JSON file")
    p.add_argument("--dashboard", action="store_true",
                   help="Generate interactive HTML dashboard")
    p.add_argument("--dashboard-file", type=str, default="xpl_dashboard.html",
                   help="Dashboard output path (default: xpl_dashboard.html)")
    p.add_argument("--excel", action="store_true",
                   help="Generate Excel (.xlsx) report")
    p.add_argument("--excel-file", type=str, default="xpl_unlock_report.xlsx",
                   help="Excel output path (default: xpl_unlock_report.xlsx)")
    p.add_argument("--verbose", "-v", action="store_true",
                   help="Verbose output")

    return p.parse_args()


def _progress(i, total):
    pct = i / total * 100 if total else 0
    bar_len = 30
    filled = int(bar_len * i / total) if total else 0
    bar = "#" * filled + "-" * (bar_len - filled)
    print(f"\r  [{bar}] {pct:5.1f}%  ({i:,}/{total:,} blocks)", end="", flush=True)
    if i >= total:
        print()


def _run_sample(args):
    """Run the full pipeline with synthetic sample data (no network needed)."""
    import pandas as pd

    print("=" * 60)
    print("  SAMPLE MODE — Using synthetic data (no RPC/API calls)")
    print("=" * 60)

    # Generate sample wallet unlock amounts
    print(f"\nGenerating sample wallets...")
    wallet_amounts = generate_sample_wallets(n_wallets=80)
    total = sum(wallet_amounts.values())
    print(f"  {len(wallet_amounts)} wallets, total {total:,.0f} XPL unlocked")

    # Classify
    print(f"\nClassifying wallets  (method={args.method}, "
          f"threshold={args.threshold}) ...")
    wallets_df, stats = classify_wallets(
        wallet_amounts,
        method=args.method,
        threshold=args.threshold,
    )
    print(f"  Cutoff: {stats['cutoff_xpl']:,.2f} XPL")
    print(f"  Large:  {stats['n_large']} / {stats['n_total']} wallets")

    if stats["n_large"] == 0:
        print("\nNo wallets classified as 'large'. Try lowering --threshold.")
        return

    # Simulate current balances instead of fetching from RPC
    large = wallets_df[wallets_df["is_large"]].copy()
    large_amounts = {r["address"]: r["amount_xpl"] for _, r in large.iterrows()}
    sample_balances = generate_sample_balances(large_amounts)

    large["current_balance"] = large["address"].map(sample_balances)
    large["balance_known"] = True
    large["amount_sold"] = (
        (large["amount_xpl"] - large["current_balance"]).clip(lower=0)
    )
    large["pct_sold"] = large.apply(
        lambda r: round(r["amount_sold"] / r["amount_xpl"] * 100, 2)
        if r["amount_xpl"] > 0 else 0.0,
        axis=1,
    )
    large["remaining"] = large["current_balance"]
    large["behavior"] = large["pct_sold"].apply(
        lambda p: "heavy_seller" if p >= 75
        else "moderate_seller" if p >= 40
        else "light_seller" if p >= 10
        else "holder"
    )

    # Generate timing data
    timing_data = generate_sample_timing(large_amounts, sample_balances)
    for col in ["unlock_date", "unlock_block", "unlock_tx_hash",
                "first_sell_date", "last_activity_date", "num_sell_txs",
                "sell_velocity_per_day", "days_since_unlock",
                "days_active_selling", "label", "source"]:
        large[col] = large["address"].map(lambda a, c=col: timing_data.get(a, {}).get(c))

    tracking_df = large.sort_values("amount_sold", ascending=False).reset_index(drop=True)

    # Report
    from tracker import generate_report
    report = generate_report(tracking_df, stats)
    print(f"\n{report}")

    run_config = {
        "start_date": args.start_date,
        "end_date": args.end_date,
        "method": args.method,
        "threshold": args.threshold,
        "mode": "sample",
    }

    # Save JSON
    if args.output:
        payload = {
            "config": run_config,
            "stats": stats,
            "large_wallets": tracking_df.to_dict(orient="records"),
        }
        with open(args.output, "w") as f:
            json.dump(payload, f, indent=2, default=str)
        print(f"\nResults saved to {args.output}")

    # Dashboard
    if args.dashboard:
        path = generate_dashboard(
            tracking_df, stats,
            all_wallets_df=wallets_df,
            output_path=args.dashboard_file,
            run_config=run_config,
        )
        print(f"\nDashboard saved to {path}")

    # Excel
    if args.excel:
        path = export_excel(
            tracking_df, stats,
            all_wallets_df=wallets_df,
            output_path=args.excel_file,
            run_config=run_config,
        )
        print(f"\nExcel report saved to {path}")


def main():
    args = parse_args()

    # ── Sample mode (offline) ──────────────────────────────
    if args.sample:
        _run_sample(args)
        return

    # ── Connect ─────────────────────────────────────────────
    rpc = args.rpc_url or None
    print("Connecting to Plasma RPC...")
    try:
        fetcher = PlasmaFetcher(rpc_url=rpc)
        latest = fetcher.latest_block()
        print(f"  Connected.  Chain ID {config.CHAIN_ID}  |  Latest block: {latest:,}")
    except Exception as e:
        print(f"  ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # ── Resolve block range ─────────────────────────────────
    print(f"\nResolving blocks for {args.start_date} to {args.end_date} ...")
    start_block = fetcher.date_to_block(args.start_date)
    end_block = fetcher.date_to_block(args.end_date)

    # Optional: narrow scan window around the 25th
    if args.scan_days > 0:
        # The monthly ecosystem unlock is ~25th of each month
        mid_date = args.start_date[:8] + "25"
        mid_block = fetcher.date_to_block(mid_date)
        # Estimate blocks per day from recent chain data
        ts1 = fetcher.block_timestamp(max(0, mid_block - 1000))
        ts2 = fetcher.block_timestamp(mid_block)
        secs_per_block = max((ts2 - ts1) / 1000, 0.5)
        blocks_per_day = int(86400 / secs_per_block)
        start_block = max(start_block, mid_block - args.scan_days * blocks_per_day)
        end_block = min(end_block, mid_block + args.scan_days * blocks_per_day)
        print(f"  Narrowed to ±{args.scan_days} days around the 25th")

    n_blocks = end_block - start_block + 1
    print(f"  Block range: {start_block:,} — {end_block:,}  ({n_blocks:,} blocks)")

    # ── Collect wallet data ─────────────────────────────────
    wallet_amounts = defaultdict(float)
    all_txs = []

    if args.wallets_file:
        # --- Mode: pre-built wallet list ---
        print(f"\nLoading wallets from {args.wallets_file} ...")
        with open(args.wallets_file) as f:
            addrs = [line.strip().lower() for line in f if line.strip()
                     and not line.startswith("#")]
        print(f"  Loaded {len(addrs)} addresses. Fetching balances...")
        balances = fetcher.get_balances(addrs)
        for addr, bal in balances.items():
            if bal is not None:
                wallet_amounts[addr] = bal
        print(f"  {len(wallet_amounts)} wallets with valid balances.")

    elif args.contracts or config.VESTING_CONTRACTS:
        # --- Mode: known vesting contracts ---
        contracts = (
            [a.strip() for a in args.contracts.split(",") if a.strip()]
            if args.contracts
            else config.VESTING_CONTRACTS
        )
        print(f"\nScanning {len(contracts)} vesting contract(s) via API...")
        for contract in contracts:
            short = f"{contract[:8]}...{contract[-4:]}"
            print(f"  Fetching txs from {short} ...")
            txs = fetcher.get_normal_txs(contract, start_block, end_block)
            count = 0
            for tx in txs:
                val_xpl = int(tx.get("value", "0")) / 10 ** config.XPL_DECIMALS
                to_addr = tx.get("to", "").lower()
                if val_xpl >= args.min_value and to_addr:
                    wallet_amounts[to_addr] += val_xpl
                    all_txs.append(tx)
                    count += 1
            print(f"    {count} qualifying transfers found")

    else:
        # --- Mode: discovery (default fallback) ---
        print(f"\nDiscovery mode: scanning {n_blocks:,} blocks for "
              f"transfers >= {args.min_value:,.0f} XPL ...")
        if n_blocks > 500_000:
            print("  NOTE: Large block range. Consider using --scan-days "
                  "to narrow the window.")

        txs = fetcher.scan_blocks(
            start_block, end_block,
            min_value_xpl=args.min_value,
            progress_cb=_progress,
        )
        print(f"  Found {len(txs):,} transactions >= {args.min_value:,.0f} XPL")
        all_txs.extend(txs)

        for tx in txs:
            if tx["to"]:
                wallet_amounts[tx["to"]] += tx["value_xpl"]

        # Show top distributors
        sender_totals = defaultdict(float)
        for tx in txs:
            sender_totals[tx["from"]] += tx["value_xpl"]
        top_senders = sorted(sender_totals.items(), key=lambda x: -x[1])[:args.top_n]
        if top_senders:
            print(f"\n  Top {len(top_senders)} distributors "
                  f"(likely vesting/treasury contracts):")
            for addr, total in top_senders:
                short = f"{addr[:6]}...{addr[-4:]}"
                print(f"    {short}  {total:>18,.2f} XPL sent")

    if not wallet_amounts:
        print("\nNo qualifying unlock transactions found.")
        print("  Suggestions:")
        print("    - Lower --min-value")
        print("    - Provide known --contracts addresses")
        print("    - Check --start-date / --end-date range")
        print("    - Use --discover to scan blocks directly")
        sys.exit(0)

    print(f"\n{len(wallet_amounts):,} unique recipient wallets found.")

    # ── Classify ────────────────────────────────────────────
    print(f"\nClassifying wallets  (method={args.method}, "
          f"threshold={args.threshold}) ...")
    wallets_df, stats = classify_wallets(
        dict(wallet_amounts),
        method=args.method,
        threshold=args.threshold,
    )
    print(f"  Cutoff: {stats['cutoff_xpl']:,.2f} XPL")
    print(f"  Large:  {stats['n_large']} / {stats['n_total']} wallets")

    if stats["n_large"] == 0:
        print("\nNo wallets classified as 'large'. Try lowering --threshold.")
        sys.exit(0)

    # ── Track selling ───────────────────────────────────────
    print(f"\nFetching current balances for {stats['n_large']} large wallets...")
    tracking_df = track_selling(fetcher, wallets_df)

    # ── Report ──────────────────────────────────────────────
    report = generate_report(tracking_df, stats)
    print(f"\n{report}")

    run_config = {
        "start_date": args.start_date,
        "end_date": args.end_date,
        "method": args.method,
        "threshold": args.threshold,
        "min_value_xpl": args.min_value,
    }

    # ── Save JSON ───────────────────────────────────────────
    if args.output:
        payload = {
            "config": run_config,
            "stats": stats,
            "large_wallets": tracking_df.to_dict(orient="records"),
        }
        with open(args.output, "w") as f:
            json.dump(payload, f, indent=2, default=str)
        print(f"\nResults saved to {args.output}")

    # ── Dashboard ───────────────────────────────────────────
    if args.dashboard:
        path = generate_dashboard(
            tracking_df, stats,
            all_wallets_df=wallets_df,
            output_path=args.dashboard_file,
            run_config=run_config,
        )
        print(f"\nDashboard saved to {path}")

    # ── Excel ───────────────────────────────────────────────
    if args.excel:
        path = export_excel(
            tracking_df, stats,
            all_wallets_df=wallets_df,
            output_path=args.excel_file,
            run_config=run_config,
        )
        print(f"\nExcel report saved to {path}")


if __name__ == "__main__":
    main()
