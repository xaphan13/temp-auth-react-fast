import { Outlet } from 'react-router-dom';
import Header from './Header';
import { useAuth } from '../context/AuthContext';
import { useToast } from './Toast';
import { logout as apiLogout } from '../api/auth';
import type { ToastCategory } from './Toast';

// Лейаут auth-шаблона: пользователь приходит из AuthContext,
// а уведомления и выход доступны общему shell приложения.
export default function Layout() {
  const { user, setUser } = useAuth();
  const { showToast } = useToast();

  const handleLogout = async () => {
    try {
      const resp = await apiLogout();
      setUser(null);
      showToast(resp.message, resp.category as ToastCategory);
    } catch {
      // Даже если запрос не прошёл — локально пользователя сбрасываем.
      setUser(null);
      showToast('Вы вышли из аккаунта', 'message');
    }
  };

  return (
    <div className="app-shell">
      <Header user={user} onLogout={handleLogout} />
      <main>
        <Outlet />
      </main>
      <footer className="site-footer">
        <div className="container">Шаблон изучения авторизации</div>
      </footer>
    </div>
  );
}