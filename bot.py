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
    ConversationHandler
)
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

# 配置日志记录，保存到文件和控制台，忽略 getUpdates 日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('bot.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)
logger.addFilter(lambda record: "getUpdates" not in record.getMessage())  # 过滤掉 getUpdates 相关的日志

# 全局配置变量
BOT_TOKEN = os.getenv("BOT_TOKEN")  # 从环境变量获取 Bot 的 Token
SUPER_ADMINS = set(os.getenv("SUPER_ADMIN_LIST", "").split(",")) if os.getenv("SUPER_ADMIN_LIST") else set()  # 超级管理员列表
CONFIG_FILE = "config.json"  # 配置文件路径
BOT_USERNAME = None  # Bot 用户名，启动时动态获取

# 加载配置文件，若不存在则返回默认配置
def load_config() -> dict:
    """从 JSON 文件加载配置，若文件不存在则初始化默认值"""
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
            return {
                "ORIGIN_CHATS": set(config.get("origin_chats", [])),  # 源频道 ID 集合
                "DESTINATION_CHATS": set(config.get("destination_chats", [])),  # 目标频道 ID 集合
                "ADMINS": set(config.get("admins", list(SUPER_ADMINS)))  # 管理员列表，包含超级管理员
            }
    except FileNotFoundError:
        return {
            "ORIGIN_CHATS": set(),
            "DESTINATION_CHATS": set(),
            "ADMINS": SUPER_ADMINS.copy()
        }

# 保存配置到文件
def save_config(config: dict) -> None:
    """将当前配置保存到 JSON 文件"""
    with open(CONFIG_FILE, "w") as f:
        json.dump({
            "origin_chats": list(config["ORIGIN_CHATS"]),
            "destination_chats": list(config["DESTINATION_CHATS"]),
            "admins": list(config["ADMINS"])
        }, f, indent=4)

# 初始化全局变量
config = load_config()
ORIGIN_CHATS: Set[int] = config["ORIGIN_CHATS"]  # 源频道集合
DESTINATION_CHATS: Set[int] = config["DESTINATION_CHATS"]  # 目标频道集合
ADMINS: Set[str] = config["ADMINS"]  # 管理员集合
IS_PAUSED: bool = False  # Bot 是否暂停

# 定义对话状态常量，用于 ConversationHandler
SET_ORIGIN, SET_DESTINATION, ADD_ADMIN = range(3)  # 状态：设置源频道、目标频道、添加管理员

# 文本替换规则：将中文替换为英文
TEXT_RULES = {
    "发布新推文": "Posted a New Tweet",
    "转发了推文": "RT a Tweet",
    "引用了推文": "Quoted a Tweet"
}

async def start(update: Update, context: ContextTypes) -> None:
    """启动 Bot，获取 Bot 用户名并发送欢迎消息"""
    global BOT_USERNAME
    if not BOT_USERNAME:  # 如果 Bot 用户名未设置，则动态获取
        bot_info = await context.bot.get_me()
        BOT_USERNAME = bot_info.username
    logger.info(f"Bot started by {update.effective_user.username}")
    await update.message.reply_text(f"@{BOT_USERNAME} has started! Use /help to see commands.")

async def check_admin(update: Update) -> bool:
    """检查用户是否为管理员或超级管理员"""
    user = update.effective_user.username
    if user in SUPER_ADMINS or user in ADMINS:  # 检查用户是否在管理员或超级管理员列表中
        return True
    logger.warning(f"Permission denied for {user}")
    await update.message.reply_text("Permission denied. Only admins can use this command.")
    return False

async def get_chat_name(chat_id: int, context: ContextTypes) -> str:
    """根据频道 ID 获取频道名称，若失败则返回 ID"""
    try:
        chat: Chat = await context.bot.get_chat(chat_id)
        return chat.title or f"Channel {chat_id}"
    except Exception as e:
        logger.error(f"Failed to get chat name for {chat_id}: {e}")
        return f"Channel {chat_id}"

async def set_origin_start(update: Update, context: ContextTypes) -> int:
    """开始设置源频道，提示用户输入 ID"""
    if not await check_admin(update):  # 权限检查
        return ConversationHandler.END
    logger.info(f"Starting set_origin for {update.effective_user.username}")
    await update.message.reply_text("Enter Channel ID to set origin channel (e.g., -123123 -123123)")
    return SET_ORIGIN

async def set_origin_handle(update: Update, context: ContextTypes) -> int:
    """处理用户输入的源频道 ID"""
    try:
        channel_ids = [int(cid) for cid in update.message.text.split()]  # 将输入的 ID 转换为整数列表
        names = [await get_chat_name(cid, context) for cid in channel_ids]  # 获取每个频道的名称
        global ORIGIN_CHATS
        ORIGIN_CHATS = set(channel_ids)  # 更新源频道集合
        save_config({"ORIGIN_CHATS": ORIGIN_CHATS, "DESTINATION_CHATS": DESTINATION_CHATS, "ADMINS": ADMINS})
        await update.message.reply_text(f"Origin channels set: {', '.join(names)}")
        logger.info(f"Origin channels set to {ORIGIN_CHATS} by {update.effective_user.username}")
    except ValueError:
        await update.message.reply_text("Invalid Channel IDs. Use integers separated by spaces.")
    except Exception as e:
        logger.error(f"Error setting origin channels: {e}")
        await update.message.reply_text("Error: Could not set origin channels.")
    return ConversationHandler.END

async def set_destination_start(update: Update, context: ContextTypes) -> int:
    """开始设置目标频道，提示用户输入 ID"""
    if not await check_admin(update):
        return ConversationHandler.END
    logger.info(f"Starting set_destination for {update.effective_user.username}")
    await update.message.reply_text("Enter Channel ID to set destination channel (e.g., -123123 -123123)")
    return SET_DESTINATION

async def set_destination_handle(update: Update, context: ContextTypes) -> int:
    """处理用户输入的目标频道 ID"""
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

async def add_admin_start(update: Update, context: ContextTypes) -> int:
    """开始添加管理员，提示输入用户名"""
    if update.effective_user.username not in SUPER_ADMINS:  # 仅超级管理员可添加
        await update.message.reply_text("Only super admins can add admins!")
        return ConversationHandler.END
    logger.info(f"Starting add_admin for {update.effective_user.username}")
    await update.message.reply_text("Enter Telegram username to add as admin (e.g., @username)")
    return ADD_ADMIN

async def add_admin_handle(update: Update, context: ContextTypes) -> int:
    """处理用户输入的管理员用户名"""
    username = update.message.text
    if not username.startswith('@'):  # 检查用户名格式
        await update.message.reply_text("Invalid username. Use format: @username")
        return ADD_ADMIN
    handle = username[1:]  # 去掉 @ 符号
    global ADMINS
    ADMINS.add(handle)
    save_config({"ORIGIN_CHATS": ORIGIN_CHATS, "DESTINATION_CHATS": DESTINATION_CHATS, "ADMINS": ADMINS})
    await update.message.reply_text(f"Added {username} as admin.")
    logger.info(f"Added {handle} as admin by {update.effective_user.username}")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes) -> int:
    """取消当前对话"""
    logger.info(f"Conversation cancelled by {update.effective_user.username}")
    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END

async def rm_admin(update: Update, context: ContextTypes) -> None:
    """移除管理员，支持按编号删除"""
    if not await check_admin(update) or not (ADMINS - SUPER_ADMINS):  # 检查权限和是否有普通管理员
        await update.message.reply_text("No regular admins to remove or insufficient permissions!")
        return
    admin_list = list(ADMINS - SUPER_ADMINS)
    if context.args and context.args[0].isdigit():  # 如果提供了编号
        idx = int(context.args[0]) - 1
        if 0 <= idx < len(admin_list):
            removed = admin_list[idx]
            ADMINS.remove(removed)
            save_config({"ORIGIN_CHATS": ORIGIN_CHATS, "DESTINATION_CHATS": DESTINATION_CHATS, "ADMINS": ADMINS})
            await update.message.reply_text(f"Removed admin {removed}.")
            logger.info(f"Removed {removed} by {update.effective_user.username}")
        else:
            await update.message.reply_text("Invalid number!")
    else:  # 显示管理员列表
        msg = "Current admins:\n" + "\n".join(f"{i+1}. {admin}" for i, admin in enumerate(admin_list))
        await update.message.reply_text(msg + "\nUse /rm_admin <number> to remove.")

async def pause(update: Update, context: ContextTypes) -> None:
    """暂停消息转发功能"""
    if not await check_admin(update):
        return
    global IS_PAUSED
    IS_PAUSED = True
    await update.message.reply_text("Message forwarding paused.")
    logger.info(f"Paused by {update.effective_user.username}")

async def resume(update: Update, context: ContextTypes) -> None:
    """恢复消息转发功能"""
    if not await check_admin(update):
        return
    global IS_PAUSED
    IS_PAUSED = False
    await update.message.reply_text("Message forwarding resumed.")
    logger.info(f"Resumed by {update.effective_user.username}")

async def status(update: Update, context: ContextTypes) -> None:
    """显示 Bot 当前状态和配置"""
    if not await check_admin(update):
        return
    # 获取频道名称和 ID 的组合
    origin_channels = [f"{await get_chat_name(cid, context)} ({cid})" for cid in ORIGIN_CHATS] or ["Not set"]
    dest_channels = [f"{await get_chat_name(cid, context)} ({cid})" for cid in DESTINATION_CHATS] or ["Not set"]
    msg = (
        f"Status: {'Paused' if IS_PAUSED else 'Running'}\n"
        f"Origin Channels: {', '.join(origin_channels)}\n"
        f"Destination Channels: {', '.join(dest_channels)}\n"
        f"Admins: {', '.join(ADMINS) or 'None'}"
    )
    await update.message.reply_text(msg)
    logger.info(f"Status checked by {update.effective_user.username}")

# 文件: bot.py
# 修改部分: process_message 函数 (原行号 239-263)

async def process_message(update: Update, context: ContextTypes) -> None:
    """处理源频道消息并转发到目标频道"""
    # 检查是否暂停、是否为源频道消息、以及目标频道是否已设置
    if IS_PAUSED or update.effective_chat.id not in ORIGIN_CHATS or not DESTINATION_CHATS:
        return
    
    # 检查 channel_post 是否存在，避免 AttributeError
    if not update.channel_post:
        logger.warning(f"No channel_post in update from chat {update.effective_chat.id}")
        return
    
    # 获取原始消息文本
    text = update.channel_post.text or ""
    # 只处理以 [Alpha] 开头的消息
    if not text.startswith("[Alpha]"):
        return
    
    # 删除 [Alpha] 前缀并按行分割消息
    text_without_alpha = text[len("[Alpha]"):].strip()  # 删除 [Alpha] 并去除首尾空格
    lines = text_without_alpha.split("\n")  # 按换行符分割消息
    
    # 处理第一行：提取人名并用 [] 包裹，再替换中文
    if lines:  # 确保消息非空
        first_line = lines[0].strip()  # 获取第一行并去除首尾空格
        processed_first_line = first_line  # 初始化处理后的第一行
        
        # 遍历文本替换规则，定位中文部分并提取人名
        for chinese, english in TEXT_RULES.items():
            if chinese in first_line:
                # 找到中文部分的起始位置
                chinese_start = first_line.index(chinese)
                # 人名是 [Alpha] 后到中文前的部分，去除首尾空格
                name = first_line[:chinese_start].strip()
                # 用 [] 包裹人名
                name_with_brackets = f"[{name}]"
                # 替换中文为英文，并拼接人名和替换后的部分
                processed_first_line = f"{name_with_brackets} {first_line[chinese_start:].replace(chinese, english)}"
                break  # 找到匹配后退出循环，避免重复替换
        
        # 如果没有匹配到中文规则，则仅删除 [Alpha] 前缀，不添加 []
        if processed_first_line == first_line:
            processed_first_line = first_line
        
        # 重组消息：第一行已处理，后续行保持不变
        processed_text = processed_first_line
        if len(lines) > 1:  # 如果有后续行，追加它们
            processed_text += "\n" + "\n".join(lines[1:]).strip()
        
        # 转发处理后的消息到所有目标频道
        for dest_id in DESTINATION_CHATS:
            try:
                await context.bot.send_message(dest_id, processed_text)
                logger.info(f"Forwarded message from {update.effective_chat.id} to {dest_id}")
            except Exception as e:
                logger.error(f"Failed to forward to {dest_id}: {e}")

def main() -> None:
    """主函数，初始化并启动 Bot"""
    if not BOT_TOKEN:  # 检查 Token 是否已设置
        raise ValueError("BOT_TOKEN not set in .env!")
    print(f"Bot Starting... Token: {'Set' if BOT_TOKEN else 'Not set'}")
    print(f"Super Admins: {', '.join(SUPER_ADMINS) or 'Not set'}")
    print(f"Initial Status: {'Paused' if IS_PAUSED else 'Running'}")

    # 创建并配置 Telegram 应用
    app = Application.builder().token(BOT_TOKEN).build()

    # 定义对话处理器
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

    # 注册命令和消息处理器
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