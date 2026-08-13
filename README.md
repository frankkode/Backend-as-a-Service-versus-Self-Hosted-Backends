# BaaS vs Self-Hosted — Reference Application

Companion repository to the bachelor thesis "Backend-as-a-Service versus Self-Hosted Backends: A
Comparative Evaluation of Supabase and Django/PostgreSQL for Small-Business Web Platforms."

- `supabase-variant/` — the Supabase (BaaS) implementation
- `django-variant/` — the self-hosted Django/PostgreSQL implementation
- `shared/data-generator/` — deterministic synthetic-data generator used by both variants
- `shared/k6/` — the benchmark script (Section 3.3 / 5.1)
- `tests/` — cross-variant equivalence and authorization tests (Section 5)
- `results/` — raw k6 benchmark output
