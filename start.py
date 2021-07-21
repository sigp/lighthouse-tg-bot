#!/usr/bin/env python
# pylint: disable=C0116,W0613
# This program is dedicated to the public domain under the CC0 license.

"""
Simple Bot to send timed Telegram messages.
This Bot uses the Updater class to handle the bot and the JobQueue to send
timed messages.
First, a few handler functions are defined. Then, those functions are passed to
the Dispatcher and registered at their respective places.
Then, the bot is started and runs until we press Ctrl-C on the command line.
Usage:
Basic Alarm Bot example, sends a message after a set time.
Press Ctrl-C on the command line or send a signal to the process to stop the
bot.
"""

import logging
import os

from telegram import Update, Message
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackContext,
    PicklePersistence
)

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)


# Define a few command handlers. These usually take the two arguments update and
# context. Error handlers also receive the raised TelegramError object in error.
# Best practice would be to replace context with an underscore,
# since context is an unused local variable.
# This being an example and not having context present confusing beginners,
# we decided to have it present as context.
def start(update: Update, context: CallbackContext) -> None:
    """Sends explanation on how to use the bot."""
    update.message.reply_text('Hi! Use /subscribe <password> to get notifications')


def update(context: CallbackContext) -> None:
    if "chat_ids" in context.bot_data.keys():
        chat_ids = context.bot_data['chat_ids']
        for chat_id in chat_ids:
            context.bot.send_message(chat_id, "ping")


def subscribe(update: Update, context: CallbackContext) -> None:
    try:
        password = os.environ['BOT_PASSWORD']
        if password == "":
            update.message.reply_text("Refusing to subscribe without BOT_PASSWORD")
            return

        supplied_password = str(context.args[0])
        if supplied_password != password:
            update.message.reply_text("Invalid password")
            return

        if "chat_ids" not in context.bot_data.keys():
            context.bot_data['chat_ids'] = set()
        context.bot_data['chat_ids'].add(update.message.chat_id)

        update.message.reply_text("You are subscribed")
    except (IndexError, ValueError):
        update.message.reply_text('Usage: /subscribe <password>')


def unsubscribe(update: Update, context: CallbackContext) -> None:
    if "chat_ids" in context.bot_data.keys():
        chat_ids = context.bot_data['chat_ids']
        chat_id = update.message.chat_id
        if chat_id in chat_ids:
            update.message.reply_text("You are unsubscribed")
            chat_ids.remove(update.message.chat_id)
            return

    update.message.reply_text("You were not subscribed")


def main() -> None:
    """Run bot."""
    persistence = PicklePersistence(filename='bot-db')
    token = os.environ['TG_TOKEN']
    # Create the Updater and pass it your bot's token.
    updater = Updater(token, persistence=persistence)

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # on different commands - answer in Telegram
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", start))
    dispatcher.add_handler(CommandHandler("subscribe", subscribe))
    dispatcher.add_handler(CommandHandler("unsubscribe", unsubscribe))

    # Start a task to poll the beacon node
    updater.job_queue.run_repeating(update, 10)

    # Start the Bot
    updater.start_polling()

    # Block until you press Ctrl-C or the process receives SIGINT, SIGTERM or
    # SIGABRT. This should be used most of the time, since start_polling() is
    # non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
