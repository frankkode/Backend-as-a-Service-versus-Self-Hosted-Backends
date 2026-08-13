#!/usr/bin/env bash
set -euo pipefail
KEY="$1"; VALUE="$2"
touch .env
if grep -q "^${KEY}=" .env; then
  sed -i.bak "s|^${KEY}=.*|${KEY}=${VALUE}|" .env && rm -f .env.bak
else
  echo "${KEY}=${VALUE}" >> .env
fi
echo "Set ${KEY} in .env"
