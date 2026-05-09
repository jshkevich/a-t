## Профайлер Telegram‑чатов

Веб‑приложение (frontend + backend), которое анализирует экспортированные данные Telegram‑чатов и строит “профиль” пользователя:
- эмоции и тональность
- интересы
- ключевые слова
- паттерны речи
- базовые эвристики (демография, занятость)

Все выводы сопровождаются **оценкой уверенности (confidence score)** и должны интерпретироваться как вероятностные.


## 🚀 Быстрый запуск (через Docker)

Это рекомендуемый способ запуска. Вам не нужно устанавливать Python или Node.js, потребуется только Docker.

### Требования
Убедитесь, что у вас установлены:
- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

### Шаги для запуска:

1. Склонируйте репозиторий и перейдите в папку с проектом:

```bash
git clone https://github.com/ВАШ_НИК/ВАШ_РЕПОЗИТОРИЙ.git
cd ВАШ_РЕПОЗИТОРИЙ
```

Запустите сборку и старт контейнеров:

```bash
docker-compose up --build
```
(Флаг -d можно добавить в конце, чтобы запустить в фоновом режиме: docker-compose up --build -d)

Проект доступен по адресам:

Frontend (Web UI): http://localhost:3000

Backend API: http://localhost:8000

💻 Локальная (Без Docker)

### Backend (FastAPI)

```bash
cd a-t/backend
pip install -r requirements.txt
python main.py
```

По умолчанию API: `http://localhost:8000`.

### Frontend (React + Vite)

```bash
cd a-t
npm install
npm run dev
```

Если backend не на `http://localhost:8000`, укажи `VITE_API_URL` (например, в `.env.local`):

```bash
VITE_API_URL=http://localhost:8000
```