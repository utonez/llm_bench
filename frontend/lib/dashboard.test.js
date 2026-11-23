// Run with: node --test frontend/
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  barWidth,
  bestModel,
  buildInsights,
  formatMs,
  formatPercent,
  formatTwd,
  latencyTier,
  monthlyCostTwd,
  PAGES,
  parseDays,
  parseRoute,
  scoreModels,
  sortRows,
  summarizeScale,
} from "./dashboard.js";

test("scoreModels normalizes speed, accuracy and cost-efficiency to 0-100 (best = 100)", () => {
  const scores = Object.fromEntries(
    scoreModels([
      { model: "a", p95_latency_ms: 500, accuracy: 0.8, cost_twd_per_correct: 0.002 },
      { model: "b", p95_latency_ms: 1000, accuracy: 1.0, cost_twd_per_correct: 0.001 },
      { model: "c", p95_latency_ms: null, accuracy: null, cost_twd_per_correct: null },
    ]).map((s) => [s.model, s]),
  );

  assert.deepEqual(scores.a, { model: "a", speed: 100, accuracy: 80, value: 50 });
  assert.deepEqual(scores.b, { model: "b", speed: 50, accuracy: 100, value: 100 });
  assert.deepEqual(scores.c, { model: "c", speed: 0, accuracy: 0, value: 0 });
});

test("summarizeScale reports models, rounds and total calls", () => {
  const scale = summarizeScale([
    { model: "a", runs: 12, calls: 324 },
    { model: "b", runs: 10, calls: 270 },
  ]);

  assert.deepEqual(scale, { models: 2, runs: 12, calls: 594 });
  assert.deepEqual(summarizeScale([]), { models: 0, runs: 0, calls: 0 });
});

test("parseRoute maps known hashes to pages and everything else to the overview", () => {
  assert.equal(parseRoute("#/trends"), "trends");
  assert.equal(parseRoute("#/cost"), "cost");
  assert.equal(parseRoute("#/about"), "about");
  assert.equal(parseRoute("#/overview"), "overview");
  assert.equal(parseRoute(""), "overview");
  assert.equal(parseRoute("#/<img src=x>"), "overview");
  assert.equal(parseRoute(undefined), "overview");
  assert.deepEqual(PAGES, ["overview", "trends", "cost", "about"]);
});

const STATS = [
  {
    model: "qwen",
    provider: "groq",
    p95_latency_ms: 506,
    accuracy: 0.952,
    success_rate: 1,
    cost_twd_per_correct: 0.00238,
  },
  {
    model: "gemini",
    provider: "gemini",
    p95_latency_ms: 10602,
    accuracy: 0.988,
    success_rate: 0.963,
    cost_twd_per_correct: 0.00543,
  },
  {
    model: "gpt-oss",
    provider: "groq",
    p95_latency_ms: 844,
    accuracy: 0.833,
    success_rate: 1,
    cost_twd_per_correct: 0.0013,
  },
];

test("latencyTier buckets P95 into fast / ok / slow", () => {
  assert.equal(latencyTier(506), "fast");
  assert.equal(latencyTier(3400), "ok");
  assert.equal(latencyTier(10602), "slow");
  assert.equal(latencyTier(null), null);
});

test("barWidth is a clamped percentage of the maximum", () => {
  assert.equal(barWidth(0.5, 1), 50);
  assert.equal(barWidth(2, 1), 100);
  assert.equal(barWidth(null, 1), 0);
  assert.equal(barWidth(1, 0), 0);
});

test("buildInsights names the best model per priority with its evidence", () => {
  const [speed, accuracy, cost] = buildInsights(STATS);

  assert.equal(speed.model, "qwen");
  assert.match(speed.detail, /506 ms/);
  assert.equal(accuracy.model, "gemini");
  assert.match(accuracy.detail, /98\.8%/);
  assert.match(accuracy.caveat, /10\.6 s/); // slow tail is called out, not hidden
  assert.equal(cost.model, "gpt-oss");
  assert.match(cost.detail, /0\.00130/);
});

test("buildInsights omits a caveat when the most accurate model is also fast", () => {
  const fastAndAccurate = STATS.map((s) => (s.model === "gemini" ? { ...s, p95_latency_ms: 700 } : s));

  const [, accuracy] = buildInsights(fastAndAccurate);

  assert.equal(accuracy.caveat, null);
});

test("buildInsights returns nothing without data", () => {
  assert.deepEqual(buildInsights([]), []);
});

test("formatPercent shows one decimal and a dash for missing values", () => {
  assert.equal(formatPercent(0.9634), "96.3%");
  assert.equal(formatPercent(1), "100.0%");
  assert.equal(formatPercent(null), "—");
});

test("formatMs switches to seconds from one second up", () => {
  assert.equal(formatMs(844.2), "844 ms");
  assert.equal(formatMs(10602), "10.6 s");
  assert.equal(formatMs(undefined), "—");
});

test("formatTwd uses the requested precision", () => {
  assert.equal(formatTwd(3.99), "NT$ 3.99");
  assert.equal(formatTwd(0.00088, 5), "NT$ 0.00088");
  assert.equal(formatTwd(1234.5, 0), "NT$ 1,235");
  assert.equal(formatTwd(null), "—");
});

test("monthlyCostTwd scales cost per call to 30 days", () => {
  assert.equal(monthlyCostTwd(0.004, 10000), 1200);
  assert.equal(monthlyCostTwd(null, 10000), null);
  assert.equal(monthlyCostTwd(0.004, -5), null);
});

test("sortRows sorts without mutating and puts nulls last either way", () => {
  const rows = [
    { model: "a", p95: 300 },
    { model: "b", p95: null },
    { model: "c", p95: 100 },
  ];
  const original = structuredClone(rows);

  assert.deepEqual(sortRows(rows, "p95", "asc").map((r) => r.model), ["c", "a", "b"]);
  assert.deepEqual(sortRows(rows, "p95", "desc").map((r) => r.model), ["a", "c", "b"]);
  assert.deepEqual(rows, original);
});

test("bestModel respects direction and ignores missing values", () => {
  const rows = [
    { model: "fast", p95: 500, accuracy: 0.9 },
    { model: "slow", p95: 9000, accuracy: 0.99 },
    { model: "none", p95: null, accuracy: null },
  ];

  assert.equal(bestModel(rows, "p95", "lower"), "fast");
  assert.equal(bestModel(rows, "accuracy", "higher"), "slow");
  assert.equal(bestModel([], "p95", "lower"), null);
});

test("parseDays only accepts the offered windows", () => {
  assert.equal(parseDays("14"), 14);
  assert.equal(parseDays("30"), 30);
  assert.equal(parseDays("99"), 7);
  assert.equal(parseDays("<script>"), 7);
  assert.equal(parseDays(null), 7);
});
