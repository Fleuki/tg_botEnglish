# 🤖 English Learning Bot

Telegram-бот для изучения английского языка с AI-генерируемыми уроками и системой интервального повторения слов.

## ✨ Возможности

- 📖 **AI-уроки** — персонализированные тексты, вопросы по содержанию и новые слова, генерируются через OpenAI API
- 💳 **Интервальные повторения (SRS)** — адаптивная система карточек, которая показывает слова в нужный момент
- 📊 **Прогресс и стрики** — статистика выученных слов, дневные серии, текущий уровень
- ⚙️ **Персонализация** — выбор языка интерфейса (8 языков), уровня владения английским, времени урока
- 🌍 **Многоязычность** — интерфейс на 8 языках, уроки адаптируются под родной язык пользователя

## 🛠 Технологии

| Технология | Назначение |
|---|---|
| [aiogram 3](https://docs.aiogram.dev/) | Telegram Bot Framework |
| [SQLAlchemy 2.0](https://www.sqlalchemy.org/) | ORM для работы с базой данных |
| [PostgreSQL](https://www.postgresql.org/) + asyncpg | Асинхронная база данных |
| [Alembic](https://alembic.sqlalchemy.org/) | Миграции схемы БД |
| [APScheduler](https://apscheduler.readthedocs.io/) | Планировщик ежедневных уроков |
| [OpenAI API](https://platform.openai.com/) | Генерация контента уроков |
| Docker + docker-compose | Контейнеризация и деплой |

## 🚀 Быстрый старт

### Требования
- Python 3.11+
- PostgreSQL
- Docker (опционально)

### Установка

```bash
# 1. Клонировать репозиторий
git clone https://github.com/Fleuki/tg_botEnglish.git
cd tg_botEnglish

# 2. Создать виртуальное окружение
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Установить зависимости
pip install -r requirements.txt

# 4. Настроить переменные окружения
cp .env.example .env
# Отредактируй .env — добавь токены
```

### Переменные окружения

Создай файл `.env` на основе `.env.example`:

```env
BOT_TOKEN=your_telegram_bot_token
OPENAI_API_KEY=your_openai_api_key
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/english_bot
```

### Запуск через Docker

```bash
docker-compose up -d
```

### Запуск без Docker

```bash
# Применить миграции
alembic upgrade head

# Запустить бота
python -m app.main
```

## 📱 Команды бота

| Команда | Описание |
|---|---|
| `/start` | Регистрация, выбор языка интерфейса |
| `/menu` | Главное меню |

**Через меню:**
- 📖 **Lessons** — получить урок дня
- 💳 **SRS Cards** — повторить слова
- 📊 **Stats** — посмотреть прогресс
- ⚙️ **Settings** — настройки профиля

## 🏗 Архитектура проекта

```
tg_botEnglish/
├── app/
│   ├── handlers/       # Обработчики команд и callback
│   ├── models/         # SQLAlchemy модели
│   ├── services/       # Бизнес-логика, OpenAI, SRS
│   └── main.py         # Точка входа
├── alembic/            # Миграции базы данных
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## 📄 Лицензия

MIT — используй свободно, оставь упоминание автора.
