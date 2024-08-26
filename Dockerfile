# Используем официальный образ Python
FROM python:3.12-slim

# Устанавливаем рабочую директорию в контейнере
WORKDIR /app

# Загружаем переменные окружения из 
ENV $(cat .env | xargs)

# Копируем файл зависимостей в контейнер
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем содержимое директории с проектом в контейнер
COPY . .

# Указываем команду для запуска бота
CMD ["python", "login_collect_bot.py"]
