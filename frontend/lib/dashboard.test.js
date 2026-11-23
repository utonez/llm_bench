// Run with: node --test frontend/
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  bestModel,
  formatMs,
  formatPercent,
  formatTwd,
  monthlyCostTwd,
  parseDays,
  sortRows,
} from "./dashboard.js";

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
