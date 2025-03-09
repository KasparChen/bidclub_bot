import os
import json
import logging
from typing import Set
from telegram import Update, Chat
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    State  # 从 telegram.ext 导入 State
)
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置日志，忽略 getUpdates 日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('bot.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)
logger.addFilter(lambda record: "getUpdates" not in record.getMessage())  # 过滤 getUpdates 日志

# 全局配置
BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPER_ADMINS = set(os.getenv("SUPER_ADMIN_LIST", "").split(",")) if os.getenv("SUPER_ADMIN_LIST") else set()
CONFIG_FILE = "config.json"
BOT_USERNAME = None  # 动态获取 Bot 用户名

# 加载配置，若文件不存在则初始化
def load_config() -> dict:
    """加载配置文件，若不存在则返回默认配置"""
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
            return {
                "ORIGIN_CHATS": set(config.get("origin_chats", [])),
                "DESTINATION_CHATS": set(config.get("destination_chats", [])),
                "ADMINS": set(config.get("admins", list(SUPER_ADMINS)))
            }
    except FileNotFoundError:
        return {"ORIGIN_CHATS": set(), "DESTINATION_CHATS": set(), "ADMINS": SUPER_ADMINS.copy()}

# 保存配置到文件
def save_config(config: dict) -> None:
    """将配置保存到 JSON 文件"""
    with open(CONFIG_FILE, "w") as f:
        json.dump({
            "origin_chats": list(config["ORIGIN_CHATS"]),
            "destination_chats": list(config["DESTINATION_CHATS"]),
            "admins": list(config["ADMINS"])
        }, f, indent=4)

# 初始化全局变量
config = load_config()
ORIGIN_CHATS: Set[int] = config["ORIGIN_CHATS"]
DESTINATION_CHATS: Set[int] = config["DESTINATION_CHATS"]
ADMINS: Set[str] = config["ADMINS"]
IS_PAUSED: bool = False

# 定义对话状态
SET_ORIGIN, SET_DESTINATION, ADD_ADMIN = range(3)

# 文本替换规则
TEXT_RULES = {
    "发布新推文": "posted a new tweet",
    "转发了推文": "retweeted a tweet",
    "引用了推文": "quoted a tweet"
}

async def start(update: Update, context: ContextTypes) -> None:
    """启动 Bot 并获取用户名"""
    global BOT_USERNAME
    if not BOT_USERNAME:
        bot_info = await context.bot.get_me()
        BOT_USERNAME = bot_info.username
    logger.info(f"Bot started by {update.effective_user.username}")
    await update.message.reply_text(f"@{BOT_USERNAME} has started! Use /help to see commands.")

async def check_admin(update: Update) -> bool:
    """检查用户是否为管理员或超级管理员"""
    user = update.effective_user.username
    if user in SUPER_ADMINS or user in ADMINS:
        return True
    logger.warning(f"Permission denied for {user}")
    await update.message.reply_text("Permission denied. Only admins can use this command.")
    return False

async def get_chat_name(chat_id: int, context: ContextTypes) -> str:
    """获取频道名称，失败时返回 ID"""
    try:
        chat: Chat = await context.bot.get_chat(chat_id)
        return chat.title or f"Channel {chat_id}"
    except Exception as e:
        logger.error(f"Failed to get chat name for {chat_id}: {e}")
        return f"Channel {chat_id}"

async def set_origin_start(update: Update, context: ContextTypes) -> State:
    """开始设置源频道"""
    if not await check_admin(update):
        return ConversationHandler.END
    logger.info(f"Starting set_origin for {update.effective_user.username}")
    await update.message.reply_text("Enter Channel ID to set origin channel (e.g., -123123 -123123)")
    return SET_ORIGIN

async def set_origin_handle(update: Update, context: ContextTypes) -> State:
    """处理源频道 ID 输入"""
    try:
        channel_ids = [int(cid) for cid in update.message.text.split()]
        names = [await get_chat_name(cid, context) for cid in channel_ids]
        global ORIGIN_CHATS
        ORIGIN_CHATS = set(channel_ids)
        save_config({"ORIGIN_CHATS": ORIGIN_CHATS, "DESTINATION_CHATS": DESTINATION_CHATS, "ADMINS": ADMINS})
        await update.message.reply_text(f"Origin channels set: {', '.join(names)}")
        logger.info(f"Origin channels set to {ORIGIN_CHATS} by {update.effective_user.username}")
    except ValueError:
        await update.message.reply_text("Invalid Channel IDs. Use integers separated by spaces.")
    except Exception as e:
        logger.error(f"Error setting origin channels: {e}")
        await update.message.reply_text("Error: Could not set origin channels.")
    return ConversationHandler.END

async def set_destination_start(update: Update, context: ContextTypes) -> State:
    """开始设置目标频道"""
    if not await check_admin(update):
        return ConversationHandler.END
    logger.info(f"Starting set_destination for {update.effective_user.username}")
    await update.message.reply_text("Enter Channel ID to set destination channel (e.g., -123123 -123123)")
    return SET_DESTINATION

async def set_destination_handle(update: Update, context: ContextTypes) -> State:
    """处理目标频道 ID 输入"""
    try:
        channel_ids = [int(cid) for cid in update.message.text.split()]
        names = [await get_chat_name(cid, context) for cid in channel_ids]
        global DESTINATION_CHATS
        DESTINATION_CHATS = set(channel_ids)
        save_config({"ORIGIN_CHATS": ORIGIN_CHATS, "DESTINATION_CHATS": DESTINATION_CHATS, "ADMINS": ADMINS})
        await update.message.reply_text(f"Destination channels set: {', '.join(names)}")
        logger.info(f"Destination channels set to {DESTINATION_CHATS} by {update.effective_user.username}")
    except ValueError:
        await update.message.reply_text("Invalid Channel IDs. Use integers separated by spaces.")
    except Exception as e:
        logger.error(f"Error setting destination channels: {e}")
        await update.message.reply_text("Error: Could not set destination channels.")
    return ConversationHandler.END

async def add_admin_start(update: Update, context: ContextTypes) -> State:
    """开始添加管理员"""
    if update.effective_user.username not in SUPER_ADMINS:
        await update.message.reply_text("Only super admins can add admins!")
        return ConversationHandler.END
    logger.info(f"Starting add_admin for {update.effective_user.username}")
    await update.message.reply_text("Enter Telegram username to add as admin (e.g., @username)")
    return ADD_ADMIN

async def add_admin_handle(update: Update, context: ContextTypes) -> State:
    """处理管理员用户名输入"""
    username = update.message.text
    if not username.startswith('@'):
        await update.message.reply_text("Invalid username. Use format: @username")
        return ADD_ADMIN
    handle = username[1:]
    global ADMINS
    ADMINS.add(handle)
    save_config({"ORIGIN_CHATS": ORIGIN_CHATS, "DESTINATION_CHATS": DESTINATION_CHATS, "ADMINS": ADMINS})
    await update.message.reply_text(f"Added {username} as admin.")
    logger.info(f"Added {handle} as admin by {update.effective_user.username}")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes) -> State:
    """取消对话"""
    logger.info(f"Conversation cancelled by {update.effective_user.username}")
    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END

async def rm_admin(update: Update, context: ContextTypes) -> None:
    """移除管理员"""
    if not await check_admin(update) or not (ADMINS - SUPER_ADMINS):
        await update.message.reply_text("No regular admins to remove or insufficient permissions!")
        return
    admin_list = list(ADMINS - SUPER_ADMINS)
    if context.args and context.args[0].isdigit():
        idx = int(context.args[0]) - 1
        if 0 <= idx < len(admin_list):
            removed = admin_list[idx]
            ADMINS.remove(removed)
            save_config({"ORIGIN_CHATS": ORIGIN_CHATS, "DESTINATION_CHATS": DESTINATION_CHATS, "ADMINS": ADMINS})
            await update.message.reply_text(f"Removed admin {removed}.")
            logger.info(f"Removed {removed} by {update.effective_user.username}")
        else:
            await update.message.reply_text("Invalid number!")
    else:
        msg = "Current admins:\n" + "\n".join(f"{i+1}. {admin}" for i, admin in enumerate(admin_list))
        await update.message.reply_text(msg + "\nUse /rm_admin <number> to remove.")

async def pause(update: Update, context: ContextTypes) -> None:
    """暂停消息转发"""
    if not await check_admin(update):
        return
    global IS_PAUSED
    IS_PAUSED = True
    await update.message.reply_text("Message forwarding paused.")
    logger.info(f"Paused by {update.effective_user.username}")

async def resume(update: Update, context: ContextTypes) -> None:
    """恢复消息转发"""
    if not await check_admin(update):
        return
    global IS_PAUSED
    IS_PAUSED = False
    await update.message.reply_text("Message forwarding resumed.")
    logger.info(f"Resumed by {update.effective_user.username}")

async def status(update: Update, context: ContextTypes) -> None:
    """显示当前状态"""
    if not await check_admin(update):
        return
    msg = (
        f"Status: {'Paused' if IS_PAUSED else 'Running'}\n"
        f"Origin Channels: {', '.join(map(str, ORIGIN_CHATS)) or 'Not set'}\n"
        f"Destination Channels: {', '.join(map(str, DESTINATION_CHATS)) or 'Not set'}\n"
        f"Admins: {', '.join(ADMINS) or 'None'}"
    )
    await update.message.reply_text(msg)
    logger.info(f"Status checked by {update.effective_user.username}")

async def process_message(update: Update, context: ContextTypes) -> None:
    """处理并转发消息"""
    if IS_PAUSED or update.effective_chat.id not in ORIGIN_CHATS or not DESTINATION_CHATS:
        return
    text = update.message.text or ""
    if not text.startswith("[Alpha]"):
        return
    for chinese, english in TEXT_RULES.items():
        if chinese in text:
            processed_text = text.replace(chinese, english)
            for dest_id in DESTINATION_CHATS:
                try:
                    await context.bot.send_message(dest_id, processed_text)
                    logger.info(f"Forwarded message from {update.effective_chat.id} to {dest_id}")
                except Exception as e:
                    logger.error(f"Failed to forward to {dest_id}: {e}")
            break

def main() -> None:
    """主函数，启动 Bot"""
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN not set in .env!")
    print(f"Bot Starting... Token: {'Set' if BOT_TOKEN else 'Not set'}")
    print(f"Super Admins: {', '.join(SUPER_ADMINS) or 'Not set'}")
    print(f"Initial Status: {'Paused' if IS_PAUSED else 'Running'}")

    app = Application.builder().token(BOT_TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("set_origin", set_origin_start),
            CommandHandler("set_destination", set_destination_start),
            CommandHandler("add_admin", add_admin_start)
        ],
        states={
            SET_ORIGIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_origin_handle)],
            SET_DESTINATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_destination_handle)],
            ADD_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_admin_handle)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    # 注册处理器
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("rm_admin", rm_admin))
    app.add_handler(CommandHandler("pause", pause))
    app.add_handler(CommandHandler("resume", resume))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(MessageHandler(filters.ChatType.CHANNEL & ~filters.COMMAND, process_message))

    logger.info("Bot polling started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()