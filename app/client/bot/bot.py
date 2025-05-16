import telebot
from dotenv import load_dotenv
import os
import codecs

# Создание объекта бота
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')

if BOT_TOKEN:
    BOT_TOKEN = codecs.decode(BOT_TOKEN, 'unicode_escape')

bot = telebot.TeleBot(BOT_TOKEN)