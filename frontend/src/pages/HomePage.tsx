import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function HomePage() {
    const { user } = useAuth();

    return (
        <div className="page-stub">
            <h1>Auth-шаблон FastAPI</h1>
            <p className="text-muted">
                Учебная страница для проверки регистрации, входа и доступа к защищённым
                backend-маршрутам.
            </p>
            {user ? (
                <div>
                    <p>Вы вошли как {user.email}.</p>
                    <p>
                        <Link to="/account">Открыть аккаунт</Link>{' '}
                        <Link to="/protected">Проверить защищённый API</Link>
                    </p>
                </div>
            ) : (
                <p>
                    <Link to="/login">Войти</Link>{' '}
                    <Link to="/register">Зарегистрироваться</Link>
                </p>
            )}
        </div>
    );
}