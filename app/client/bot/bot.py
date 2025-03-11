import telebot

from dotenv import load_dotenv
import os

# Создание объекта бота
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)