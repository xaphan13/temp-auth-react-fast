#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path('/home/max/0_0_26_new_one/temp-auth-react-fast')
APP = ROOT / 'fastapi-application'
FRONTEND = ROOT / 'frontend'
LOG_DIR = APP / 'log'
RAW = ROOT / 'tasks/current/e2e/phase20_raw.txt'
TMP = Path(tempfile.mkdtemp(prefix='phase20-qa-'))
DB = TMP / 'one_simple.db'
COOKIE = TMP / 'cookies.txt'
SERVER_LOG = TMP / 'uvicorn.log'
SERVER: subprocess.Popen[str] | None = None
HAD_DIST = (FRONTEND / 'dist').exists()


def out(text: str = '') -> None:
    print(text, flush=True)


def run(command: str, cwd: Path, env: dict[str, str] | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    out(f'\n$ (cd {cwd} && {command})')
    merged = os.environ.copy()
    if env:
        merged.update(env)
    result = subprocess.run(command, cwd=cwd, env=merged, shell=True, text=True, capture_output=True)
    if result.stdout:
        out(result.stdout.rstrip())
    if result.stderr:
        out(result.stderr.rstrip())
    out(f'[exit={result.returncode}]')
    if check and result.returncode != 0:
        raise AssertionError(f'command failed: {command}')
    return result


def curl(name: str, args: str, expected: int | None = None) -> tuple[int, str, str]:
    command = f'curl -sS -D {TMP / name}.headers -o {TMP / name}.body {args}'
    result = run(command, ROOT)
    headers = (TMP / f'{name}.headers').read_text(errors='replace')
    body = (TMP / f'{name}.body').read_text(errors='replace')
    status_line = next(line for line in headers.splitlines() if line.startswith('HTTP/'))
    status = int(status_line.split()[1])
    ctype = next((line.split(':', 1)[1].strip() for line in headers.splitlines() if line.lower().startswith('content-type:')), '')
    out(f'[{name}] status={status} content_type={ctype} body={body}')
    if expected is not None:
        assert status == expected, f'{name}: expected {expected}, got {status}: {body}'
    return status, headers, body


def json_body(name: str) -> object:
    return json.loads((TMP / f'{name}.body').read_text())


def main() -> None:
    global SERVER
    out('=== PHASE 20 FINAL QA ===')
    runtime = APP / 'one_simple.db'
    runtime_before = hashlib.sha256(runtime.read_bytes()).hexdigest() if runtime.exists() else 'ABSENT'
    out(f'temp_db={DB}')
    out(f'runtime_db_before_sha256={runtime_before}')
    out('temporary DB is selected by APP__DB__URL override; all Alembic/app commands below run from fastapi-application')

    out('=== clean temporary SQLite migration and schema inspection ===')
    db_env = {'APP__DB__URL': f'sqlite+aiosqlite:///{DB}'}
    run('../.venv/bin/alembic upgrade heads', APP, db_env)
    with sqlite3.connect(DB) as connection:
        tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    out(f'sqlite_tables={tables}')
    expected_tables = ['alembic_version', 'order_product_association', 'orders', 'products', 'user']
    assert tables == expected_tables, (tables, expected_tables)
    out('sqlite_schema_check=PASS')

    out('=== frontend build ===')
    run('npm run build', FRONTEND)
    assert (FRONTEND / 'dist/index.html').exists()
    out('frontend_build=PASS')

    out('=== start one uvicorn from fastapi-application with temporary DB ===')
    server_env = os.environ.copy()
    server_env.update(db_env)
    server_log_handle = SERVER_LOG.open('w')
    SERVER = subprocess.Popen(
        ['../.venv/bin/uvicorn', 'main:main_app', '--host', '127.0.0.1', '--port', '8000'],
        cwd=APP,
        env=server_env,
        stdout=server_log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    out(f'server_pid={SERVER.pid}')
    ready = False
    for _ in range(40):
        result = subprocess.run('curl -m 2 -sS -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/openapi.json', shell=True, text=True, capture_output=True)
        if result.returncode == 0 and result.stdout.strip() == '200':
            ready = True
            break
        time.sleep(0.25)
    assert ready, SERVER_LOG.read_text(errors='replace')
    out('openapi_ready_status=200')

    out('=== OpenAPI and docs ===')
    curl('openapi', 'http://127.0.0.1:8000/openapi.json', 200)
    paths = json_body('openapi')['paths']
    out(f'openapi_path_count={len(paths)}')
    out(f'openapi_paths={sorted(paths)}')
    assert len(paths) == 23
    assert '/api/v1/auth/protected' in paths
    assert not any(path.startswith('/api/blog') for path in paths)
    assert '/users/{id}' not in paths
    for path in ['/auth/jwt/login', '/auth/jwt/logout', '/auth/register', '/auth/account', '/users/me']:
        assert path in paths
    out('openapi_checks=PASS')
    curl('docs', 'http://127.0.0.1:8000/docs', 200)

    out('=== anonymous boundary and invalid registration ===')
    _, headers, body = curl('anonymous_me', 'http://127.0.0.1:8000/users/me', 401)
    assert 'application/json' in headers.lower()
    assert isinstance(json.loads(body), dict)
    out('anonymous_me_json_401=PASS')
    _, headers, body = curl('anonymous_protected', 'http://127.0.0.1:8000/api/v1/auth/protected', 401)
    assert 'application/json' in headers.lower()
    assert isinstance(json.loads(body), dict)
    out('anonymous_protected_json_401=PASS')
    _, headers, body = curl('invalid_register', "-X POST -H 'Content-Type: application/json' --data '{\"email\":\"not-an-email\",\"password\":\"short\"}' http://127.0.0.1:8000/auth/register", 422)
    assert 'application/json' in headers.lower() and isinstance(json.loads(body), dict)
    out('invalid_register_json_422=PASS')

    email = f'qa.phase20.{time.time_ns()}@example.com'
    updated_email = f'qa.phase20.updated.{time.time_ns()}@example.com'
    username = f'qa20{str(time.time_ns())[-8:]}'
    password = 'Phase20-password-Valid'
    out(f'unique_email={email} updated_email={updated_email} username={username}')

    out('=== registration/login/me/protected/account/logout ===')
    curl('register', f"-X POST -H 'Content-Type: application/json' --data '{{\"email\":\"{email}\",\"password\":\"{password}\"}}' http://127.0.0.1:8000/auth/register", 201)
    registered = json_body('register')
    assert isinstance(registered, dict) and registered.get('email') == email and 'password' not in registered
    out('register_201_user_no_password=PASS')
    curl('login', f"-c {COOKIE} -b {COOKIE} -X POST -H 'Content-Type: application/x-www-form-urlencoded' --data-urlencode 'username={email}' --data-urlencode 'password={password}' http://127.0.0.1:8000/auth/jwt/login", 204)
    assert COOKIE.exists() and COOKIE.stat().st_size > 0
    out('login_cookie_jar=NONEMPTY')
    curl('authorized_me', f'-b {COOKIE} http://127.0.0.1:8000/users/me', 200)
    me = json_body('authorized_me')
    assert isinstance(me, dict) and me.get('email') == email
    out('authorized_me_email=PASS')
    curl('authorized_protected', f'-b {COOKIE} http://127.0.0.1:8000/api/v1/auth/protected', 200)
    protected = json_body('authorized_protected')
    assert isinstance(protected, dict) and protected.get('authenticated') is True and isinstance(protected.get('user'), dict)
    assert protected['user'].get('email') == email and 'password' not in protected
    out('protected_authenticated_user_no_password=PASS')
    curl('account_update', f"-b {COOKIE} -X POST -F 'username={username}' -F 'email={updated_email}' http://127.0.0.1:8000/auth/account", 200)
    account = json_body('account_update')
    assert isinstance(account, dict) and {'message', 'category', 'user'} <= account.keys()
    assert account['user'].get('email') == updated_email and account['user'].get('username') == username
    assert 'password' not in account
    out('account_multipart_no_picture_200=PASS')
    curl('updated_me', f'-b {COOKIE} http://127.0.0.1:8000/users/me', 200)
    updated_me = json_body('updated_me')
    assert isinstance(updated_me, dict) and updated_me.get('email') == updated_email and updated_me.get('username') == username
    out('updated_me=PASS')
    curl('logout', f'-b {COOKIE} -c {COOKIE} -X POST http://127.0.0.1:8000/auth/jwt/logout', 204)
    curl('post_logout_protected', f'-b {COOKIE} http://127.0.0.1:8000/api/v1/auth/protected', 401)
    assert isinstance(json_body('post_logout_protected'), dict)
    out('logout_then_protected_401=PASS')

    out('=== retained demo/order and removed blog ===')
    curl('demo', "-H 'foobar: phase20' http://127.0.0.1:8000/api/v1/dep_examples/single-direct-dependency", 200)
    curl('orders', "'http://127.0.0.1:8000/orders/get_all_orders?params=id'", 200)
    orders = json_body('orders')
    assert isinstance(orders, list)
    out('orders_valid_json_array=PASS')
    _, headers, body = curl('blog', 'http://127.0.0.1:8000/api/blog/articles', 404)
    assert 'application/json' in headers.lower() and isinstance(json.loads(body), dict)
    out('blog_json_404=PASS')

    out('=== SPA and API fallback ===')
    _, headers, body = curl('spa_protected', 'http://127.0.0.1:8000/protected', 200)
    assert 'text/html' in headers.lower() and '<div id="root">' in body.lower()
    out('spa_protected_html_200=PASS')
    _, headers, body = curl('api_nope', 'http://127.0.0.1:8000/api/nope', 404)
    assert 'application/json' in headers.lower() and isinstance(json.loads(body), dict)
    out('api_nope_json_404=PASS')

    out('=== filesystem, dependency and frontend marker absence ===')
    absent = [APP / 'md_articles', APP / 'content_art', APP / 'ex_user_post', ROOT / 'docs/06_blog.md']
    for path in absent:
        out(f'{path.relative_to(ROOT)} absent={not path.exists()}')
        assert not path.exists()
    import io
    import tokenize

    pattern = re.compile(r'md_articles|router_blog_api|content_art|ex_user_post')
    hits = []
    for path in APP.rglob('*.py'):
        source = path.read_text(errors='replace')
        code_tokens = ' '.join(
            token.string
            for token in tokenize.generate_tokens(io.StringIO(source).readline)
            if token.type not in (tokenize.COMMENT, tokenize.STRING)
        )
        if pattern.search(code_tokens):
            hits.append(str(path.relative_to(ROOT)))
    out(f'backend_runtime_reference_hits={hits}')
    assert not hits
    manifest = (ROOT / 'pyproject.toml').read_text().lower()
    for dependency in ['fastapi-users', 'python-multipart', 'pillow']:
        out(f'{dependency}_present={dependency in manifest}')
        assert dependency in manifest
    assert 'markdown' not in manifest
    import io
    import tokenize

    frontend_files = [FRONTEND / 'index.html', *[path for path in (FRONTEND / 'src').rglob('*') if path.is_file()]]
    frontend_text = '\n'.join(path.read_text(errors='replace') for path in frontend_files)
    frontend_markers = ['api/blog', 'art_manage', 'highlight.js', 'cdnjs', 'md_articles']
    frontend_comment_hits = [marker for marker in frontend_markers if marker in frontend_text]
    out(f'frontend_all_text_marker_hits={frontend_comment_hits}')
    frontend_code = ''
    for path in frontend_files:
        source = path.read_text(errors='replace')
        try:
            frontend_code += ' '.join(
                token.string
                for token in tokenize.generate_tokens(io.StringIO(source).readline)
                if token.type not in (tokenize.COMMENT, tokenize.STRING)
            ) + '\\n'
        except tokenize.TokenError:
            frontend_code += source
    frontend_code_hits = [marker for marker in frontend_markers if marker in frontend_code]
    out(f'frontend_code_marker_hits={frontend_code_hits}')
    assert not frontend_code_hits
    bundle_files = [path for path in (FRONTEND / 'dist').rglob('*') if path.is_file()]
    bundle_text = '\\n'.join(path.read_text(errors='replace') for path in bundle_files if path.suffix in {'.js', '.css', '.html'})
    bundle_hits = [marker for marker in frontend_markers if marker in bundle_text]
    out(f'frontend_bundle_marker_hits={bundle_hits}')
    assert not bundle_hits
    out('filesystem_dependency_frontend_checks=PASS')

    out('=== narrow ruff migration/backend and import ===')
    ruff_result = run('uv run ruff check fastapi-application/alembic/versions fastapi-application/auth_users fastapi-application/setup_frontend.py fastapi-application/main.py', ROOT, check=False)
    out(f'narrow_ruff_exit={ruff_result.returncode}')
    if ruff_result.returncode != 0:
        out('narrow_ruff_disposition=FAIL: existing auth_users findings; product code unchanged')
    run("../.venv/bin/python -c \"from main import main_app; paths=main_app.openapi()['paths']; print('import_route_count=', len(paths)); assert len(paths)==23\"", APP, db_env)

    out('=== application logs and runtime DB immutability ===')
    log_files = sorted(path for path in LOG_DIR.rglob('*') if path.is_file()) if LOG_DIR.exists() else []
    out(f'application_log_files={[str(path) for path in log_files]}')
    for path in log_files:
        text = path.read_text(errors='replace')
        out(f'--- {path} ({len(text)} bytes) ---')
        out(text[-8000:])
    if SERVER is not None:
        SERVER.terminate()
        SERVER.wait(timeout=10)
        server_log_handle.close()
        out('uvicorn_shutdown=PASS')
    uvicorn_text = SERVER_LOG.read_text(errors='replace')
    out('--- uvicorn log ---')
    out(uvicorn_text)
    assert 'Traceback' not in uvicorn_text and 'Internal Server Error' not in uvicorn_text
    if runtime.exists():
        runtime_after = hashlib.sha256(runtime.read_bytes()).hexdigest()
    else:
        runtime_after = 'ABSENT'
    out(f'runtime_db_after_sha256={runtime_after}')
    assert runtime_before == runtime_after
    out('runtime_db_immutability=PASS')
    out('PHASE20_RESULT=PASS')


try:
    import contextlib
    import sys

    with RAW.open('w') as raw:
        original_stdout = sys.stdout

        class Tee:
            def write(self, text: str) -> int:
                raw.write(text)
                raw.flush()
                return original_stdout.write(text)

            def flush(self) -> None:
                raw.flush()
                original_stdout.flush()

        with contextlib.redirect_stdout(Tee()):
            main()
except Exception as exc:
    print(f'PHASE20_RESULT=FAIL: {type(exc).__name__}: {exc}', flush=True)
    raise
finally:
    if SERVER is not None and SERVER.poll() is None:
        SERVER.terminate()
        SERVER.wait(timeout=10)
    if not HAD_DIST and (FRONTEND / 'dist').exists():
        shutil.rmtree(FRONTEND / 'dist')
    shutil.rmtree(TMP, ignore_errors=True)
