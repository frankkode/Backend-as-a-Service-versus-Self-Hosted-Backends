#!/usr/bin/env bash
# Batched hands-on checks for the criteria catalog (Section 7).
# Read-only / non-destructive — safe to run against your seeded data.
# Run from the repo root: bash criteria_hands_on_checks.sh
set -a; source .env; set +a

hr() { echo; echo "===== $1 ====="; }

hr "1. PAGINATION — list endpoint, unbounded or capped?"
echo "-- Supabase --"
curl -s "$SUPABASE_URL/rest/v1/records?select=id" \
  -H "apikey: $SUPABASE_ANON_KEY" -H "Authorization: Bearer $SUPABASE_USER_JWT" \
  -D - -o /tmp/sb_records.json | grep -iE "content-range|^HTTP"
echo "rows returned: $(jq 'length' /tmp/sb_records.json)"
echo "-- Django --"
curl -s "$DJANGO_BASE_URL/records/" -H "Authorization: Bearer $DJANGO_USER_JWT" \
  -D - -o /tmp/dj_records.json | grep -iE "^HTTP"
echo "response shape (first 200 chars):"; head -c 200 /tmp/dj_records.json; echo

hr "2. SECURITY HEADERS"
echo "-- Supabase --"
curl -sI "$SUPABASE_URL/rest/v1/records?select=id&limit=1" -H "apikey: $SUPABASE_ANON_KEY" -H "Authorization: Bearer $SUPABASE_USER_JWT" | grep -iE "strict-transport|x-content-type|x-frame|content-security"
echo "-- Django --"
curl -sI "$DJANGO_BASE_URL/records/" -H "Authorization: Bearer $DJANGO_USER_JWT" | grep -iE "strict-transport|x-content-type|x-frame|content-security"

hr "3. CORS POLICY"
echo "-- Supabase --"
curl -sI -X OPTIONS "$SUPABASE_URL/rest/v1/records" -H "Origin: https://evil-example.com" -H "Access-Control-Request-Method: GET" | grep -i "access-control-allow-origin"
echo "-- Django --"
curl -sI -X OPTIONS "$DJANGO_BASE_URL/records/" -H "Origin: https://evil-example.com" -H "Access-Control-Request-Method: GET" | grep -i "access-control-allow-origin"

hr "4. RATE LIMITING (20 rapid unauthenticated requests to an auth endpoint)"
echo "-- Supabase (auth token endpoint) --"
for i in $(seq 1 20); do curl -s -o /dev/null -w "%{http_code} " "$SUPABASE_URL/auth/v1/token?grant_type=password" -H "apikey: $SUPABASE_ANON_KEY" -X POST -d '{"email":"nobody@example.com","password":"wrong"}' -H "Content-Type: application/json"; done; echo
echo "-- Django (assumes a login endpoint exists at /api/auth/login/ — adjust path if different) --"
for i in $(seq 1 20); do curl -s -o /dev/null -w "%{http_code} " -X POST "$DJANGO_BASE_URL/auth/login/" -H "Content-Type: application/json" -d '{"email":"nobody@example.com","password":"wrong"}'; done; echo
echo "(look for any 429s in the sequence above — none means no rate limiting observed in this burst)"

hr "5. SQL INJECTION PROBE (classic payload in a filter param — should error safely or return empty, never dump data)"
echo "-- Supabase --"
curl -s "$SUPABASE_URL/rest/v1/records?id=eq.1%27%20OR%20%271%27=%271" -H "apikey: $SUPABASE_ANON_KEY" -H "Authorization: Bearer $SUPABASE_USER_JWT" -w "\nHTTP %{http_code}\n"
echo "-- Django --"
curl -s "$DJANGO_BASE_URL/records/?id=1%27%20OR%20%271%27=%271" -H "Authorization: Bearer $DJANGO_USER_JWT" -w "\nHTTP %{http_code}\n"

hr "6. MALFORMED / INCOMPLETE PAYLOAD REJECTION (missing required field on create)"
echo "-- Supabase --"
curl -s -X POST "$SUPABASE_URL/rest/v1/records" -H "apikey: $SUPABASE_ANON_KEY" -H "Authorization: Bearer $SUPABASE_USER_JWT" -H "Content-Type: application/json" -d '{}' -w "\nHTTP %{http_code}\n"
echo "-- Django --"
curl -s -X POST "$DJANGO_BASE_URL/records/" -H "Authorization: Bearer $DJANGO_USER_JWT" -H "Content-Type: application/json" -d '{}' -w "\nHTTP %{http_code}\n"

hr "7. OVERSIZED PAYLOAD (large string in a text field)"
BIGSTR=$(python3 -c "print('a'*500000)")
echo "-- Supabase --"
curl -s -o /dev/null -w "HTTP %{http_code}\n" -X POST "$SUPABASE_URL/rest/v1/records" -H "apikey: $SUPABASE_ANON_KEY" -H "Authorization: Bearer $SUPABASE_USER_JWT" -H "Content-Type: application/json" -d "{\"org_id\":\"$SUPABASE_TEST_ORG_ID\",\"title\":\"$BIGSTR\"}"
echo "-- Django --"
curl -s -o /dev/null -w "HTTP %{http_code}\n" -X POST "$DJANGO_BASE_URL/records/" -H "Authorization: Bearer $DJANGO_USER_JWT" -H "Content-Type: application/json" -d "{\"title\":\"$BIGSTR\"}"

hr "8. HEALTH / STATUS ENDPOINT"
echo "-- Supabase (implicit — no custom health endpoint expected, platform-managed) --"
curl -s -o /dev/null -w "root: HTTP %{http_code}\n" "$SUPABASE_URL"
echo "-- Django (checking common paths) --"
for path in /health /healthz /api/health /api/health/; do
  echo -n "$path: "; curl -s -o /dev/null -w "HTTP %{http_code}\n" "http://localhost$path"
done

hr "9. LOGOUT / TOKEN INVALIDATION (sign out, then try reusing the old token)"
echo "-- Supabase --"
curl -s -o /dev/null -w "logout call: HTTP %{http_code}\n" -X POST "$SUPABASE_URL/auth/v1/logout" -H "apikey: $SUPABASE_ANON_KEY" -H "Authorization: Bearer $SUPABASE_USER_JWT"
curl -s -o /dev/null -w "reuse old token after logout: HTTP %{http_code}\n" "$SUPABASE_URL/rest/v1/records?select=id&limit=1" -H "apikey: $SUPABASE_ANON_KEY" -H "Authorization: Bearer $SUPABASE_USER_JWT"
echo "-- Django (simplejwt has no server-side logout/blacklist unless explicitly added — expect the token to still work) --"
curl -s -o /dev/null -w "reuse token (no logout endpoint built): HTTP %{http_code}\n" "$DJANGO_BASE_URL/records/" -H "Authorization: Bearer $DJANGO_USER_JWT"

hr "10. DEPENDENCY VULNERABILITY SCAN"
echo "-- Django (pip-audit) --"
pip install pip-audit --break-system-packages -q 2>/dev/null
pip-audit -r django-variant/requirements.txt 2>&1 | tail -20
echo "-- Supabase CLI (npm audit, dev-time tool only) --"
(cd supabase-variant 2>/dev/null && npm audit --omit=dev 2>&1 | tail -10) || echo "no package.json in supabase-variant — likely N/A, no npm deps in the deployed backend itself"

hr "DONE — paste this whole output back"
