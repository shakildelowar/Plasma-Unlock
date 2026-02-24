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
    }, indent=2)

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
    --bg: #0f172a; --surface: #1e293b; --surface2: #334155;
    --text: #f1f5f9; --muted: #94a3b8; --accent: #38bdf8;
    --green: #34d399; --red: #f87171; --amber: #fbbf24; --blue: #60a5fa;
    --purple: #a78bfa;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--bg); color: var(--text); line-height: 1.5;
    padding: 0 20px 40px;
  }
  .header {
    text-align: center; padding: 32px 0 24px;
    border-bottom: 1px solid var(--surface2); margin-bottom: 24px;
  }
  .header h1 { font-size: 28px; font-weight: 700; letter-spacing: -0.5px; }
  .header h1 span { color: var(--accent); }
  .header .meta { color: var(--muted); font-size: 13px; margin-top: 6px; }

  .kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 28px; }
  .kpi {
    background: var(--surface); border-radius: 12px; padding: 20px;
    border: 1px solid var(--surface2); text-align: center;
  }
  .kpi .label { font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: var(--muted); }
  .kpi .value { font-size: 26px; font-weight: 700; margin-top: 4px; font-variant-numeric: tabular-nums; }
  .kpi .sub { font-size: 11px; color: var(--muted); margin-top: 2px; }
  .kpi.green .value { color: var(--green); }
  .kpi.red .value { color: var(--red); }
  .kpi.blue .value { color: var(--accent); }
  .kpi.amber .value { color: var(--amber); }
  .kpi.purple .value { color: var(--purple); }

  .charts { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 28px; }
  @media (max-width: 900px) { .charts { grid-template-columns: 1fr; } }
  .chart-card {
    background: var(--surface); border-radius: 12px; padding: 20px;
    border: 1px solid var(--surface2);
  }
  .chart-card h3 { font-size: 13px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 16px; }
  .chart-wrap { position: relative; width: 100%; }

  .table-section {
    background: var(--surface); border-radius: 12px; padding: 20px;
    border: 1px solid var(--surface2); margin-bottom: 28px; overflow-x: auto;
  }
  .table-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 12px; }
  .table-header h3 { font-size: 13px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; }
  .search-box {
    background: var(--surface2); border: 1px solid #475569; border-radius: 8px;
    padding: 8px 14px; color: var(--text); font-size: 13px; width: 300px;
    outline: none; transition: border-color 0.2s;
  }
  .search-box:focus { border-color: var(--accent); }

  table { width: 100%; border-collapse: collapse; font-size: 12px; }
  th {
    text-align: left; padding: 8px 10px; font-weight: 600; color: var(--muted);
    border-bottom: 2px solid var(--surface2); cursor: pointer; white-space: nowrap;
    user-select: none; font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px;
  }
  th:hover { color: var(--accent); }
  th .arrow { font-size: 9px; margin-left: 3px; }
  td {
    padding: 8px 10px; border-bottom: 1px solid rgba(255,255,255,0.05);
    white-space: nowrap;
  }
  tr:hover td { background: rgba(56, 189, 248, 0.04); }
  .mono { font-family: 'Consolas', 'Monaco', monospace; font-size: 11px; }
  .addr { font-family: 'Consolas', 'Monaco', monospace; font-size: 11px; color: var(--accent); }
  .num { text-align: right; font-variant-numeric: tabular-nums; font-family: 'Consolas', monospace; font-size: 11px; }
  .dim { color: var(--muted); font-size: 11px; }
  .badge {
    display: inline-block; padding: 2px 8px; border-radius: 9999px;
    font-size: 10px; font-weight: 600; text-transform: capitalize;
  }
  .badge.heavy_seller { background: rgba(248,113,113,0.2); color: var(--red); }
  .badge.moderate_seller { background: rgba(251,191,36,0.2); color: var(--amber); }
  .badge.light_seller { background: rgba(96,165,250,0.2); color: var(--blue); }
  .badge.holder { background: rgba(52,211,153,0.2); color: var(--green); }

  .sold-bar { width: 80px; height: 6px; background: var(--surface2); border-radius: 3px; display: inline-block; vertical-align: middle; }
  .sold-bar-fill { height: 100%; border-radius: 3px; }

  .lbl { display: inline-block; padding: 1px 6px; border-radius: 4px; font-size: 9px; font-weight: 600; background: rgba(167,139,250,0.15); color: var(--purple); margin-left: 4px; }

  .sources {
    background: var(--surface); border-radius: 12px; padding: 20px;
    border: 1px solid var(--surface2);
  }
  .sources h3 { font-size: 13px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px; }
  .source-item { display: flex; gap: 16px; padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.05); }
  .source-item:last-child { border: none; }
  .source-name { font-weight: 600; min-width: 140px; color: var(--accent); font-size: 13px; }
  .source-url { font-family: monospace; font-size: 11px; color: var(--muted); word-break: break-all; }
  .source-desc { font-size: 12px; color: var(--text); }

  .footer { text-align: center; color: var(--muted); font-size: 12px; margin-top: 32px; }
</style>
</head>
<body>

<div class="header">
  <h1><span>XPL</span> Wallet Unlock Dashboard</h1>
  <div class="meta" id="meta"></div>
</div>

<div class="kpis" id="kpis"></div>

<div class="charts">
  <div class="chart-card">
    <h3>Selling Behavior Distribution</h3>
    <div class="chart-wrap"><canvas id="behaviorChart"></canvas></div>
  </div>
  <div class="chart-card">
    <h3>Top Wallets - Amount Received (XPL)</h3>
    <div class="chart-wrap"><canvas id="topWalletsChart"></canvas></div>
  </div>
  <div class="chart-card">
    <h3>Sell Velocity - XPL Sold Per Day</h3>
    <div class="chart-wrap"><canvas id="velocityChart"></canvas></div>
  </div>
  <div class="chart-card">
    <h3>Time to First Sell (Hours After Unlock)</h3>
    <div class="chart-wrap"><canvas id="timeToSellChart"></canvas></div>
  </div>
  <div class="chart-card" style="grid-column: 1 / -1;">
    <h3>Sold vs Remaining - Large Wallets</h3>
    <div class="chart-wrap"><canvas id="soldRemainingChart"></canvas></div>
  </div>
</div>

<div class="table-section">
  <div class="table-header">
    <h3>Large Wallet Details - Full Breakdown with Timing</h3>
    <input type="text" class="search-box" id="searchBox" placeholder="Search address, behavior, label, or source...">
  </div>
  <table>
    <thead><tr id="tableHead"></tr></thead>
    <tbody id="tableBody"></tbody>
  </table>
</div>

<div class="sources">
  <h3>Data Sources & Methodology</h3>
  <div id="sourcesList"></div>
</div>

<div class="footer" id="footer"></div>

<script>
/* __DATA__ */

const fmt = (n) => n.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
const fmtK = (n) => {
  if (n >= 1e6) return (n/1e6).toFixed(1) + 'M';
  if (n >= 1e3) return (n/1e3).toFixed(0) + 'K';
  return n.toFixed(0);
};
const fmtDate = (d) => d ? d.replace(' UTC','') : '-';
const fmtVel = (v) => v > 0 ? fmtK(v) + '/day' : '-';

const BEHAVIOR_COLORS = {
  heavy_seller: '#f87171', moderate_seller: '#fbbf24',
  light_seller: '#60a5fa', holder: '#34d399',
};

// ── Meta ──
document.getElementById('meta').innerHTML =
  `Generated: ${DATA.generated} &nbsp;|&nbsp; ` +
  `Method: <strong>${DATA.stats.method || 'N/A'}</strong> &nbsp;|&nbsp; ` +
  `Threshold: <strong>${DATA.stats.threshold || 'N/A'}</strong> &nbsp;|&nbsp; ` +
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
  kpiDiv.innerHTML += `<div class="kpi ${k.cls}"><div class="label">${k.label}</div><div class="value">${k.value}</div><div class="sub">${k.sub}</div></div>`;
});

// ── Behavior Doughnut ──
const behLabels = Object.keys(DATA.behavior_counts).map(b => b.replace(/_/g,' ').replace(/\b\w/g, c => c.toUpperCase()));
const behValues = Object.values(DATA.behavior_counts);
const behColors = Object.keys(DATA.behavior_counts).map(b => BEHAVIOR_COLORS[b] || '#a78bfa');

new Chart(document.getElementById('behaviorChart'), {
  type: 'doughnut',
  data: {
    labels: behLabels,
    datasets: [{ data: behValues, backgroundColor: behColors, borderWidth: 0, hoverOffset: 8 }]
  },
  options: {
    responsive: true,
    plugins: {
      legend: { position: 'right', labels: { color: '#f1f5f9', padding: 14, font: { size: 11 } } }
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
      backgroundColor: DATA.top_wallets.map(w => BEHAVIOR_COLORS[w.behavior] || '#a78bfa'),
      borderRadius: 4,
    }]
  },
  options: {
    responsive: true, indexAxis: 'y',
    scales: {
      x: { ticks: { color: '#94a3b8', callback: v => fmtK(v) }, grid: { color: 'rgba(255,255,255,0.05)' } },
      y: { ticks: { color: '#94a3b8', font: { family: 'Consolas', size: 9 } }, grid: { display: false } }
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
      backgroundColor: sellingWallets.map(w => BEHAVIOR_COLORS[w.behavior] || '#a78bfa'),
      borderRadius: 4,
    }]
  },
  options: {
    responsive: true, indexAxis: 'y',
    scales: {
      x: { ticks: { color: '#94a3b8', callback: v => fmtK(v) }, grid: { color: 'rgba(255,255,255,0.05)' } },
      y: { ticks: { color: '#94a3b8', font: { family: 'Consolas', size: 9 } }, grid: { display: false } }
    },
    plugins: {
      legend: { display: false },
      tooltip: { callbacks: { label: ctx => fmt(ctx.raw) + ' XPL/day (' + ctx.label + ')' } }
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
      backgroundColor: ttfs.map(t => BEHAVIOR_COLORS[t.behavior] || '#a78bfa'),
      borderRadius: 4,
    }]
  },
  options: {
    responsive: true,
    scales: {
      y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.05)' }, title: { display: true, text: 'Hours', color: '#94a3b8' } },
      x: { ticks: { color: '#94a3b8', font: { family: 'Consolas', size: 9 } }, grid: { display: false } }
    },
    plugins: {
      legend: { display: false },
      tooltip: { callbacks: { label: ctx => ctx.raw + ' hours after unlock (' + fmt(ttfs[ctx.dataIndex].received) + ' XPL received)' } }
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
      { label: 'Sold', data: svr_wallets.map(w => w.sold), backgroundColor: '#f87171', borderRadius: 4 },
      { label: 'Remaining', data: svr_wallets.map(w => w.remaining), backgroundColor: '#34d399', borderRadius: 4 },
    ]
  },
  options: {
    responsive: true,
    scales: {
      x: { stacked: true, ticks: { color: '#94a3b8', font: { family: 'Consolas', size: 9 } }, grid: { display: false } },
      y: { stacked: true, ticks: { color: '#94a3b8', callback: v => fmtK(v) }, grid: { color: 'rgba(255,255,255,0.05)' } }
    },
    plugins: {
      legend: { labels: { color: '#f1f5f9', padding: 20 } },
      tooltip: { callbacks: { label: ctx => ctx.dataset.label + ': ' + fmt(ctx.raw) + ' XPL' } }
    }
  }
});

// ── Sortable Table ──
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
    const barColor = BEHAVIOR_COLORS[r.behavior] || '#a78bfa';
    const barPct = Math.min(r.pct_sold, 100);
    const labelHtml = r.label ? `<span class="lbl">${r.label}</span>` : '';
    tr.innerHTML =
      `<td class="num">${r.rank}</td>` +
      `<td class="addr">${r.short_addr}</td>` +
      `<td>${r.label || '<span class="dim">-</span>'}</td>` +
      `<td class="num">${fmt(r.received)}</td>` +
      `<td class="num">${fmt(r.sold)}</td>` +
      `<td><div class="sold-bar"><div class="sold-bar-fill" style="width:${barPct}%;background:${barColor}"></div></div> ${r.pct_sold}%</td>` +
      `<td class="num">${fmt(r.remaining)}</td>` +
      `<td><span class="badge ${r.behavior}">${r.behavior_label}</span></td>` +
      `<td class="mono dim">${fmtDate(r.unlock_date)}</td>` +
      `<td class="mono dim">${fmtDate(r.first_sell_date)}</td>` +
      `<td class="mono dim">${fmtDate(r.last_activity)}</td>` +
      `<td class="num">${r.num_sell_txs || '-'}</td>` +
      `<td class="num" style="color:${r.velocity > 0 ? 'var(--red)' : 'var(--muted)'}">${r.velocity > 0 ? fmtK(r.velocity) + '/d' : '-'}</td>` +
      `<td class="num">${r.days_selling > 0 ? r.days_selling + 'd' : '-'}</td>` +
      `<td class="dim" style="font-size:10px">${r.source}</td>`;
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
