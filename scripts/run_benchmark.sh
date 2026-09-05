#!/usr/bin/env bash
# Full benchmark driver — Table 3.1 matrix, 2 variants x 3 profiles x 3 concurrency levels,
# one discarded warm-up plus three timed repetitions each (54 exported result files).
#
# Run from the repo root, ON YOUR OWN MACHINE (never on the VPS -- running it on the VPS would
# put Django back on loopback and reintroduce the network-path confound this run exists to remove).
#
#   ./scripts/run_benchmark.sh
#
# Why this exists rather than the inline loop in Platform_Build_Guide.md: Supabase access tokens
# expire after 60 minutes, and the Supabase half of the matrix takes ~58.5 minutes. This script
# re-mints the Supabase token before every configuration, so token lifetime stops mattering.
# Django tokens last 24h and are minted once.
#
# Safe to re-run: it skips any configuration whose three result files already exist, so if the
# run is interrupted you can just start it again and it resumes.

set -uo pipefail

# Resolve the repo root absolutely and never rely on the caller's working directory or on any
# shell startup hook (direnv/autoenv/BASH_ENV) having left us somewhere sensible. A stray hook
# that cd's elsewhere previously caused this script to source an unrelated project's .env and
# fail with "SUPABASE_URL is not set".
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"
cd "$REPO_ROOT" || { echo "ERROR: cannot cd to $REPO_ROOT"; exit 1; }

ENV_FILE="$REPO_ROOT/.env"
[ -f "$ENV_FILE" ] || { echo "ERROR: no .env at $ENV_FILE"; exit 1; }
set -a; source "$ENV_FILE"; set +a
mkdir -p "$REPO_ROOT/results"

echo "repo root : $REPO_ROOT"
echo "env file  : $ENV_FILE"

need() { [ -n "${!1:-}" ] || { echo "ERROR: $1 is not set in $ENV_FILE"; exit 1; }; }
for v in SUPABASE_URL SUPABASE_ANON_KEY SUPABASE_TEST_ORG_ID TEST_USER_EMAIL TEST_USER_PASSWORD \
         DJANGO_BASE_URL DJANGO_USER_JWT; do need "$v"; done

mint_supabase_token() {
  local tok
  tok=$(curl -s -X POST "${SUPABASE_URL}/auth/v1/token?grant_type=password" \
    -H "apikey: ${SUPABASE_ANON_KEY}" -H "Content-Type: application/json" \
    -d "{\"email\":\"${TEST_USER_EMAIL}\",\"password\":\"${TEST_USER_PASSWORD}\"}" \
    | python3 -c "import sys,json;print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)
  [ -n "$tok" ] || return 1
  printf '%s' "$tok"
}

# Restore the variant's records table to BASELINE_ROWS before every measurement, so each
# repetition starts from an identical dataset. Without this, write-bearing profiles inflate the
# table as the sweep proceeds and later configurations measure a much larger dataset than earlier
# ones -- see scripts/reset_data.py for the full rationale.
BASELINE_ROWS="${BASELINE_ROWS:-2000}"
reset_baseline() {
  local target="$1"
  python3 "$REPO_ROOT/scripts/reset_data.py" --rows "$BASELINE_ROWS" --only "$target" --quiet \
    || { echo "ERROR: reset failed for $target — aborting so no config is measured on a dirty dataset"; exit 1; }
}

run_config() {   # target base_url token profile vus  [extra args...]
  local target="$1" base_url="$2" token="$3" profile="$4" vus="$5"; shift 5
  local extra=("$@")

  local have=0
  for rep in 1 2 3; do
    [ -s "$REPO_ROOT/results/${target}_${profile}_${vus}_rep${rep}.json" ] && have=$((have+1))
  done
  if [ "$have" -eq 3 ]; then
    echo "  [skip] ${target} ${profile} ${vus}VU — already has 3 results"
    return 0
  fi

  reset_baseline "$target"
  echo "  [warm] ${target} ${profile} ${vus}VU"
  k6 run -e BASE_URL="$base_url" -e AUTH_TOKEN="$token" "${extra[@]}" \
    -e PROFILE="$profile" -e VUS="$vus" --duration 30s "$REPO_ROOT/shared/k6/workload.js" >/dev/null 2>&1

  for rep in 1 2 3; do
    reset_baseline "$target"
    echo "  [rep$rep] ${target} ${profile} ${vus}VU"
    k6 run --summary-export="$REPO_ROOT/results/${target}_${profile}_${vus}_rep${rep}.json" \
      -e BASE_URL="$base_url" -e AUTH_TOKEN="$token" "${extra[@]}" \
      -e PROFILE="$profile" -e VUS="$vus" "$REPO_ROOT/shared/k6/workload.js" >/dev/null 2>&1
    if [ ! -s "$REPO_ROOT/results/${target}_${profile}_${vus}_rep${rep}.json" ]; then
      echo "  !! no output for ${target} ${profile} ${vus} rep${rep} — check auth/connectivity"
    fi
  done
}

START=$(date +%s)
echo "=== Supabase (token re-minted per configuration) ==="
for profile in read-heavy write-heavy mixed; do
  for vus in 10 50 200; do
    TOKEN=$(mint_supabase_token) || { echo "ERROR: could not mint Supabase token"; exit 1; }
    run_config supabase "${SUPABASE_URL}/rest/v1" "$TOKEN" "$profile" "$vus" \
      -e "APIKEY=${SUPABASE_ANON_KEY}" -e "ORG_ID=${SUPABASE_TEST_ORG_ID}"
  done
done

echo
echo "=== Django (VPS) ==="
for profile in read-heavy write-heavy mixed; do
  for vus in 10 50 200; do
    run_config django "${DJANGO_BASE_URL}" "${DJANGO_USER_JWT}" "$profile" "$vus" \
      -e "TRAILING_SLASH=true"
  done
done

END=$(date +%s)
echo
echo "=== done in $(( (END-START)/60 )) min ==="
COUNT=$(ls "$REPO_ROOT"/results/*_rep*.json 2>/dev/null | wc -l | tr -d ' ')
echo "result files: ${COUNT} / 54"
if [ "$COUNT" -ne 54 ]; then
  echo "MISSING configurations:"
  for t in supabase django; do for p in read-heavy write-heavy mixed; do for v in 10 50 200; do
    for r in 1 2 3; do
      f="$REPO_ROOT/results/${t}_${p}_${v}_rep${r}.json"
      [ -s "$f" ] || echo "  $f"
    done
  done; done; done
  echo "Re-run this script to fill them in (completed configs are skipped)."
fi
