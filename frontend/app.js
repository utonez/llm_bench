// Dashboard wiring: fetch from the same-origin API, render with textContent only.
import {
  bestModel,
  formatMs,
  formatPercent,
  formatTwd,
  monthlyCostTwd,
  parseDays,
  sortRows,
} from "./lib/dashboard.js";

const PALETTE = ["#0b6e4f", "#2563eb", "#d97706", "#9333ea", "#dc2626", "#0891b2"];
const charts = new Map();
const state = { days: 7, stats: [], sortKey: "p95_latency_ms", sortDir: "asc" };

const $ = (selector) => document.querySelector(selector);

function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function setStatus(message, isError = false) {
  const status = $("#status");
  status.textContent = message;
  status.classList.toggle("error", isError);
  status.hidden = message === "";
}

async function fetchJson(path) {
  const response = await fetch(path, { headers: { Accept: "application/json" } });
  const body = await response.json().catch(() => null);
  if (!response.ok || !body?.success) {
    throw new Error(body?.error ?? `HTTP ${response.status}`);
  }
  return body.data;
}

function colorFor(model) {
  const index = state.stats.findIndex((s) => s.model === model);
  return PALETTE[(index < 0 ? 0 : index) % PALETTE.length];
}

// ── Highlight cards ──────────────────────────────────────────────────
function renderHighlights(stats) {
  const picks = {
    p95: [bestModel(stats, "p95_latency_ms", "lower"), (s) => formatMs(s.p95_latency_ms)],
    accuracy: [bestModel(stats, "accuracy", "higher"), (s) => formatPercent(s.accuracy)],
    success: [bestModel(stats, "success_rate", "higher"), (s) => formatPercent(s.success_rate)],
    value: [
      bestModel(stats, "cost_twd_per_correct", "lower"),
      (s) => formatTwd(s.cost_twd_per_correct, 5),
    ],
  };
  for (const [metric, [model, format]] of Object.entries(picks)) {
    const card = $(`.card[data-metric="${metric}"]`);
    const row = stats.find((s) => s.model === model);
    card.querySelector(".card-model").textContent = row ? row.model : "—";
    card.querySelector(".card-value").textContent = row ? format(row) : "—";
  }
}

// ── Leaderboard ──────────────────────────────────────────────────────
function renderLeaderboard() {
  const tbody = $("#leaderboard tbody");
  const rows = sortRows(state.stats, state.sortKey, state.sortDir);
  const bestP95 = bestModel(state.stats, "p95_latency_ms", "lower");
  const bestAcc = bestModel(state.stats, "accuracy", "higher");
  const bestValue = bestModel(state.stats, "cost_twd_per_correct", "lower");

  tbody.replaceChildren(
    ...rows.map((s) => {
      const tr = document.createElement("tr");
      const name = el("td");
      name.append(el("span", s.model, "model-name"), el("span", s.provider, "provider"));
      const errors = Object.entries(s.error_counts)
        .map(([kind, n]) => `${kind} ${n}`)
        .join(", ");
      tr.append(
        name,
        el("td", formatPercent(s.success_rate)),
        el("td", formatMs(s.avg_latency_ms)),
        el("td", formatMs(s.p95_latency_ms), s.model === bestP95 ? "best" : undefined),
        el("td", formatPercent(s.accuracy), s.model === bestAcc ? "best" : undefined),
        el("td", formatTwd(s.cost_twd_per_1k_calls)),
        el("td", formatTwd(s.cost_twd_per_correct, 5), s.model === bestValue ? "best" : undefined),
        el("td", String(s.runs)),
        el("td", errors || "—", errors ? "errors" : undefined),
      );
      return tr;
    }),
  );

  for (const button of document.querySelectorAll("th button[data-sort]")) {
    const active = button.dataset.sort === state.sortKey;
    button.setAttribute(
      "aria-sort",
      active ? (state.sortDir === "asc" ? "ascending" : "descending") : "none",
    );
  }
}

// ── Charts ───────────────────────────────────────────────────────────
function themeColors() {
  const css = getComputedStyle(document.documentElement);
  return { text: css.getPropertyValue("--muted").trim(), grid: css.getPropertyValue("--border").trim() };
}

function drawChart(id, config) {
  charts.get(id)?.destroy();
  charts.set(id, new window.Chart(document.getElementById(id), config));
}

function lineConfig(series, pick, yTitle, yFormat) {
  const { text, grid } = themeColors();
  return {
    type: "line",
    data: {
      datasets: series.map((s) => ({
        label: s.model,
        data: s.points.map((p) => ({ x: Date.parse(p.timestamp), y: pick(p) })),
        borderColor: colorFor(s.model),
        backgroundColor: colorFor(s.model),
        tension: 0, // straight segments: no implied values between measured runs
        pointRadius: 2,
        spanGaps: true,
      })),
    },
    options: {
      maintainAspectRatio: false,
      interaction: { mode: "nearest", intersect: false },
      scales: {
        x: {
          type: "linear",
          ticks: {
            color: text,
            maxTicksLimit: 6,
            callback: (v) => new Date(v).toLocaleDateString("zh-TW", { month: "numeric", day: "numeric" }),
          },
          grid: { color: grid },
        },
        y: {
          title: { display: true, text: yTitle, color: text },
          ticks: { color: text, callback: yFormat },
          grid: { color: grid },
          beginAtZero: true,
        },
      },
      plugins: {
        legend: { labels: { color: text, boxWidth: 12 } },
        tooltip: {
          callbacks: {
            title: (items) => new Date(items[0].parsed.x).toLocaleString("zh-TW"),
            label: (item) => `${item.dataset.label}: ${yFormat(item.parsed.y)}`,
          },
        },
      },
    },
  };
}

function valueConfig(stats) {
  const { text, grid } = themeColors();
  const measured = stats.filter((s) => s.cost_twd_per_1k_calls != null && s.accuracy != null);
  return {
    type: "scatter",
    data: {
      datasets: measured.map((s) => ({
        label: s.model,
        data: [{ x: s.cost_twd_per_1k_calls, y: s.accuracy }],
        backgroundColor: colorFor(s.model),
        pointRadius: 8,
      })),
    },
    options: {
      maintainAspectRatio: false,
      scales: {
        x: {
          title: { display: true, text: "每千次成本（NT$）", color: text },
          ticks: { color: text },
          grid: { color: grid },
          beginAtZero: true,
        },
        y: {
          title: { display: true, text: "正確率", color: text },
          ticks: { color: text, callback: (v) => formatPercent(v) },
          grid: { color: grid },
          suggestedMin: 0.5,
          suggestedMax: 1,
        },
      },
      plugins: {
        legend: { labels: { color: text, boxWidth: 12 } },
        tooltip: {
          callbacks: {
            label: (item) =>
              `${item.dataset.label}: ${formatTwd(item.parsed.x)} / 千次、${formatPercent(item.parsed.y)}`,
          },
        },
      },
    },
  };
}

function renderCharts(series) {
  if (!window.Chart) return; // vendor script failed to load; tables still work
  drawChart("chart-p95", lineConfig(series, (p) => p.p95_latency_ms, "毫秒", (v) => formatMs(v)));
  drawChart(
    "chart-success",
    lineConfig(series, (p) => p.success_rate, "成功率", (v) => formatPercent(v)),
  );
  drawChart("chart-value", valueConfig(state.stats));
}

// ── Monthly estimate ─────────────────────────────────────────────────
function renderEstimate() {
  const callsPerDay = Number($("#calls-per-day").value);
  const rows = sortRows(state.stats, "cost_twd_per_call", "asc");
  $("#estimate tbody").replaceChildren(
    ...rows.map((s) => {
      const tr = document.createElement("tr");
      tr.append(
        el("td", s.model, "model-name"),
        el("td", formatTwd(s.cost_twd_per_call, 5)),
        el("td", formatTwd(monthlyCostTwd(s.cost_twd_per_call, callsPerDay), 0)),
      );
      return tr;
    }),
  );
}

// ── Load + events ────────────────────────────────────────────────────
async function load(days) {
  state.days = days;
  for (const button of document.querySelectorAll(".window-picker button")) {
    button.setAttribute("aria-pressed", String(Number(button.dataset.days) === days));
  }
  setStatus("載入中…");
  try {
    const [stats, series] = await Promise.all([
      fetchJson(`/v1/stats?days=${days}`),
      fetchJson(`/v1/timeseries?days=${days}`),
    ]);
    state.stats = stats;
    if (stats.length === 0) {
      setStatus("這個區間還沒有評測資料。");
    } else {
      setStatus("");
    }
    renderHighlights(stats);
    renderLeaderboard();
    renderEstimate();
    renderCharts(series);
    const latest = stats.map((s) => Date.parse(s.last_run_at)).sort().at(-1);
    $("#updated").textContent = latest
      ? `最近一輪評測：${new Date(latest).toLocaleString("zh-TW")}`
      : "—";
  } catch (error) {
    setStatus(`無法載入資料（${error instanceof Error ? error.message : "未知錯誤"}），請稍後再試。`, true);
  }
}

function init() {
  const url = new URL(window.location.href);
  for (const button of document.querySelectorAll(".window-picker button")) {
    button.addEventListener("click", () => {
      const days = Number(button.dataset.days);
      url.searchParams.set("days", String(days));
      window.history.replaceState(null, "", url);
      load(days);
    });
  }
  for (const button of document.querySelectorAll("th button[data-sort]")) {
    button.addEventListener("click", () => {
      const key = button.dataset.sort;
      state.sortDir = state.sortKey === key && state.sortDir === "asc" ? "desc" : "asc";
      state.sortKey = key;
      renderLeaderboard();
    });
  }
  $("#calls-per-day").addEventListener("input", renderEstimate);
  load(parseDays(url.searchParams.get("days")));
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
