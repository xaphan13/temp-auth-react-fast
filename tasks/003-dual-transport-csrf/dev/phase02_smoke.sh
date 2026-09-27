#!/bin/bash
# Smoke фазы 2: CSRF middleware, порт 8010 (свой сервер, будет погашен отдельно).
set -u
BASE=http://127.0.0.1:8010
DEV=/home/max/0_0_26_new_one/temp-auth-react-fast/tasks/current/dev
JAR=$DEV/phase02_cookies.txt
> "$JAR"

echo "=== S0a: register phase02@example.com ==="
curl -s -o /dev/null -w "register: %{http_code}\n" -X POST $BASE/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"phase02@example.com","password":"Ph2TestPass!9"}'

echo "=== S1: cookie login -> Set-Cookie auth + csrf_token ==="
curl -s -D - -o /dev/null -c "$JAR" -X POST $BASE/auth/cookie/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=phase02@example.com&password=Ph2TestPass!9" \
  | grep -i -E "^(HTTP|set-cookie)"

CSRF=$(grep csrf_token "$JAR" | awk '{print $NF}')
echo "csrf_token from jar: ${CSRF:0:40}..."

echo "=== S2: GET /users/me with cookie (GET, no CSRF needed) ==="
curl -s -b "$JAR" -o /dev/null -w "users/me GET: %{http_code}\n" $BASE/users/me

echo "=== S3: POST /auth/account, no X-CSRF-Token -> 403 ==="
curl -s -b "$JAR" -X POST $BASE/auth/account \
  -H "Content-Type: application/json" -d '{}' \
  -w "\naccount no-header: %{http_code}\n"

echo "=== S4: POST /auth/account, tampered token (valid sig of other nonce) -> 403 ==="
TAMPERED="OtherNonce1111111111111111111111111111111111111111111.$(echo "$CSRF" | cut -d. -f2)"
curl -s -b "$JAR" -X POST $BASE/auth/account \
  -H "Content-Type: application/json" -d '{}' \
  -H "X-CSRF-Token: $TAMPERED" \
  -w "\naccount tampered: %{http_code}\n"

echo "=== S4b: POST /auth/account, invalid signature -> 403 ==="
curl -s -b "$JAR" -X POST $BASE/auth/account \
  -H "Content-Type: application/json" -d '{}' \
  -H "X-CSRF-Token: abc.def" \
  -w "\naccount bad-sig: %{http_code}\n"

echo "=== S5: POST /auth/account, valid X-CSRF-Token -> NOT 403 (reaches endpoint) ==="
curl -s -b "$JAR" -X POST $BASE/auth/account \
  -H "Content-Type: application/json" -d '{}' \
  -H "X-CSRF-Token: $CSRF" \
  -w "\naccount valid: %{http_code}\n"

echo "=== bearer token for mixed scenarios ==="
BTOKEN=$(curl -s -X POST $BASE/auth/bearer/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=phase02@example.com&password=Ph2TestPass!9" \
  | sed 's/.*"access_token":"\([^"]*\)".*/\1/')
echo "bearer token: ${BTOKEN:0:30}..."

echo "=== S6: mixed auth-cookie + Bearer, no X-CSRF-Token -> 403 ==="
curl -s -b "$JAR" -X POST $BASE/auth/account \
  -H "Content-Type: application/json" -d '{}' \
  -H "Authorization: Bearer $BTOKEN" \
  -w "\nmixed no-csrf: %{http_code}\n"

echo "=== S7: mixed auth-cookie + Bearer + valid X-CSRF-Token -> NOT 403 ==="
curl -s -b "$JAR" -X POST $BASE/auth/account \
  -H "Content-Type: application/json" -d '{}' \
  -H "Authorization: Bearer $BTOKEN" \
  -H "X-CSRF-Token: $CSRF" \
  -w "\nmixed valid-csrf: %{http_code}\n"

echo "=== S8: pure Bearer (no auth-cookie), no X-CSRF-Token -> passes middleware ==="
curl -s -X POST $BASE/orders/add_order \
  -H "Authorization: Bearer $BTOKEN" \
  -H "Content-Type: application/json" -d '{}' \
  -w "\npure bearer add_order: %{http_code}\n"

echo "=== S9: POST /orders/add_order with cookie, no X-CSRF-Token -> 403 ==="
curl -s -b "$JAR" -X POST $BASE/orders/add_order \
  -H "Content-Type: application/json" -d '{}' \
  -w "\norders cookie no-csrf: %{http_code}\n"

echo "=== S10: cookie logout with valid X-CSRF-Token -> 204, csrf_token Max-Age=0 ==="
curl -s -D - -o /dev/null -b "$JAR" -c "$JAR" -X POST $BASE/auth/cookie/logout \
  -H "X-CSRF-Token: $CSRF" \
  | grep -i -E "^(HTTP|set-cookie)"

echo "=== S10b: after logout, POST with stale auth cookie + old csrf -> 401 or 403 ==="
curl -s -b "$JAR" -X POST $BASE/auth/account \
  -H "Content-Type: application/json" -d '{}' \
  -H "X-CSRF-Token: $CSRF" \
  -w "\nafter-logout account: %{http_code}\n"

echo "=== S11: bearer logout, no auth-cookie, no X-CSRF-Token -> 204 ==="
curl -s -o /dev/null -X POST $BASE/auth/bearer/logout \
  -H "Authorization: Bearer $BTOKEN" \
  -w "bearer logout: %{http_code}\n"

echo "=== done ==="
