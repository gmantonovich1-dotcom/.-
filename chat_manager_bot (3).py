import logging
import json
import re
from datetime import datetime, timedelta
from telegram import Update, ChatMemberUpdated
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ChatMemberHandler
from telegram.constants import ChatMemberStatus, ParseMode

# Логирование
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация (замени на свой токен)
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

# Хранилище данных (в реальности лучше использовать базу данных)
chat_settings = {}
user_warnings = {}
spam_tracker = {}

# Настройки по умолчанию для чата
DEFAULT_SETTINGS = {
    "welcome_enabled": True,
    "welcome_message": "Добро пожаловать в чат, {name}! 👋",
    "goodbye_enabled": True,
    "goodbye_message": "Пока, {name}! 👋",
    "antispam_enabled": True,
    "max_messages_per_minute": 5,
    "auto_delete_links": False,
    "auto_delete_forwards": False,
    "warn_limit": 3,
    "bad_words": ["спам", "реклама"],
    "auto_responses": {}
}

def get_chat_settings(chat_id):
    """Получить настройки чата"""
    if chat_id not in chat_settings:
        chat_settings[chat_id] = DEFAULT_SETTINGS.copy()
    return chat_settings[chat_id]

def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Проверить является ли пользователь админом"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    try:
        chat_member = context.bot.get_chat_member(chat_id, user_id)
        return chat_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except:
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /start"""
    if update.effective_chat.type == "private":
        await update.message.reply_text(
            "🤖 Привет! Я чат-менеджер бот.\n\n"
            "Добавь меня в свой чат и дай права администратора.\n\n"
            "Команды:\n"
            "/help - список всех команд\n"
            "/settings - настройки чата\n"
            "/stats - статистика чата"
        )
    else:
        await update.message.reply_text("Бот активирован! Используй /help для списка команд.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /help"""
    help_text = """
🤖 **Команды чат-менеджера:**

**👑 Команды админов:**
/warn [@user] - предупредить пользователя
/unwarn [@user] - снять предупреждение
/kick [@user] - кикнуть пользователя
/ban [@user] - забанить пользователя
/unban [@user] - разбанить пользователя
/mute [@user] [время] - замутить пользователя

**⚙️ Настройки:**
/settings - показать настройки
/welcome on/off - вкл/выкл приветствие
/goodbye on/off - вкл/выкл прощание
/antispam on/off - вкл/выкл анти-спам
/addresponse [слово] [ответ] - добавить автоответ
/delresponse [слово] - удалить автоответ

**📊 Статистика:**
/stats - статистика чата
/top - топ активных пользователей

**🛡️ Модерация:**
/clean [число] - удалить сообщения (до 100)
/pin - закрепить сообщение (ответом)
/unpin - открепить сообщение
    """
    
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать настройки чата"""
    if not is_admin(update, context):
        await update.message.reply_text("❌ Только админы могут просматривать настройки!")
        return
    
    chat_id = update.effective_chat.id
    settings = get_chat_settings(chat_id)
    
    settings_text = f"""
⚙️ **Настройки чата:**

👋 Приветствие: {'✅' if settings['welcome_enabled'] else '❌'}
📝 Сообщение: `{settings['welcome_message']}`

👋 Прощание: {'✅' if settings['goodbye_enabled'] else '❌'}
📝 Сообщение: `{settings['goodbye_message']}`

🛡️ Анти-спам: {'✅' if settings['antispam_enabled'] else '❌'}
📊 Лимит сообщений: {settings['max_messages_per_minute']}/мин

🔗 Удалять ссылки: {'✅' if settings['auto_delete_links'] else '❌'}
📤 Удалять пересылки: {'✅' if settings['auto_delete_forwards'] else '❌'}

⚠️ Лимит предупреждений: {settings['warn_limit']}
🚫 Запрещённые слова: {len(settings['bad_words'])}
🤖 Автоответы: {len(settings['auto_responses'])}
    """
    
    await update.message.reply_text(settings_text, parse_mode=ParseMode.MARKDOWN)

async def warn_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Предупредить пользователя"""
    if not is_admin(update, context):
        await update.message.reply_text("❌ Только админы могут выдавать предупреждения!")
        return
    
    # Получаем пользователя для предупреждения
    target_user = None
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
    elif context.args:
        # Тут можно добавить логику парсинга @username
        pass
    
    if not target_user:
        await update.message.reply_text("❌ Укажите пользователя для предупреждения (ответом на сообщение или @username)")
        return
    
    chat_id = update.effective_chat.id
    user_id = target_user.id
    settings = get_chat_settings(chat_id)
    
    # Увеличиваем счётчик предупреждений
    if chat_id not in user_warnings:
        user_warnings[chat_id] = {}
    if user_id not in user_warnings[chat_id]:
        user_warnings[chat_id][user_id] = 0
    
    user_warnings[chat_id][user_id] += 1
    warnings = user_warnings[chat_id][user_id]
    
    if warnings >= settings['warn_limit']:
        # Бан за превышение лимита предупреждений
        try:
            await context.bot.ban_chat_member(chat_id, user_id)
            await update.message.reply_text(f"🔨 {target_user.first_name} забанен за {warnings} предупреждений!")
            user_warnings[chat_id][user_id] = 0
        except:
            await update.message.reply_text("❌ Не удалось забанить пользователя")
    else:
        await update.message.reply_text(
            f"⚠️ {target_user.first_name} получил предупреждение!\n"
            f"Предупреждений: {warnings}/{settings['warn_limit']}"
        )

async def member_joined(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка новых участников"""
    chat_id = update.effective_chat.id
    settings = get_chat_settings(chat_id)
    
    if not settings['welcome_enabled']:
        return
    
    for member in update.message.new_chat_members:
        welcome_text = settings['welcome_message'].format(
            name=member.first_name,
            username=f"@{member.username}" if member.username else member.first_name
        )
        
        await update.message.reply_text(welcome_text)

async def member_left(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка ушедших участников"""
    chat_id = update.effective_chat.id
    settings = get_chat_settings(chat_id)
    
    if not settings['goodbye_enabled']:
        return
    
    left_member = update.message.left_chat_member
    goodbye_text = settings['goodbye_message'].format(
        name=left_member.first_name,
        username=f"@{left_member.username}" if left_member.username else left_member.first_name
    )
    
    await update.message.reply_text(goodbye_text)

async def check_spam(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Проверка на спам"""
    if not update.message or not update.effective_user:
        return
        
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    settings = get_chat_settings(chat_id)
    
    if not settings['antispam_enabled']:
        return
    
    # Трекинг сообщений
    now = datetime.now()
    if chat_id not in spam_tracker:
        spam_tracker[chat_id] = {}
    if user_id not in spam_tracker[chat_id]:
        spam_tracker[chat_id][user_id] = []
    
    # Удаляем старые записи (старше минуты)
    spam_tracker[chat_id][user_id] = [
        msg_time for msg_time in spam_tracker[chat_id][user_id]
        if now - msg_time < timedelta(minutes=1)
    ]
    
    spam_tracker[chat_id][user_id].append(now)
    
    # Проверяем лимит
    if len(spam_tracker[chat_id][user_id]) > settings['max_messages_per_minute']:
        try:
            await context.bot.delete_message(chat_id, update.message.message_id)
            await update.message.reply_text(f"⚠️ {update.effective_user.first_name}, не спамь!")
        except:
            pass

async def check_bad_words(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Проверка на запрещённые слова"""
    if not update.message or not update.message.text:
        return
        
    chat_id = update.effective_chat.id
    settings = get_chat_settings(chat_id)
    message_text = update.message.text.lower()
    
    for bad_word in settings['bad_words']:
        if bad_word.lower() in message_text:
            try:
                await context.bot.delete_message(chat_id, update.message.message_id)
                await update.message.reply_text("🚫 Сообщение удалено за нарушение правил!")
            except:
                pass
            break

async def auto_response(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Автоответы"""
    if not update.message or not update.message.text:
        return
        
    chat_id = update.effective_chat.id
    settings = get_chat_settings(chat_id)
    message_text = update.message.text.lower()
    
    for trigger, response in settings['auto_responses'].items():
        if trigger.lower() in message_text:
            await update.message.reply_text(response)
            break

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Основной обработчик сообщений"""
    await check_spam(update, context)
    await check_bad_words(update, context)
    await auto_response(update, context)

def main() -> None:
    """Запуск бота"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("settings", settings_command))
    application.add_handler(CommandHandler("warn", warn_user))
    
    # Обработчики событий чата
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, member_joined))
    application.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, member_left))
    
    # Обработчик всех сообщений
    application.add_handler(MessageHandler(filters.ALL, message_handler))
    
    # Запуск бота
    print("🤖 Бот запущен!")
    application.run_polling()

if __name__ == '__main__':
    main()