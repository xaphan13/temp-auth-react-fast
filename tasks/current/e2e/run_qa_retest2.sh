#!/usr/bin/env bash
# QA-прогон фазы 9 (задание: актуализация документации auth + логирование цепочки).
# Воспроизведение: bash tasks/current/e2e/run_qa_phase09.sh
# Порт 8031 выбран свободно; чужой процесс на 8012 не затрагивается.
set -u

BASE=http://127.0.0.1:8031
JAR=/tmp/qa_cookie.cookies
BJAR=/tmp/qa_bearer.cookies
EMAIL="qa_$(date +%s%N | tail -c 9)@example.com"
PASS='Qa-Pass_2026!x'
rm -f "$JAR" "$BJAR"

LOG=/home/max/0_0_26_new_one/temp-auth-react-fast/fastapi-application/log/temp_auth.log
LOG_START=$(wc -l < "$LOG")
echo "LOG_START_LINE=$LOG_START"

show() { echo; echo "### $1"; }

show "0. OpenAPI paths"
curl -s -m 5 "$BASE/openapi.json" | python3 -c "import json,sys; print(len(json.load(sys.stdin)['paths']))"

show "1. register (новый пользователь)"
curl -s -i -X POST "$BASE/auth/register" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" | sed -e 's/\r$//'

show "2. cookie login (ожидаем 204 + Set-Cookie auth + Set-Cookie csrf_token)"
curl -s -i -c "$JAR" -X POST "$BASE/auth/cookie/login" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data "username=$EMAIL&password=$PASS" | sed -e 's/\r$//'

echo; echo "--- cookie jar ---"; cat "$JAR"
CSRF=$(awk '$6=="csrf_token"{print $7}' "$JAR")
echo "CSRF-from-jar-length=${#CSRF}"

show "3. /users/me с cookie (ожидаем 200 + email)"
curl -s -i -b "$JAR" "$BASE/users/me" | sed -e 's/\r$//'

show "4. /api/v1/auth/protected с cookie GET (ожидаем 200 authenticated)"
curl -s -i -b "$JAR" "$BASE/api/v1/auth/protected" | sed -e 's/\r$//'

show "5. CSRF: state-changing БЕЗ X-CSRF-Token -> /auth/cookie/logout (ожидаем 403)"
curl -s -i -b "$JAR" -X POST "$BASE/auth/cookie/logout" | sed -e 's/\r$//'

show "6. CSRF: state-changing БЕЗ X-CSRF-Token -> /auth/account (ожидаем 403)"
curl -s -i -b "$JAR" -X PATCH "$BASE/auth/account" -H 'Content-Type: application/json' \
  -d '{"password":"'"$PASS"'","new_password":"Qa-Other_2026!x"}' | sed -e 's/\r$//'

show "7. mixed cookie+Bearer БЕЗ X-CSRF-Token -> /auth/account (ожидаем 403)"
show "7a. bearer login (ожидаем 200 + JSON access_token)"
BLOGIN=$(curl -s -i -c "$BJAR" -X POST "$BASE/auth/bearer/login" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data "username=$EMAIL&password=$PASS")
echo "$BLOGIN" | sed -e 's/\r$//'
TOKEN=$(echo "$BLOGIN" | tr -d '\r' | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')
echo "TOKEN-length=${#TOKEN}"
echo "--- bearer cookie jar (не должно быть auth-cookie) ---"; cat "$BJAR" 2>/dev/null

echo; show "7b. mixed: cookie + Authorization Bearer без X-CSRF-Token (ожидаем 403)"
curl -s -i -b "$JAR" -H "Authorization: Bearer $TOKEN" -X PATCH "$BASE/auth/account" \
  -H 'Content-Type: application/json' \
  -d '{"password":"'"$PASS"'","new_password":"Qa-Other_2026!x"}' | sed -e 's/\r$//'

show "8. Bearer: /users/me с Authorization (ожидаем 200)"
curl -s -i -H "Authorization: Bearer $TOKEN" "$BASE/users/me" | sed -e 's/\r$//'

show "9. Bearer: /api/v1/auth/protected с Authorization (ожидаем 200 authenticated)"
curl -s -i -H "Authorization: Bearer $TOKEN" "$BASE/api/v1/auth/protected" | sed -e 's/\r$//'

show "10. Bearer logout (ожидаем 204)"
curl -s -i -X POST "$BASE/auth/bearer/logout" -H "Authorization: Bearer $TOKEN" | sed -e 's/\r$//'

show "11. cookie logout С X-CSRF-Token (ожидаем 204 + удаление auth-cookie)"
curl -s -i -b "$JAR" -c "$JAR" -X POST "$BASE/auth/cookie/logout" \
  -H "X-CSRF-Token: $CSRF" | sed -e 's/\r$//'

show "12. protected после logout (ожидаем 401)"
curl -s -i -b "$JAR" "$BASE/api/v1/auth/protected" | sed -e 's/\r$//'

show "13. РЕГРЕСС: /docs (ожидаем 200)"
curl -s -o /dev/null -w "GET /docs -> %{http_code}\n" "$BASE/docs"
show "13b. РЕГРЕСС: анонимный /users/me (ожидаем 401)"
curl -s -i "$BASE/users/me" | sed -e 's/\r$//'

show "13c. РЕГРЕСС: /orders/get_all_orders?params=id"
curl -s -i "$BASE/orders/get_all_orders?params=id" | sed -e 's/\r$//'

show "13d. РЕГРЕСС: /api/v1/dep_examples/single-direct-dependency без foobar"
curl -s -o /dev/null -w "-> %{http_code}\n" "$BASE/api/v1/dep_examples/single-direct-dependency"
show "13e. РЕГРЕСС: /api/v1/dep_examples/single-direct-dependency с foobar"
curl -s -i -H 'foobar: qa-check' "$BASE/api/v1/dep_examples/single-direct-dependency" | sed -e 's/\r$//'

show "14. ЛОГИ: новые строки temp_auth.log после прогона"
tail -n +"$((LOG_START + 1))" "$LOG"

echo
echo "===== END (email=$EMAIL, port=8031) ====="
