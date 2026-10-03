import uvicorn
from api import router_api
from auth_users.csrf import CSRFMiddleware
from auth_users.fastapi_users_obj import fastapi_users
from auth_users.router import router as auth_users_router
from base_dir_path import BASE_DIR
from config_log import logF
from core.config import settings
from core.create_fastapi import create_app
from core.setup_frontend import mount_frontend
from ex_order_product.router_order_one import r_order_one

logF.info("\n\n\n\n'**************************************************************************'")


# load_model_registry()
main_app = create_app(custom_docs_url=False)

# Состав и порядок auth backend'ов (контракт cookie -> bearer, fastapi_users_obj.py).
# Логируем только имена транспортов, без секретов и значений токенов.
logF.info(
    "auth backends order: %s",
    " -> ".join(backend.name for backend in fastapi_users.authenticator.backends),
)

# CSRF-защита cookie-транспорта: Signed Double Submit Cookie (auth_users/csrf.py).
# Starlette middleware глобален для всего приложения; mount_frontend ниже
# остаётся последним маршрутизирующим вызовом.
main_app.add_middleware(
    CSRFMiddleware,
    secret_key=settings.web.secret_key,
    auth_cookie_name=settings.auth_users.cookie_name,
)

main_app.include_router(router_api)
main_app.include_router(r_order_one)
main_app.include_router(auth_users_router)

# React: монтирование /assets + catch-all, строго после роутеров.
# Подробности в setup_frontend.py и docs/13_frontend_spa_module.md.
mount_frontend(main_app)


def main() -> None:
    logF.info(f"Base dir path :\n{BASE_DIR=}")

    uvicorn.run(
        "main:main_app",
        host=settings.run.host,
        port=settings.run.port,
        reload=True,
    )


if __name__ == "__main__":
    main()
