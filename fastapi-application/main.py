import uvicorn
from api import router_api
from auth_users import router as auth_users_router
from base_dir_path import BASE_DIR
from config_log import logF
from core.config import settings
from create_fastapi import create_app
from ex_order_product.router_order_one import r_order_one
from md_articles.setup_frontend import (
    include_router_api_frontend,
    mount_vite_react_assets,
)

# load_model_registry()

main_app = create_app(custom_docs_url=False)

main_app.include_router(router_api)
main_app.include_router(r_order_one)

include_router_api_frontend(main_app, auth_users_router=auth_users_router)

# React: монтирование /assets + catch-all, строго после роутеров.
# Подробности в setup_frontend.py и docs/13_frontend_spa_module.md.
mount_vite_react_assets(main_app)


def main() -> None:
    logF.info(f"Base dir path :\n{BASE_DIR=}")

    uvicorn.run(
        "main:main_app",
        host=settings.run.host,
        port=settings.run.port,
        reload=True,
    )

    logF.warning(
        "end '-----------------------------' my-fastapi-one '----------------------------' \n\n\n\n"
        "'********************************************************************************'"
    )


if __name__ == "__main__":
    main()
