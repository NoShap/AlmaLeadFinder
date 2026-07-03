#!/bin/bash
# E2E against the running docker stack (`docker compose up --build` first):
#   1. API contract   — backend/tests/e2e (pytest -m e2e)
#   2. Browser flows  — frontend/e2e (Playwright)
set -e
cd "$(dirname "$0")/.."

echo "== API e2e (pytest -m e2e) =="
(cd backend && ${PYTEST:-pytest} -m e2e -v)

echo
echo "== Browser e2e (Playwright) =="
(cd frontend && npx playwright test)

echo
echo "== E2E PASSED =="
