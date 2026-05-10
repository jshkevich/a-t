# backend/Dockerfile

# Используем официальный образ Python
FROM python:3.11-slim

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Копируем файл зависимостей и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь остальной код бэкенда
COPY . .

# Открываем порт (предположим, у тебя FastAPI работает на 8000)
EXPOSE 8000

# Команда для запуска сервера (скорректируй, если используешь не uvicorn или файл называется иначе)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
