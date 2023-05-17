import telebot
import sqlite3
from config import Token_tg 

bot = telebot.TeleBot(Token_tg)

@bot.message_handler(commands=['start'])
def handle_start(message):
    # Подключение к базе данных SQLite3
    conn = sqlite3.connect('bd.sql') # Метод connect() модуля sqlite3 используется для подключения к базе данных SQLite.
    cur = conn.cursor() # Получив объект-курсор, можно использовать его методы для выполнения операторов SQL
    cur.execute('CREATE TABLE IF NOT EXISTS users(id int auto_increment primary key, login_school varchar(10), login_tg varchar(20) )') # Если таблица не была созданна, создаеем со следующими столбцами id, login_school и login_tg
    conn.commit() # Применяем изменения
    cur.close()
    conn.close()
    
    bot.send_message(message.chat.id, f'привет, {message.from_user.first_name}, введи свой школьный ник')
    bot.register_next_step_handler(message, hi)

def hi(message): # определение функции 'hi', которая принимает сообщение от пользователя в качестве параметра.

    # user_data = {'id': message.chat.id, 'login_school': message.text.lower(), 'login_tg': message.from_user.username} #  создание словаря, который 'user_data', содержит идентификатор чата, школьный логин и логин пользователя Telegram.
    # with open('text.txt', 'a') as f: # открытие файла 'text.txt' в режиме добавления и записи в него строкового представления словаря 'данные пользователя'.
    #     f.write(str(user_data) + '\n')

    login_school = message.text.lower()
    login_tg = message.from_user.username.lower()
    
    conn = sqlite3.connect('bd.sql')
    cur = conn.cursor()
    cur.execute("INSERT INTO users (login_school, login_tg) VALUES ('%s', '%s')" % ( login_school, login_tg))
    conn.commit()
    cur.close()
    conn.close()
    
    bot.send_message(message.chat.id, 'Успешный успех!')
    bot.send_message(message.chat.id, 'Введи школьный или телеграм ник.')
    bot.register_next_step_handler(message, callback)


@bot.message_handler(content_types=['text'])

def callback(call):
    conn = sqlite3.connect('bd.sql')
    cur = conn.cursor()
    user_name = call.text

    cur.execute("SELECT login_tg, login_school FROM users WHERE login_school=?", (user_name,))
    users = cur.fetchall()
    info = ''
    if users:
        for el in users:
            info = f'Login school: {el[1].capitalize()}, login Tg: @{el[0].capitalize()}\n'
    else:
        cur.execute("SELECT login_tg, login_school FROM users WHERE login_tg=?", (user_name,))
        users = cur.fetchall()
        if users:
            for el in users:
                info = f'Login school: {el[1].capitalize()}, login Tg: @{el[0].capitalize()}\n'
        else:
            info = 'Пользователь не обнаружен'

    cur.close()
    conn.close()
    bot.send_message(call.chat.id, info)
    bot.register_next_step_handler(call, callback)

bot.polling()