import json
import os
import logging
import shutil
from datetime import datetime
import glob
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, 
    ContextTypes, ConversationHandler
)

# === НАСТРОЙКИ ЛОГИРОВАНИЯ ===
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === НАСТРОЙКИ ===
ADMIN_ID = 6340165614
CHANNELS = [
    "@filmhd1080k",
    "@cryptostandarts"
]
MOVIES_FILE = "movies.json"
MOVIES_PER_PAGE = 5
BACKUP_DIR = "backups"
WELCOME_PHOTO_ID = "AgACAgIAAxkBAAIC0GgRx39DHkeM9JJXYO8DuxTveHn4AAKv7zEbgwSRSLD7T93AH_M6AQADAgADeQADNgQ"
CANCEL = "cancel_add"

# Создаем папку для бэкапов
if not os.path.exists(BACKUP_DIR):
    os.makedirs(BACKUP_DIR)

# Состояния для добавления фильма
(ASK_CODE, ASK_TITLE, ASK_DESC, ASK_PHOTO, ASK_YT, ASK_VK) = range(10, 16)
# Состояния для редактирования фильма
(EDIT_TITLE, EDIT_DESC, EDIT_PHOTO, EDIT_YT, EDIT_VK) = range(20, 25)

def create_backup():
    """Создание резервной копии базы фильмов"""
    if os.path.exists(MOVIES_FILE):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"{BACKUP_DIR}/movies_backup_{timestamp}.json"
        shutil.copy2(MOVIES_FILE, backup_file)
        
        # Удаляем старые бэкапы (оставляем только последние 5)
        backup_files = sorted(glob.glob(f"{BACKUP_DIR}/movies_backup_*.json"))
        if len(backup_files) > 5:
            for old_backup in backup_files[:-5]:
                os.remove(old_backup)

def load_movies():
    if os.path.exists(MOVIES_FILE):
        with open(MOVIES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_movies(movies):
    """Сохранение фильмов с созданием резервной копии"""
    with open(MOVIES_FILE, "w", encoding="utf-8") as f:
        json.dump(movies, f, ensure_ascii=False, indent=2)
    create_backup()

movies = load_movies()

async def check_subscriptions(user_id, bot):
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(channel, user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        except Exception as e:
            logger.warning(f"Ошибка проверки подписки: {e}")
            return False
    return True

def get_subscribe_keyboard():
    buttons = [[InlineKeyboardButton(f"Подписаться на {ch}", url=f"https://t.me/{ch.lstrip('@')}")] for ch in CHANNELS]
    buttons.append([InlineKeyboardButton("🔄 Проверить подписку", callback_data="check_subs")])
    return InlineKeyboardMarkup(buttons)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"Пользователь {user_id} запустил бота.")
    if not await check_subscriptions(user_id, context.bot):
        await update.message.reply_text(
            "⚠️Для использования бота необходимо подписаться на каналы:",
            reply_markup=get_subscribe_keyboard()
        )
        return
    await show_main_menu(update, context)

async def show_main_menu(update, context):
    user_id = update.effective_user.id
    text = (
        "👋 Добро пожаловать!\n\n"
        "С помощью этого бота вы сможете найти нужный фильм по коду."
    )
    buttons = [[InlineKeyboardButton("🔍 Поиск фильма", callback_data="search")]]
    if user_id == ADMIN_ID:
        buttons.append([InlineKeyboardButton("⚙️ Админ", callback_data="admin")])
    markup = InlineKeyboardMarkup(buttons)
    await update.effective_chat.send_photo(
        WELCOME_PHOTO_ID,
        caption=text,
        reply_markup=markup
    )
    async def check_subs_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    logger.info(f"Пользователь {user_id} проверяет подписку.")
    if not await check_subscriptions(user_id, context.bot):
        try:
            await query.edit_message_text(
                "⚠️Для использования бота необходимо подписаться на каналы:",
                reply_markup=get_subscribe_keyboard()
            )
        except Exception:
            await query.message.reply_text(
                "⚠️Для использования бота необходимо подписаться на каналы:",
                reply_markup=get_subscribe_keyboard()
            )
        return
    await show_main_menu(update, context)

async def search_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        await query.edit_message_text("Введите код фильма (только цифры):")
    except Exception:
        await query.message.reply_text("Введите код фильма (только цифры):")
    context.user_data["search"] = True
    return SEARCH_CODE

async def search_code_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    code = update.message.text.strip()
    logger.info(f"Пользователь {user_id} ищет фильм по коду: {code}")
    
    if not code.isdigit():
        await update.message.reply_text(
            "❌ Код должен содержать только цифры. Попробуйте еще раз:"
        )
        return SEARCH_CODE
        
    if code not in movies:
        await update.message.reply_text(
            "❌ Фильм с таким кодом не найден. Попробуйте еще раз:"
        )
        return SEARCH_CODE
        
    if not await check_subscriptions(user_id, context.bot):
        await update.message.reply_text(
            "⚠️Для просмотра фильма подпишитесь на каналы:",
            reply_markup=get_subscribe_keyboard()
        )
        return ConversationHandler.END
        
    film = movies[code]
    # Увеличиваем счетчик просмотров
    if 'views' not in film:
        film['views'] = 0
    film['views'] += 1
    save_movies(movies)
    
    text = (
        f"*Название:* {film['title']}\n\n"
        f"*Описание:*\n{film['description']}\n\n"
        f"*Ссылки для просмотра ниже 👇*"
    )
    
    film_buttons = [
        [InlineKeyboardButton("▶️ Смотреть на YouTube", url=film['youtube'])],
        [InlineKeyboardButton("🎬 Смотреть ВКонтакте", url=film['vk'])]
    ]
    
    try:
        await update.message.reply_photo(
            film['photo_id'],
            caption=text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(film_buttons)
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке фото: {e}")
        await update.message.reply_text(
            f"⚠️ Не удалось отправить фото фильма.\n\n{text}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(film_buttons)
        )
    return ConversationHandler.END

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    buttons = [
        [InlineKeyboardButton("➕ Добавить фильм", callback_data="add_movie")],
        [InlineKeyboardButton("📋 Список фильмов", callback_data="list_movies_0")],
        [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton("🏠 В меню", callback_data="menu")]
    ]
    try:
        await query.edit_message_text("⚙️ Админ-меню", reply_markup=InlineKeyboardMarkup(buttons))
    except Exception:
        await query.message.reply_text("⚙️ Админ-меню", reply_markup=InlineKeyboardMarkup(buttons))