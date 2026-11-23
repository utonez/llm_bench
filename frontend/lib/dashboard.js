// Pure dashboard logic: no DOM, no network. Unit-tested with `node --test`.

/** @typedef {"asc" | "desc"} SortDirection */
/** @typedef {"lower" | "higher"} Better */

export const DAY_OPTIONS = Object.freeze([7, 14, 30]);
export const DEFAULT_DAYS = 7;
const DAYS_PER_MONTH = 30;
const MISSING = "—";

/** @param {unknown} value @returns {value is number} */
const isNumber = (value) => typeof value === "number" && Number.isFinite(value);

/**
 * @param {number | null | undefined} ratio 0..1
 * @returns {string}
 */
export function formatPercent(ratio) {
  return isNumber(ratio) ? `${(ratio * 100).toFixed(1)}%` : MISSING;
}

/**
 * @param {number | null | undefined} ms
 * @returns {string}
 */
export function formatMs(ms) {
  if (!isNumber(ms)) return MISSING;
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${Math.round(ms)} ms`;
}

/**
 * @param {number | null | undefined} amount
 * @param {number} [digits]
 * @returns {string}
 */
export function formatTwd(amount, digits = 2) {
  if (!isNumber(amount)) return MISSING;
  const text = amount.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
  return `NT$ ${text}`;
}

/**
 * Projected monthly spend for a given daily volume.
 * @param {number | null | undefined} costPerCallTwd
 * @param {number} callsPerDay
 * @returns {number | null}
 */
export function monthlyCostTwd(costPerCallTwd, callsPerDay) {
  if (!isNumber(costPerCallTwd) || !isNumber(callsPerDay) || callsPerDay < 0) return null;
  return costPerCallTwd * callsPerDay * DAYS_PER_MONTH;
}

/**
 * Returns a new sorted array; missing values always sort last.
 * @template {Record<string, unknown>} T
 * @param {readonly T[]} rows
 * @param {keyof T & string} key
 * @param {SortDirection} direction
 * @returns {T[]}
 */
export function sortRows(rows, key, direction) {
  const sign = direction === "asc" ? 1 : -1;
  return [...rows].sort((a, b) => {
    const x = a[key];
    const y = b[key];
    if (!isNumber(x) && !isNumber(y)) return 0;
    if (!isNumber(x)) return 1;
    if (!isNumber(y)) return -1;
    return (x - y) * sign;
  });
}

/**
 * Model id with the best value for a metric, or null when nothing is measurable.
 * @param {readonly Record<string, unknown>[]} rows
 * @param {string} key
 * @param {Better} better
 * @returns {string | null}
 */
export function bestModel(rows, key, better) {
  const measured = rows.filter((row) => isNumber(row[key]));
  if (measured.length === 0) return null;
  const [best] = sortRows(measured, key, better === "lower" ? "asc" : "desc");
  return /** @type {string} */ (best.model);
}

/**
 * Accept only the offered windows from untrusted input (e.g. the URL).
 * @param {string | null | undefined} raw
 * @returns {number}
 */
export function parseDays(raw) {
  const value = Number.parseInt(String(raw ?? ""), 10);
  return DAY_OPTIONS.includes(value) ? value : DEFAULT_DAYS;
}
