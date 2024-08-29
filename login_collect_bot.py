import logging
from logging.handlers import RotatingFileHandler
import telebot
from pymongo import MongoClient
from telebot import types
from pymongo.errors import ConnectionFailure
from datetime import datetime
import re
import os
from dotenv import load_dotenv, find_dotenv
import pandas as pd
from telebot.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat
import time
from telebot.apihelper import ApiTelegramException

# Настройка логирования
log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
logFile = '/app/bot.log'

file_handler = RotatingFileHandler(logFile, mode='a', maxBytes=5*1024*1024, backupCount=2, encoding=None, delay=0)
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.INFO)

logger = logging.getLogger('root')
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

logger.info("Бот запускается...")

load_dotenv(find_dotenv())

bot = telebot.TeleBot(os.getenv("Token_tg"))

now = datetime.now()
current_date = now.strftime("%Y-%m-%d %H:%M")
current_month = now.strftime("%Y-%m")

# Переменная для хранения состояния активности бота в группах
group_states = {}

class DataBase:
    def __init__(self):
        try:
            cluster = MongoClient(os.getenv("Token_MDB"))
            self.db = cluster["Users_school_21"]
            self.login = self.db["login"]
            self.users = self.db["users"]

            if self.users.count_documents({}) == 0:
                self.users.insert_one({
                    "total_users": self.login.count_documents({}),
                    "new_users_this_month": 0,
                    "total_requests": 0,
                    "requests_this_month": 0,
                    "bot_requests_this_month": 0,
                    "group_requests_this_month": 0,
                    "month": current_month
                })
            logger.info("Подключение к базе данных установлено.")
        except ConnectionFailure as e:
            logger.error(f"Ошибка подключения к базе данных: {e}")
            raise

    def get_user(self, chat_id):
        try:
            user = self.login.find_one({"chat_id": chat_id})
            if user is not None:
                return user

            user = {
                "chat_id": chat_id,
                "login_school": [],
                "login_tg": [],
                "user_id": [],
            }
            self.login.insert_one(user)
            self.increment_users()
            return user
        except Exception as e:
            logger.error(f"Ошибка при получении пользователя: {e}")
            return None

    def set_user(self, chat_id, update):
        try:
            self.login.update_one({"chat_id": chat_id}, {"$set": update})
            logger.info(f"Данные пользователя {chat_id} обновлены.")
        except Exception as e:
            logger.error(f"Ошибка при обновлении пользователя: {e}")

    def delete_user(self, user_id):
        try:
            self.login.delete_one({"user_id": user_id})
            logger.info(f"Пользователь {user_id} удален.")
        except Exception as e:
            logger.error(f"Ошибка при удалении пользователя: {e}")

    def increment_bot_requests(self):
        self._increment_requests("bot_requests_this_month")

    def increment_group_requests(self):
        self._increment_requests("group_requests_this_month")

    def _increment_requests(self, field_name):
        try:
            if not self.users.find_one({"month": current_month}):
                self.users.insert_one({
                    "total_users": self.login.count_documents({}),
                    "new_users_this_month": 0,
                    "total_requests": 0,
                    "requests_this_month": 0,
                    "bot_requests_this_month": 0,
                    "group_requests_this_month": 0,
                    "month": current_month
                })
                logger.info("Создана новая запись для текущего месяца.")

            result = self.users.update_one(
                {"month": current_month},
                {
                    "$inc": {
                        "total_requests": 1,
                        "requests_this_month": 1,
                        field_name: 1
                    }
                }
            )
            if result.modified_count > 0:
                logger.info(f"Запросы успешно обновлены для {field_name}.")
            else:
                logger.warning(f"Запросы не были обновлены для {field_name}.")
        except Exception as e:
            logger.error(f"Ошибка при обновлении запросов: {e}")

    def increment_users(self):
        try:
            result = self.users.update_one(
                {"month": current_month},
                {"$inc": {"new_users_this_month": 1}}
            )
            if result.modified_count > 0:
                logger.info("Количество новых пользователей обновлено.")
            else:
                logger.warning("Не удалось обновить количество новых пользователей.")
        except Exception as e:
            logger.error(f"Ошибка при обновлении количества новых пользователей: {e}")

    def get_stats(self):
        total_users = self.login.count_documents({})
        stats = self.users.find_one({"month": current_month})

        if stats:
            stats["total_users"] = total_users
            if "bot_requests_this_month" not in stats:
                stats["bot_requests_this_month"] = 0
            if "group_requests_this_month" not in stats:
                stats["group_requests_this_month"] = 0
        else:
            stats = {
                "total_users": total_users,
                "new_users_this_month": 0,
                "total_requests": 0,
                "requests_this_month": 0,
                "bot_requests_this_month": 0,
                "group_requests_this_month": 0,
                "month": current_month
            }
            self.users.insert_one(stats)
            logger.info("Создана новая запись статистики для текущего месяца.")

        return stats

    def export_users_to_excel(self, file_path):
        try:
            users = self.login.find({})
            df = pd.DataFrame(list(users))
            df.to_excel(file_path, index=False)
            logger.info("Данные пользователей экспортированы в Excel.")
        except Exception as e:
            logger.error(f"Ошибка при экспорте пользователей в Excel: {e}")


db = DataBase()

@bot.message_handler(commands=['stat'])
def handle_stat(message):
    try:
        if str(message.from_user.id) == os.getenv("Your_user_ID"):
            stats = db.get_stats()
            if stats:
                stat_message = (f"Общее количество пользователей: {stats['total_users']}\n"
                                f"Новых пользователей в этом месяце: {stats['new_users_this_month']}\n"
                                f"Общее количество запросов: {stats['total_requests']}\n"
                                f"Запросов в этом месяце: {stats['requests_this_month']}\n"
                                f"Запросов из бота в этом месяце: {stats['bot_requests_this_month']}\n"
                                f"Запросов из группы в этом месяце: {stats['group_requests_this_month']}")
                bot.send_message(message.chat.id, stat_message)
            else:
                bot.send_message(message.chat.id, "Статистика недоступна.")
            logger.info("Команда /stat успешно обработана.")
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /stat: {e}")

@bot.message_handler(commands=['log'])
def handle_log(message):
    try:
        if str(message.from_user.id) == os.getenv("Your_user_ID"):
            with open(logFile, "rb") as file:
                bot.send_document(message.chat.id, file)
            logger.info("Команда /log успешно обработана.")
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /log: {e}")
        
@bot.message_handler(commands=['user'])
def handle_user(message):
    try:
        if str(message.from_user.id) == os.getenv("Your_user_ID"):
            file_path = "users_data.xlsx"
            db.export_users_to_excel(file_path)
            with open(file_path, "rb") as file:
                bot.send_document(message.chat.id, file)
            logger.info("Команда /user успешно обработана.")
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /user: {e}")

# Функция для установки команд в меню
def set_bot_commands():
    # Команды, доступные в личных сообщениях
    private_commands = [
        BotCommand("start", "Старт"),
        BotCommand("help", "Помощь"),
        BotCommand("delete", "Удалить логин"),
    ]

    # Команды, доступные в группах
    group_commands = [
        BotCommand("start", "Старт"),
        BotCommand("help", "Помощь"),
        BotCommand("stop", "Остановить бота"),
        BotCommand("bot", "Найти логин"),
    ]

    # Установка команд для личных сообщений
    bot.set_my_commands(private_commands, scope=BotCommandScopeDefault())

    # Установка команд для группы
    for group_id in group_states.keys():
        bot.set_my_commands(group_commands, scope=BotCommandScopeChat(group_id))

# Вызов функции установки команд при старте бота
set_bot_commands()

# Обработка команды /start для установки команд в группах при первом запуске
@bot.message_handler(commands=['start'])
def handle_start(message):
    try:
        if message.chat.type == "private":
            db.increment_bot_requests()
            user_id = message.from_user.id
            user = db.login.find_one({"user_id": user_id})
            if user is not None and user.get("login_school"):
                bot.send_message(message.chat.id, 'Введи школьный или телеграм ник интересующего тебя пира.')
                bot.register_next_step_handler(message, callback)
            else:
                bot.send_message(message.chat.id, f'Привет, {message.from_user.first_name}, введи свой школьный ник')
                bot.register_next_step_handler(message, hi)
            logger.info("Команда /start успешно обработана.")
        elif message.chat.type in ["group", "supergroup"]:
            group_states[message.chat.id] = True
            bot.send_message(message.chat.id, "Бот активирован и теперь будет реагировать на обращения.")
            set_bot_commands()  # Установка команд для группы при активации бота
            logger.info(f"Бот активирован в группе {message.chat.title} ({message.chat.id})")
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /start: {e}")

def hi(message):
    try:
        logger.info(f"Пользователь {message.from_user.id} начал ввод школьного ника.")

        # Получение текста сообщения пользователя в нижнем регистре
        text = message.text.lower().strip()

        # Проверка на кириллицу или начало с символа "/"
        if re.search('[а-яА-Я]', text) or text.startswith('/'):
            logger.warning(f"Пользователь {message.from_user.id} ввел некорректные данные: {text}")
            bot.send_message(message.chat.id, 'Неверно введены данные, пожалуйста, введи свой школьный ник.')
            bot.register_next_step_handler(message, hi)  # Ожидаем нового ввода
        else:
            login_school = text
            login_tg = message.from_user.username.lower().strip() if message.from_user.username is not None else None
            user_id = message.from_user.id

            if login_tg is None:
                logger.warning(f"Пользователь {message.from_user.id} не имеет логина Telegram.")
                bot.send_message(message.chat.id, 'Для использования бота необходимо создать логин (имя пользователя) в настройках Telegram, это не сложно.')
            else:
                existing_user = db.login.find_one({"user_id": user_id})
                if existing_user:
                    logger.info(f"Пользователь {message.from_user.id} уже существует. Обновляем данные.")
                    db.login.update_one({"user_id": user_id}, {"$set": {"login_school": login_school, "login_tg": login_tg}})
                    bot.send_message(message.chat.id, 'Ваши данные обновлены.')
                else:
                    logger.info(f"Пользователь {message.from_user.id} добавлен в базу данных.")
                    db.login.insert_one({"login_school": login_school, "login_tg": login_tg, "user_id": user_id})
                    bot.send_message(message.chat.id, 'Ваши данные сохранены.')

                bot.send_message(message.chat.id, 'Введи школьный или телеграм ник интересующего тебя пира.')
                bot.register_next_step_handler(message, callback)

    except Exception as e:
        logger.error(f"Ошибка в функции hi для пользователя {message.from_user.id}: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка, попробуйте снова.")

@bot.message_handler(commands=['stop'])
def handle_stop(message):
    try:
        if message.chat.type in ["group", "supergroup"]:
            group_states[message.chat.id] = False
            bot.send_message(message.chat.id, "Бот деактивирован и больше не будет реагировать на обращения, кроме команды /start.")
            logger.info(f"Бот деактивирован в группе {message.chat.title} ({message.chat.id})")
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /stop: {e}")

@bot.message_handler(commands=['delete'])
def handle_delete(message):
    try:
        if message.chat.type == "private":
            db.increment_bot_requests()
            user_id = message.from_user.id
            user = db.login.find_one({"user_id": user_id})
            if user:
                confirm_message = "Ты точно хочешь удалить свой логин?"
                confirm_keyboard = types.InlineKeyboardMarkup()
                yes_button = types.InlineKeyboardButton("Да", callback_data='confirm_yes')
                no_button = types.InlineKeyboardButton("Нет", callback_data='confirm_no')
                confirm_keyboard.row(yes_button, no_button)
                bot.send_message(message.chat.id, confirm_message, reply_markup=confirm_keyboard)
            else:
                bot.send_message(message.chat.id, 'Ты ещё не зарегистрирован.')
            logger.info("Команда /delete успешно обработана.")
        else:
            bot.send_message(message.chat.id, 'Эта команда доступна только в личных сообщениях.')
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /delete: {e}")


@bot.message_handler(commands=['bot'])
def handle_bot(message):
    try:
        if message.chat.type in ["group", "supergroup"]:
            if group_states.get(message.chat.id, False):
                db.increment_group_requests()
                parts = message.text.split()

                if len(parts) == 2:
                    login = parts[1].strip().lower()

                    if login.startswith('@'):
                        login = login[1:]

                    result = find_login(login)
                    if result is None:
                        bot.send_message(message.chat.id, "Логин не найден")
                    else:
                        text = f"Login school: {result[0].capitalize()}, login tg: @{result[1].capitalize()}"
                        bot.send_message(message.chat.id, text, parse_mode='HTML')
                else:
                    logger.info("Команда /bot обработана без ответа.")
                    # bot.send_message(message.chat.id, 'Пожалуйста, используйте команду в формате: /bot <логин>')
                logger.info("Команда /bot успешно обработана.")
            else:
                logger.info(f"Бот не активен в группе {message.chat.title} ({message.chat.id}), команда /bot проигнорирована.")
        else:
            bot.send_message(message.chat.id, 'Эта команда доступна только в группах.')
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /bot: {e}")

@bot.message_handler(commands=['help'])
def handle_help(message):
    try:
        db.increment_bot_requests()
        
        if message.chat.type == "private":
            # Ответ для личных сообщений
            help_text = (
                "Привет! Я бот для поиска пользователей по школьному или телеграм нику.\n\n"
                "Чтобы начать, введи команду /start и следуй инструкциям.\n\n"
                "Чтобы удалить логин, введи команду /delete. В дальнейшем по команде /start ты сможешь создать новый логин.\n\n"
                "Если у тебя возникли вопросы или проблемы - обратись к администратору @kaoekb."
            )
        elif message.chat.type in ["group", "supergroup"]:
            # Ответ для групп
            help_text = (
                "Привет! Я бот для поиска пользователей по школьному или телеграм нику.\n\n"
                "В группе вы можете использовать команду /bot <логин>, чтобы получить информацию о пользователе.\n\n"
                "Чтобы активировать бота в группе, используйте команду /start.\n"
                "Чтобы деактивировать бота в группе, используйте команду /stop.\n"
                "Для добавления нового логина, перейдите в личные сообщения бота и введите команду /start.\n\n"
            )

        bot.send_message(message.chat.id, help_text)
        logger.info(f"Команда /help успешно обработана в {'группе' if message.chat.type in ['group', 'supergroup'] else 'личных сообщениях'}.")
    
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /help: {e}")

@bot.callback_query_handler(func=lambda call: True)
def handle_confirmation(call):
    try:
        user_id = call.from_user.id
        if call.data == 'confirm_yes':
            db.delete_user(user_id)
            bot.send_message(call.message.chat.id, 'Твоя запись удалена из базы данных.')
        elif call.data == 'confirm_no':
            bot.send_message(call.message.chat.id, 'Отменено.')
        logger.info("Запрос подтверждения успешно обработан.")
    except Exception as e:
        logger.error(f"Ошибка при обработке подтверждения: {e}")

@bot.message_handler(content_types=['text'])
def callback(message):
    try:
        if message.chat.type == "private":
            # Проверяем, является ли сообщение командой
            if message.text.startswith('/'):
                # Если это команда, не обрабатываем ее как текст, просто выходим из функции
                return

            db.increment_bot_requests()
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
                bot.send_message(message.chat.id, "Логин не найден. Попробуйте снова или введите другой ник.")
                bot.register_next_step_handler(message, callback)  # Ожидаем нового ввода
            else:
                text = f"Login school: <a href='https://edu.21-school.ru/profile/{result[0].lower()}@student.21-school.ru'>{result[0].capitalize()}</a>, login tg: @{result[1].capitalize()}"
                bot.send_message(message.chat.id, text, parse_mode='HTML')
                bot.send_message(message.chat.id, 'Введи школьный или телеграм ник интересующего тебя пира.')
                bot.register_next_step_handler(message, callback)
            logger.info("Сообщение успешно обработано.")
    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения: {e}")


def find_login(login):
    try:
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
            db.login.update_one(
                {"_id": result["_id"]},
                {"$set": {"last_access_date_int": current_date}},
                upsert=True
            )
            return login_school, login_tg
    except Exception as e:
        logger.error(f"Ошибка при поиске логина: {e}")
        return None

def polling_with_retries(bot, num_retries=5, delay=5):
    for _ in range(num_retries):
        try:
            bot.polling()
            break
        except ApiTelegramException as e:
            if "502" in str(e):
                logger.warning("Получена ошибка 502. Повторная попытка через несколько секунд...")
                time.sleep(delay)
                continue
            else:
                raise e

# Запуск бота с повторными попытками
polling_with_retries(bot)
