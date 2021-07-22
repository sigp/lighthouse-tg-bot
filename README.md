# Lighthouse Validator Performance Telegram Bot

[timerbot.py]: https://github.com/python-telegram-bot/python-telegram-bot/blob/master/examples/timerbot.py
[DictPersistence]: https://python-telegram-bot.readthedocs.io/en/stable/telegram.ext.dictpersistence.html

This repository contains a Telegram bot which will send a messages to alert
users of validator activity.

## Cavets

This project is under-development and **not production-ready**.

Presently, this only works with the following branch of Lighthouse
https://github.com/sigp/lighthouse/pull/2416. No other clients are supported at
this stage.

## Features

This bot is based off the [timerbot.py] example and provides:

- A password-protected `/subscribe` method.
- Persistence between process instantiations via [DictPersistence].
- Interval-based polling of a Lighthouse Beacon Node.

## Usage

To create a bot and obtain a `telegram_token`, see the [Telegram Bot Documentation].

1. Clone this repository.
1. `cp default-config.yaml config.yaml`
1. Edit `config.yaml` to suit your setup.
1. `python start.py config.yaml`

The bot is ready. Send it a Telegram message with `/start` to get started.

## Notifications

The current notifications are provided:

- When a validator casts a head-vote which does not align with a
    super-majority.
- When a validator is active but fails to have an attestation included.


