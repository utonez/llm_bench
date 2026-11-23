# Vendored third-party files

Served from our own origin so the dashboard can use a strict Content-Security-Policy
(`script-src 'self'`) instead of trusting a CDN at runtime.

| Package | Version | Released | License | Source | Verification |
|---|---|---|---|---|---|
| Chart.js | 4.6.1 | 2026-10-22 | MIT (`chartjs-4.6.1/LICENSE.md`) | npm registry tarball `chart.js-4.6.1.tgz` → `package/dist/chart.umd.min.js` | Tarball SHA-512 matched npm's published `dist.integrity` (`sha512-hJyniucsFmq//EvXYvJ6c6mahPoI3kaxdjVH8awTaJ/fDNWeSqqqArixMJWkWNN6fcYvPU3HneSANFNYtRi61g==`). File SHA-256: `87364cc2b2a76a6684929e7d6b80b18a897794db38400caff1fcf1791c6925d2` |

To upgrade: download the new tarball from `https://registry.npmjs.org/chart.js`, verify its
SHA-512 against the registry's `dist.integrity`, replace the folder, and update this table.
