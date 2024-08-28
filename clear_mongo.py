import logging
import os
import requests
from pymongo import MongoClient

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

try:
    # Подключение к MongoDB
    mongo_uri = os.getenv("Token_MDB")
    if not mongo_uri:
        raise ValueError("Переменная окружения 'Token_MDB' не найдена или пуста.")
    
    cluster = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    db = cluster["Users_school_21_kzn"]
    login_collection = db["login"]

    # Проверка подключения
    cluster.admin.command('ping')
    logging.info("Подключение к базе данных MongoDB установлено успешно.")

except Exception as e:
    logging.error(f"Ошибка подключения к базе данных MongoDB: {e}")
    exit(1)

# API URL и ключ
API_URL = "https://edu-api.21-school.ru/services/21-school/api/v1/participants/"
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    logging.error("Переменная окружения 'API_KEY' не найдена или пуста.")
    exit(1)

# Функция для получения данных пользователя через API
def get_user_data(email):
    headers = {"Authorization": f"Bearer {API_KEY}"}
    try:
        response = requests.get(f"{API_URL}{email}", headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            logging.warning(f"Не удалось получить данные для {email}, код ответа: {response.status_code}")
            return None
    except Exception as e:
        logging.error(f"Ошибка при запросе данных пользователя: {e}")
        return None

# Проход по всем пользователям в коллекции
try:
    for user in login_collection.find():
        login_school = user.get('login_school')
        if not login_school:
            logging.warning(f"Отсутствует поле 'login_school' для пользователя с id {user['_id']}")
            continue

        email = f"{login_school}@student.21-school.ru"
        user_info = get_user_data(email)

        if user_info:
            update_fields = {
                "login": user_info.get("login"),
                "className": user_info.get("className"),
                "parallelName": user_info.get("parallelName"),
                "expValue": user_info.get("expValue"),
                "level": user_info.get("level"),
                "expToNextLevel": user_info.get("expToNextLevel"),
                "campus_id": user_info.get("campus", {}).get("id"),
                "campus_shortName": user_info.get("campus", {}).get("shortName"),
                "status": user_info.get("status"),
            }
            login_collection.update_one({"_id": user["_id"]}, {"$set": update_fields})
            logging.info(f"Пользователь {email} успешно обновлен.")
        else:
            login_collection.delete_one({"_id": user["_id"]})
            logging.info(f"Пользователь {email} удален из базы данных, так как не найден.")
except Exception as e:
    logging.error(f"Ошибка при обработке пользователей: {e}")

logging.info("Процесс обновления завершен.")
