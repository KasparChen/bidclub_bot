# Telegram Message Forwarding Bot

A simple, efficient, and elegant Telegram bot designed to forward messages from specified origin channels to destination channels with customizable text processing rules. The bot includes admin management features and supports pausing/resuming operations. Only authorized admins or super admins can configure and control the bot.

## Features

- **Message Forwarding**: Automatically forwards messages from specified origin channels to destination channels.
- **Text Processing**: Replaces predefined Chinese phrases with English equivalents (e.g., "发布新推文" → "Posted a New Tweet").
- **Admin Management**: 
  - Super admins can add new admins.
  - Admins can remove regular admins (via numbered list).
- **Pause/Resume**: Temporarily pause or resume message forwarding.
- **Status Overview**: Displays current bot status, including origin/destination channels and admin list.
- **Persistent Configuration**: Stores settings (channels, admins) in a `config.json` file.
- **Logging**: Logs operations and errors to `bot.log` and console (excludes `getUpdates` noise).

## Command List

| Command            | Description                                      | Usage Example                 | Permission       |
|--------------------|--------------------------------------------------|-------------------------------|------------------|
| `/start`           | Starts the bot and displays a welcome message.   | `/start`                      | All users        |
| `/set_origin`      | Sets/overwrites origin channel IDs.              | `/set_origin -123123 -456456` | Admins           |
| `/set_destination` | Sets/overwrites destination channel IDs.         | `/set_destination -789789`    | Admins           |
| `/add_admin`       | Adds a new admin by Telegram username.           | `/add_admin @JohnDoe`         | Super Admins     |
| `/rm_admin`        | Lists admins or removes one by number.           | `/rm_admin` or `/rm_admin 1`  | Admins           |
| `/pause`           | Pauses message forwarding.                       | `/pause`                      | Admins           |
| `/resume`          | Resumes message forwarding.                      | `/resume`                     | Admins           |
| `/status`          | Shows bot status and configurations.             | `/status`                     | Admins           |
| `/cancel`          | Cancels an ongoing command operation.            | `/cancel`                     | Admins (in conv.)|

### Notes on Commands
- Channel IDs must be integers (e.g., `-100123456789`), obtainable via Telegram's API or bots like `@GetIDsBot`.
- Only messages starting with `[Alpha]` from origin channels are forwarded.
- Text replacement rules are hardcoded in `TEXT_RULES` (see `bot.py` line 73-77).

## Prerequisites

- **Python**: 3.8 or higher
- **Telegram Bot Token**: Obtain from [@BotFather](https://t.me/BotFather) on Telegram.
- **Super Admin Usernames**: Comma-separated Telegram usernames (e.g., `@user1,@user2`) for initial setup.

## Installation

1. **Clone the Repository**:
   ~~~bash
   git clone https://github.com/yourusername/telegram-forwarding-bot.git
   cd telegram-forwarding-bot
   ~~~

2. **Install Dependencies**:
   ~~~bash
   pip install -r requirements.txt
   ~~~

3. **Set Up Environment Variables**:
   Create a `.env` file in the root directory with the following content:
   ~~~
   BOT_TOKEN=your_bot_token_here
   SUPER_ADMIN_LIST=@superadmin1,@superadmin2
   ~~~
   - Replace `your_bot_token_here` with your Telegram Bot Token.
   - Replace `@superadmin1,@superadmin2` with your super admin Telegram usernames.

4. **Run the Bot**:
   ~~~bash
   python bot.py
   ~~~

## Configuration

- **Initial Setup**: Use `/set_origin` and `/set_destination` to define channels after starting the bot.
- **Persistent Storage**: Configurations are saved to `config.json` and loaded on startup.
- **Default Behavior**: If `config.json` is missing, the bot starts with empty channel lists and the super admin list from `.env`.

## Logging

- **Log File**: Operations are logged to `bot.log` in the project directory.
- **Console Output**: Logs are also printed to the console for real-time monitoring.
- **Filtered Noise**: `getUpdates`-related logs are excluded for clarity.
- **Debugging**: Check `bot.log` for errors or detailed operation history.

## Initial Status

On startup, the bot prints its initial configuration to the console:
~~~
Bot Starting... Token: Set
Super Admins: @superadmin1, @superadmin2
Initial Status: Running
~~~
This helps verify that the bot is correctly initialized.

## Development

- **Code Structure**:
  - `bot.py`: Main bot logic, command handlers, and message processing.
  - `.gitignore`: Excludes sensitive files (e.g., `.env`, logs).
  - `requirements.txt`: Lists dependencies (`python-telegram-bot` v20.0a0, `python-dotenv`).

- **Extending Features**:
  - Add new text replacement rules in `TEXT_RULES` (line 73).
  - Modify command logic in the respective `async def` functions.

## Troubleshooting

- **Bot Not Responding**: Ensure the `BOT_TOKEN` is valid and the bot is added to the specified channels with posting permissions.
- **Permission Denied**: Verify your Telegram username is in `SUPER_ADMIN_LIST` or `ADMINS`.
- **Channel ID Errors**: Use negative integers for channel IDs (e.g., `-100123456789`).