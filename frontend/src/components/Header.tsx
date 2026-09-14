import { NavLink, Link } from 'react-router-dom';
import type { User } from '../types';

interface HeaderProps {
    user: User | null;
    onLogout: () => void;
}

// Шапка auth-шаблона: домашняя страница и маршруты авторизации.
export default function Header({ user, onLogout }: HeaderProps) {
    const navClass = ({ isActive }: { isActive: boolean }) =>
        isActive ? 'nav-link active' : 'nav-link';

    return (
        <header className="site-header">
            <div className="container header-inner">
                <Link to="/" className="brand">
                    Шаблон авторизации
                </Link>

                <nav className="nav-links" aria-label="Навигация авторизации">
                    <NavLink to="/" end className={navClass}>
                        Главная
                    </NavLink>
                    {user ? (
                        <>
                            <NavLink to="/account" className={navClass}>
                                Аккаунт
                            </NavLink>
                            <NavLink to="/protected" className={navClass}>
                                Защищённая страница
                            </NavLink>
                            <button type="button" className="nav-link as-button" onClick={onLogout}>
                                Выход
                            </button>
                        </>
                    ) : (
                        <>
                            <NavLink to="/login" className={navClass}>
                                Вход
                            </NavLink>
                            <NavLink to="/register" className={navClass}>
                                Регистрация
                            </NavLink>
                        </>
                    )}
                </nav>
            </div>
        </header>
    );
}