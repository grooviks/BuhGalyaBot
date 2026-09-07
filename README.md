# BuhGalyaBot

Telegram-бот для учёта долгов и сборов. Архитектура API-first: Telegram —
первый клиент внутреннего FastAPI-приложения; позднее к нему можно подключить
браузерный интерфейс.

## Локальный запуск

1. Скопируйте `.env.example` в `.env` и укажите `BOT_TOKEN`.
2. Установите зависимости: `uv sync`.
3. Поднимите PostgreSQL: `docker compose up -d db`.
4. Примените миграции: `uv run alembic upgrade head`.
5. Создайте первое пространство и добавьте свой Telegram ID в allowlist:
   `uv run python scripts/bootstrap.py --workspace-name "Личный учёт" --actor-id <ваш_ID>`.
   Укажите напечатанный UUID в `DEFAULT_WORKSPACE_ID`.
6. Запустите API: `uv run uvicorn buhgalya.api:app --reload`.
7. В отдельном терминале запустите бота: `uv run python -m buhgalya.telegram.bot`.

Проверки: `uv run ruff check .` и `uv run pytest`.

Логи пишутся в stderr и в `/var/log/buhgalya` через Loguru. Файлы ротируются при
достижении 10 MB, хранятся 14 дней и сжимаются в ZIP. В Docker этот каталог
подключён к отдельному volume `app_logs`; уровень задаётся в `.env`, например
`LOG_LEVEL=DEBUG`. Токены, пароли, имена людей и суммы в сообщения не попадают.

## Production: внешний PostgreSQL и secrets

Compose не запускает PostgreSQL: `DATABASE_URL` должен указывать на отдельный
экземпляр БД. В production API и бот получают его из Docker secret
`/run/secrets/database_url`; бот дополнительно получает `/run/secrets/bot_token`.
Создайте эти файлы вне репозитория, например в `/opt/buhgalya/secrets/`, и
запустите Compose с `SECRETS_DIR=/opt/buhgalya/secrets`. В `database_url` должна
быть одна строка вида `postgresql+asyncpg://пользователь:пароль@хост:5432/база`.
В переменных окружения deployment оставьте только несекретные
`DEFAULT_WORKSPACE_ID` и `LOG_LEVEL`.

### Сборка и доставка образа

Workflow `.github/workflows/build-image.yml` после push в `main` запускает
проверки, собирает единый образ для API и бота и публикует его в Yandex
Container Registry. В GitHub нужно создать:

- variable `YC_REGISTRY_ID` — ID Container Registry;
- secret `YC_REGISTRY_JSON_KEY` — JSON-ключ service account с правом push.

На production VM разместите `compose.prod.yaml`, `scripts/deploy.sh`, файл
`.env` и каталог секретов. В `.env` должны быть `IMAGE_REPOSITORY`,
`DEFAULT_WORKSPACE_ID`, `SECRETS_DIR` и, при необходимости, `LOG_LEVEL`.
Запуск версии по SHA коммита:

```bash
/opt/buhgalya/scripts/deploy.sh <commit-sha>
```

Скрипт скачивает образ, применяет миграции, поднимает контейнеры и проверяет
`/health`. Откат выполняется повторным запуском скрипта с предыдущим SHA.

## Команды MVP

- `/debt_add <имя> <сумма>`, `/debt_repay <id> <сумма>`, `/debt_edit <id> <сумма>`,
  `/debt_delete <id>`, `/debts`;
- `/person_link <имя> <@telegram_username>` — связать карточку человека с Telegram username;
- `/fund_create <monthly|once> <название> <сумма>`;
- `/fund_add <id_сбора> <имя> [индивидуальная_сумма]`;
- `/fund_pay <id_участника> <сумма>`, `/fund_status <id_сбора>`.

На первом шаге названия людей и сборов передаются одним словом; поддержку
кавычек и кнопок можно добавить без изменения API.
