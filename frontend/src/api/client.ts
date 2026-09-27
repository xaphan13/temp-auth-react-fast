// Базовый API-клиент для fastapi-users (/auth/*, /users/*).
// Все запросы идут с cookie-сессией (credentials: 'include').
// fastapi-users ставит cookie через Set-Cookie — fetch должен её принять.
// CSRF: backend требует X-CSRF-Token для state-changing запросов с auth-cookie
// (Signed Double Submit Cookie). Токен живёт в non-HttpOnly cookie csrf_token,
// SPA читает её и зеркалит значение в заголовок.

export class ApiError extends Error {
    status: number;
    data: unknown;
    constructor(status: number, message: string, data: unknown = null) {
        super(message);
        this.status = status;
        this.data = data;
        this.name = 'ApiError';
    }
}

// Читает csrf_token из document.cookie (backend ставит её non-HttpOnly).
export function getCsrfToken(): string | null {
    const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]*)/);
    return match ? decodeURIComponent(match[1]) : null;
}

// Добавляет X-CSRF-Token, только если csrf_token cookie существует.
// Cookie нет (аноним, logout уже прошёл) — headers не меняются.
function withCsrfHeader(headers: Record<string, string>): Record<string, string> {
    const csrfToken = getCsrfToken();
    if (!csrfToken) return headers;
    return { ...headers, 'X-CSRF-Token': csrfToken };
}

async function request(path: string, init: RequestInit = {}): Promise<Response> {
    const res = await fetch(path, { credentials: 'include', ...init });
    return res;
}

async function ensureOk(res: Response): Promise<unknown> {
    if (res.ok) {
        if (res.status === 204) return null;
        const ct = res.headers.get('content-type') || '';
        if (ct.includes('application/json')) return res.json();
        return res.text();
    }
    let data: unknown = null;
    try {
        data = await res.json();
    } catch {
        data = await res.text().catch(() => null);
    }
    throw new ApiError(res.status, `HTTP ${res.status}`, data);
}

export async function getJson<T = unknown>(path: string): Promise<T> {
    const res = await request(path, { method: 'GET' });
    return (await ensureOk(res)) as T;
}

export async function postJson<T = unknown>(path: string, body: unknown): Promise<T> {
    const res = await request(path, {
        method: 'POST',
        headers: withCsrfHeader({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(body),
    });
    return (await ensureOk(res)) as T;
}

export async function postForm<T = unknown>(path: string, form: URLSearchParams): Promise<T> {
    const res = await request(path, {
        method: 'POST',
        headers: withCsrfHeader({ 'Content-Type': 'application/x-www-form-urlencoded' }),
        body: form.toString(),
    });
    return (await ensureOk(res)) as T;
}

export async function postMultipart<T = unknown>(path: string, formData: FormData): Promise<T> {
    // Content-Type не выставляем — браузер сам с boundary. Только CSRF-заголовок.
    const res = await request(path, {
        method: 'POST',
        headers: withCsrfHeader({}),
        body: formData,
    });
    return (await ensureOk(res)) as T;
}
