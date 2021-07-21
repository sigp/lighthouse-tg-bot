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
import requests
import json
import yaml
import sys

from telegram import Update, Message, ParseMode
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

SLOTS_PER_EPOCH = 32
POLL_TIME = 30
EPOCH_LOOKBACK=2

# Testing variables.
EVERYTHING_OK_ALARM=False  # Set to False for production.
ONCE_PER_EPOCH=True    # Set to True for production.


# Define a few command handlers. These usually take the two arguments update and
# context. Error handlers also receive the raised TelegramError object in error.
# Best practice would be to replace context with an underscore,
# since context is an unused local variable.
# This being an example and not having context present confusing beginners,
# we decided to have it present as context.
def start(update: Update, context: CallbackContext) -> None:
    """Sends explanation on how to use the bot."""
    update.message.reply_text('Hi! Use /subscribe <password> to get notifications')


def get_current_epoch(bn_api: str) -> int:
    r = requests.get(bn_api + "/eth/v1/beacon/headers/head");
    slot = int(r.json()['data']['header']['message']['slot'])
    return slot // SLOTS_PER_EPOCH

def message_with_json(message, json_data) -> str:
    return "{}\n\n```json\n{}\n```".format(
        message,
        json.dumps(json_data, indent=1)
    )

def process_performance_data(bn_api, epoch, context: CallbackContext) -> [str]:
    if epoch < EPOCH_LOOKBACK:
        return
    else:
        epoch -= EPOCH_LOOKBACK

    data = context.bot_data["validator_indices"]
    url = "{}/lighthouse/attestation_performance/{}".format(bn_api, epoch)
    print(url)
    r = requests.post(url, json=data);
    response = r.json()
    messages = []
    for v in response:
        index = v["validator_index"]
        if not v["is_optimal"]:
            messages.append(message_with_json(
                "🤒 Validator {} suboptimal in epoch {} 🤒".format(index, epoch),
                v
            ))
        else:
            if EVERYTHING_OK_ALARM:
                messages.append(message_with_json(
                    "🚀 Validator {} optimal in epoch {} 🚀".format(index, epoch),
                    v
                ))
    return messages


def poll_epoch(context: CallbackContext) -> None:
    chat_ids = context.bot_data['chat_ids']
    bn_api = context.bot_data['bn_api']
    try:
        current_epoch = get_current_epoch(bn_api)
        if current_epoch > context.bot_data['head_epoch']:
            if ONCE_PER_EPOCH == True:
                context.bot_data['head_epoch'] = current_epoch
            messages = process_performance_data(bn_api, current_epoch, context)
            for message in messages:
                for chat_id in chat_ids:
                    context.bot.send_message(chat_id, message, parse_mode=ParseMode.MARKDOWN_V2)
    except Exception as e:
        for chat_id in chat_ids:
            context.bot.send_message(
                chat_id,
                "Error polling epoch {}: {}".format(current_epoch, e)
            )
        raise e


def subscribe(update: Update, context: CallbackContext) -> None:
    try:
        password = context.bot_data['password']
        if password == "":
            update.message.reply_text("Refusing to subscribe without bot_password")
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
    chat_ids = context.bot_data['chat_ids']
    chat_id = update.message.chat_id
    if chat_id in chat_ids:
        update.message.reply_text("You are unsubscribed")
        chat_ids.remove(update.message.chat_id)
    else:
        update.message.reply_text("You were not subscribed")


def main() -> None:
    config_path = sys.argv[1]
    with open(config_path, 'r') as stream:
        config = yaml.safe_load(stream)
        token = config['telegram_token']
        bn_api = config['bn_api']
        password = config['bot_password']
        validator_indices = config['validator_indices']

    """Run bot."""
    persistence = PicklePersistence(filename='bot-db')
    # Create the Updater and pass it your bot's token.
    updater = Updater(token, persistence=persistence)

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    if "chat_ids" not in dispatcher.bot_data.keys():
        dispatcher.bot_data['chat_ids'] = set()
    if "head_epoch" not in dispatcher.bot_data.keys():
        dispatcher.bot_data['head_epoch'] = 0
    dispatcher.bot_data['bn_api'] = os.environ['BN_API']
    dispatcher.bot_data['password'] = password
    dispatcher.bot_data['validator_indices'] = validator_indices

    # on different commands - answer in Telegram
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", start))
    dispatcher.add_handler(CommandHandler("subscribe", subscribe))
    dispatcher.add_handler(CommandHandler("unsubscribe", unsubscribe))

    # Start a task to poll the beacon node
    updater.job_queue.run_repeating(poll_epoch, 30)

    # Start the Bot
    updater.start_polling()

    # Block until you press Ctrl-C or the process receives SIGINT, SIGTERM or
    # SIGABRT. This should be used most of the time, since start_polling() is
    # non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
