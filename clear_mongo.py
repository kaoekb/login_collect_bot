import os
import requests
import logging
from pymongo import MongoClient

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("mongo_update.log"),
        logging.StreamHandler()
    ]
)

# Подключение к MongoDB
try:
    cluster = MongoClient(os.getenv("Token_MDB"), serverSelectionTimeoutMS=5000)
    db = cluster["Users_school_21_kzn"]
    login_collection = db["login"]
    logging.info("Подключение к базе данных MongoDB установлено успешно.")
    print("Подключение к базе данных MongoDB установлено успешно.")
except Exception as e:
    logging.error(f"Ошибка подключения к MongoDB: {e}")
    raise

# API URL и ключ
API_URL = "https://edu-api.21-school.ru/services/21-school/api/v1/participants/"
API_KEY = os.getenv("API_KEY")

# Функция для получения данных пользователя через API
def get_user_data(email):
    headers = {"Authorization": f"Bearer {API_KEY}"}
    try:
        response = requests.get(f"{API_URL}{email}", headers=headers)
        if response.status_code == 200:
            logging.info(f"Данные для {email} успешно получены.")
            return response.json()
        else:
            logging.warning(f"Не удалось получить данные для {email}. Статус код: {response.status_code}")
            return None
    except Exception as e:
        logging.error(f"Ошибка при обращении к API для {email}: {e}")
        return None

# Проход по всем пользователям в коллекции
try:
    for user in login_collection.find():
        login_school = user['login_school']
        email = f"{login_school}@student.21-school.ru"
        logging.info(f"Обработка пользователя с логином {login_school}.")
        
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
            # Удаление пользователя, если данных по нему нет
            login_collection.delete_one({"_id": user["_id"]})
            logging.info(f"Пользователь {email} удален из базы данных, так как не найден.")
except Exception as e:
    logging.error(f"Ошибка при обработке пользователей: {e}")

logging.info("Процесс обновления завершен.")
