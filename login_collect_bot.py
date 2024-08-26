import telebot
from pymongo import MongoClient
from telebot import types
from pymongo.errors import ConnectionFailure
from datetime import datetime
import re
import os
from dotenv import load_dotenv, find_dotenv
import pandas as pd  # Для работы с Excel

load_dotenv(find_dotenv())

bot = telebot.TeleBot(os.getenv("Token_tg"))

# Получение текущей даты и времени
now = datetime.now()
current_date = now.strftime("%Y-%m-%d %H:%M")
current_month = now.strftime("%Y-%m")

# Класс для работы с базой данных MongoDB
class DataBase:
    def __init__(self):
        cluster = MongoClient(os.getenv("Token_MDB"))

        self.db = cluster["Users_school_21"]
        self.login = self.db["login"]
        self.users = self.db["users"]

        # Инициализация коллекции статистики, если ее еще нет
        if self.users.count_documents({}) == 0:
            self.users.insert_one({
                "total_users": 0,
                "new_users_this_month": 0,
                "total_requests": 0,
                "requests_this_month": 0,
                "month": current_month
            })

    def get_user(self, chat_id):
        try:
            # Обновление статистики при каждом запросе
            self.increment_requests()

            user = self.login.find_one({"chat_id": chat_id})

            if user is not None:
                return user

            # Если пользователь не найден, создаем нового пользователя в базе данных
            user = {
                "chat_id": chat_id,
                "login_school": [],
                "login_tg": [],
                "user_id": [],
            }
            self.login.insert_one(user)
            self.increment_users()
            return user

        except ConnectionFailure as e:
            print(f"Ошибка соединения с базой данных: {e}")
            return None

    def set_user(self, chat_id, update):
        # Обновление информации о пользователе в базе данных
        self.login.update_one({"chat_id": chat_id}, {"$set": update})

    def delete_user(self, user_id):
        # Удаление пользователя из базы данных по его user_id
        self.login.delete_one({"user_id": user_id})

    def increment_requests(self):
        # Проверяем, существует ли запись для текущего месяца
        if not self.users.find_one({"month": current_month}):
            self.users.insert_one({
                "total_users": 0,
                "new_users_this_month": 0,
                "total_requests": 0,
                "requests_this_month": 0,
                "month": current_month
            })
        
        # Увеличение общего количества запросов и запросов за текущий месяц
        result = self.users.update_one({"month": current_month}, {
            "$inc": {"total_requests": 1, "requests_this_month": 1}})
        print(f"Increment requests result: {result.modified_count}")

    def increment_users(self):
        # Проверяем, существует ли запись для текущего месяца
        if not self.users.find_one({"month": current_month}):
            self.users.insert_one({
                "total_users": 0,
                "new_users_this_month": 0,
                "total_requests": 0,
                "requests_this_month": 0,
                "month": current_month
            })
        
        # Увеличение количества пользователей и новых пользователей за месяц
        result = self.users.update_one({"month": current_month}, {
            "$inc": {"total_users": 1, "new_users_this_month": 1}})
        print(f"Increment users result: {result.modified_count}")

    def reset_monthly_stats(self):
        # Сброс статистики для нового месяца
        self.users.update_one({"month": current_month}, {
            "$set": {"new_users_this_month": 0, "requests_this_month": 0}})

    def get_stats(self):
        # Получение статистики из базы данных
        return self.users.find_one({"month": current_month})

    def export_users_to_excel(self, file_path):
        # Экспорт всех пользователей в Excel
        users = self.login.find({})
        df = pd.DataFrame(list(users))
        df.to_excel(file_path, index=False)


db = DataBase()

# Обработчик команды /stat
@bot.message_handler(commands=['stat'])
def handle_stat(message):
    if str(message.from_user.id) == os.getenv("Your_user_ID"):
        stats = db.get_stats()
        if stats:
            stat_message = (f"Общее количество пользователей: {stats['total_users']}\n"
                            f"Новых пользователей в этом месяце: {stats['new_users_this_month']}\n"
                            f"Общее количество запросов: {stats['total_requests']}\n"
                            f"Запросов в этом месяце: {stats['requests_this_month']}")
            bot.send_message(message.chat.id, stat_message)
        else:
            bot.send_message(message.chat.id, "Статистика недоступна.")

# Обработчик команды /user
@bot.message_handler(commands=['user'])
def handle_user(message):
    if str(message.from_user.id) == os.getenv("Your_user_ID"):
        file_path = "users_data.xlsx"
        db.export_users_to_excel(file_path)
        with open(file_path, "rb") as file:
            bot.send_document(message.chat.id, file)

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.from_user.id
    if db.login.find_one({"user_id": user_id}) is not None:
        bot.register_next_step_handler(message, callback)
        bot.send_message(message.chat.id, 'Введи школьный или телеграм ник интересующего тебя пира.')
    else:
        bot.send_message(message.chat.id, f'Привет, {message.from_user.first_name}, введи свой школьный ник')
        bot.register_next_step_handler(message, hi)

# Функция для обработки ввода школьного ника
def hi(message):
    text = message.text.lower().strip()
    if re.search('[а-яА-Я]', text) or text.startswith('/'):
        bot.send_message(message.chat.id, 'Неверно введены данные, пожалуйста, введи свой школьный ник.')
        bot.register_next_step_handler(message, hi)
    else:
        login_school = text
        login_tg = message.from_user.username.lower().strip() if message.from_user.username is not None else None
        user_id = message.from_user.id
        if login_tg is None:
            bot.send_message(message.chat.id, 'Для использования бота необходимо создать логин (имя пользователя) в настройках Telegram, это не сложно.')
        else:
            db.login.insert_one({"login_school": login_school, "login_tg": login_tg, "user_id": user_id})
            db.increment_users()
            bot.send_message(message.chat.id, 'Введи школьный или телеграм ник интересующего тебя пира.')
        
        bot.register_next_step_handler(message, callback)

# Обработчик команды /bot login для чатов
# @bot.message_handler(commands=['bot'])
# def handle_bot(message):
#     if message.chat.type in ["group", "supergroup"]:
#         # Разделяем текст сообщения на части
#         parts = message.text.split()

#         # Проверяем, что команда содержит ровно две части: /bot и логин
#         if len(parts) == 2:
#             login = parts[1].lower()

#         if login.startswith('@'):
#             login = login[1 :]


#             # Ищем логин в базе данных
#             result = find_login(login)
#             if result is None:
#                 bot.send_message(message.chat.id, "Логин не найден")
#             else:
#                 text = f"Login school: <a href='https://edu.21-school.ru/profile/{result[0].lower()}@student.21-school.ru'>{result[0].capitalize()}</a>, login tg: @{result[1].capitalize()}"
#                 bot.send_message(message.chat.id, text, parse_mode='HTML')
#         else:
#             bot.send_message(message.chat.id, 'Пожалуйста, используйте команду в формате: /bot <логин>')
@bot.message_handler(commands=['bot'])
def handle_bot(message):
    if message.chat.type in ["group", "supergroup"]:
        # Разделяем текст сообщения на части
        parts = message.text.split()

        # Проверяем, что команда содержит ровно две части: /bot и логин
        if len(parts) == 2:
            login = parts[1].strip().lower()

            # Убираем символ '@', если он присутствует в начале
            if login.startswith('@'):
                login = login[1:]

            # Ищем логин в базе данных
            result = find_login(login)
            if result is None:
                bot.send_message(message.chat.id, "Логин не найден")
            else:
                text = f"Login school: {result[0].capitalize()}, login tg: @{result[1].capitalize()}"
                bot.send_message(message.chat.id, text, parse_mode='HTML')
        else:
            bot.send_message(message.chat.id, 'Пожалуйста, используйте команду в формате: /bot <логин>')
    else:
        bot.send_message(message.chat.id, 'Эта команда доступна только в группах.')


# Обработчик команды /help
@bot.message_handler(commands=['help'])
def handle_help(message):
    help_text = ("Привет! Я бот для поиска пользователей по школьному или телеграм нику.\n\n"
                 "Чтобы начать, введи команду /start и следуй инструкциям.\n\n"
                 "Чтобы удалить логин, введи команду /delete. В дальнейшем по команде /start ты сможешь создать новый логин.\n\n"
                 "Если у тебя возникли вопросы или проблемы - обратись к администратору @kaoekb.")
    bot.send_message(message.chat.id, help_text)

# Обработчик команды /delete
@bot.message_handler(commands=['delete'])
def handle_delete(message):
    user_id = message.from_user.id
    if db.login.find_one({"user_id": user_id}) is not None:
        confirm_message = "Ты точно хочешь удалить свой логин?"
        confirm_keyboard = types.InlineKeyboardMarkup()
        yes_button = types.InlineKeyboardButton("Да", callback_data='confirm_yes')
        no_button = types.InlineKeyboardButton("Нет", callback_data='confirm_no')
        confirm_keyboard.row(yes_button, no_button)
        bot.send_message(message.chat.id, confirm_message, reply_markup=confirm_keyboard)
    else:
        bot.send_message(message.chat.id, 'Ты ещё не зарегистрирован.')

# Обработчик нажатия кнопки подтверждения удаления
@bot.callback_query_handler(func=lambda call: True)
def handle_confirmation(call):
    if call.data == 'confirm_yes':
        user_id = call.from_user.id
        db.delete_user(user_id)
        bot.send_message(call.message.chat.id, 'Твоя запись удалена из базы данных.')
    elif call.data == 'confirm_no':
        bot.send_message(call.message.chat.id, 'Отменено.')

# Обработчик ввода текста (школьного или телеграм ника)
@bot.message_handler(content_types=['text'])
def callback(message):
    db.login.update_one(
        {"user_id": message.from_user.id},
        {"$set": {"last_access_date_out": current_date}},
        upsert=True
    )
    login = message.text.lower()
    if login.startswith('@'):
        login = login[1:]
    
    result = find_login(login)
    if result is None:
        bot.send_message(message.chat.id, "Логин не найден")
        bot.send_message(message.chat.id, 'Введи школьный или телеграм ник интересующего тебя пира.')
    else:
        text = f"Login school: <a href='https://edu.21-school.ru/profile/{result[0].lower()}@student.21-school.ru'>{result[0].capitalize()}</a>, login tg: @{result[1].capitalize()}"
        bot.send_message(message.chat.id, text, parse_mode='HTML')
        bot.send_message(message.chat.id, 'Введи школьный или телеграм ник интересующего тебя пира.')

def find_login(login):
    # Параметризованный запрос к базе данных
    query = {"$or": [
        {"login_school": {"$eq": login}},
        {"login_tg": {"$eq": login}}
    ]}
    result = db.login.find_one(query)
    if result is None:
        return None
    else:
        login_school = result["login_school"]
        login_tg = result["login_tg"]

        # Обновление или добавление поля с датой в базу данных. Используется для отслеживания последнего обращения к пользователю.
        db.login.update_one(
            {"_id": result["_id"]},
            {"$set": {"last_access_date_int": current_date}},
            upsert=True
        )
        return login_school, login_tg

# Запуск бота
bot.polling()
