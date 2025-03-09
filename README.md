# Telegram Message Forwarding Bot

A simple, efficient, and elegant Telegram bot for forwarding messages from specified channels to destination channels with text processing rules. Only admins or super admins can manage the bot.

## Features
- Forward messages from origin channels to destination channels.
- Process messages by replacing Chinese descriptions with English (e.g., "发布新推文" -> "posted a new tweet").
- Admin management (add/remove admins, super admin only for adding).
- Pause/resume message forwarding.
- Show bot status and configurations.

## Command List
1. set_origin - Set/Overwrite the Origin Channel ID (-123123 -123123)
2. set_destination - Set/Overwrite the Sending Channel ID (-123123 -123123)
3. add_admin - Add New Admin (John_doe)
4. rm_admin - Remove Existing Admin
5. pause - Pause the current bot
6. resume - Resume Bot
5. status - Show all configs

## Prerequisites
- Python 3.8+
- Telegram Bot Token (obtain from @BotFather on Telegram)
- Super admin Telegram usernames (comma-separated in `.env`)

## Installation

1. Clone the repository or download the code.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt

## Logging
- The bot logs critical operations (commands, message forwarding, errors) to a `bot.log` file and console, ignoring `getUpdates` logs for clarity.
- Check `bot.log` for debugging or monitoring.

## Initial Status
- Upon startup, the bot prints its initial configuration (token, admins, channels, status) to the console for quick verification.