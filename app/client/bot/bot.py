import telebot
from dotenv import load_dotenv
import os
import codecs
from app.client.config import ConfigError, require_env

# Создание объекта бота
load_dotenv()
try:
    BOT_TOKEN = require_env("BOT_TOKEN")
except ConfigError as exc:
    raise RuntimeError(str(exc)) from exc

if BOT_TOKEN:
    BOT_TOKEN = codecs.decode(BOT_TOKEN, 'unicode_escape')

bot = telebot.TeleBot(BOT_TOKEN)
