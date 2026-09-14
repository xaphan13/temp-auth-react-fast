import { useEffect, useState } from 'react';
import { ApiError, getJson } from '../api/client';

interface ProtectedResponse {
  authenticated: boolean;
  user: {
    id: string;
    email: string;
    username: string;
  };
}

export default function ProtectedPage() {
  const [response, setResponse] = useState<ProtectedResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    getJson<ProtectedResponse>('/api/v1/auth/protected')
      .then((data) => {
        if (!cancelled) setResponse(data);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          setError('Backend отклонил запрос: требуется авторизация.');
        } else {
          setError('Не удалось проверить доступ к защищённому backend API.');
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="page-stub">
      <h1>Защищённая страница</h1>
      <p className="text-muted">
        Эта страница проверяет доступ не только через UI guard, но и запросом к
        защищённому backend endpoint.
      </p>
      {loading && <p>Проверка backend-доступа...</p>}
      {error && <p className="text-muted">{error}</p>}
      {response && (
        <div>
          <p>Backend подтвердил авторизованный доступ.</p>
          <p>Пользователь: {response.user.email}</p>
          <p>authenticated: {String(response.authenticated)}</p>
        </div>
      )}
    </div>
  );
}
