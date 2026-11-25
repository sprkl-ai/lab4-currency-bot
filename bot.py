from getpass import getpass
from os import getenv

import httpx
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from rates import get_rate


HELP = "Введи пару валют, например USD EUR или /rate EUR GBP."


async def start(update, context):
    await update.message.reply_text(HELP)


async def rate(update, context):
    parts = context.args if context.args is not None else update.message.text.split()
    if len(parts) != 2:
        await update.message.reply_text(HELP)
        return
    base, quote = (code.upper() for code in parts)
    if any(len(code) != 3 or not code.isascii() or not code.isalpha() for code in (base, quote)):
        await update.message.reply_text("Код валюты должен состоять из трёх латинских букв.")
        return
    try:
        value, date = await get_rate(base, quote)
    except httpx.HTTPStatusError as error:
        message = "Пара валют недоступна." if error.response.status_code == 404 else "Сервис курсов недоступен."
    except (httpx.RequestError, ValueError, KeyError, TypeError):
        message = "Не удалось получить курс. Попробуй позже."
    else:
        message = f"1 {base} = {value:g} {quote}\nДата курса: {date}"
    await update.message.reply_text(message)


def main():
    token = getenv("TELEGRAM_BOT_TOKEN") or getpass("Токен Telegram: ")
    if not token.strip():
        raise SystemExit("Токен не указан.")
    app = Application.builder().token(token.strip()).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("rate", rate))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, rate))
    app.run_polling()


if __name__ == "__main__":
    main()
