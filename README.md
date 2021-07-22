# Lighthouse Validator Performance Telegram Bot

[Telegram Bot Documentation]: https://core.telegram.org/bots

This repository contains a Telegram bot which will send a messages to alert
users of validator activity.

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


