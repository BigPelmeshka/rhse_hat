import json
import logging
import os
from datetime import datetime, timedelta

import pytz
import pandas as pd
from src.gsheets import GoogleSheets
from telegram import ReplyKeyboardRemove, Update
from telegram.constants import ParseMode
from telegram.error import Forbidden
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import BOT_TOKEN_HAT as TOKEN

HQ_ID = 151466050

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

GET_URL, FINISH = range(2)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the conversation and ask user for input."""
    user_id = update.effective_user.id

    if (
        "_bot" in update.effective_user.username
        or "Bot" in update.effective_user.username
    ):
        await update.message.reply_text(
            text="Привет, бот! Извини, но я буду общаться только с человеком",
            parse_mode=ParseMode.HTML,
        )
        return ConversationHandler.END

    GS = GoogleSheets()
    authenticated_users = GS.get_authenticated_users()

    if str(update.message.from_user.username) not in [
        user[0] for user in authenticated_users
    ]:
        await update.message.reply_text(
            "Вы не авторизованы для использования бота. Обратитесь к своему менеджеру, чтобы вас внесли в список"
        )
        return ConversationHandler.END

    user = {
        "user_id": user_id,
        "username": update.effective_user.username,
        "first_name": update.effective_user.first_name,
        "last_name": update.effective_user.last_name,
    }

    context.user_data["user"] = user
    context.user_data["user_id"] = user_id

    with open(f"{os.getcwd()}/users/users.json", "r", encoding="utf-8") as file:
        user_data = json.load(file)

    if str(user["user_id"]) not in user_data:
        user_data[user_id] = user
        with open(f"{os.getcwd()}/users/users.json", "w", encoding="utf-8") as file:
            json.dump(user_data, file, indent=4, ensure_ascii=False)

    reply_keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text="🌥️ 1 задание",
                    callback_data=1,
                ),
                InlineKeyboardButton(
                    text="👻 2 задание",
                    callback_data=2,
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⭐️ 3 задание",
                    callback_data=3,
                ),
            ],
        ]
    )

    add_text = "Выбери этап домашнего задания, которое ты хочешь сдать: "

    await update.message.reply_text(
        text=(
            f"Привет, {update.effective_user.first_name} {update.effective_user.last_name}! Это бот для конкурса Мистер и Мисс РХСЕ 2025"
            "\n"
            f"{add_text}"
        ),
        parse_mode="HTML",
        reply_markup=reply_keyboard,
    )

    return GET_URL


async def get_url(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = context.user_data["user_id"]
    username = context.user_data["user"]["username"]
    choice = update.callback_query.data
    context.user_data["choice"] = choice

    GS = GoogleSheets()
    results = GS.get_results()

    for value in results:
        if (
            len(value) > 4
            and username in value[1]
            and value[2] == choice
            and value[4] == "1"
        ):
            text = f"К сожалению, мы уже оценили этот этап. Сосредоточься на других заданиях!"
            await context.bot.send_message(chat_id=user_id, text=text)
            return await cancel(update=update, context=context)

    text = f"Пришли ссылку на облачное хранилище с ответом на задание №{choice}"

    await context.bot.send_message(chat_id=user_id, text=text)

    return FINISH


async def finish(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = context.user_data["user_id"]
    context.user_data["result"] = update.message.text

    await update_google_history(context=context)

    text = f"Спасибо, задание принято!"

    await context.bot.send_message(chat_id=user_id, text=text)

    return await cancel(update=update, context=context)


async def update_google_history(context: ContextTypes.DEFAULT_TYPE):
    logger.warning("Updating Google History")
    data = {
        "Дата": datetime.now(tz=pytz.timezone("Europe/Moscow")).strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "Участник": context.user_data["user"]["username"],
        "Задание": context.user_data["choice"],
        "Ответ": context.user_data["result"],
    }

    google_df = pd.DataFrame([data])

    GS = GoogleSheets()
    GS.df_to_spreadsheets(google_df=google_df)

    logger.warning("Google History was updated")
    return True


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    bot = context.bot

    await bot.send_message(
        text=("До свидания 🫶\n" "Нажмите на /start, чтобы начать"),
        chat_id=context.user_data["user_id"],
        reply_markup=ReplyKeyboardRemove(),
    )

    context.user_data.clear()
    context.chat_data.clear()
    return ConversationHandler.END


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    # Log the error before we do anything else, so we can see it even if something breaks.
    logger.error("Exception while handling an update:", exc_info=context.error)

    message = "An exception was raised while handling an update\n"
    if type(context.error) == Forbidden:
        try:
            return await cancel(update=update, context=context)
        except:
            pass
        return True

    # Finally, send the message
    await context.bot.send_message(
        chat_id=HQ_ID, text=message, parse_mode=ParseMode.HTML
    )
    logger.info("=" * 80)
    logger.info(
        "Context Error: %s",
        context.error,
    )
    logger.info("=" * 80)

    return await cancel(update=update, context=context)


def main() -> None:
    """Run the bot."""
    application = Application.builder().token(TOKEN).concurrent_updates(True).build()
    # job_queue = application.job_queue

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
        ],
        states={
            GET_URL: [
                CallbackQueryHandler(get_url, block=False),
            ],
            FINISH: [
                MessageHandler(filters.ALL, finish, block=False),
            ],
        },
        fallbacks=[
            CommandHandler("skip", cancel),
        ],
        allow_reentry=True,
    )

    application.add_handler(conv_handler)

    # Handle the case when a user sends /start but they're not in a conversation
    application.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )
    application.add_handler(CommandHandler("skip", cancel))
    # application.add_handler(CallbackQueryHandler(im_in, pattern="im_in_(.*)"))

    application.add_error_handler(error_handler, block=False)

    application.run_polling()


if __name__ == "__main__":
    main()
