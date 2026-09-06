import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pymongo import MongoClient

# ==================== CONFIGURATION (FROM ENVIRONMENT VARIABLES) ====================
API_ID = int(os.environ.get("API_ID", "1234567"))
API_HASH = os.environ.get("API_HASH", "your_api_hash")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token")
MONGO_URL = os.environ.get("MONGO_URL", "your_mongodb_url")

# Mongo Database Connection
mongo_client = MongoClient(MONGO_URL)
db = mongo_client["music_bot_db"]
albums_col = db["albums"]
songs_col = db["songs"]

app = Client("MyanmarMusicBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

PAGE_SIZE = 5

# ==================== HELPER KEYBOARDS ====================

def get_home_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📚 Albums", callback_data="page_albums_1")],
        [InlineKeyboardButton("🔍 Search Music", callback_data="menu_search")],
        [InlineKeyboardButton("🎤 Artists", callback_data="menu_artists")],
        [InlineKeyboardButton("🆕 New Releases", callback_data="menu_new")],
        [InlineKeyboardButton("❤️ Favorites", callback_data="menu_favs")],
        [InlineKeyboardButton("ℹ️ About / Help", callback_data="menu_help")]
    ])

def get_albums_keyboard(page: int = 1):
    # MongoDB မှ Albums များကို ရှာယူခြင်း
    total_albums = albums_col.count_documents({})
    total_pages = max(1, (total_albums + PAGE_SIZE - 1) // PAGE_SIZE)
    
    skip = (page - 1) * PAGE_SIZE
    albums = list(albums_col.find().skip(skip).limit(PAGE_SIZE))

    buttons = []
    for alb in albums:
        btn_text = f"🎵 {alb.get('title')} - {alb.get('artist')} ({alb.get('songs_count', 0)} Songs)"
        buttons.append([InlineKeyboardButton(btn_text, callback_data=f"view_album_{alb['_id']}")])
    
    # Navigation
    nav = []
    nav.append(InlineKeyboardButton("« Prev", callback_data=f"page_albums_{page-1}" if page > 1 else "noop"))
    nav.append(InlineKeyboardButton(f"{page} / {total_pages}", callback_data="noop"))
    nav.append(InlineKeyboardButton("Next »", callback_data=f"page_albums_{page+1}" if page < total_pages else "noop"))
    
    buttons.append(nav)
    buttons.append([InlineKeyboardButton("🏠 Back to Home", callback_data="menu_home")])
    return InlineKeyboardMarkup(buttons)

# ==================== HANDLERS ====================

@app.on_message(filters.command("start"))
async def start_handler(client, message):
    text = (
        f"မင်္ဂလာပါရှင် 👋\n"
        f"<b>မြန်မာသီချင်းများကို အလွယ်တကူ ရှာဖွေ နားဆင်နိုင်ပါသည်။</b> 🎵🎧"
    )
    banner_url = "https://telegra.ph/file/0b263b6526cbdf61b0c03.jpg"
    await message.reply_photo(
        photo=banner_url,
        caption=text,
        reply_markup=get_home_keyboard()
    )

@app.on_callback_query()
async def callback_handler(client, callback_query: CallbackQuery):
    data = callback_query.data
    
    if data == "menu_home":
        text = "<b>မြန်မာသီချင်းများကို အလွယ်တကူ ရှာဖွေ နားဆင်နိုင်ပါသည်။</b> 🎵🎧"
        await callback_query.message.edit_caption(
            caption=text,
            reply_markup=get_home_keyboard()
        )
        await callback_query.answer()

    elif data.startswith("page_albums_"):
        page = int(data.split("_")[2])
        text = "📚 <b>ALBUM COLLECTION</b>\nအယ်လ်ဘမ် ရွေးချယ်ပါ"
        await callback_query.message.edit_caption(
            caption=text,
            reply_markup=get_albums_keyboard(page=page)
        )
        await callback_query.answer()

    elif data == "noop":
        await callback_query.answer()

if __name__ == "__main__":
    print("Bot is starting...")
    app.run()
