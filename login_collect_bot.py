import telebot
from config import Token_MDB, Token_tg 
from pymongo import MongoClient
from telebot import types
from pymongo.errors import ConnectionFailure
from datetime import datetime
import re
import os
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

bot = telebot.TeleBot(os.getenv("Token_tg"))

# Получение текущей даты и времени
now = datetime.now()    
current_date = now.strftime("%Y-%m-%d %H:%M")

# Класс для работы с базой данных MongoDB
class DataBase:
    def __init__(self):
        cluster = MongoClient(os.getenv("Token_MDB"))

        self.db = cluster["Users_school_21"]
        self.login = self.db["login"]

    def get_user(self, chat_id):
        try:
            # Получение пользователя из базы данных по его chat_id
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


db = DataBase()

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


# Обработчик команды /start
@bot.message_handler(commands=['start'])
def handle_start(message):
    # Получение id пользователя
    user_id = message.from_user.id
    # Проверка, есть ли пользователь в базе данных
    if db.login.find_one({"user_id": user_id}) is not None:
        # Если пользователь уже есть в базе данных, переходим в функцию callback
            bot.register_next_step_handler(message, callback)
            bot.send_message(message.chat.id, 'Введи школьный или телеграм ник интересующего тебя пира.')

    else:
        # Если пользователь новый, отправляем сообщение с просьбой ввести школьный ник
        bot.send_message(message.chat.id, f'Привет, {message.from_user.first_name}, введи свой школьный ник')
        bot.register_next_step_handler(message, hi)

# # Функция для обработки ввода школьного ника
def hi(message):
    # Получение текста сообщения пользователя в нижнем регистре
    text = message.text.lower().strip()

    # Проверка на кириллицу или начало с символа "/"
    if re.search('[а-яА-Я]', text) or text.startswith('/'):
        # Если текст содержит кириллицу или начинается с символа "/", отправляем сообщение о неверно введенных данных
        bot.send_message(message.chat.id, 'Неверно введены данные, пожалуйста, введи свой школьный ник.')
        bot.register_next_step_handler(message, hi)  # Ожидаем нового ввода
    else:
        # Получение логина пользователя в нижнем регистре
        login_school = text
        # Получение логина пользователя в Telegram в нижнем регистре
        login_tg = message.from_user.username.lower().strip() if message.from_user.username is not None else None
        user_id = message.from_user.id
        # Проверка, есть ли логин в Telegram
        if login_tg is None:
            # Если логина нет, отправляем сообщение с просьбой создать логин
            bot.send_message(message.chat.id, 'Для использования бота необходимо создать логин (имя пользователя) в настройках Telegram, это не сложно.')
        else:
            # Если логин есть, добавляем логины в базу данных
            db.login.insert_one({"login_school": login_school, "login_tg": login_tg, "user_id": user_id})
            bot.send_message(message.chat.id, 'Введи школьный или телеграм ник интересующего тебя пира.')
        
        bot.register_next_step_handler(message, callback)

# Обработчик команды /help
@bot.message_handler(commands=['help'])
def handle_help(message):
    # Отправляем сообщение с помощью по использованию бота
    help_text = "Привет! Я бот для поиска пользователей по школьному или телеграм нику.\n\n" \
                "Чтобы начать, введи команду /start и следуй инструкциям.\n\n" \
                "Чтобы удалить логин, введи команду /delete. В дальнейшем по команде /start ты сможешь создать новый логин.\n\n" \
                "Если у тебя возникли вопросы или проблемы - обратись к администратору @kaoekb."
    bot.send_message(message.chat.id, help_text)

# Обработчик команды /delete
@bot.message_handler(commands=['delete'])
def handle_delete(message):
    # Получение id пользователя
    user_id = message.from_user.id
    # Проверка, есть ли пользователь в базе данных
    if db.login.find_one({"user_id": user_id}) is not None:
        # Если пользователь есть в базе данных, отправляем сообщение с подтверждением удаления
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
        # Получение id пользователя
        user_id = call.from_user.id
        # Удаляем запись пользователя из базы данных
        db.delete_user(user_id)
        bot.send_message(call.message.chat.id, 'Твоя запись удалена из базы данных.')
    elif call.data == 'confirm_no':
        bot.send_message(call.message.chat.id, 'Отменено.')

# Обработчик ввода текста (школьного или телеграм ника)
@bot.message_handler(content_types=['text'])
def callback(message):
    # Обновление или добавление поля с датой в базу данных. Используется для отслеживания последнего обращения к пользователю.
    db.login.update_one(
        {"user_id": message.from_user.id},
        {"$set": {"last_access_date_out": current_date}},
        upsert=True
    )
    login = message.text.lower()
    # Удаляет символ "@", если он является первым символом текста сообщения        
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

# Запуск бота
bot.polling()
