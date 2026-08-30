#!/usr/bin/env bash
# One-time repo cleanup — run from the repo root (baas-vs-selfhosted/).
# Delete this script once you've run it; it's not meant to stay in the repo.
#
# Phase 1: stop tracking junk that's already committed, commit the real evidence files that
#          were generated locally but never pushed, push normally.
# Phase 2: rewrite history to remove the two things that were actually exposed publicly —
#          supabase/.temp (leaks your live project ref, org id, pooler host) and the old
#          hardcoded Django SECRET_KEY. This force-rewrites the remote; anyone who already
#          cloned needs to re-clone afterward. Run Phase 2 only when you're ready for that.

set -euo pipefail
cd "$(dirname "$0")/.."

echo "== Phase 1: untrack junk, commit real results, push =="

git rm -r --cached --ignore-unmatch \
  .venv \
  django-variant/.venv \
  .DS_Store \
  supabase/.temp \
  django-variant/.coverage \
  $(git ls-files | grep -E '__pycache__/|\.pyc$' || true)

git add -A
git status --short

git commit -m "Repo cleanup: untrack .venv/__pycache__/.DS_Store/supabase .temp, publish raw benchmark results and criteria catalog, harden settings.py secrets via env vars, add README with diagrams/results charts, LICENSE, .env.example"
git push

echo
echo "== Phase 1 done. Verify the repo on GitHub looks right before continuing. =="
echo "== Phase 2 (history rewrite) is NOT run automatically — see the commands below. =="
cat <<'EOF'

Phase 2 — only once you're ready (this force-rewrites remote history):

  pip install git-filter-repo --break-system-packages   # or: brew install git-filter-repo

  # Remove .venv and the leaked Supabase project info from every past commit:
  git filter-repo --force \
    --path .venv --path django-variant/.venv --path supabase/.temp --invert-paths

  # Scrub the old hardcoded Django SECRET_KEY value from history:
  echo 'django-insecure-$vs(g=$fx(c!&m00k2^%mff$!kf5v2jae9r3u=@i-72w)65koa==>***REMOVED***' > /tmp/replace-rules.txt
  git filter-repo --force --replace-text /tmp/replace-rules.txt

  # filter-repo removes the 'origin' remote as a safety measure — re-add it:
  git remote add origin https://github.com/frankkode/Backend-as-a-Service-versus-Self-Hosted-Backends.git
  git push --force --all
  git push --force --tags

  # Afterward, rotate anything that was genuinely a live credential. The pooler-url that leaked
  # had no password embedded, and the old SECRET_KEY was only ever used for local benchmarking,
  # so practical exposure is low — but regenerating your Supabase project's service-role key and
  # setting a fresh DJANGO_SECRET_KEY (see .env.example) costs nothing and closes the loop.
EOF
