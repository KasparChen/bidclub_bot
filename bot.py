import os
import re
import json
import logging
from typing import Set, Dict
from telegram import Update, Chat
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from telegram.ext._utils.types import State  # 修正 State 导入
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 配置日志，忽略 getUpdates 的日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 自定义日志过滤器，忽略 getUpdates
class NoGetUpdatesFilter(logging.Filter):
    def filter(self, record):
        return "getUpdates" not in record.getMessage()

logger.addFilter(NoGetUpdatesFilter())

# 从环境变量加载配置
BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPER_ADMINS = set(os.getenv("SUPER_ADMIN_LIST", "").split(",")) if os.getenv("SUPER_ADMIN_LIST") else set()
BOT_USERNAME = None  # 会在启动时动态获取

# 配置文件路径
CONFIG_FILE = "config.json"

# 加载或初始化配置
def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
            return {
                "ORIGIN_CHATS": set(config.get("origin_chats", [])),
                "DESTINATION_CHATS": set(config.get("destination_chats", [])),
                "ADMINS": set(config.get("admins", list(SUPER_ADMINS)))
            }
    except FileNotFoundError:
        return {
            "ORIGIN_CHATS": set(),
            "DESTINATION_CHATS": set(),
            "ADMINS": SUPER_ADMINS.copy()
        }

# 保存配置
def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump({
            "origin_chats": list(config["ORIGIN_CHATS"]),
            "destination_chats": list(config["DESTINATION_CHATS"]),
            "admins": list(config["ADMINS"])
        }, f, indent=4)

# 加载配置
config = load_config()
ORIGIN_CHATS = config["ORIGIN_CHATS"]
DESTINATION_CHATS = config["DESTINATION_CHATS"]
ADMINS = config["ADMINS"]
IS_PAUSED: bool = False  # 暂停状态

# 对话状态
SET_ORIGIN, SET_DESTINATION, ADD_ADMIN = range(3)

# 文本处理规则：将中文描述替换为英文
TEXT_RULES = {
    "发布新推文": "posted a new tweet",
    "转发了推文": "retweeted a tweet",
    "引用了推文": "quoted a tweet"
}

async def start(update: Update, context: ContextTypes) -> None:
    """启动时获取 Bot 用户名并初始化"""
    global BOT_USERNAME
    if not BOT_USERNAME:
        bot_info = await context.bot.get_me()
        BOT_USERNAME = bot_info.username
    logger.info("Bot started by user: %s", update.effective_user.username)
    await update.message.reply_text(f"@{BOT_USERNAME} has started! Use /help to see commands.")

async def check_admin(update: Update) -> bool:
    """检查用户是否为管理员或超级管理员"""
    user_name = update.effective_user.username
    if user_name in SUPER_ADMINS or user_name in (ADMINS - SUPER_ADMINS):
        return True
    logger.warning("Permission denied for user: %s", user_name)
    await update.message.reply_text("Permission denied. Only admins or super admins can use this command.")
    return False

async def get_chat_name(chat_id: int, context: ContextTypes) -> str:
    """获取频道的名称"""
    try:
        chat: Chat = await context.bot.get_chat(chat_id)
        return chat.title or f"Channel {chat_id}"
    except Exception as e:
        logger.error("Failed to get chat name for ID %d: %s", chat_id, str(e))
        return f"Channel {chat_id}"

async def get_user_name(username: str, context: ContextTypes) -> str:
    """获取用户的名称"""
    try:
        user = await context.bot.get_chat(f"@{username}")
        return user.username or f"User {username}"
    except Exception as e:
        logger.error("Failed to get user name for %s: %s", username, str(e))
        return f"User {username}"

async def set_origin_start(update: Update, context: ContextTypes) -> State:
    """开始设置源频道，提示用户输入 ID"""
    if not await check_admin(update):
        return ConversationHandler.END
    logger.info("Starting set_origin conversation for user: %s", update.effective_user.username)
    await update.message.reply_text("Enter Channel ID to set origin channel, use space to separate. e.g. -123123123 -123123123")
    return SET_ORIGIN

async def set_origin_handle(update: Update, context: ContextTypes) -> State:
    """处理用户输入的源频道 ID"""
    user_input = update.message.text
    try:
        channel_ids = [int(cid) for cid in user_input.split()]
        channel_names = []
        for cid in channel_ids:
            name = await get_chat_name(cid, context)
            channel_names.append(name)
        global ORIGIN_CHATS
        ORIGIN_CHATS = set(channel_ids)
        save_config({"ORIGIN_CHATS": ORIGIN_CHATS, "DESTINATION_CHATS": DESTINATION_CHATS, "ADMINS": ADMINS})
        current_list = "\n".join(channel_names)
        response = f"{', '.join(channel_names)} added as Origin Channels\nCurrent Origin List:\n{current_list}"
        logger.info("Origin channels set to: %s by user: %s", ORIGIN_CHATS, update.effective_user.username)
        await update.message.reply_text(response)
    except ValueError:
        logger.error("Invalid channel IDs provided by user: %s", update.effective_user.username)
        await update.message.reply_text("Invalid Channel IDs. Please enter valid integers separated by spaces.")
    except Exception as e:
        logger.error("Error setting origin channels for user %s: %s", update.effective_user.username, str(e))
        await update.message.reply_text(f"Error: Could not find or access the channel. Please check the Channel ID.")
    return ConversationHandler.END

async def set_destination_start(update: Update, context: ContextTypes) -> State:
    """开始设置目标频道，提示用户输入 ID"""
    if not await check_admin(update):
        return ConversationHandler.END
    logger.info("Starting set_destination conversation for user: %s", update.effective_user.username)
    await update.message.reply_text("Enter Channel ID to set destination channel, use space to separate. e.g. -123123123 -123123123")
    return SET_DESTINATION

async def set_destination_handle(update: Update, context: ContextTypes) -> State:
    """处理用户输入的目标频道 ID"""
    user_input = update.message.text
    try:
        channel_ids = [int(cid) for cid in user_input.split()]
        channel_names = []
        for cid in channel_ids:
            name = await get_chat_name(cid, context)
            channel_names.append(name)
        global DESTINATION_CHATS
        DESTINATION_CHATS = set(channel_ids)
        save_config({"ORIGIN_CHATS": ORIGIN_CHATS, "DESTINATION_CHATS": DESTINATION_CHATS, "ADMINS": ADMINS})
        current_list = "\n".join(channel_names)
        response = f"{', '.join(channel_names)} added as Destination Channels\nCurrent Destination List:\n{current_list}"
        logger.info("Destination channels set to: %s by user: %s", DESTINATION_CHATS, update.effective_user.username)
        await update.message.reply_text(response)
    except ValueError:
        logger.error("Invalid channel IDs provided by user: %s", update.effective_user.username)
        await update.message.reply_text("Invalid Channel IDs. Please enter valid integers separated by spaces.")
    except Exception as e:
        logger.error("Error setting destination channels for user %s: %s", update.effective_user.username, str(e))
        await update.message.reply_text(f"Error: Could not find or access the channel. Please check the Channel ID.")
    return ConversationHandler.END

async def add_admin_start(update: Update, context: ContextTypes) -> State:
    """开始添加管理员，提示用户输入用户名"""
    if update.effective_user.username not in SUPER_ADMINS:
        logger.warning("User %s attempted to add admin without super admin privilege", update.effective_user.username)
        await update.message.reply_text("Only super admins can add admins!")
        return ConversationHandler.END
    logger.info("Starting add_admin conversation for user: %s", update.effective_user.username)
    await update.message.reply_text("Enter Telegram username to add as admin (e.g. @username)")
    return ADD_ADMIN

async def add_admin_handle(update: Update, context: ContextTypes) -> State:
    """处理用户输入的管理员用户名"""
    user_input = update.message.text
    if not user_input.startswith('@'):
        logger.info("Invalid username format provided by user: %s", update.effective_user.username)
        await update.message.reply_text("Invalid username. Please enter a username starting with '@' (e.g. @username)")
        return ADD_ADMIN
    handle = user_input[1:]  # 去除 @ 符号
    try:
        name = await get_user_name(handle, context)
        global ADMINS
        ADMINS.add(handle)
        save_config({"ORIGIN_CHATS": ORIGIN_CHATS, "DESTINATION_CHATS": DESTINATION_CHATS, "ADMINS": ADMINS})
        logger.info("Added %s as admin by super admin: %s", handle, update.effective_user.username)
        await update.message.reply_text(f"Added {name} as admin.")
    except Exception as e:
        logger.error("Error adding admin %s by user %s: %s", handle, update.effective_user.username, str(e))
        await update.message.reply_text(f"Error: Could not find or access the user. Please check the username.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes) -> State:
    """取消当前对话"""
    logger.info("Conversation cancelled by user: %s", update.effective_user.username)
    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END

async def rm_admin(update: Update, context: ContextTypes) -> None:
    """移除管理员（显示当前管理员列表及编号，支持按编号删除，普通管理员可删除其他普通管理员，但不能删除超级管理员）"""
    if not await check_admin(update):
        return
    if not ADMINS - SUPER_ADMINS:  # 仅剩超级管理员时禁止删除
        logger.info("Attempt to remove last admin or super admin by user: %s", update.effective_user.username)
        await update.message.reply_text("Cannot remove super admins or the last admin!")
        return
    admin_list = list(ADMINS - SUPER_ADMINS)  # 排除超级管理员
    if not admin_list:
        logger.info("No regular admins to remove, reported to user: %s", update.effective_user.username)
        await update.message.reply_text("No regular admins currently.")
        return
    msg = "Current regular admins (enter number to remove):\n" + "\n".join(f"{i+1}. {admin}" for i, admin in enumerate(admin_list))
    await update.message.reply_text(msg)
    if context.args and context.args[0].isdigit():
        idx = int(context.args[0]) - 1
        if 0 <= idx < len(admin_list):
            removed = admin_list[idx]
            if removed in SUPER_ADMINS and update.effective_user.username not in SUPER_ADMINS:
                logger.warning("User %s attempted to remove super admin %s", update.effective_user.username, removed)
                await update.message.reply_text("Cannot remove super admins!")
                return
            ADMINS.remove(removed)
            save_config({"ORIGIN_CHATS": ORIGIN_CHATS, "DESTINATION_CHATS": DESTINATION_CHATS, "ADMINS": ADMINS})
            logger.info("Removed admin %s by user: %s", removed, update.effective_user.username)
            await update.message.reply_text(f"Removed admin {removed}.")
        else:
            logger.info("Invalid number provided by user: %s for removing admin", update.effective_user.username)
            await update.message.reply_text("Invalid number!")

async def pause(update: Update, context: ContextTypes) -> None:
    """暂停消息转发"""
    if not await check_admin(update):
        return
    global IS_PAUSED
    IS_PAUSED = True
    save_config({"ORIGIN_CHATS": ORIGIN_CHATS, "DESTINATION_CHATS": DESTINATION_CHATS, "ADMINS": ADMINS})
    logger.info("Message forwarding paused by user: %s", update.effective_user.username)
    await update.message.reply_text("Message forwarding paused.")

async def resume(update: Update, context: ContextTypes) -> None:
    """恢复消息转发"""
    if not await check_admin(update):
        return
    global IS_PAUSED
    IS_PAUSED = False
    save_config({"ORIGIN_CHATS": ORIGIN_CHATS, "DESTINATION_CHATS": DESTINATION_CHATS, "ADMINS": ADMINS})
    logger.info("Message forwarding resumed by user: %s", update.effective_user.username)
    await update.message.reply_text("Message forwarding resumed.")

async def status(update: Update, context: ContextTypes) -> None:
    """显示当前配置和状态"""
    if not await check_admin(update):
        return
    status_msg = (
        "Current Status:\n"
        f"Running Status: {'Paused' if IS_PAUSED else 'Running'}\n"
        f"Origin Channels: {', '.join(map(str, ORIGIN_CHATS)) if ORIGIN_CHATS else 'Not set'}\n"
        f"Destination Channels: {', '.join(map(str, DESTINATION_CHATS)) if DESTINATION_CHATS else 'Not set'}\n"
        f"Admins: {', '.join(ADMINS) if ADMINS else 'None'}\n"
    )
    logger.info("Status checked by user: %s, Status: %s", update.effective_user.username, status_msg.strip())
    await update.message.reply_text(status_msg)

async def process_message(update: Update, context: ContextTypes) -> None:
    """处理来自源频道的消息并转发到目标频道，只有匹配规则的消息才会转发"""
    if IS_PAUSED or not ORIGIN_CHATS or not DESTINATION_CHATS:
        return
    if update.effective_chat.id not in ORIGIN_CHATS or update.effective_chat.type != "channel":
        return

    # 获取消息文本
    message_text = update.message.text or ""
    if not message_text.startswith("[Alpha]"):
        return

    # 文本处理：替换中文描述为英文，只有匹配规则的消息才会转发
    processed_text = None
    for chinese, english in TEXT_RULES.items():
        if chinese in message_text:
            processed_text = message_text.replace(chinese, english)
            break
    if not processed_text:  # 如果没有匹配规则，则不转发
        return

    # 转发到所有目标频道
    for dest_id in DESTINATION_CHATS:
        try:
            await context.bot.send_message(chat_id=dest_id, text=processed_text)
            logger.info("Forwarded message from channel %d to %d", update.effective_chat.id, dest_id)
        except Exception as e:
            logger.error("Failed to forward message to %d: %s", dest_id, str(e))

def main() -> None:
    """主函数，启动 Bot，并打印初始运行状态"""
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is not set in .env!")
    if not SUPER_ADMINS:
        print("Warning: SUPER_ADMIN_LIST is not set, super admins will be empty!")

    # 打印 Bot 启动状态
    print("Bot Starting...")
    print(f"Bot Token: {'Set' if BOT_TOKEN else 'Not set'}")
    print(f"Super Admins: {', '.join(SUPER_ADMINS) if SUPER_ADMINS else 'Not set'}")
    print(f"Initial Origin Channels: {', '.join(map(str, ORIGIN_CHATS)) if ORIGIN_CHATS else 'Not set'}")
    print(f"Initial Destination Channels: {', '.join(map(str, DESTINATION_CHATS)) if DESTINATION_CHATS else 'Not set'}")
    print(f"Initial Admins: {', '.join(ADMINS) if ADMINS else 'Not set'}")
    print(f"Initial Paused Status: {'Paused' if IS_PAUSED else 'Running'}")

    application = Application.builder().token(BOT_TOKEN).build()

    # 定义对话处理器
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("set_origin", set_origin_start), CommandHandler("set_destination", set_destination_start), CommandHandler("add_admin", add_admin_start)],
        states={
            SET_ORIGIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_origin_handle)],
            SET_DESTINATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_destination_handle)],
            ADD_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_admin_handle)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # 注册命令处理器
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("rm_admin", rm_admin))
    application.add_handler(CommandHandler("pause", pause))
    application.add_handler(CommandHandler("resume", resume))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(conv_handler)

    # 注册消息处理器，仅处理频道消息
    application.add_handler(MessageHandler(filters.ChatType.CHANNEL & ~filters.COMMAND, process_message))

    # 启动 Bot
    logger.info("Bot started polling for updates")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()