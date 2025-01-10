import json
import logging
import os
import random
from datetime import datetime, timedelta

import pytz
import telebot
from telebot.types import InlineKeyboardButton as IKB
from telebot.types import InlineKeyboardMarkup as IKM
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.constants import ParseMode
from telegram.error import Forbidden
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import BOT_TOKEN_HAT as TOKEN_HAT
from config import BOT_TOKEN_HAT_ADMIN as TOKEN

HQ_ID = 151466050

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

PROCESSING_REQUEST, ASK_DETAILS, IM_IN = range(3)
HOURS = 4


async def send_base_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    button1 = InlineKeyboardButton(
        text="📝 Новый мастер-класс",
        callback_data="create_notification",
    )
    button2 = InlineKeyboardButton(
        text="📢 Отправить рассылку",
        callback_data="send_notification",
    )
    button3 = InlineKeyboardButton(
        text="✏️ Редактировать скрипт",
        callback_data="edit_script",
    )
    button4 = InlineKeyboardButton(
        text="🗑 Удалить скрипт",
        callback_data="delete_script",
    )

    buttons = [[button1], [button2], [button3], [button4]]
    reply_keyboard = InlineKeyboardMarkup(buttons)

    await context.bot.send_message(
        chat_id=context.user_data["user_id"],
        text=(
            "\nВыбери опцию:\n"
            ">> Назначить новый мастер-класс\n"
            ">> Отправить рассылку\n"
            ">> Редактировать скрипт\n"
            ">> Удалить черновик\n"
        ),
        parse_mode="HTML",
        reply_markup=reply_keyboard,
    )


async def choose_script():
    directory = f"{os.getcwd()}/scripts"
    files = os.listdir(directory)
    keyboard = []
    for file in files:
        if file.endswith(".txt"):
            keyboard.append(
                [
                    InlineKeyboardButton(
                        text=file.replace(".txt", ""),
                        callback_data=file,
                    )
                ]
            )
    return keyboard, InlineKeyboardMarkup(keyboard)


async def send_result(text="", job_id=""):
    with open(f"{os.getcwd()}/jobs/{job_id}/alarm.json", "r", encoding="utf-8") as file:
        alarm = json.load(file)

    subscribers = alarm["subscribed_users"]

    bot_hat = telebot.TeleBot(TOKEN_HAT)
    for user in subscribers:
        try:
            bot_hat.send_message(chat_id=user, text=text, parse_mode="HTML")
        except Exception as e:
            print(user, e)
            continue


async def send_notification(
    update: Update, context: ContextTypes.DEFAULT_TYPE, text="", user_data="", job_id=""
):
    bot_hat = telebot.TeleBot(TOKEN_HAT)

    reply_keyboard = IKM(
        [
            [
                IKB(text="🤩 Я буду!", callback_data=f"im_in_{job_id}"),
            ],
        ]
    )

    for user in user_data:
        try:
            bot_hat.send_message(chat_id=user, text=text, reply_markup=reply_keyboard)
        except Exception as e:
            print(user, e)
            continue

    return await set_alarms(update=update, context=context, job_id=job_id)


async def set_alarms(
    update: Update, context: ContextTypes.DEFAULT_TYPE, job_id: str = ""
) -> None:

    context.job_queue.run_once(
        run_hat,
        when=HOURS * 60 * 60,
        chat_id=None,
        name=job_id,
        data=context,
    )


async def run_hat(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the alarm message."""
    job = context.job
    job_id = job.data.chat_data["job_id"]

    with open(f"{os.getcwd()}/jobs/{job_id}/alarm.json", "r", encoding="utf-8") as file:
        alarm = json.load(file)

    with open(f"{os.getcwd()}/users/users.json", "r", encoding="utf-8") as file:
        user_data = json.load(file)

    subscribers = alarm["subscribed_users"]

    chosen_one = random.sample(subscribers, k=min(5, len(subscribers)))

    text = alarm["text"]
    text += "\n\n<b>Распределение участников:</b>\n\n"
    for user in chosen_one:
        mention_name = (
            f"{user_data[str(user)]['first_name']} {user_data[str(user)]['last_name']}"
        )
        text += f"<a href='tg://user?id={user}'>{mention_name} </a> \n"

    await send_result(text=text, job_id=job_id)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the conversation and ask user for input."""

    context.user_data.clear()
    context.chat_data.clear()

    context.user_data["user_id"] = update.effective_user.id
    context.user_data["user_name"] = update.effective_user.username
    context.user_data["effective_script"] = None
    context.user_data["script_name"] = None

    await update.message.reply_text(
        text=(
            f"Привет, {update.effective_user.first_name} {update.effective_user.last_name}! \nЭто Админка распределяющей шляпы для Мастер-Классов РХСЕ"
        ),
        parse_mode="HTML",
    )

    await send_base_message(update, context)

    return PROCESSING_REQUEST


async def processing_request(
    update: Update, context: ContextTypes.DEFAULT_TYPE, second_request=None
):

    context.user_data["first_step"] = update.callback_query.data
    keyboard = []
    text = ""

    if (
        update.callback_query.data == "create_notification"
        or second_request == "edit_script"
    ):

        context.user_data["first_step"] = "create_notification"

        text = (
            "Отправь следующим сообщением текст для рассылки\n\n"
            "<i>Например: Сочный, мощный, очный мастер-класс с Рахленко, 32.02.2099, с 17 до 22, по адресу Красная площать д.1, ауд.404</i>"
        )

        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=text, parse_mode="HTML"
        )

    if update.callback_query.data == "send_notification":

        with open(f"{os.getcwd()}/users/users.json", "r", encoding="utf-8") as file:
            user_data = json.load(file)

        count_users = len(user_data)

        keyboard, reply_markup = await choose_script()

        if keyboard == []:
            await update.callback_query.answer(
                text="Скрипты не найдены, создайте, пожалуйста, скрипт", show_alert=True
            )

            await send_base_message(update, context)

            return PROCESSING_REQUEST

        text = f"Выбери скрипт для отправки. Рассылка будет отправлена для {count_users} человек"

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )

    if update.callback_query.data == "confirm_send_notification":

        text = context.user_data["effective_script"]
        user_data = context.user_data["user_data"]
        subscribe = context.chat_data["subscribe"]
        job_id = context.chat_data["job_id"]

        with open(
            f"{os.getcwd()}/jobs/{job_id}/alarm.json",
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                {
                    "text": text,
                    "subscribe": subscribe,
                    "subscribed_users": [],
                    "subscriptions": [],
                },
                file,
                indent=4,
                ensure_ascii=False,
            )

        await send_notification(
            update=update,
            context=context,
            text=text,
            user_data=user_data,
            job_id=context.chat_data["job_id"],
        )

    if update.callback_query.data == "cancel_send_notification":

        await send_base_message(update, context)

        return PROCESSING_REQUEST

    if update.callback_query.data == "edit_script":

        keyboard, reply_markup = await choose_script()

        if keyboard == []:
            await update.callback_query.answer(
                text="Скрипты не найдены, создайте, пожалуйста, скрипт", show_alert=True
            )

            await send_base_message(update, context)

            return PROCESSING_REQUEST

        text = "Выбери скрипт для редактирования"

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )

    if update.callback_query.data == "delete_script":
        keyboard, reply_markup = await choose_script()

        if keyboard == []:
            await update.callback_query.answer(
                text="Скрипты не найдены, создайте, пожалуйста, скрипт", show_alert=True
            )

            await send_base_message(update, context)

            return PROCESSING_REQUEST

        text = "Выбери скрипт для удаления"

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )
    return ASK_DETAILS


async def ask_details(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if context.user_data["first_step"] == "create_notification":

        message = update.message.text

        try:
            filename = context.user_data["script_to_change"]
        except:
            filename = f"{(datetime.now(tz = pytz.UTC) + timedelta(hours=3)).strftime('%d.%m.%Y %H:%M')} {context.user_data['user_name']}.txt"

        with open(
            f"{os.getcwd()}/scripts/{filename}",
            "w",
            encoding="utf-8",
        ) as file:
            file.write(message)

        text = f"Скрипт сохранен под именем {filename}\n\n"

        await update.message.reply_text(text=text)

        await send_base_message(update, context)

        return PROCESSING_REQUEST

    if context.user_data["first_step"] == "send_notification":

        context.chat_data["job_id"] = (
            f"{update.effective_chat.id}_{int(datetime.now().timestamp())}"
        )

        os.makedirs(
            f"{os.getcwd()}/jobs/{update.effective_chat.id}_{int(datetime.now().timestamp())}",
            exist_ok=True,
        )

        directory = f"{os.getcwd()}/scripts"
        files = os.listdir(directory)

        for file in files:
            if file.endswith(".txt") and file == update.callback_query.data:
                with open(directory + "/" + file, "r", encoding="utf-8") as file:
                    text_to_send = file.read()
                break
            break

        with open(f"{os.getcwd()}/users/users.json", "r", encoding="utf-8") as file:
            user_data = json.load(file)

        context.user_data["effective_script"] = (
            text_to_send
            + f"\n\nРаспределение участников состоится автоматически <b>в {(datetime.now() + timedelta(hours = 3 + HOURS)).strftime('%d.%m.%Y, %H:%M:%S')}</b>"
        )
        context.user_data["user_data"] = user_data
        context.chat_data["subscribe"] = True

        reply_keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text="Подтвердить",
                        callback_data="confirm_send_notification",
                    ),
                    InlineKeyboardButton(
                        text="Отменить",
                        callback_data="cancel_send_notification",
                    ),
                ]
            ],
        )

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                "<i>Текст для рассылки будет выглядеть вот так:\n\n</i>"
                f"{text_to_send}"
                "\n\nНажми Подтвердить, чтобы отправить рассылку прямо сейчас или Отменить, чтобы вернуться в меню"
            ),
            parse_mode="HTML",
            reply_markup=reply_keyboard,
        )

        return PROCESSING_REQUEST

    if context.user_data["first_step"] == "edit_script":

        context.user_data["script_to_change"] = update.callback_query.data

        return await processing_request(
            update=update, context=context, second_request="edit_script"
        )

    if context.user_data["first_step"] == "delete_script":

        os.remove(f"{os.getcwd()}/scripts/{update.callback_query.data}")

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Скрипт {update.callback_query.data} удален",
            parse_mode="HTML",
        )

        await send_base_message(update, context)

        return PROCESSING_REQUEST


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
            PROCESSING_REQUEST: [
                CallbackQueryHandler(
                    processing_request,
                )
            ],
            ASK_DETAILS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_details),
                CallbackQueryHandler(ask_details, pattern=r"(.*)\.txt(.*)"),
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

    application.add_error_handler(error_handler, block=False)

    application.run_polling()


if __name__ == "__main__":
    main()
