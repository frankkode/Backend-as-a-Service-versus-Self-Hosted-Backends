# Benchmark run provenance and validity notes

Three benchmark sweeps exist. Only the third is valid. This file records why, so the thesis can
cite the conditions accurately and so the discarded runs are not mistaken for evidence.

## Run 3 — VALID (use this one)

**Date:** 2026-09-03. **Duration:** 124 min. **Files:** `results/*_rep*.json` (54), summarised in
`results/table_5_1_summary_final.csv`.

Conditions:

| | |
|---|---|
| Django host | Hostinger KVM 2, 2 vCPU / 8 GB, Ubuntu 24.04, **Frankfurt, Germany** |
| Django URL | `http://<vps-ip>:8080/api` (nginx to gunicorn, 5 sync workers) |
| Django `DEBUG` | **False** |
| Supabase | Free tier project, AWS **eu-west-2 (London)** |
| Load generator | Author's macOS machine, single location, k6 |
| Co-tenant | An unrelated production stack on the same VPS was **stopped** for the whole sweep, so Django had the full 2 vCPU |
| Dataset | **2,000 records reset before every repetition** (72 resets) via `scripts/reset_data.py` |
| Token handling | Supabase JWT re-minted before each configuration (60 min expiry vs ~2 h sweep) |

Data quality: 54/54 files contain real request data; error rates 0.0% everywhere except
read-heavy 200 VU (≤0.1%). No configuration hit the k6 timeout ceiling.

Measured network asymmetry (`results/rtt_measurement.txt`): median TCP connect 58.9 ms to the
Frankfurt VPS vs 25.8 ms to Supabase London — a **33 ms residual gap that disadvantages the
self-hosted variant**. Immaterial at 50/200 VU where latencies are in the hundreds/thousands of ms;
comparable to the effect size only at 10 VU.

## Run 2 — DISCARDED (`results/vps_run_no_reset/`)

Same infrastructure as Run 3, but **no dataset reset**. The `small` seed is 50 records; the sweep
POSTed an estimated 27,264 records, so the table grew ~545× during the run. Because neither variant
paginates `GET /records`, read latency tracks table size, so configurations executed later queried a
vastly larger dataset than earlier ones. The faster variant also wrote more rows, penalising itself.
Additionally the co-tenant was running during part of the Django phase, and three repetitions failed
outright (83%, 100%, 79% errors).

This run is the origin of the "mixed 200 VU total collapse" and "head-of-line blocking on
`report_view`" readings. Both were artifacts of dataset growth, not architecture.

## Run 1 — DISCARDED (`results/localhost_run_archive/`)

August 2026. Django was reached over **loopback** (`http://localhost/api`) with `DEBUG=True`, while
Supabase was reached over the public internet. Three simultaneous confounds:

- no network path for Django at all (≈0 ms vs ≈26 ms for Supabase) — favoured Django
- `DEBUG=True` retains every SQL query in `connection.queries`, slowing requests and growing memory
  under sustained load — penalised Django
- unbounded dataset growth, as in Run 2

Not usable for any RQ1 claim.

## Thesis passages changed (all done, 2026-09-04)

Written against Run 1/2 and now corrected to Run 3:

1. **Table 5.1** — all 18 rows replaced from `table_5_1_summary_final.csv`; asterisk markers and the
   60 s-ceiling footnote removed, since no configuration reached the timeout.
2. **Figure 5.1** — regenerated (`scripts/figures/` equivalents); no capacity-exhausted cells remain.
3. **Section 5.1** — rewritten as three paragraphs: indistinguishable at 10 VUs (largest gap 1.34x,
   within the measured 33 ms path difference); the read/write split from 50 VUs up; zero failures plus
   tail behaviour.
4. **Section 6.1, RQ1** — head-of-line blocking and the Django-collapse narrative removed; the
   mechanism is now hedged as "the most plausible reading" rather than a demonstrated one.
5. **Section 6.1, RQ4** — the low-versus-high-concurrency axis replaced by workload composition.
6. **Table 6.1** — "Workload shape" reversed (write-dominant to Supabase, read-dominant and mixed to
   Django); "Expected concurrency and growth" no longer implies a Django saturation cliff.
7. **Abstract** — performance sentence rewritten around the read/write split.
8. **Figure D.2** — regenerated from Run 3.
9. **Section 3.3** — now states two EU regions, `DEBUG=False`, 5 Gunicorn workers, co-tenant stopped,
   and the 2,000-row reset before every repetition. The 60 s timeout sentence notes it was never hit.
10. **Section 3.6 and 6.3** — the 33 ms measured path asymmetry is stated with its direction and the
    operating points where it does and does not matter.

### Cascade found afterwards: Appendix B performance-efficiency criteria

Six ISO/IEC 25010 Performance efficiency criteria had been scored against the invalid benchmark.
Three changed, and two of those **inverted between variants**:

| # | criterion | before | after |
|---|---|---|---|
| 14 | median read < 200 ms at 10 VU | both Satisfied (106-151 / 39-56 ms) | **both Not satisfied** (219-228 / 296-304 ms) |
| 15 | p95 < 2 s at 50 VU read-heavy | Supabase Satisfied, Django Not satisfied (13.25-13.83 s) | **Supabase Not satisfied** (2,561-2,676 ms), **Django Satisfied** (1,496-1,502 ms) |
| 16 | degrades gracefully beyond capacity | Django Partial (73-100% collapse) | **Django Satisfied** (<=0.1% errors, no timeouts) |

Row 19's justification also cited "hundreds of accumulated rows", an artifact of the unreset dataset;
it now cites the fixed 2,000-row baseline. Rows 17 and 18 are code-inspection criteria and are
unchanged.

Consequences propagated: Table 5.2 Performance efficiency row (Supabase 6/6 -> **4 satisfied, 2 not
satisfied**; Django 1 satisfied/1 partial/4 not satisfied -> **2 satisfied, 4 not satisfied**);
Section 5.2's attribution of Django's cluster (no longer "worker-pool saturation" but absent pooling,
query optimisation and pagination); Section 6.1 RQ2, whose claim that Supabase scored at or above
Django on *every* performance-efficiency criterion is now false and has been replaced; Section 6.4's
future-research item; and Figure D.1, regenerated by `scripts/figures/fig_D1.py` directly from
`criteria_catalog.csv` so it cannot drift from the catalog again.

Reliability tallies are unaffected: row 16 sits under Performance efficiency, not Reliability.

## Original list of passages requiring change (kept for the audit trail)

Written against Run 1/2 and now contradicted by Run 3:

1. **Table 5.1** — replace with `table_5_1_summary_final.csv`.
2. **Figure 5.1** — regenerate; no capacity-exhausted cells remain, so the asterisk footnote and the
   60 s ceiling discussion go.
3. **Section 5.1** — the "three regimes" reading is void. Run 3 shows a read/write split: Django
   faster on read-heavy and mixed at 50–200 VU, Supabase faster on write-heavy at 50–200 VU, both
   effectively tied at 10 VU, neither failing.
4. **Section 6.1, RQ1 interpretation** — remove the head-of-line-blocking mechanism and the
   Django-collapse narrative entirely.
5. **Section 6.1, RQ4 synthesis** — the "Django wins at low concurrency, loses badly at high
   concurrency" axis no longer holds.
6. **Table 6.1, "Workload shape" row** — should now read: write-heavy traffic points toward
   Supabase, read-heavy and mixed toward Django.
7. **Abstract** — the performance sentence must be rewritten.
8. **Figure D.2** — regenerate from Run 3.
9. **Section 3.3** — must state: two different EU regions (not "same cloud region"), 2,000-record
   reset before every repetition, `DEBUG=False`, co-tenant stopped, 5 Gunicorn workers.
10. **Section 3.6 / 6.3** — add the 33 ms measured path asymmetry and the dataset-reset protocol.

## Headline Run 3 numbers (p50 range across 3 reps)

| profile | VU | Supabase | Django |
|---|---|---|---|
| read-heavy | 10 | 219–228 | 296–304 |
| read-heavy | 50 | 1098–1141 | **515–544** |
| read-heavy | 200 | 5622–6708 | **4170–4469** |
| write-heavy | 10 | 98–100 | 97–98 |
| write-heavy | 50 | **104–110** | 147–196 |
| write-heavy | 200 | **1951–2258** | 3295–3503 |
| mixed | 10 | 214–230 | 242–251 |
| mixed | 50 | 770–930 | **338–485** |
| mixed | 200 | 4198–4868 | **3899–4452** |

Throughput: Django leads on reads (29.5 vs 21.1 req/s at 200 VU), Supabase on writes (53.2 vs
41.7 req/s at 200 VU).
