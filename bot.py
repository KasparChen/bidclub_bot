import os
import re
from typing import Set
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 从环境变量加载配置
BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPER_ADMINS = set(os.getenv("SUPER_ADMIN_LIST", "").split(",")) if os.getenv("SUPER_ADMIN_LIST") else set()
BOT_USERNAME = None  # 会在启动时动态获取

# 状态和配置
ORIGIN_CHATS: Set[int] = set()  # 源频道 ID 集合
DESTINATION_CHATS: Set[int] = set()  # 目标频道 ID 集合
ADMINS: Set[str] = SUPER_ADMINS.copy()  # 管理员列表（包括超级管理员）
IS_PAUSED: bool = False  # 暂停状态

# 文本处理规则：将中文描述替换为英文
TEXT_RULES = {
    "发布新推文": "posted a new tweet",
    "转发了推文": "retweeted a tweet",
    "引用了推文": "quoted a tweet"
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """启动时获取 Bot 用户名并初始化"""
    global BOT_USERNAME
    if not BOT_USERNAME:
        bot_info = await context.bot.get_me()
        BOT_USERNAME = bot_info.username
    await update.message.reply_text(f"@{BOT_USERNAME} has started! Use /help to see commands.")

async def check_admin(update: Update) -> bool:
    """检查用户是否为管理员或超级管理员"""
    user_name = update.effective_user.username
    if user_name in SUPER_ADMINS or user_name in (ADMINS - SUPER_ADMINS):
        return True
    await update.message.reply_text("Permission denied. Only admins or super admins can use this command.")
    return False

async def set_origin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """设置源频道 ID（覆盖原有配置，支持多个 ID，用空格分隔）"""
    if not await check_admin(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /set_origin <channel_id1> <channel_id2> ...")
        return
    try:
        global ORIGIN_CHATS
        ORIGIN_CHATS = set(int(cid) for cid in context.args)
        await update.message.reply_text(f"Origin channels set to: {', '.join(map(str, ORIGIN_CHATS))}")
    except ValueError:
        await update.message.reply_text("Channel IDs must be integers!")

async def set_destination(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """设置目标频道 ID（覆盖原有配置，支持多个 ID，用空格分隔）"""
    if not await check_admin(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /set_destination <channel_id1> <channel_id2> ...")
        return
    try:
        global DESTINATION_CHATS
        DESTINATION_CHATS = set(int(cid) for cid in context.args)
        await update.message.reply_text(f"Destination channels set to: {', '.join(map(str, DESTINATION_CHATS))}")
    except ValueError:
        await update.message.reply_text("Channel IDs must be integers!")

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """添加管理员（仅超级管理员可用）"""
    if update.effective_user.username not in SUPER_ADMINS:
        await update.message.reply_text("Only super admins can add admins!")
        return
    if not context.args or not context.args[0].startswith('@'):
        await update.message.reply_text("Usage: /add_admin @username")
        return
    handle = context.args[0][1:]  # 去除 @ 符号
    global ADMINS
    ADMINS.add(handle)
    await update.message.reply_text(f"Added {handle} as admin.")

async def rm_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """移除管理员（显示当前管理员列表及编号，支持按编号删除，普通管理员可删除其他普通管理员，但不能删除超级管理员）"""
    if not await check_admin(update):
        return
    if not ADMINS - SUPER_ADMINS:  # 仅剩超级管理员时禁止删除
        await update.message.reply_text("Cannot remove super admins or the last admin!")
        return
    admin_list = list(ADMINS - SUPER_ADMINS)  # 排除超级管理员
    if not admin_list:
        await update.message.reply_text("No regular admins currently.")
        return
    msg = "Current regular admins (enter number to remove):\n" + "\n".join(f"{i+1}. {admin}" for i, admin in enumerate(admin_list))
    await update.message.reply_text(msg)
    if context.args and context.args[0].isdigit():
        idx = int(context.args[0]) - 1
        if 0 <= idx < len(admin_list):
            removed = admin_list[idx]
            if removed in SUPER_ADMINS and update.effective_user.username not in SUPER_ADMINS:
                await update.message.reply_text("Cannot remove super admins!")
                return
            ADMINS.remove(removed)
            await update.message.reply_text(f"Removed admin {removed}.")
        else:
            await update.message.reply_text("Invalid number!")

async def pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """暂停消息转发"""
    if not await check_admin(update):
        return
    global IS_PAUSED
    IS_PAUSED = True
    await update.message.reply_text("Message forwarding paused.")

async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """恢复消息转发"""
    if not await check_admin(update):
        return
    global IS_PAUSED
    IS_PAUSED = False
    await update.message.reply_text("Message forwarding resumed.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """显示当前配置和状态"""
    if not await check_admin(update):
        return
    status_msg = (
        f"**Current Status:**\n"
        f"Running Status: {'Paused' if IS_PAUSED else 'Running'}\n"
        f"Origin Channels: {', '.join(map(str, ORIGIN_CHATS)) if ORIGIN_CHATS else 'Not set'}\n"
        f"Destination Channels: {', '.join(map(str, DESTINATION_CHATS)) if DESTINATION_CHATS else 'Not set'}\n"
        f"Admins: {', '.join(ADMINS) if ADMINS else 'None'}\n"
    )
    await update.message.reply_text(status_msg, parse_mode="Markdown")

async def process_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
        except Exception as e:
            print(f"Failed to forward to {dest_id}: {e}")

def main() -> None:
    """主函数，启动 Bot"""
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is not set in .env!")
    if not SUPER_ADMINS:
        print("Warning: SUPER_ADMIN_LIST is not set, super admins will be empty!")

    application = Application.builder().token(BOT_TOKEN).build()

    # 注册命令处理器
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("set_origin", set_origin))
    application.add_handler(CommandHandler("set_destination", set_destination))
    application.add_handler(CommandHandler("add_admin", add_admin))
    application.add_handler(CommandHandler("rm_admin", rm_admin))
    application.add_handler(CommandHandler("pause", pause))
    application.add_handler(CommandHandler("resume", resume))
    application.add_handler(CommandHandler("status", status))

    # 注册消息处理器，仅处理频道消息
    application.add_handler(MessageHandler(filters.ChatType.CHANNEL & ~filters.COMMAND, process_message))

    # 启动 Bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()