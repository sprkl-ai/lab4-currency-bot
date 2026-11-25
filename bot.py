import sqlite3
from contextlib import closing
from getpass import getpass
from os import getenv
from pathlib import Path

import httpx
from telegram import ReplyKeyboardMarkup, Update
from telegram.error import InvalidToken, NetworkError, TelegramError
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from rates import get_rate


DB = Path(__file__).with_name("settings.sqlite3")
FAVORITE = "Мой курс"
HELP = (
    "Введи пару валют, например USD EUR или /rate EUR GBP.\n"
    "/set USD EUR — запомнить пару.\n"
    "/my или кнопка «Мой курс» — показать курс сохранённой пары."
)


def favorite_pair(user_id, pair=None):
    with closing(sqlite3.connect(DB)) as db, db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS favorites "
            "(user_id INTEGER PRIMARY KEY, base TEXT, quote TEXT)"
        )
        if pair is not None:
            db.execute("INSERT OR REPLACE INTO favorites VALUES (?, ?, ?)", (user_id, *pair))
            return pair
        return db.execute("SELECT base, quote FROM favorites WHERE user_id = ?", (user_id,)).fetchone()


async def start(update, context):
    keyboard = ReplyKeyboardMarkup([[FAVORITE]], resize_keyboard=True)
    await update.message.reply_text(HELP, reply_markup=keyboard)


async def rate(update, context):
    text = update.message.text.split()
    command = text[0].split("@", 1)[0].lower() if context.args is not None else ""
    user_id = update.effective_user.id
    try:
        parts = context.args if context.args is not None else text
        if command == "/my" or update.message.text.strip() == FAVORITE:
            parts = favorite_pair(user_id)
            if parts is None:
                await update.message.reply_text("Сначала сохрани пару командой /set USD EUR.")
                return
        if len(parts) != 2:
            await update.message.reply_text(HELP)
            return
        base, quote = (code.upper() for code in parts)
        if any(len(code) != 3 or not code.isascii() or not code.isalpha() for code in (base, quote)):
            await update.message.reply_text("Код валюты должен состоять из трёх латинских букв.")
            return
        if base == quote:
            await update.message.reply_text("Выбери две разные валюты.")
            return
        value, date = await get_rate(base, quote)
        message = f"1 {base} = {value:g} {quote}\nДата курса: {date}"
        if command == "/set":
            favorite_pair(user_id, (base, quote))
            message = f"Сохранена пара {base}/{quote}.\n{message}"
    except httpx.HTTPStatusError as error:
        if error.response.status_code in (400, 404, 422):
            message = "Пара валют недоступна."
        else:
            message = "Сервис курсов недоступен."
    except (httpx.RequestError, ValueError, KeyError, TypeError):
        message = "Не удалось получить курс. Попробуй позже."
    except sqlite3.Error:
        message = "Не удалось прочитать или сохранить настройки."
    await update.message.reply_text(message)


async def on_error(update, context):
    print("Ошибка Telegram:", type(context.error).__name__)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text("Не удалось обработать сообщение.")
        except TelegramError:
            pass


def main():
    token = getenv("TELEGRAM_BOT_TOKEN") or getpass("Токен Telegram: ")
    if not token.strip():
        raise SystemExit("Токен не указан.")
    private = filters.ChatType.PRIVATE
    try:
        app = Application.builder().token(token.strip()).build()
        app.add_handler(CommandHandler(["start", "help"], start, private))
        app.add_handler(CommandHandler(["rate", "set", "my"], rate, private))
        app.add_handler(MessageHandler(private & filters.TEXT & ~filters.COMMAND, rate))
        app.add_error_handler(on_error)
        app.run_polling(allowed_updates=["message"])
    except InvalidToken:
        raise SystemExit("Проверь токен Telegram.") from None
    except NetworkError:
        raise SystemExit("Не удалось подключиться к Telegram.") from None


if __name__ == "__main__":
    main()
