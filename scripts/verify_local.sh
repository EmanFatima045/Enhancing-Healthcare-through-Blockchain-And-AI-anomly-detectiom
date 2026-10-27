#!/usr/bin/env bash
set -u

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

failed=0
strict=0
if [ "${1:-}" = "--strict" ]; then
  strict=1
fi
run_check() {
  local label="$1"
  shift
  printf '\n==> %s\n' "$label"
  if "$@"; then
    printf 'PASS: %s\n' "$label"
  else
    printf 'FAIL: %s\n' "$label"
    failed=1
  fi
}

run_check "Python syntax" python3 -m compileall -q backend
run_check "Git whitespace" git diff --check

if [ -x frontend/node_modules/.bin/tsc ] && [ -x frontend/node_modules/.bin/vite ]; then
  run_check "Frontend TypeScript" bash -c 'cd frontend && ./node_modules/.bin/tsc -b --pretty false'
  run_check "Frontend production build" bash -c 'cd frontend && ./node_modules/.bin/vite build'
else
  printf '\nSKIP: frontend dependencies are not installed (run npm ci in frontend/)\n'
  [ "$strict" -eq 1 ] && failed=1
fi

if [ -x .venv/bin/python ] && .venv/bin/python -c 'import fastapi, sqlalchemy, pytest, web3' 2>/dev/null; then
  run_check "Backend acceptance tests" .venv/bin/python -m pytest -q backend/tests/test_acceptance.py
else
  printf 'SKIP: backend dependencies are not installed (run .venv/bin/pip install -r backend/requirements-dev.txt)\n'
  [ "$strict" -eq 1 ] && failed=1
fi

if [ -x blockchain/node_modules/.bin/hardhat ]; then
  run_check "Solidity tests" bash -c 'cd blockchain && ./node_modules/.bin/hardhat test'
else
  printf 'SKIP: blockchain dependencies are not installed (run npm ci in blockchain/)\n'
  [ "$strict" -eq 1 ] && failed=1
fi

if [ "$failed" -ne 0 ]; then
  printf '\nVerification completed with failures.\n'
  exit 1
fi
printf '\nVerification completed.\n'
