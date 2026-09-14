// Страница аккаунта: GET /users/me при входе, форма username/email.
// После успеха — обновление пользователя в AuthContext + toast.
// Доступ только для авторизованных (RequireAuth в App.tsx), 401/API-сбой — страховка.

import { useEffect, useState, type FormEvent } from 'react';
import { getAccount, updateAccount, extractErrors, MessageResp } from '../api/auth';
import { ApiError } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../components/Toast';
import { FormField } from './RegisterPage';
import type { User } from '../types';
import type { ToastCategory } from '../components/Toast';

export default function AccountPage() {
  const { setUser } = useAuth();
  const { showToast } = useToast();

  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [errors, setErrors] = useState<Record<string, string[]>>({});
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getAccount()
      .then((data) => {
        if (cancelled) return;
        setUsername(data.user.username);
        setEmail(data.user.email);
        setUser(data.user);
      })
      .catch((err) => {
        // RequireAuth обычно перехватит 401 раньше, здесь остаётся показать ошибку.
        if (cancelled) return;
        const message =
          err instanceof ApiError
            ? `Ошибка ${err.status}: не удалось загрузить аккаунт`
            : 'Не удалось загрузить аккаунт';
        showToast(message, 'danger');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // setUser в зависимостях не нужен: сеттер стабилен.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setErrors({});
    setSubmitting(true);
    try {
      const resp: MessageResp & { user: User } = await updateAccount({
        username,
        email,
      });
      setUser(resp.user);
      showToast(resp.message, resp.category as ToastCategory);
    } catch (err) {
      const serverErrors = extractErrors(err);
      if (Object.keys(serverErrors).length > 0) {
        setErrors(serverErrors);
      } else {
        const message =
          err instanceof ApiError && err.status === 403
            ? 'Требуется вход в аккаунт'
            : 'Не удалось сохранить аккаунт';
        showToast(message, 'danger');
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return <div className="page-stub text-muted">Загрузка аккаунта...</div>;
  }

  return (
    <div className="auth-page">
      <h1>Аккаунт</h1>

      <form onSubmit={handleSubmit} noValidate>
        <FormField
          label="Имя пользователя"
          name="username"
          type="text"
          value={username}
          errors={errors.username}
          onChange={setUsername}
        />
        <FormField
          label="Email"
          name="email"
          type="email"
          value={email}
          errors={errors.email}
          onChange={setEmail}
        />
        <button type="submit" className="btn btn-primary" disabled={submitting}>
          {submitting ? 'Сохранение...' : 'Сохранить'}
        </button>
      </form>
    </div>
  );
}