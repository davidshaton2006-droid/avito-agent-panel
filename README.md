# Avito Agent Panel

Отдельный проект (не связан с romatik-client2/sharevo-next): ИИ-агент, который отвечает
гостям базы отдыха «Романтик» на Авито через Claude API, плюс веб-панель администратора.

Использует Firestore, но с коллекциями, отдельными от бронирований основного сайта
(`avito_agent_*`), поэтому Firebase-проект можно переиспользовать без риска пересечения данных.

## Структура

```
backend/    FastAPI-сервис: вебхук Avito, Claude-агент, движок сценариев, REST API для админки
frontend/   React + TypeScript + Vite админка
```

## Быстрый старт (локально)

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate    # Windows
pip install -r requirements.txt
copy .env.example .env    # и заполнить значения
python -m scripts.seed_knowledge_base
python -m scripts.seed_scenarios
uvicorn app.main:app --reload
```

Требуется Python 3.10+.

### Frontend

```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```

## Переменные окружения (backend/.env)

| Переменная | Назначение |
|---|---|
| `ANTHROPIC_API_KEY` | ключ Claude API |
| `CLAUDE_MODEL` | модель (по умолчанию Claude Sonnet) |
| `AVITO_CLIENT_ID`, `AVITO_CLIENT_SECRET`, `AVITO_USER_ID` | доступ к Avito Messenger API |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ADMIN_CHAT_ID` | уведомления администратору |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | путь к JSON-ключу сервисного аккаунта или сам JSON целиком |
| `FIREBASE_PROJECT_ID` | ID проекта Firebase |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | логин админки (один пользователь) |
| `JWT_SECRET` | секрет для подписи токена сессии админки |
| `CORS_ORIGINS` | домены фронтенда, которым разрешён доступ к API |

## Архитектурные решения

- **Firestore-коллекции**: `avito_agent_knowledge_base`, `avito_agent_conversations`,
  `avito_agent_scenarios` — см. `backend/app/firestore_db.py`.
- **Админка ходит только в backend API**, не напрямую в Firestore — так авторизация и вся
  логика (включая реальную отправку сообщений в Avito) остаются в одном месте, а фронтенду
  не нужны ни Firebase SDK, ни security rules.
- **Финальное подтверждение брони** после проверки чека отправляется администратором
  вручную через страницу «Переписки» — это осознанно не автоматизировано.
- **Формат вебхука Avito** (`backend/app/avito_client.py::parse_webhook_payload`) построен по
  документированным принципам их API, но помечен `TODO` в местах, которые нужно сверить
  после получения реального доступа к developers.avito.ru и первого вебхука.

## Деплой

- Backend: Render/Railway — см. `backend/Procfile` (`uvicorn app.main:app --host 0.0.0.0 --port $PORT`).
  Настройте вебхук Avito на `https://<ваш-backend>/webhook/avito` через `subscribe_webhook()`
  или напрямую в кабинете разработчика Avito.
- Frontend: Vercel — задайте `VITE_API_BASE_URL` на адрес задеплоенного backend.

## Известное ограничение этой сборки

Python не был доступен в среде, где собирался проект, поэтому backend не запускался и не
тестировался локально (только код-ревью и статическая проверка). Frontend прошёл
`npx tsc --noEmit` и `npx vite build` без ошибок. Перед реальным использованием стоит поднять
backend локально и прогнать через него тестовый вебхук.
