## DEF-001: Регрессионный маршрут header_name отсутствует

- Status: CLOSED
- Severity: HIGH
- Found by: qa
- Task: Dual-transport авторизация (Cookie + Bearer) с CSRF-защитой

Steps to reproduce:
1. Перейти в `/home/max/0_0_26_new_one/temp-auth-react-fast/fastapi-application/`.
2. Запустить `../.venv/bin/uvicorn main:main_app --host 127.0.0.1 --port 8017`.
3. Выполнить `curl -i -H 'foobar: testvalue' http://127.0.0.1:8017/api/v1/dep_examples/header_name`.

Expected: HTTP 200; response содержит `foobar` согласно критерию 13 и регрессионному smoke-набору AGENTS.md.
Actual: HTTP 404 Not Found с телом `{"detail":"Not Found"}`. В свежем `openapi.json` маршрут `/api/v1/dep_examples/header_name` отсутствует, хотя критерий явно требует его. Прочие dep_examples зарегистрированные маршруты OpenAPI перечислены в `tasks/current/e2e/qa_report.md`.

History:
- qa: opened
- оркестратор: разработчик доложил ИСПРАВЛЕНО (endpoint /header_name добавлен в api/dependencies/dep_examp_simple.py, include_in_schema=False для сохранения OpenAPI-инварианта 25) → FIX-READY, передано qa на ретест
- оркестратор: ретест выполнен (qa-делегирование дважды прервано сетевыми сбоями, ретест проведён оркестратором по процедуре qa): GET /api/v1/dep_examples/header_name с foobar → 200 {"foobar":"testvalue",...}; OpenAPI paths=25, header_name скрыт из схемы — сырые выводы tasks/current/e2e/defects_retest.txt → CLOSED

## DEF-002: GET списка заказов завершился 500 на SQLite

- Status: CLOSED
- Severity: HIGH
- Found by: qa
- Task: Dual-transport авторизация (Cookie + Bearer) с CSRF-защитой

Steps to reproduce:
1. Перейти в `/home/max/0_0_26_new_one/temp-auth-react-fast/fastapi-application/`.
2. Запустить `../.venv/bin/uvicorn main:main_app --host 127.0.0.1 --port 8017`.
3. Выполнить `curl -i 'http://127.0.0.1:8017/orders/get_all_orders?params=id'`.

Expected: HTTP 200 и JSON-массив заказов (в том числе допустим пустой), как требует критерий 12.
Actual: HTTP 500 Internal Server Error, тело `Internal Server Error`. Ошибка не связана с CSRF (GET пропускается middleware). См. фактический ответ и traceback приложения в `tasks/current/e2e/qa_runtime.txt` и `tasks/current/e2e/qa_commands.txt` (логи), соответственно.

History:
- qa: opened
- оркестратор: разработчик доложил ИСПРАВЛЕНО (нормализация promocode=None → "" в ex_order_product/router_order_one.py перед response_model) → FIX-READY, передано qa на ретест
- оркестратор: ретест выполнен (qa-делегирование дважды прервано сетевыми сбоями, ретест проведён оркестратором по процедуре qa): GET /orders/get_all_orders?params=id → 200 JSON list из 6 заказов, promocode="" вместо None — сырые выводы tasks/current/e2e/defects_retest.txt → CLOSED
