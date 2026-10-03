"""CSRF-защита для cookie-транспорта: Signed Double Submit Cookie.

Middleware проверяет state-changing запросы (POST/PUT/PATCH/DELETE) только если
в запросе присутствует auth-cookie (по умолчанию ``auth``). Требуется точное
совпадение cookie ``csrf_token`` и заголовка ``X-CSRF-Token`` плюс валидная
HMAC-SHA256-подпись (секрет — ``settings.web.secret_key``). Наличие заголовка
``Authorization`` не освобождает от проверки, если auth-cookie тоже присутствует:
иначе Bearer создавал бы обход cookie-защиты.

Lifecycle CSRF-cookie (response inspection вокруг call_next, без hook'ов
fastapi-users):
- успешный ``POST /auth/cookie/login`` (204) -> установка ``csrf_token`` с
  Max-Age = settings.auth_users.cookie_max_age, Path=/, SameSite=Lax,
  Secure=False (dev), без HttpOnly — SPA читает через document.cookie;
- успешный ``POST /auth/cookie/logout`` -> удаление ``csrf_token`` (Max-Age=0).

Bearer-logout stateless: отзыва токена нет, клиент забывает его сам.
"""

import hashlib
import hmac
import secrets

from config_log import logF
from core.config import settings
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# Методы, для которых работает CSRF-проверка (GET/HEAD/OPTIONS пропускаются).
STATE_CHANGING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# Пути lifecycle-обработки CSRF-cookie (запросы без auth-cookie до login
# проходят middleware по общему правилу; logout при наличии auth-cookie
# проходит обычную CSRF-проверку до call_next — bypass не создаётся).
COOKIE_LOGIN_PATH = "/auth/cookie/login"
COOKIE_LOGOUT_PATH = "/auth/cookie/logout"

CSRF_TOKEN_COOKIE = "csrf_token"
CSRF_TOKEN_HEADER = "x-csrf-token"

ERROR_DETAIL = "CSRF validation failed"


class CSRFMiddleware(BaseHTTPMiddleware):
    """Signed Double Submit Cookie middleware для cookie-транспорта.

    Формат значения: ``<nonce>.<hex HMAC-SHA256(secret_key, nonce)>``.
    Заголовок ``X-CSRF-Token`` должен в точности совпадать со всем значением
    cookie, подпись проверяется по nonce через ``hmac.compare_digest``.
    """

    def __init__(
        self,
        app,
        secret_key: str,
        cookie_name: str = "csrf_token",
        auth_cookie_name: str = "auth",
    ) -> None:
        super().__init__(app)
        self.secret_key = secret_key.encode("utf-8")
        self.cookie_name = cookie_name
        self.auth_cookie_name = auth_cookie_name

    # ==== Подпись и генерация токена ====

    def _sign(self, nonce: str) -> str:
        """hex HMAC-SHA256(secret_key, nonce) — подписывается только nonce."""
        return hmac.new(self.secret_key, nonce.encode("utf-8"), hashlib.sha256).hexdigest()

    def _issue_token(self) -> str:
        """Новый подписанный токен ``<nonce>.<signature>``."""
        nonce = secrets.token_urlsafe(32)
        return f"{nonce}.{self._sign(nonce)}"

    def _is_valid(self, token: str) -> bool:
        """Токен имеет формат ``<nonce>.<signature>`` и валидную подпись."""
        nonce, sep, signature = token.rpartition(".")
        if not sep or not nonce or not signature:
            return False
        expected = self._sign(nonce)
        return hmac.compare_digest(signature, expected)

    # ==== Проверка запроса ====

    def _requires_check(self, request: Request) -> bool:
        """CSRF-проверка нужна: state-changing метод И auth-cookie присутствует.

        Наличие Authorization не проверяется намеренно: если auth-cookie
        присутствует, Bearer-заголовок не должен обходить cookie-защиту.
        """
        return (
            request.method in STATE_CHANGING_METHODS
            and self.auth_cookie_name in request.cookies
        )

    def _check_request(self, request: Request) -> bool:
        """Cookie и заголовок совпадают в точности, подпись валидна."""
        cookie_token = request.cookies.get(self.cookie_name)
        if not cookie_token:
            return False
        header_token = request.headers.get(CSRF_TOKEN_HEADER)
        if not header_token:
            return False
        return header_token == cookie_token and self._is_valid(cookie_token)

    # ==== Lifecycle CSRF-cookie ====

    def _set_token_cookie(self, response: Response) -> None:
        """Установка csrf_token после успешного cookie-login (204)."""
        response.set_cookie(
            key=self.cookie_name,
            value=self._issue_token(),
            max_age=settings.auth_users.cookie_max_age,
            path="/",
            secure=False,  # dev-профиль; SSL терминируется на nginx в prod
            httponly=False,  # SPA читает через document.cookie
            samesite="lax",
        )

    def _delete_token_cookie(self, response: Response) -> None:
        """Удаление csrf_token после успешного cookie-logout."""
        response.delete_cookie(key=self.cookie_name, path="/")

    # ==== dispatch ====

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Проверка ДО call_next: logout при наличии auth-cookie обязан пройти
        # обычную CSRF-проверку, login её не требует (auth-cookie ещё нет).
        required = self._requires_check(request)
        csrf_valid = self._check_request(request) if required else None
        # Логируем только факты решения, без значений cookie и токена.
        logF.debug(
            "auth csrf: method=%s path=%s required=%s valid=%s",
            request.method,
            request.url.path,
            required,
            csrf_valid,
        )
        if required and not csrf_valid:
            logF.warning(
                "auth csrf: rejected method=%s path=%s",
                request.method,
                request.url.path,
            )
            return JSONResponse({"detail": ERROR_DETAIL}, status_code=403)

        response = await call_next(request)

        # Lifecycle по фактическому ответу endpoint'а.
        path = request.url.path
        if path == COOKIE_LOGIN_PATH and response.status_code == 204:
            self._set_token_cookie(response)
            logF.info("auth csrf: issued csrf_token cookie path=%s", path)
        elif path == COOKIE_LOGOUT_PATH and response.status_code < 400:
            self._delete_token_cookie(response)
            logF.info("auth csrf: deleted csrf_token cookie path=%s", path)

        return response
