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

# Configuration constants.
SLOTS_PER_EPOCH = 32
POLL_TIME = 30
EPOCH_LOOKBACK=2

# Testing variables.
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


# Request the current epoch from the beacon node.
def get_current_epoch(bn_api: str) -> int:
    r = requests.get(bn_api + "/eth/v1/beacon/headers/head");
    slot = int(r.json()['data']['header']['message']['slot'])
    return slot // SLOTS_PER_EPOCH

# Format a message with a text header and JSON footer.
def message_with_json(message, json_data) -> str:
    return "{}\n\n```json\n{}\n```".format(
        message,
        json.dumps(json_data, indent=1)
    )

# Request attestation performance data from the beacon node.
def get_performance_data(bn_api, epoch, indices):
    url = "{}/lighthouse/attestation_performance/{}".format(bn_api, epoch)
    r = requests.post(url, json=indices)
    return r.json()

# Translate perfomance data for a single validator into a list of messages.
def process_validator_performance_data(v, epoch) -> [str]:
    messages = []

    index = v["validator_index"]
    best_inclusion = v["best_inclusion"]
    eligible_to_attest = v["eligible_to_attest"]

    if best_inclusion is None:
        # Alert if the validator was active but failed to attest.
        if eligible_to_attest:
            messages.append("🚨 Validator {} missed an attestation in epoch {}!"
                           .format(index, epoch))
    else:
        head_vote = best_inclusion['head_vote']
        agreeing = int(head_vote['total_votes_agreeing'])
        disagreeing = int(head_vote['total_votes_disagreeing'])
        total = agreeing + disagreeing
        # Alert if the validator produced an attestation for a minority head
        # vote.
        if not agreeing * 3 >= total * 2:
            message = "😕 Validator {} did not  in epoch {} did not form a super\-majority\.".format(index, epoch)
            message += "\n\n```json\n{}\n```".format(json.dumps(head_vote,
                                                                indent=1))
            messages.append(message)

    return messages

# Translate data from the beacon node into a list of messages.
def process_performance_data(performance_data, epoch, context: CallbackContext) -> [str]:
    messages = []

    for v in performance_data:
        try:
            messages += process_validator_performance_data(v, epoch)
        except Exception as e:
            index = v["validator_index"]
            messages.append(
                "Error processing validator {}: {}".format(index, e)
            )
            # Note: we're not re-raising the error here. This prevents an error
            # with one validator preventing progress for all other validators.

    return messages

# Poll the beacon node for the current epoch and determine if an update is
# required.
def poll_performance_data(context: CallbackContext) -> None:
    chat_ids = context.bot_data['chat_ids']
    bn_api = context.bot_data['bn_api']
    indices = context.bot_data["validator_indices"]
    try:
        # Request the current epoch from the beacon node.
        current_epoch = get_current_epoch(bn_api)

        if current_epoch > context.bot_data['head_epoch']:
            # If enabled, de-bounce so we query once per epoch.
            if ONCE_PER_EPOCH == True:
                context.bot_data['head_epoch'] = current_epoch

            # Always request data for a prior epoch.
            if current_epoch < EPOCH_LOOKBACK:
                return
            else:
                request_epoch = current_epoch - EPOCH_LOOKBACK

            # Request data from the beacon node.
            performance_data = get_performance_data(bn_api, request_epoch, indices)
            # Translate beacon node data into messages.
            messages = process_performance_data(performance_data, request_epoch, context)

            # Send messages out to all subscribers.
            for message in messages:
                for chat_id in chat_ids:
                    context.bot.send_message(chat_id, message, parse_mode=ParseMode.MARKDOWN_V2)
    except Exception as e:
        # Update failed, send an error message to all subscribers.
        for chat_id in chat_ids:
            context.bot.send_message(
                chat_id,
                "Error polling epoch {}: {}".format(current_epoch, e)
            )
        raise e


# Allow a user to receive updates.
def subscribe(update: Update, context: CallbackContext) -> None:
    try:
        password = context.bot_data['password']
        # Do not allow an empty password.
        if password == "":
            update.message.reply_text("Refusing to subscribe without bot_password")
            return

        # Validate password.
        supplied_password = str(context.args[0])
        if supplied_password != password:
            update.message.reply_text("Invalid password")
            return

        # Subscribe chat id, regardless of an existing subscription.
        context.bot_data['chat_ids'].add(update.message.chat_id)
        update.message.reply_text("You are subscribed")
    except (IndexError, ValueError):
        update.message.reply_text('Usage: /subscribe <password>')


# Allow a user to stop receiving updates.
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

    # Start a task to poll the beacon node for performance data.
    updater.job_queue.run_repeating(poll_performance_data, 30)

    # Start the Bot
    updater.start_polling()

    # Block until you press Ctrl-C or the process receives SIGINT, SIGTERM or
    # SIGABRT. This should be used most of the time, since start_polling() is
    # non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
