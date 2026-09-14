// Страница регистрации: форма (email, password, confirm_password)
// с клиентской валидацией. POST /auth/register; server validation показываем
// по полям и в общем блоке; при успехе — toast + редирект на /login.

import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { register, extractErrors } from '../api/auth';
import { ApiError } from '../api/client';
import { useToast } from '../components/Toast';

interface FormState {
  email: string;
  password: string;
  confirm_password: string;
}

// Клиентская валидация полей, которые отправляются на /auth/register.
export function validate(form: FormState): Record<string, string[]> {
  const errors: Record<string, string[]> = {};
  if (!form.email.trim()) {
    errors.email = ['This field is required.'];
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) {
    errors.email = ['Invalid email address.'];
  }
  if (!form.password) {
    errors.password = ['This field is required.'];
  } else if (form.password.length < 8) {
    errors.password = ['Field must be at least 8 characters long.'];
  }
  if (!form.confirm_password) {
    errors.confirm_password = ['This field is required.'];
  } else if (form.password !== form.confirm_password) {
    errors.confirm_password = ['Passwords must match.'];
  }
  return errors;
}

function getServerValidationErrors(err: unknown): Record<string, string[]> {
  const errors = extractErrors(err);
  if (!(err instanceof ApiError)) return errors;

  const data = err.data as
    | { detail?: string | Array<{ loc?: unknown[]; msg?: string }> }
    | null;
  if (Array.isArray(data?.detail)) {
    for (const item of data.detail) {
      const field = item.loc?.find(
        (part): part is string => part === 'email' || part === 'password',
      );
      const message = item.msg || 'Invalid value.';
      if (field) {
        errors[field] = [...(errors[field] || []), message];
      } else {
        errors.form = [...(errors.form || []), message];
      }
    }
  } else if (typeof data?.detail === 'string' && Object.keys(errors).length === 0) {
    errors.form = [data.detail];
  }
  return errors;
}

export default function RegisterPage() {
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [form, setForm] = useState<FormState>({
    email: '',
    password: '',
    confirm_password: '',
  });
  const [errors, setErrors] = useState<Record<string, string[]>>({});
  const [submitting, setSubmitting] = useState(false);

  const setField = (field: keyof FormState, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    // Первая правка поля снимает его ошибку.
    setErrors((prev) => {
      if (!prev[field]) return prev;
      const next = { ...prev };
      delete next[field];
      return next;
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const clientErrors = validate(form);
    if (Object.keys(clientErrors).length > 0) {
      setErrors(clientErrors);
      return;
    }
    setSubmitting(true);
    try {
      // fastapi-users /auth/register получает только email и password.
      await register({ email: form.email, password: form.password });
      showToast('Регистрация выполнена', 'success');
      navigate('/login');
    } catch (err) {
      const serverErrors = getServerValidationErrors(err);
      if (Object.keys(serverErrors).length > 0) {
        setErrors(serverErrors);
      } else {
        const detail =
          err instanceof Error ? err.message : 'Не удалось зарегистрироваться';
        showToast(detail, 'danger');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="auth-page">
      <h1>Регистрация</h1>
      <form onSubmit={handleSubmit} noValidate>
        <FormField
          label="Email"
          name="email"
          type="email"
          value={form.email}
          errors={errors.email}
          onChange={(v) => setField('email', v)}
        />
        <FormField
          label="Пароль"
          name="password"
          type="password"
          value={form.password}
          errors={errors.password}
          onChange={(v) => setField('password', v)}
        />
        <FormField
          label="Подтверждение пароля"
          name="confirm_password"
          type="password"
          value={form.confirm_password}
          errors={errors.confirm_password}
          onChange={(v) => setField('confirm_password', v)}
        />
        {errors.form?.map((text) => (
          <div key={text} className="form-error-text">
            {text}
          </div>
        ))}
        <button type="submit" className="btn btn-primary" disabled={submitting}>
          {submitting ? 'Регистрация...' : 'Зарегистрироваться'}
        </button>
      </form>
      <p className="text-muted">
        Уже есть аккаунт? <Link to="/login">Войти</Link>
      </p>
    </div>
  );
}

// Общая строка формы с блоком ошибок 422 (serverErrors отобразятся
// под полем). Используется и на LoginPage, и на AccountPage.
export function FormField({
  label,
  name,
  type,
  value,
  errors,
  onChange,
}: {
  label: string;
  name: string;
  type: string;
  value: string;
  errors?: string[];
  onChange: (value: string) => void;
}) {
  const hasError = errors && errors.length > 0;
  return (
    <div className={`form-field${hasError ? ' form-field-invalid' : ''}`}>
      <label htmlFor={name}>{label}</label>
      <input
        id={name}
        name={name}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
      {hasError && (
        <div className="form-errors">
          {errors.map((text) => (
            <div key={text} className="form-error-text">
              {text}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}