// Тост-уведомления: message + category из ответов /api/blog
// (success, danger, info, warning, message). Без библиотек —
// простой контекст со списком активных тостов и автоскрытием.

import {
    createContext,
    useCallback,
    useContext,
    useEffect,
    useState,
    type ReactNode,
} from 'react';

// Категории совпадают с флеш-категориями бэкенда (get_flashed_messages).
export type ToastCategory =
    | 'success'
    | 'danger'
    | 'info'
    | 'warning'
    | 'message';

interface ToastItem {
    id: number;
    message: string;
    category: ToastCategory;
}

interface ToastContextValue {
    showToast: (message: string, category?: ToastCategory) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

let nextId = 1;

// Класс блока под категорию: стили .toast / .toast-<category> в index.css.
function categoryClass(category: ToastCategory): string {
    return `toast toast-${category}`;
}

export function ToastProvider({ children }: { children: ReactNode }) {
    const [toasts, setToasts] = useState<ToastItem[]>([]);

    const showToast = useCallback(
        (message: string, category: ToastCategory = 'info') => {
            const id = nextId++;
            setToasts((prev) => [...prev, { id, message, category }]);
        },
        [],
    );

    const removeToast = useCallback((id: number) => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
    }, []);

    return (
        <ToastContext.Provider value={{ showToast }}>
            {children}
            <div className="toast-container" aria-live="polite">
                {toasts.map((t) => (
                    <Toast key={t.id} item={t} onClose={() => removeToast(t.id)} />
                ))}
            </div>
        </ToastContext.Provider>
    );
}

// Автоскрытие через 4 секунды; тост можно закрыть и руками.
function Toast({ item, onClose }: { item: ToastItem; onClose: () => void }) {
    useEffect(() => {
        const timer = setTimeout(onClose, 4000);
        return () => clearTimeout(timer);
    }, [item.id, onClose]);

    return (
        <div className={categoryClass(item.category)} role="alert">
            <span className="toast-message">{item.message}</span>
            <button
                type="button"
                className="toast-close"
                onClick={onClose}
                aria-label="Закрыть уведомление"
            >
                ×
            </button>
        </div>
    );
}

// Хук доступа к toast; снаружи ToastProvider должен быть подключён.
export function useToast(): ToastContextValue {
    const ctx = useContext(ToastContext);
    if (!ctx) {
        throw new Error('useToast must be used within ToastProvider');
    }
    return ctx;
}