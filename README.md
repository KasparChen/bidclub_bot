# Telegram Message Forwarding Bot

A simple, efficient, and elegant Telegram bot for forwarding messages from specified channels to destination channels with text processing rules. Only admins or super admins can manage the bot.

## Features
- Forward messages from origin channels to destination channels.
- Process messages by replacing Chinese descriptions with English (e.g., "发布新推文" -> "posted a new tweet").
- Admin management (add/remove admins, super admin only for adding).
- Pause/resume message forwarding.
- Show bot status and configurations.

## Prerequisites
- Python 3.8+
- Telegram Bot Token (obtain from @BotFather on Telegram)
- Super admin Telegram usernames (comma-separated in `.env`)

## Installation

1. Clone the repository or download the code.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt