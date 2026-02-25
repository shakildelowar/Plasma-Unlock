"""Interactive HTML dashboard generator for XPL wallet unlock data.

Produces a single self-contained .html file with:
  - KPI cards (total unlocked, sold, remaining, large wallet count)
  - Doughnut chart for selling behavior distribution
  - Bar chart for top wallets by amount received
  - Sell velocity scatter chart (XPL/day vs amount received)
  - Horizontal bar for sold vs remaining per wallet
  - Sortable, searchable data table with timing details
  - Data sources section
  - All powered by Chart.js (loaded from CDN) with no other dependencies
"""

import json
import html as html_mod
from datetime import datetime

import config


def generate_dashboard(
    tracking_df,
    stats: dict,
    all_wallets_df=None,
    output_path: str = "xpl_dashboard.html",
    run_config: dict = None,
) -> str:
    """
    Write an interactive HTML dashboard and return the output path.
    """
    # Prepare data for JS
    if tracking_df.empty:
        wallet_rows = []
    else:
        wallet_rows = []
        for i, (_, r) in enumerate(tracking_df.iterrows()):
            wallet_rows.append({
                "rank": i + 1,
                "address": r["address"],
                "short_addr": f"{r['address'][:6]}...{r['address'][-4:]}" if len(r["address"]) > 12 else r["address"],
                "received": round(r["amount_xpl"], 2),
                "balance": round(r.get("current_balance", 0), 2),
                "sold": round(r.get("amount_sold", 0), 2),
                "pct_sold": round(r.get("pct_sold", 0), 1),
                "remaining": round(r.get("remaining", 0), 2),
                "behavior": r.get("behavior", "unknown"),
                "behavior_label": r.get("behavior", "unknown").replace("_", " ").title(),
                "source": r.get("source", "Plasma RPC / PlasmaScan"),
                # Timing fields
                "unlock_date": r.get("unlock_date", None),
                "unlock_block": int(r["unlock_block"]) if r.get("unlock_block") else None,
                "unlock_tx": r.get("unlock_tx_hash", None),
                "first_sell_date": r.get("first_sell_date", None),
                "last_activity": r.get("last_activity_date", None),
                "num_sell_txs": int(r["num_sell_txs"]) if r.get("num_sell_txs") else 0,
                "velocity": round(r["sell_velocity_per_day"], 2) if r.get("sell_velocity_per_day") else 0,
                "days_since_unlock": round(r["days_since_unlock"], 1) if r.get("days_since_unlock") else 0,
                "days_selling": round(r["days_active_selling"], 1) if r.get("days_active_selling") else 0,
                "label": r.get("label", None),
            })

    total_recv = sum(w["received"] for w in wallet_rows)
    total_sold = sum(w["sold"] for w in wallet_rows)
    total_rem = sum(w["remaining"] for w in wallet_rows)

    behavior_counts = {}
    for w in wallet_rows:
        b = w["behavior"]
        behavior_counts[b] = behavior_counts.get(b, 0) + 1

    # Top 20 for charts
    top_wallets = wallet_rows[:20]

    # Replace NaN/None with JSON-safe null values
    def _sanitize(val):
        if val is None:
            return None
        if isinstance(val, float) and (val != val):  # NaN check
            return None
        return val

    for w in wallet_rows:
        for k, v in w.items():
            w[k] = _sanitize(v)

    js_data = json.dumps({
        "wallets": wallet_rows,
        "top_wallets": top_wallets,
        "stats": stats,
        "totals": {
            "received": round(total_recv, 2),
            "sold": round(total_sold, 2),
            "remaining": round(total_rem, 2),
            "pct_sold": round(total_sold / total_recv * 100, 1) if total_recv else 0,
        },
        "behavior_counts": behavior_counts,
        "config": run_config or {},
        "generated": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    }, indent=2, default=str)

    rpc_url = config.RPC_URL
    plasmascan_url = config.PLASMASCAN_API_URL
    arkham_url = config.ARKHAM_API_URL
    xpl_contract = config.XPL_CONTRACT
    chain_id = config.CHAIN_ID

    page_html = _TEMPLATE
    page_html = page_html.replace("/* __DATA__ */", f"const DATA = {js_data};")
    page_html = page_html.replace("__RPC_URL__", rpc_url)
    page_html = page_html.replace("__PLASMASCAN_URL__", plasmascan_url)
    page_html = page_html.replace("__ARKHAM_URL__", arkham_url)
    page_html = page_html.replace("__XPL_CONTRACT__", xpl_contract)
    page_html = page_html.replace("__CHAIN_ID__", str(chain_id))

    with open(output_path, "w") as f:
        f.write(page_html)

    return output_path


# ── HTML Template ─────────────────────────────────────────

_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>XPL Wallet Unlock Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
  :root {
    --bg: #0a0a12;
    --surface: rgba(255, 255, 255, 0.05);
    --surface-solid: #13131f;
    --border: rgba(255, 255, 255, 0.08);
    --border-outer: rgba(99, 102, 241, 0.15);
    --text: #e8e8f0;
    --text-secondary: #a5b4fc;
    --muted: #7a7a9a;
    --accent: #818cf8;
    --accent2: #a78bfa;
    --blue: #60a5fa;
    --indigo: #818cf8;
    --violet: #a78bfa;
    --green: #34d399;
    --red: #f87171;
    --amber: #fbbf24;
    --purple: #a78bfa;
    --blur: 24px;
    --radius: 20px;
    --shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    --shadow-lg: 0 16px 48px rgba(99, 102, 241, 0.15);
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', 'Segoe UI', Roboto, sans-serif;
    background: var(--bg); color: var(--text); line-height: 1.6;
    padding: 0 24px 48px;
    min-height: 100vh;
    background-image:
      radial-gradient(ellipse at 20% 0%, rgba(99, 102, 241, 0.15) 0%, transparent 50%),
      radial-gradient(ellipse at 80% 0%, rgba(139, 92, 246, 0.12) 0%, transparent 50%),
      radial-gradient(ellipse at 50% 100%, rgba(59, 130, 246, 0.08) 0%, transparent 50%);
    background-attachment: fixed;
  }
  .container { max-width: 1400px; margin: 0 auto; }

  .header {
    text-align: center; padding: 40px 0 28px;
    margin-bottom: 28px;
  }
  .header h1 {
    font-size: 32px; font-weight: 800; letter-spacing: -0.5px;
    background: linear-gradient(135deg, var(--indigo), var(--violet), var(--blue));
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
  }
  .header .meta {
    color: var(--muted); font-size: 13px; margin-top: 8px;
    font-weight: 500;
  }
  .header .meta strong { color: var(--accent); }

  /* Glass card base */
  .glass {
    background: var(--surface);
    backdrop-filter: blur(var(--blur));
    -webkit-backdrop-filter: blur(var(--blur));
    border-radius: var(--radius);
    border: 1px solid var(--border);
    box-shadow: var(--shadow);
    transition: box-shadow 0.3s ease, transform 0.2s ease;
  }
  .glass:hover {
    box-shadow: var(--shadow-lg);
  }

  .kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 16px; margin-bottom: 28px; }
  .kpi {
    padding: 22px; text-align: center;
  }
  .kpi .label {
    font-size: 11px; text-transform: uppercase; letter-spacing: 1.2px;
    color: var(--muted); font-weight: 600;
  }
  .kpi .value {
    font-size: 28px; font-weight: 800; margin-top: 6px;
    font-variant-numeric: tabular-nums;
  }
  .kpi .sub { font-size: 11px; color: var(--muted); margin-top: 4px; font-weight: 500; }
  .kpi.green .value { color: var(--green); }
  .kpi.red .value { color: var(--red); }
  .kpi.blue .value {
    background: linear-gradient(135deg, var(--indigo), var(--blue));
    -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
  }
  .kpi.amber .value { color: var(--amber); }
  .kpi.purple .value {
    background: linear-gradient(135deg, var(--violet), var(--indigo));
    -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
  }

  .charts { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 28px; }
  @media (max-width: 900px) { .charts { grid-template-columns: 1fr; } }
  .chart-card { padding: 24px; }
  .chart-card h3 {
    font-size: 12px; color: var(--muted); text-transform: uppercase;
    letter-spacing: 0.8px; margin-bottom: 18px; font-weight: 700;
  }
  .chart-wrap { position: relative; width: 100%; }

  .table-section {
    padding: 24px; margin-bottom: 28px; overflow-x: auto;
  }
  .table-header {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 18px; flex-wrap: wrap; gap: 12px;
  }
  .table-header h3 {
    font-size: 12px; color: var(--muted); text-transform: uppercase;
    letter-spacing: 0.8px; font-weight: 700;
  }
  .search-box {
    background: rgba(255, 255, 255, 0.06);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    padding: 10px 16px; color: var(--text); font-size: 13px; width: 320px;
    outline: none; transition: all 0.3s ease; font-weight: 500;
  }
  .search-box::placeholder { color: #5a5a7a; }
  .search-box:focus {
    border-color: var(--accent);
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.12);
  }

  table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 12px; }
  th {
    text-align: left; padding: 10px 12px; font-weight: 700; color: var(--muted);
    border-bottom: 2px solid rgba(255, 255, 255, 0.06); cursor: pointer;
    white-space: nowrap; user-select: none; font-size: 10px;
    text-transform: uppercase; letter-spacing: 0.8px;
    background: rgba(255, 255, 255, 0.03);
  }
  th:first-child { border-radius: 10px 0 0 0; }
  th:last-child { border-radius: 0 10px 0 0; }
  th:hover { color: var(--accent); }
  th .arrow { font-size: 9px; margin-left: 3px; color: var(--accent); }
  td {
    padding: 10px 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    white-space: nowrap;
  }
  tr:hover td { background: rgba(129, 140, 248, 0.06); }
  .mono { font-family: 'SF Mono', 'Consolas', 'Monaco', monospace; font-size: 11px; }
  .addr-link {
    font-family: 'SF Mono', 'Consolas', 'Monaco', monospace; font-size: 11px;
    color: var(--accent); text-decoration: none; font-weight: 600;
    transition: color 0.2s;
  }
  .addr-link:hover { color: var(--violet); text-decoration: underline; }
  .num {
    text-align: right; font-variant-numeric: tabular-nums;
    font-family: 'SF Mono', 'Consolas', monospace; font-size: 11px;
  }
  .dim { color: var(--muted); font-size: 11px; }
  .badge {
    display: inline-block; padding: 3px 10px; border-radius: 9999px;
    font-size: 10px; font-weight: 700; text-transform: capitalize;
    letter-spacing: 0.3px;
  }
  .badge.heavy_seller { background: rgba(248, 113, 113, 0.15); color: var(--red); }
  .badge.moderate_seller { background: rgba(251, 191, 36, 0.15); color: var(--amber); }
  .badge.light_seller { background: rgba(96, 165, 250, 0.15); color: var(--blue); }
  .badge.holder { background: rgba(52, 211, 153, 0.15); color: var(--green); }

  .sold-bar {
    width: 80px; height: 6px; background: rgba(255, 255, 255, 0.08);
    border-radius: 3px; display: inline-block; vertical-align: middle;
    overflow: hidden;
  }
  .sold-bar-fill { height: 100%; border-radius: 3px; }

  .lbl {
    display: inline-block; padding: 2px 8px; border-radius: 6px;
    font-size: 9px; font-weight: 700;
    background: rgba(167, 139, 250, 0.15);
    color: var(--violet); margin-left: 4px;
  }

  .sources { padding: 24px; }
  .sources h3 {
    font-size: 12px; color: var(--muted); text-transform: uppercase;
    letter-spacing: 0.8px; margin-bottom: 14px; font-weight: 700;
  }
  .source-item {
    display: flex; gap: 16px; padding: 12px 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  }
  .source-item:last-child { border: none; }
  .source-name {
    font-weight: 700; min-width: 150px; font-size: 13px;
    color: var(--accent);
  }
  .source-url {
    font-family: 'SF Mono', monospace; font-size: 11px; color: var(--muted);
    word-break: break-all;
  }
  .source-desc { font-size: 12px; color: var(--text); line-height: 1.5; }

  .footer {
    text-align: center; color: var(--muted); font-size: 12px; margin-top: 36px;
    font-weight: 500;
  }

  /* Scrollbar styling */
  ::-webkit-scrollbar { height: 6px; width: 6px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: rgba(99, 102, 241, 0.2); border-radius: 3px; }
  ::-webkit-scrollbar-thumb:hover { background: rgba(99, 102, 241, 0.4); }
</style>
</head>
<body>

<div class="container">

<div class="header">
  <h1>XPL Wallet Unlock Dashboard</h1>
  <div class="meta" id="meta"></div>
</div>

<div class="kpis" id="kpis"></div>

<div class="charts">
  <div class="chart-card glass">
    <h3>Selling Behavior Distribution</h3>
    <div class="chart-wrap"><canvas id="behaviorChart"></canvas></div>
  </div>
  <div class="chart-card glass">
    <h3>Top Wallets - Amount Received (XPL)</h3>
    <div class="chart-wrap"><canvas id="topWalletsChart"></canvas></div>
  </div>
  <div class="chart-card glass">
    <h3>Sell Velocity - XPL Sold Per Day</h3>
    <div class="chart-wrap"><canvas id="velocityChart"></canvas></div>
  </div>
  <div class="chart-card glass">
    <h3>Time to First Sell (Hours After Unlock)</h3>
    <div class="chart-wrap"><canvas id="timeToSellChart"></canvas></div>
  </div>
  <div class="chart-card glass" style="grid-column: 1 / -1;">
    <h3>Sold vs Remaining - Large Wallets</h3>
    <div class="chart-wrap"><canvas id="soldRemainingChart"></canvas></div>
  </div>
</div>

<div class="table-section glass">
  <div class="table-header">
    <h3>Large Wallet Details - Full Breakdown with Timing</h3>
    <input type="text" class="search-box" id="searchBox" placeholder="Search address, behavior, label, or source...">
  </div>
  <table>
    <thead><tr id="tableHead"></tr></thead>
    <tbody id="tableBody"></tbody>
  </table>
</div>

<div class="sources glass">
  <h3>Data Sources & Methodology</h3>
  <div id="sourcesList"></div>
</div>

<div class="footer" id="footer"></div>

</div>

<script>
/* __DATA__ */

const PLASMASCAN_BASE = '__PLASMASCAN_URL__'.replace('/api', '');

const fmt = (n) => n != null ? n.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2}) : '0.00';
const fmtK = (n) => {
  if (n == null || isNaN(n)) return '0';
  if (n >= 1e6) return (n/1e6).toFixed(1) + 'M';
  if (n >= 1e3) return (n/1e3).toFixed(0) + 'K';
  return n.toFixed(0);
};
const fmtDate = (d) => d ? d.replace(' UTC','') : '-';

const BEHAVIOR_COLORS = {
  heavy_seller: '#ef4444', moderate_seller: '#f59e0b',
  light_seller: '#3b82f6', holder: '#10b981',
};
const CHART_PALETTE = ['#6366f1','#8b5cf6','#3b82f6','#a78bfa','#818cf8','#7c3aed','#6d28d9','#4f46e5','#4338ca','#2563eb'];

// ── Meta ──
document.getElementById('meta').innerHTML =
  `Generated: ${DATA.generated} &nbsp;&middot;&nbsp; ` +
  `Method: <strong>${DATA.stats.method || 'N/A'}</strong> &nbsp;&middot;&nbsp; ` +
  `Threshold: <strong>${DATA.stats.threshold || 'N/A'}</strong> &nbsp;&middot;&nbsp; ` +
  `Cutoff: <strong>${fmt(DATA.stats.cutoff_xpl || 0)} XPL</strong>`;

// ── KPIs ──
const avgVelocity = DATA.wallets.filter(w => w.velocity > 0).reduce((s,w) => s + w.velocity, 0) / Math.max(1, DATA.wallets.filter(w => w.velocity > 0).length);
const avgDaysSelling = DATA.wallets.filter(w => w.days_selling > 0).reduce((s,w) => s + w.days_selling, 0) / Math.max(1, DATA.wallets.filter(w => w.days_selling > 0).length);
const totalSellTxs = DATA.wallets.reduce((s,w) => s + (w.num_sell_txs || 0), 0);

const kpiDiv = document.getElementById('kpis');
const kpis = [
  { label: 'Total XPL Unlocked', value: fmtK(DATA.totals.received), sub: `across ${DATA.wallets.length} large wallets`, cls: 'blue' },
  { label: 'Total XPL Sold', value: fmtK(DATA.totals.sold), sub: `${DATA.totals.pct_sold}% of received`, cls: 'red' },
  { label: 'Total XPL Remaining', value: fmtK(DATA.totals.remaining), sub: 'potential sell pressure', cls: 'green' },
  { label: 'Large Wallets', value: DATA.stats.n_large || 0, sub: `of ${DATA.stats.n_total || 0} total (${DATA.stats.pct_large || 0}%)`, cls: 'amber' },
  { label: 'Avg Sell Velocity', value: fmtK(avgVelocity), sub: 'XPL/day (selling wallets)', cls: 'red' },
  { label: 'Total Sell Txs', value: totalSellTxs.toLocaleString(), sub: `avg ${Math.round(avgDaysSelling)} days active`, cls: 'purple' },
];
kpis.forEach(k => {
  kpiDiv.innerHTML += `<div class="kpi glass ${k.cls}"><div class="label">${k.label}</div><div class="value">${k.value}</div><div class="sub">${k.sub}</div></div>`;
});

// ── Chart defaults ──
Chart.defaults.font.family = "-apple-system, BlinkMacSystemFont, 'SF Pro Text', sans-serif";
Chart.defaults.color = '#7a7a9a';

// ── Behavior Doughnut ──
const behLabels = Object.keys(DATA.behavior_counts).map(b => b.replace(/_/g,' ').replace(/\b\w/g, c => c.toUpperCase()));
const behValues = Object.values(DATA.behavior_counts);
const behColors = Object.keys(DATA.behavior_counts).map(b => BEHAVIOR_COLORS[b] || '#8b5cf6');

new Chart(document.getElementById('behaviorChart'), {
  type: 'doughnut',
  data: {
    labels: behLabels,
    datasets: [{ data: behValues, backgroundColor: behColors, borderWidth: 2, borderColor: '#1a1a2e', hoverOffset: 10 }]
  },
  options: {
    responsive: true,
    cutout: '65%',
    plugins: {
      legend: { position: 'right', labels: { color: '#374151', padding: 14, font: { size: 11, weight: '600' }, usePointStyle: true, pointStyleWidth: 10 } }
    }
  }
});

// ── Top Wallets Bar ──
new Chart(document.getElementById('topWalletsChart'), {
  type: 'bar',
  data: {
    labels: DATA.top_wallets.map(w => w.label ? w.short_addr + ' (' + w.label + ')' : w.short_addr),
    datasets: [{
      label: 'Received (XPL)',
      data: DATA.top_wallets.map(w => w.received),
      backgroundColor: DATA.top_wallets.map((w,i) => CHART_PALETTE[i % CHART_PALETTE.length]),
      borderRadius: 6, borderSkipped: false,
    }]
  },
  options: {
    responsive: true, indexAxis: 'y',
    scales: {
      x: { ticks: { color: '#6b7280', callback: v => fmtK(v) }, grid: { color: 'rgba(99,102,241,0.06)' } },
      y: { ticks: { color: '#6b7280', font: { family: "'SF Mono', Consolas", size: 9 } }, grid: { display: false } }
    },
    plugins: {
      legend: { display: false },
      tooltip: { callbacks: { label: ctx => fmt(ctx.raw) + ' XPL' } }
    }
  }
});

// ── Sell Velocity Chart ──
const sellingWallets = DATA.wallets.filter(w => w.velocity > 0).sort((a,b) => b.velocity - a.velocity).slice(0, 15);
new Chart(document.getElementById('velocityChart'), {
  type: 'bar',
  data: {
    labels: sellingWallets.map(w => w.short_addr),
    datasets: [{
      label: 'XPL/day',
      data: sellingWallets.map(w => w.velocity),
      backgroundColor: sellingWallets.map(w => BEHAVIOR_COLORS[w.behavior] || '#8b5cf6'),
      borderRadius: 6, borderSkipped: false,
    }]
  },
  options: {
    responsive: true, indexAxis: 'y',
    scales: {
      x: { ticks: { color: '#6b7280', callback: v => fmtK(v) }, grid: { color: 'rgba(99,102,241,0.06)' } },
      y: { ticks: { color: '#6b7280', font: { family: "'SF Mono', Consolas", size: 9 } }, grid: { display: false } }
    },
    plugins: {
      legend: { display: false },
      tooltip: { callbacks: { label: ctx => fmt(ctx.raw) + ' XPL/day' } }
    }
  }
});

// ── Time to First Sell ──
const sellTimingWallets = DATA.wallets.filter(w => w.unlock_date && w.first_sell_date);
function hoursGap(d1, d2) {
  return (new Date(d2) - new Date(d1)) / 3600000;
}
const ttfs = sellTimingWallets.map(w => ({
  addr: w.short_addr, hours: hoursGap(w.unlock_date, w.first_sell_date),
  behavior: w.behavior, received: w.received
})).sort((a,b) => a.hours - b.hours).slice(0, 15);

new Chart(document.getElementById('timeToSellChart'), {
  type: 'bar',
  data: {
    labels: ttfs.map(t => t.addr),
    datasets: [{
      label: 'Hours to First Sell',
      data: ttfs.map(t => Math.round(t.hours * 10) / 10),
      backgroundColor: ttfs.map(t => BEHAVIOR_COLORS[t.behavior] || '#8b5cf6'),
      borderRadius: 6, borderSkipped: false,
    }]
  },
  options: {
    responsive: true,
    scales: {
      y: { ticks: { color: '#6b7280' }, grid: { color: 'rgba(99,102,241,0.06)' }, title: { display: true, text: 'Hours', color: '#6b7280' } },
      x: { ticks: { color: '#6b7280', font: { family: "'SF Mono', Consolas", size: 9 } }, grid: { display: false } }
    },
    plugins: {
      legend: { display: false },
      tooltip: { callbacks: { label: ctx => ctx.raw + ' hours after unlock (' + fmt(ttfs[ctx.dataIndex].received) + ' XPL)' } }
    }
  }
});

// ── Sold vs Remaining ──
const svr_wallets = DATA.top_wallets.slice(0, 15);
new Chart(document.getElementById('soldRemainingChart'), {
  type: 'bar',
  data: {
    labels: svr_wallets.map(w => w.label ? w.short_addr + ' (' + w.label + ')' : w.short_addr),
    datasets: [
      { label: 'Sold', data: svr_wallets.map(w => w.sold), backgroundColor: '#ef4444', borderRadius: 6 },
      { label: 'Remaining', data: svr_wallets.map(w => w.remaining), backgroundColor: '#10b981', borderRadius: 6 },
    ]
  },
  options: {
    responsive: true,
    scales: {
      x: { stacked: true, ticks: { color: '#6b7280', font: { family: "'SF Mono', Consolas", size: 9 } }, grid: { display: false } },
      y: { stacked: true, ticks: { color: '#6b7280', callback: v => fmtK(v) }, grid: { color: 'rgba(99,102,241,0.06)' } }
    },
    plugins: {
      legend: { labels: { color: '#374151', padding: 20, font: { weight: '600' }, usePointStyle: true, pointStyleWidth: 10 } },
      tooltip: { callbacks: { label: ctx => ctx.dataset.label + ': ' + fmt(ctx.raw) + ' XPL' } }
    }
  }
});

// ── Sortable Table with Clickable Addresses ──
const columns = [
  { key: 'rank', label: '#', sortType: 'num' },
  { key: 'address', label: 'Address', sortType: 'str' },
  { key: 'label', label: 'Label', sortType: 'str' },
  { key: 'received', label: 'Received', sortType: 'num' },
  { key: 'sold', label: 'Sold', sortType: 'num' },
  { key: 'pct_sold', label: '% Sold', sortType: 'num' },
  { key: 'remaining', label: 'Remaining', sortType: 'num' },
  { key: 'behavior', label: 'Behavior', sortType: 'str' },
  { key: 'unlock_date', label: 'Unlock Date', sortType: 'str' },
  { key: 'first_sell_date', label: 'First Sell', sortType: 'str' },
  { key: 'last_activity', label: 'Last Activity', sortType: 'str' },
  { key: 'num_sell_txs', label: '# Txs', sortType: 'num' },
  { key: 'velocity', label: 'Velocity', sortType: 'num' },
  { key: 'days_selling', label: 'Days Active', sortType: 'num' },
  { key: 'source', label: 'Source', sortType: 'str' },
];

let sortCol = 'rank', sortDir = 1;
let filterText = '';

function renderHead() {
  const tr = document.getElementById('tableHead');
  tr.innerHTML = '';
  columns.forEach(c => {
    const th = document.createElement('th');
    const arrow = sortCol === c.key ? (sortDir === 1 ? ' ▲' : ' ▼') : '';
    th.innerHTML = c.label + `<span class="arrow">${arrow}</span>`;
    th.onclick = () => { if (sortCol === c.key) sortDir *= -1; else { sortCol = c.key; sortDir = 1; } renderTable(); };
    tr.appendChild(th);
  });
}

function renderTable() {
  renderHead();
  let rows = [...DATA.wallets];
  if (filterText) {
    const q = filterText.toLowerCase();
    rows = rows.filter(r =>
      r.address.toLowerCase().includes(q) ||
      r.behavior_label.toLowerCase().includes(q) ||
      (r.label || '').toLowerCase().includes(q) ||
      (r.source || '').toLowerCase().includes(q)
    );
  }
  const col = columns.find(c => c.key === sortCol);
  rows.sort((a, b) => {
    let va = a[sortCol] ?? '', vb = b[sortCol] ?? '';
    if (col && col.sortType === 'num') return ((+va || 0) - (+vb || 0)) * sortDir;
    return String(va).localeCompare(String(vb)) * sortDir;
  });
  const tbody = document.getElementById('tableBody');
  tbody.innerHTML = '';
  rows.forEach(r => {
    const tr = document.createElement('tr');
    const barColor = BEHAVIOR_COLORS[r.behavior] || '#8b5cf6';
    const barPct = Math.min(r.pct_sold || 0, 100);
    const addrUrl = PLASMASCAN_BASE + '/address/' + r.address;
    tr.innerHTML =
      `<td class="num">${r.rank}</td>` +
      `<td><a href="${addrUrl}" target="_blank" rel="noopener" class="addr-link" title="View on PlasmaScan: ${r.address}">${r.short_addr}</a></td>` +
      `<td>${r.label || '<span class="dim">-</span>'}</td>` +
      `<td class="num">${fmt(r.received)}</td>` +
      `<td class="num">${fmt(r.sold)}</td>` +
      `<td><div class="sold-bar"><div class="sold-bar-fill" style="width:${barPct}%;background:${barColor}"></div></div> ${r.pct_sold || 0}%</td>` +
      `<td class="num">${fmt(r.remaining)}</td>` +
      `<td><span class="badge ${r.behavior}">${r.behavior_label}</span></td>` +
      `<td class="mono dim">${fmtDate(r.unlock_date)}</td>` +
      `<td class="mono dim">${fmtDate(r.first_sell_date)}</td>` +
      `<td class="mono dim">${fmtDate(r.last_activity)}</td>` +
      `<td class="num">${r.num_sell_txs || '-'}</td>` +
      `<td class="num" style="color:${r.velocity > 0 ? 'var(--red)' : 'var(--muted)'}">${r.velocity > 0 ? fmtK(r.velocity) + '/d' : '-'}</td>` +
      `<td class="num">${r.days_selling > 0 ? r.days_selling + 'd' : '-'}</td>` +
      `<td class="dim" style="font-size:10px">${r.source || '-'}</td>`;
    tbody.appendChild(tr);
  });
}

document.getElementById('searchBox').addEventListener('input', e => { filterText = e.target.value; renderTable(); });
renderTable();

// ── Sources ──
const sourcesList = document.getElementById('sourcesList');
const sources = [
  { name: 'Plasma RPC', url: '__RPC_URL__', desc: 'Primary blockchain data. Block scanning identifies unlock transactions by value threshold. Balance queries (eth_getBalance) track current holdings for sell pressure calculation.' },
  { name: 'PlasmaScan API', url: '__PLASMASCAN_URL__', desc: 'Etherscan-compatible indexed API. Transaction history lookups by address for vesting contract outflows, transfer timestamps, and sell transaction counts.' },
  { name: 'Arkham Intelligence', url: '__ARKHAM_URL__', desc: 'Entity labeling engine. Maps on-chain addresses to known entities (Plasma Foundation, Ecosystem Fund, Early Investors, etc.). Used for wallet identification and attribution.' },
  { name: 'XPL Token Contract', url: '__XPL_CONTRACT__', desc: 'XPL ERC-20 token on Plasma mainnet. Transfer events parsed to track token movements from vesting contracts to recipient wallets.' },
  { name: 'Classification', url: 'Statistical (MAD)', desc: 'Wallets classified as "large" using Median Absolute Deviation with threshold 2.0 (cutoff: ' + fmt(DATA.stats.cutoff_xpl || 0) + ' XPL). Behavior: Heavy (>=75% sold), Moderate (40-75%), Light (10-40%), Holder (<10%).' },
  { name: 'Timing', url: 'On-chain timestamps', desc: 'Unlock dates from block timestamps of the distribution transaction. First sell / last activity from outbound transaction history. Velocity = total sold / days since first sell.' },
];
sources.forEach(s => {
  sourcesList.innerHTML += `<div class="source-item"><div class="source-name">${s.name}</div><div><div class="source-url">${s.url}</div><div class="source-desc">${s.desc}</div></div></div>`;
});

document.getElementById('footer').textContent = `XPL Wallet Unlock Dashboard — Generated ${DATA.generated} — Plasma Chain ID __CHAIN_ID__`;
</script>
</body>
</html>"""
