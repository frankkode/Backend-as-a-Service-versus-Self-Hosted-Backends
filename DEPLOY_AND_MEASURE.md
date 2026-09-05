# VPS deployment, benchmark re-run and operational-effort measurement

Runbook for moving the Django variant off `localhost` and onto the Hostinger VPS, re-running the
k6 benchmark so both variants are measured over a real network path, and measuring operational
effort instead of estimating it.

**Why this matters more than it looks.** The benchmark results currently in Table 5.1 were produced
with `DJANGO_BASE_URL=http://localhost/api`. Supabase requests crossed the internet to AWS
`eu-west-2` (London); Django requests went over loopback with effectively zero network latency. The
low-concurrency finding — Django p50 39–56 ms vs Supabase 106–151 ms — has a gap of roughly
70–95 ms, which is about one round trip to that region. Until Django is measured over a comparable
network path, that finding cannot be attributed to architecture.

There is a second confound in the same direction, working against Django: the benchmark ran with
`DEBUG = True`, under which Django retains every executed SQL query in `connection.queries` for the
life of the process. That slows request handling and grows memory under sustained load. Step 2
below sets `DJANGO_DEBUG=False`.

Do the whole thing in one sitting if you can — roughly 45 minutes of work plus about two hours of
unattended benchmark time.

---

## Step 0 — Match the region (do this before provisioning)

Supabase project is on `aws-0-eu-west-2` = **AWS London**. Provision the Hostinger VPS in
**London/UK** if offered, otherwise the nearest EU location (Netherlands or Germany). Note the
location you chose — it goes into Section 3.3.

Choose the KVM tier matching the 2 vCPU budget in Section 3.3 (KVM 2 = 2 vCPU / 8 GB). Capture a
screenshot of the plan specification page for Appendix C.

Record the IP and hostname Hostinger assigns (something like `srv123456.hstgr.cloud`).

---

## Step 1 — Prepare the server

SSH in as root using the credentials from the Hostinger panel:

```bash
ssh root@YOUR_VPS_IP
```

Install Docker and Compose:

```bash
apt update && apt install -y docker.io docker-compose-plugin git
systemctl enable --now docker
docker --version && docker compose version
```

---

## Step 2 — Get the code and configure it

```bash
git clone https://github.com/frankkode/Backend-as-a-Service-versus-Self-Hosted-Backends.git
cd Backend-as-a-Service-versus-Self-Hosted-Backends/django-variant
```

Create `django-variant/.env` on the server (it is git-ignored, so it will not have come across):

```bash
cat > .env << 'EOF'
DB_PASSWORD=<pick-a-strong-password>
DATABASE_URL=postgresql://appuser:<same-password>@db:5432/appdb
GUNICORN_WORKERS=5
DJANGO_SECRET_KEY=<generate-one>
DJANGO_DEBUG=False
ALLOWED_HOSTS=YOUR_VPS_IP,srv123456.hstgr.cloud
EOF
```

Generate a secret key with:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

`ALLOWED_HOSTS` and `DJANGO_DEBUG` are read by `config/settings.py`. With `DEBUG=False` and an
unlisted host, Django returns 400 on every request — if that happens, this line is why.

---

## Step 3 — Bring the stack up

```bash
export $(grep -v '^#' .env | xargs)
docker compose up -d --build
docker compose ps          # db, web, nginx should all be Up
docker compose run --rm web python manage.py migrate
```

Seed the same deterministic dataset used everywhere else:

```bash
docker compose run --rm web python manage.py seed_data --scenario small
```

Verify from your Mac, not from the server:

```bash
curl -i http://YOUR_VPS_IP/api/records/
```

A 401 or 403 is success — it means Django is reachable and enforcing auth. A 400 means
`ALLOWED_HOSTS` is wrong. A timeout means Hostinger's firewall is blocking port 80.

---

## Step 4 — Mint a JWT against the VPS

From your Mac, in the repo root:

```bash
set -a; source .env; set +a

curl -s -X POST http://YOUR_VPS_IP/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$TEST_USER_EMAIL\",\"password\":\"$TEST_USER_PASSWORD\"}"
```

Copy the returned access token, then update the root `.env`:

```bash
./scripts/set_env.sh DJANGO_VPS_IP "YOUR_VPS_IP"
./scripts/set_env.sh DJANGO_BASE_URL "http://YOUR_VPS_IP/api"
./scripts/set_env.sh DJANGO_USER_JWT "<the access token>"
```

Also refresh `DJANGO_TEST_ORG_ID` and `DJANGO_OTHER_ORG_RECORD_ID` against the newly seeded data —
the old values refer to your local database and will not exist on the server.

---

## Step 5 — Re-run the benchmark (this is the important one)

Smoke-test both targets first. Run this **from your Mac**, so both variants are measured from the
same client over a real network path:

```bash
set -a; source .env; set +a

k6 run -e BASE_URL="$SUPABASE_URL/rest/v1" -e AUTH_TOKEN="$SUPABASE_USER_JWT" \
  -e APIKEY="$SUPABASE_ANON_KEY" -e ORG_ID="$SUPABASE_TEST_ORG_ID" \
  -e PROFILE=mixed -e VUS=2 -e DURATION=10s shared/k6/workload.js

k6 run -e BASE_URL="$DJANGO_BASE_URL" -e AUTH_TOKEN="$DJANGO_USER_JWT" \
  -e TRAILING_SLASH=true \
  -e PROFILE=mixed -e VUS=2 -e DURATION=10s shared/k6/workload.js
```

Both must show `checks_succeeded: 100.00%` before you continue.

Move the old results aside rather than deleting them — they are still evidence of the localhost run:

```bash
mkdir -p results/localhost_run_archive
mv results/django_*.json results/supabase_*.json results/localhost_run_archive/
```

Then run the full loop from Section 6 of `Platform_Build_Guide.md` (the `for target ... for profile
... for vus` block). It takes about two hours. Leave the machine alone and on mains power — a laptop
throttling or sleeping mid-run corrupts the comparison.

---

## Step 6 — TLS

Point a domain (or use the Hostinger-assigned hostname) at the VPS, then:

```bash
apt install -y certbot
docker compose stop nginx
certbot certonly --standalone -d srv123456.hstgr.cloud
```

Mount the certificates into nginx and add a `listen 443 ssl` server block referencing
`/etc/letsencrypt/live/<host>/fullchain.pem` and `privkey.pem`. Bring nginx back up and confirm:

```bash
curl -I https://srv123456.hstgr.cloud/api/records/
```

This closes criteria rows 46 and 56, currently scored "Not satisfied — TLS not configured".

---

## Step 7 — Measure operational effort

Now that a real server exists, all seven tasks are measurable. On your Mac, in the repo root:

```bash
./scripts/measure_ops_effort.sh start django os_patching
# ssh in, run: apt update && apt upgrade -y, reboot if the kernel changed
./scripts/measure_ops_effort.sh stop django os_patching "11 packages, no reboot"
```

Repeat for `image_update`, `backup_run`, `backup_verify`, `health_check`, `dependency_triage`,
`tls_renewal`. For Supabase, log the platform-managed ones as N/A:

```bash
./scripts/measure_ops_effort.sh na supabase os_patching "platform-managed"
```

Run a second round several days later so each task has n=2 and a standard deviation. Then:

```bash
python3 scripts/aggregate_ops_effort.py
```

---

## Step 8 — What to send back

- `results/*.json` — the new benchmark output (54 files)
- `results/ops_effort_summary.csv`
- The VPS location, KVM tier, vCPU/RAM
- Whether TLS succeeded

Those four things are enough to update Table 5.1, Figure 5.1, Section 5.1, the RQ1 interpretation in
6.1, Table 5.3's operational-effort inputs, Figure D.2, the abstract, and criteria rows 36, 46 and 56.

---

## If you run out of time

Do **Steps 0–5 only**. The benchmark re-run is what protects RQ1; TLS and ops measurement are
worth marks but are additive. If you cannot do even that, tell me — the honest fallback is to
correct Sections 3.3 and 4.2 to state that the Django variant ran locally while Supabase ran
remotely, and to qualify the low-concurrency finding accordingly. That weakens RQ1 but keeps the
thesis truthful, which matters more.
