# Фаза 8 — прогресс

- Прочитаны контракт фазы 8, AGENTS.md и используемые props/layout auth-файлы.
- `Layout.tsx`: удалены side panel, section menu, theme hooks и blog navigation props; сохранены `Outlet`, `Toast`, logout и auth state.
- `Header.tsx`: оставлены home/login/register/account/protected и logout; удалены theme/highlight/article navigation; сохранён avatar URL `/static/profile_pics/{image_file}`.
- `types.ts`: оставлен только auth `User` с полями `id`, `email`, `username`, `image_file`, `is_active`, `is_superuser`, `is_verified`.
- `phase08_grep.txt`: требуемые `Article|Section|Theme|Hljs|art_manage|/api/blog` совпадения в трёх целевых файлах отсутствуют (`GREP_EXIT=1`, ожидаемо).
- `phase08_build.txt`: `npm run build` не проходит из-за blog-файлов следующих фаз, которые ещё импортируют удалённые `Article`/`Section`; целевые файлы и запрещённые blog-файлы не расширялись.
