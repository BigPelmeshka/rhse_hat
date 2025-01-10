import json
import logging
import os
from datetime import datetime, timedelta

import pytz
from telegram import ReplyKeyboardRemove, Update
from telegram.constants import ParseMode
from telegram.error import Forbidden
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
)

from config import BOT_TOKEN_HAT as TOKEN

HQ_ID = 151466050

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

IM_IN, TEST = range(2)


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

    user = {
        "user_id": user_id,
        "username": update.effective_user.username,
        "first_name": update.effective_user.first_name,
        "last_name": update.effective_user.last_name,
        "created_at": datetime.now(pytz.timezone("Europe/Moscow")).strftime(
            "%d.%m.%Y %H:%M:%S"
        ),
    }

    with open(f"{os.getcwd()}/users/users.json", "r", encoding="utf-8") as file:
        user_data = json.load(file)

    if str(user["user_id"]) not in user_data:
        user_data[user_id] = user
        with open(f"{os.getcwd()}/users/users.json", "w", encoding="utf-8") as file:
            json.dump(user_data, file, indent=4, ensure_ascii=False)

        add_text = "Ты успешно зарегистрирован/а в системе, жди сообщения о наборе желающих на мастер-класс!"
    else:
        add_text = "Ты уже в системе, жди сообщения о наборе желающих на мастер-класс!"

    await update.message.reply_text(
        text=(
            f"Привет, {update.effective_user.first_name} {update.effective_user.last_name}! Это распределяющая шляпа для Мастер-Классов РХСЕ"
            "\n"
            f"{add_text}"
        ),
        parse_mode="HTML",
    )


async def im_in(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.callback_query.from_user.id
    job_id = update.callback_query.data.replace("im_in_", "")

    with open(
        f"{os.getcwd()}/jobs/{job_id}/alarm.json",
        "r",
        encoding="utf-8",
    ) as file:
        alarm = json.load(file)

    subscription = {"user": chat_id, "date": int(datetime.now().timestamp())}

    if chat_id not in alarm["subscribed_users"]:
        alarm["subscribed_users"].append(chat_id)
        alarm["subscriptions"].append(subscription)

        with open(
            f"{os.getcwd()}/jobs/{job_id}/alarm.json",
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(alarm, file, indent=4, ensure_ascii=False)

    await context.bot.send_message(chat_id=chat_id, text=f"Отлично! Жди распределения!")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    bot = context.bot

    await bot.send_message(
        text=("До свидания 🫶\n" "Нажмите на /start, чтобы начать"),
        chat_id=update.effective_chat.id,
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
            IM_IN: [
                CallbackQueryHandler(im_in, pattern="im_in_(.*)"),
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
    application.add_handler(CallbackQueryHandler(im_in, pattern="im_in_(.*)"))

    application.add_error_handler(error_handler, block=False)

    application.run_polling()


if __name__ == "__main__":
    main()
