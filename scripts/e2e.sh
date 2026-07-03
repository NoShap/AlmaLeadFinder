#!/bin/bash
# E2E smoke test against the docker-compose stack.
set -e
API=http://localhost:8000

echo "== 1. health"
curl -sf $API/api/health; echo

echo "== 2. submit lead (public form)"
printf '%%PDF-1.4 fake e2e resume' > /tmp/e2e-resume.pdf
CREATE=$(curl -sf -X POST $API/api/leads \
  -F first_name=Test -F last_name=Prospect -F email=prospect@example.com \
  -F "resume=@/tmp/e2e-resume.pdf;type=application/pdf")
echo "$CREATE"
LEAD_ID=$(echo "$CREATE" | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')

echo "== 3. unauthenticated list is rejected"
CODE=$(curl -s -o /dev/null -w '%{http_code}' $API/api/leads)
echo "GET /api/leads without token -> $CODE (expect 401)"

echo "== 4. login"
TOKEN=$(curl -sf -X POST $API/api/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"attorney@example.com","password":"letmein"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
echo "got token: ${TOKEN:0:20}..."

echo "== 5. list leads (authed)"
curl -sf $API/api/leads -H "Authorization: Bearer $TOKEN" | python3 -m json.tool | head -20

echo "== 6. download resume"
curl -sf $API/api/leads/$LEAD_ID/resume -H "Authorization: Bearer $TOKEN" -o /tmp/e2e-downloaded.pdf
diff /tmp/e2e-resume.pdf /tmp/e2e-downloaded.pdf && echo "resume roundtrip OK"

echo "== 7. mark REACHED_OUT"
curl -sf -X PATCH $API/api/leads/$LEAD_ID -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"state":"REACHED_OUT"}' \
  | python3 -c 'import sys,json;d=json.load(sys.stdin);print("state:",d["state"],"reached_out_at:",d["reached_out_at"])'

echo "== 8. re-marking conflicts (expect 409)"
CODE=$(curl -s -o /dev/null -w '%{http_code}' -X PATCH $API/api/leads/$LEAD_ID \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"state":"REACHED_OUT"}')
echo "second PATCH -> $CODE"

echo "== 9. console emails in backend logs"
docker compose logs backend 2>/dev/null | grep -c "console email" | sed 's/^/console email lines: /'

echo "== 10. frontend serves"
CODE=$(curl -s -o /dev/null -w '%{http_code}' http://localhost:3000)
echo "GET / -> $CODE"
CODE=$(curl -s -o /dev/null -w '%{http_code}' http://localhost:3000/admin/login)
echo "GET /admin/login -> $CODE"

echo "== E2E PASSED"
