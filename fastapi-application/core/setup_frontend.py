from base_dir_path import BASE_DIR
from config_log import logF
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.routing import Route

FRONTEND_DIST = BASE_DIR.parent / "frontend" / "dist"
ASSETS_DIR = FRONTEND_DIST / "assets"
INDEX_HTML = FRONTEND_DIST / "index.html"


async def spa_fallback(request: Request) -> FileResponse | JSONResponse:
    """Отдаёт SPA для client-side маршрутов и JSON 404 для API-путей."""
    path = request.url.path
    if path == "/api" or path.startswith("/api/"):
        return JSONResponse(status_code=404, content={"detail": "Not Found"})

    if not INDEX_HTML.is_file():
        logF.warning(
            "SPA: frontend/dist/index.html не найден — "
            "соберите фронт командой 'cd frontend && npm run build'"
        )
        return JSONResponse(
            status_code=404,
            content={"detail": "Frontend не собран: выполните npm run build в frontend/"},
        )

    return FileResponse(INDEX_HTML)


def mount_frontend(app: FastAPI) -> None:
    """Подключает Vite assets и последний SPA catch-all."""
    app.mount(
        "/assets",
        StaticFiles(directory=ASSETS_DIR, check_dir=False),
        name="spa_assets",
    )
    app.router.routes.append(Route("/{full_path:path}", spa_fallback, methods=["GET"]))

    logF.info(f"SPA подключена: index={INDEX_HTML}, assets={ASSETS_DIR}")
