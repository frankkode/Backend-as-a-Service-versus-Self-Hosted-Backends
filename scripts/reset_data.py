#!/usr/bin/env python3
"""
Reset both variants' `records` table to an identical fixed baseline before a benchmark repetition.

Why this exists
---------------
The benchmark's write-bearing profiles insert rows as they run. With the `small` seed (50 rows) a
single sweep added ~27,000 rows, so later configurations queried a table three orders of magnitude
larger than earlier ones -- and, because neither variant paginates `GET /records`, read latency
tracks table size directly. Configurations were therefore not comparable with each other, and the
faster variant penalised itself by writing more rows.

This script restores a known row count on both sides before every repetition, so each measurement
starts from the same dataset. Organisations and user accounts are left untouched (recreating auth
users would collide on duplicate emails, and the org/user distribution is what RLS and the DRF
permission classes filter on -- that must stay stable).

Usage
-----
    python3 scripts/reset_data.py --rows 2000            # both variants
    python3 scripts/reset_data.py --rows 2000 --only supabase
    python3 scripts/reset_data.py --verify               # just report current counts

Requires in .env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, DJANGO_VPS_IP,
and passwordless SSH to the VPS (see DEPLOY_AND_MEASURE.md).
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REMOTE_DIR = "~/Backend-as-a-Service-versus-Self-Hosted-Backends/django-variant"


def load_env():
    env = {}
    path = os.path.join(REPO, ".env")
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def sb_request(env, method, path, body=None, extra_headers=None):
    """Talk to PostgREST via curl.

    Deliberately not urllib: python.org macOS builds ship their own CA bundle and commonly fail
    with CERTIFICATE_VERIFY_FAILED against Supabase, while curl uses the system trust store and
    works. Shelling out removes that whole class of environment problem.
    """
    key = env["SUPABASE_SERVICE_ROLE_KEY"]
    url = f"{env['SUPABASE_URL']}/rest/v1/{path}"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)

    with tempfile.TemporaryDirectory() as td:
        hdr_path = os.path.join(td, "h")
        body_path = os.path.join(td, "b")
        cmd = ["curl", "-sS", "-X", method, url, "-D", hdr_path, "-o", body_path,
               "--max-time", "180", "-w", "%{http_code}"]
        for k, v in headers.items():
            cmd += ["-H", f"{k}: {v}"]
        if body is not None:
            payload_path = os.path.join(td, "p")
            with open(payload_path, "w") as f:
                json.dump(body, f)
            cmd += ["--data-binary", f"@{payload_path}"]

        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            sys.exit(f"curl failed for {method} {path}: {p.stderr.strip()[:300]}")
        code = int(p.stdout.strip() or 0)
        raw = open(body_path).read() if os.path.exists(body_path) else ""
        if code >= 400:
            sys.exit(f"Supabase {method} {path} failed: HTTP {code} {raw[:300]}")

        hdrs = {}
        if os.path.exists(hdr_path):
            for line in open(hdr_path, errors="replace"):
                if ":" in line:
                    k, v = line.split(":", 1)
                    hdrs[k.strip().lower()] = v.strip()
        return hdrs, (json.loads(raw) if raw.strip() else None)


def sb_count(env):
    headers, _ = sb_request(
        env, "GET", "records?select=id",
        extra_headers={"Prefer": "count=exact", "Range": "0-0"},
    )
    cr = headers.get("content-range", "")
    return int(cr.split("/")[-1]) if "/" in cr else -1


def sb_reset(env, rows):
    # PostgREST refuses an unfiltered DELETE; `id=not.is.null` matches every row.
    sb_request(env, "DELETE", "records?id=not.is.null")

    _, profiles = sb_request(env, "GET", "profiles?select=id,org_id")
    if not profiles:
        sys.exit("Supabase: no profiles found -- reseed orgs/users first.")

    payload = [
        {
            "org_id": profiles[i % len(profiles)]["org_id"],
            "created_by": profiles[i % len(profiles)]["id"],
            "status": "open",
            "payload": {"seq": i},
        }
        for i in range(rows)
    ]
    # chunked so a single request never gets too large
    for i in range(0, len(payload), 500):
        sb_request(env, "POST", "records", payload[i:i + 500],
                   extra_headers={"Prefer": "return=minimal"})
    return sb_count(env)


DJANGO_SQL = """
DELETE FROM core_record;
INSERT INTO core_record (id, org_id, created_by_id, status, payload, updated_at)
SELECT gen_random_uuid(), u.org_id, u.id, 'open',
       json_build_object('seq', s.i)::jsonb, now()
FROM generate_series(1, {rows}) AS s(i)
JOIN LATERAL (
  SELECT id, org_id FROM core_useraccount
  ORDER BY id OFFSET (s.i % (SELECT GREATEST(count(*),1) FROM core_useraccount)) LIMIT 1
) u ON true;
SELECT count(*) FROM core_record;
"""


def dj_ssh(env, sql):
    host = f"root@{env['DJANGO_VPS_IP']}"
    remote = (
        f"cd {REMOTE_DIR} && docker compose exec -T db "
        f"psql -U appuser -d appdb -t -A -c \"{sql}\""
    )
    cmd = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new"]
    # Name the private key explicitly and ignore ~/.ssh/config. A config whose IdentityFile
    # points at the .pub file makes ssh reject it as a "private key with bad permissions",
    # which is a confusing failure that has nothing to do with the server.
    key = os.environ.get("SSH_KEY") or os.path.expanduser("~/.ssh/id_ed25519")
    if os.path.exists(key):
        cmd += ["-F", "/dev/null", "-o", "IdentitiesOnly=yes", "-i", key]
    cmd += [host, remote]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if p.returncode != 0:
        sys.exit(
            "SSH/psql failed. Passwordless SSH is required for automated resets.\n"
            "Set it up once with:\n"
            "  ssh-keygen -t ed25519 -N '' -f ~/.ssh/id_ed25519   # if you have no key\n"
            f"  ssh-copy-id root@{env['DJANGO_VPS_IP']}\n\n"
            f"stderr: {p.stderr.strip()[:400]}"
        )
    return p.stdout.strip()


def dj_count(env):
    out = dj_ssh(env, "SELECT count(*) FROM core_record;")
    for line in reversed(out.splitlines()):
        if line.strip().isdigit():
            return int(line.strip())
    return -1


def dj_reset(env, rows):
    sql = DJANGO_SQL.format(rows=rows).replace("\n", " ").strip()
    out = dj_ssh(env, sql)
    for line in reversed(out.splitlines()):
        if line.strip().isdigit():
            return int(line.strip())
    return -1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=2000,
                    help="baseline record count per variant (default 2000 = 'growing')")
    ap.add_argument("--only", choices=["supabase", "django"])
    ap.add_argument("--verify", action="store_true", help="report counts, change nothing")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    env = load_env()
    for k in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "DJANGO_VPS_IP"):
        if not env.get(k):
            sys.exit(f"ERROR: {k} missing from .env")

    if args.verify:
        print(f"supabase records: {sb_count(env)}")
        print(f"django   records: {dj_count(env)}")
        return

    results = {}
    if args.only != "django":
        results["supabase"] = sb_reset(env, args.rows)
    if args.only != "supabase":
        results["django"] = dj_reset(env, args.rows)

    if not args.quiet:
        print("  reset ->", "  ".join(f"{k}={v}" for k, v in results.items()))

    for name, got in results.items():
        if got != args.rows:
            sys.exit(f"ERROR: {name} has {got} rows after reset, expected {args.rows}")


if __name__ == "__main__":
    main()
