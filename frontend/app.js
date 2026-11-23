// Dashboard wiring: hash-routed pages over one same-origin API; render with textContent only.
// Per-element colors/widths use element.style (CSSOM), which the strict CSP allows.
import {
  barWidth,
  bestModel,
  buildInsights,
  formatMs,
  formatPercent,
  formatTwd,
  latencyTier,
  monthlyCostTwd,
  parseDays,
  parseRoute,
  scoreModels,
  sortRows,
  summarizeScale,
} from "./lib/dashboard.js";

const PALETTE = ["#0e8a5f", "#2f6fdb", "#d4880f", "#8b5cf6", "#d9485f", "#0891b2"];
const SVG_NS = "http://www.w3.org/2000/svg";
const charts = new Map();
const state = {
  page: "overview",
  stats: [],
  series: [],
  loaded: false,
  sortKey: "p95_latency_ms",
  sortDir: "asc",
  colors: new Map(),
};

const $ = (selector) => document.querySelector(selector);

function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function colorOf(model) {
  return state.colors.get(model) ?? PALETTE[0];
}

function dot(model) {
  const node = el("span", undefined, "dot");
  node.style.setProperty("--dot", colorOf(model));
  node.setAttribute("aria-hidden", "true");
  return node;
}

function cell(child, className) {
  const td = el("td", undefined, className);
  td.append(child);
  return td;
}

function setStatus(message) {
  const status = $("#status");
  status.textContent = message;
  status.hidden = message === "";
}

async function fetchJson(path) {
  const response = await fetch(path, { headers: { Accept: "application/json" } });
  const body = await response.json().catch(() => null);
  if (!response.ok || !body?.success) throw new Error(body?.error ?? `HTTP ${response.status}`);
  return body.data;
}

/** Stable colors: assigned by model name, so a model keeps its color across windows. */
function assignColors(stats) {
  const names = [...new Set(stats.map((s) => s.model))].sort();
  state.colors = new Map(names.map((name, i) => [name, PALETTE[i % PALETTE.length]]));
}

/** Big number, small unit: "NT$ 0.00130" → [unit "NT$", "0.00130"], "506 ms" → ["506", unit "ms"]. */
function withUnit(text) {
  const prefix = text.match(/^(NT\$)\s(.+)$/);
  if (prefix) return [el("span", prefix[1], "unit"), document.createTextNode(prefix[2])];
  const suffix = text.match(/^([\d.,]+)\s?(ms|s|%)$/);
  if (suffix) return [document.createTextNode(suffix[1]), el("span", suffix[2], "unit")];
  return [document.createTextNode(text)];
}

// ── Overview: evidence strip ─────────────────────────────────────────
function renderScale(stats) {
  const scale = summarizeScale(stats);
  const values = {
    models: [String(scale.models), "個"],
    runs: [String(scale.runs), "輪"],
    calls: [scale.calls.toLocaleString("en-US"), "次"],
  };
  for (const [key, [number, unit]] of Object.entries(values)) {
    $(`[data-scale="${key}"]`).replaceChildren(document.createTextNode(number), el("span", unit, "unit"));
  }
}

// ── Overview: verdict with P95 sparklines ────────────────────────────
function sparkline(model) {
  const points = state.series.find((s) => s.model === model)?.points ?? [];
  const values = points.map((p) => p.p95_latency_ms).filter((v) => typeof v === "number");
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", "spark");
  svg.setAttribute("viewBox", "0 0 100 30");
  svg.setAttribute("preserveAspectRatio", "none");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", `${model} 的 P95 延遲走勢`);
  if (values.length < 2) return svg;

  const logs = values.map((v) => Math.log10(Math.max(v, 1)));
  const lo = Math.min(...logs);
  const span = Math.max(...logs) - lo || 1;
  const coords = logs.map((v, i) => [(i / (logs.length - 1)) * 100, 27 - ((v - lo) / span) * 24]);
  const path = document.createElementNS(SVG_NS, "polyline");
  path.setAttribute("points", coords.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" "));
  path.setAttribute("fill", "none");
  path.setAttribute("stroke", colorOf(model));
  path.setAttribute("stroke-width", "2");
  path.setAttribute("vector-effect", "non-scaling-stroke");
  path.setAttribute("stroke-linejoin", "round");
  svg.append(path);
  return svg;
}

function renderVerdict(stats) {
  const cards = buildInsights(stats).map((insight) => {
    const card = el("article", undefined, "insight");
    const model = el("p", undefined, "insight-model");
    model.append(dot(insight.model), el("span", insight.model));
    const body = el("div");
    body.append(el("p", insight.title, "insight-title"), model, el("p", insight.detail, "insight-detail"));
    if (insight.caveat) body.append(el("p", `⚠ ${insight.caveat}`, "insight-caveat"));
    const spark = el("div");
    spark.append(sparkline(insight.model), el("p", "P95 延遲走勢（每輪）", "spark-label"));
    card.append(body, spark);
    return card;
  });
  $("#verdict").replaceChildren(...(cards.length ? cards : [el("p", "這個區間還沒有評測資料。", "insight")]));
}

// ── Overview: KPIs ───────────────────────────────────────────────────
function renderKpis(stats) {
  const picks = {
    p95: [bestModel(stats, "p95_latency_ms", "lower"), (s) => formatMs(s.p95_latency_ms)],
    accuracy: [bestModel(stats, "accuracy", "higher"), (s) => formatPercent(s.accuracy)],
    success: [bestModel(stats, "success_rate", "higher"), (s) => formatPercent(s.success_rate)],
    value: [bestModel(stats, "cost_twd_per_correct", "lower"), (s) => formatTwd(s.cost_twd_per_correct, 5)],
  };
  for (const [metric, [model, format]] of Object.entries(picks)) {
    const card = $(`.kpi[data-metric="${metric}"]`);
    const row = stats.find((s) => s.model === model);
    card.querySelector(".kpi-value").replaceChildren(...withUnit(row ? format(row) : "—"));
    const label = card.querySelector(".kpi-model");
    label.replaceChildren(...(row ? [dot(row.model), el("span", `${row.model} · ${row.provider}`)] : []));
    if (!row) label.textContent = "—";
  }
}

// ── Overview: capability scorecard ───────────────────────────────────
function renderScorecard(stats) {
  const axes = [
    ["speed", "速度"],
    ["accuracy", "正確率"],
    ["value", "成本效益"],
  ];
  const rows = scoreModels(stats).map((score) => {
    const row = el("div", undefined, "score-row");
    const name = el("div", undefined, "score-name");
    name.append(dot(score.model), el("span", score.model));
    const bars = el("div", undefined, "score-bars");
    for (const [key, label] of axes) {
      const bar = el("div", undefined, "score-bar");
      const caption = el("div", undefined, "score-bar-label");
      caption.append(el("span", label), el("strong", String(score[key])));
      const track = el("div", undefined, "score-track");
      const fill = el("div", undefined, "score-fill");
      fill.style.width = `${score[key]}%`;
      fill.style.setProperty("--dot", colorOf(score.model));
      track.append(fill);
      bar.append(caption, track);
      bars.append(bar);
    }
    row.append(name, bars);
    return row;
  });
  $("#scorecard").replaceChildren(...rows);
}

// ── Overview: leaderboard ────────────────────────────────────────────
function meter(text, ratio) {
  const wrap = el("div", undefined, "meter");
  const track = el("div", undefined, "meter-track");
  const fill = el("div", undefined, "meter-fill");
  fill.style.width = `${barWidth(ratio, 1)}%`;
  track.append(fill);
  wrap.append(el("span", text), track);
  return wrap;
}

function errorList(counts) {
  const errors = Object.entries(counts);
  if (!errors.length) return el("span", "無", "none");
  const list = el("div", undefined, "error-list");
  list.append(...errors.map(([kind, n]) => el("span", `${kind} ×${n}`, "error-badge")));
  return list;
}

function renderLeaderboard() {
  const rows = sortRows(state.stats, state.sortKey, state.sortDir);
  const best = {
    accuracy: bestModel(state.stats, "accuracy", "higher"),
    value: bestModel(state.stats, "cost_twd_per_correct", "lower"),
    cost: bestModel(state.stats, "cost_twd_per_1k_calls", "lower"),
  };
  $("#leaderboard tbody").replaceChildren(
    ...rows.map((s, index) => {
      const tr = document.createElement("tr");
      const name = el("div", undefined, "model-cell");
      const label = el("div");
      label.append(el("span", s.model, "model-name"), el("span", s.provider, "provider"));
      name.append(dot(s.model), label);
      const tier = latencyTier(s.p95_latency_ms);
      tr.append(
        cell(el("span", String(index + 1), "rank"), "col-rank"),
        cell(name, "col-model"),
        cell(meter(formatPercent(s.success_rate), s.success_rate)),
        cell(el("span", formatMs(s.p95_latency_ms), tier ? `tier tier-${tier}` : "none")),
        el("td", formatMs(s.avg_latency_ms)),
        cell(meter(formatPercent(s.accuracy), s.accuracy), s.model === best.accuracy ? "best" : undefined),
        el("td", formatTwd(s.cost_twd_per_1k_calls), s.model === best.cost ? "best" : undefined),
        el("td", formatTwd(s.cost_twd_per_correct, 5), s.model === best.value ? "best" : undefined),
        el("td", String(s.runs)),
        cell(errorList(s.error_counts), "col-errors"),
      );
      return tr;
    }),
  );
  for (const button of document.querySelectorAll("th button[data-sort]")) {
    const active = button.dataset.sort === state.sortKey;
    button.setAttribute("aria-sort", active ? (state.sortDir === "asc" ? "ascending" : "descending") : "none");
  }
}

// ── Charts (drawn only when their page is visible) ───────────────────
function theme() {
  const css = getComputedStyle(document.documentElement);
  return { text: css.getPropertyValue("--muted").trim(), grid: css.getPropertyValue("--line").trim() };
}

function drawChart(id, config) {
  charts.get(id)?.destroy();
  charts.set(id, new window.Chart(document.getElementById(id), config));
}

function baseOptions(text, grid) {
  return {
    maintainAspectRatio: false,
    animation: { duration: 300 },
    plugins: {
      legend: {
        position: "bottom",
        labels: { color: text, boxWidth: 10, boxHeight: 10, useBorderRadius: true, borderRadius: 2 },
      },
      tooltip: { backgroundColor: "#0e1a2b", padding: 10, cornerRadius: 8, boxPadding: 4 },
    },
    scales: {
      x: { ticks: { color: text, maxTicksLimit: 6 }, grid: { display: false }, border: { color: grid } },
      y: { ticks: { color: text }, grid: { color: grid }, border: { display: false } },
    },
  };
}

function lineConfig(pick, yFormat, yScale = {}) {
  const { text, grid } = theme();
  const options = baseOptions(text, grid);
  options.interaction = { mode: "nearest", axis: "x", intersect: false };
  options.scales.x = {
    ...options.scales.x,
    type: "linear",
    ticks: {
      ...options.scales.x.ticks,
      callback: (v) => new Date(v).toLocaleDateString("zh-TW", { month: "numeric", day: "numeric" }),
    },
  };
  options.scales.y = { ...options.scales.y, ...yScale, ticks: { ...options.scales.y.ticks, callback: yFormat } };
  options.plugins.tooltip.callbacks = {
    title: (items) => new Date(items[0].parsed.x).toLocaleString("zh-TW"),
    label: (item) => ` ${item.dataset.label}：${yFormat(item.parsed.y)}`,
  };
  return {
    type: "line",
    data: {
      datasets: state.series.map((s) => ({
        label: s.model,
        data: s.points.map((p) => ({ x: Date.parse(p.timestamp), y: pick(p) })),
        borderColor: colorOf(s.model),
        backgroundColor: colorOf(s.model),
        borderWidth: 2,
        tension: 0, // straight segments: no implied values between measured runs
        pointRadius: 0,
        pointHoverRadius: 4,
        spanGaps: true,
      })),
    },
    options,
  };
}

function valueConfig() {
  const { text, grid } = theme();
  const options = baseOptions(text, grid);
  const measured = state.stats.filter((s) => s.cost_twd_per_1k_calls != null && s.accuracy != null);
  options.scales.x = {
    ...options.scales.x,
    beginAtZero: true,
    grid: { color: grid },
    title: { display: true, text: "每千次成本（NT$）", color: text },
  };
  options.scales.y = {
    ...options.scales.y,
    suggestedMin: 0.7,
    suggestedMax: 1,
    title: { display: true, text: "正確率", color: text },
    ticks: { ...options.scales.y.ticks, callback: (v) => formatPercent(v) },
  };
  options.plugins.tooltip.callbacks = {
    label: (item) => ` ${item.dataset.label}：${formatTwd(item.parsed.x)} / 千次 · ${formatPercent(item.parsed.y)}`,
  };
  return {
    type: "scatter",
    data: {
      datasets: measured.map((s) => ({
        label: s.model,
        data: [{ x: s.cost_twd_per_1k_calls, y: s.accuracy }],
        backgroundColor: colorOf(s.model),
        pointRadius: 9,
        pointHoverRadius: 11,
      })),
    },
    options,
  };
}

function renderPageCharts(page) {
  if (!window.Chart || !state.loaded) return;
  if (page === "trends") {
    drawChart("chart-p95", lineConfig((p) => p.p95_latency_ms, (v) => formatMs(v), { type: "logarithmic" }));
    drawChart("chart-success", lineConfig((p) => p.success_rate, (v) => formatPercent(v), { suggestedMin: 0.8, max: 1 }));
  } else if (page === "cost") {
    drawChart("chart-value", valueConfig());
  }
}

// ── Cost page: monthly estimate ──────────────────────────────────────
function renderEstimate() {
  const callsPerDay = Number($("#calls-per-day").value);
  $("#estimate tbody").replaceChildren(
    ...sortRows(state.stats, "cost_twd_per_call", "asc").map((s) => {
      const tr = document.createElement("tr");
      const name = el("div", undefined, "model-cell");
      name.append(dot(s.model), el("span", s.model, "model-name"));
      tr.append(
        cell(name, "col-model"),
        el("td", formatTwd(s.cost_twd_per_call, 5)),
        el("td", formatTwd(monthlyCostTwd(s.cost_twd_per_call, callsPerDay), 0), "monthly"),
      );
      return tr;
    }),
  );
}

// ── Routing ──────────────────────────────────────────────────────────
function showPage(page) {
  state.page = page;
  for (const section of document.querySelectorAll(".page")) {
    section.hidden = section.dataset.page !== page;
  }
  for (const link of document.querySelectorAll(".tabs a")) {
    if (link.dataset.page === page) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
  const heading = document.querySelector(`.page[data-page="${page}"] h1`);
  document.title = page === "overview" ? "金融場景 LLM 評測報告" : `${heading?.textContent ?? ""} · LLM 評測報告`;
  window.scrollTo({ top: 0 });
  renderPageCharts(page);
}

// ── Load + events ────────────────────────────────────────────────────
async function load(days) {
  for (const button of document.querySelectorAll(".segmented button")) {
    button.setAttribute("aria-pressed", String(Number(button.dataset.days) === days));
  }
  document.body.classList.add("is-loading");
  setStatus("");
  try {
    const [stats, series] = await Promise.all([
      fetchJson(`/v1/stats?days=${days}`),
      fetchJson(`/v1/timeseries?days=${days}`),
    ]);
    Object.assign(state, { stats, series, loaded: true });
    assignColors(stats);
    renderScale(stats);
    renderVerdict(stats);
    renderKpis(stats);
    renderScorecard(stats);
    renderLeaderboard();
    renderEstimate();
    renderPageCharts(state.page);
    const latest = stats.map((s) => Date.parse(s.last_run_at)).sort((a, b) => a - b).at(-1);
    $("#updated").textContent = latest
      ? `最近一輪：${new Date(latest).toLocaleString("zh-TW", { dateStyle: "medium", timeStyle: "short" })}`
      : "尚無資料";
  } catch (error) {
    setStatus(`無法載入資料（${error instanceof Error ? error.message : "未知錯誤"}），請稍後再試。`);
    $("#updated").textContent = "資料載入失敗";
  } finally {
    document.body.classList.remove("is-loading");
  }
}

function init() {
  for (const button of document.querySelectorAll(".segmented button")) {
    button.addEventListener("click", () => {
      const days = Number(button.dataset.days);
      const url = new URL(window.location.href);
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
  window.addEventListener("hashchange", () => showPage(parseRoute(window.location.hash)));

  showPage(parseRoute(window.location.hash));
  load(parseDays(new URL(window.location.href).searchParams.get("days")));
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
