import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pymongo import MongoClient

# ==================== CONFIGURATION ====================
API_ID = int(os.environ.get("API_ID", "1234567"))
API_HASH = os.environ.get("API_HASH", "your_api_hash")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token")
MONGO_URL = os.environ.get("MONGO_URL", "your_mongodb_url")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "123456789")) # Admin ID

# Database Connection
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
    total_albums = albums_col.count_documents({})
    total_pages = max(1, (total_albums + PAGE_SIZE - 1) // PAGE_SIZE)
    
    skip = (page - 1) * PAGE_SIZE
    albums = list(albums_col.find().skip(skip).limit(PAGE_SIZE))

    buttons = []
    for alb in albums:
        btn_text = f"🎵 {alb.get('title')} - {alb.get('artist')} ({alb.get('songs_count', 0)} Songs)"
        buttons.append([InlineKeyboardButton(btn_text, callback_data=f"view_album_{alb['_id']}")])
    
    nav = []
    nav.append(InlineKeyboardButton("« Prev", callback_data=f"page_albums_{page-1}" if page > 1 else "noop"))
    nav.append(InlineKeyboardButton(f"{page} / {total_pages}", callback_data="noop"))
    nav.append(InlineKeyboardButton("Next »", callback_data=f"page_albums_{page+1}" if page < total_pages else "noop"))
    
    buttons.append(nav)
    buttons.append([InlineKeyboardButton("🏠 Back to Home", callback_data="menu_home")])
    return InlineKeyboardMarkup(buttons)

# ==================== USER HANDLERS ====================

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    text = "<b>မြန်မာသီချင်းများကို အလွယ်တကူ ရှာဖွေ နားဆင်နိုင်ပါသည်။</b> 🎵🎧"
    banner_url = "https://telegra.ph/file/0b263b6526cbdf61b0c03.jpg"
    await message.reply_photo(
        photo=banner_url,
        caption=text,
        reply_markup=get_home_keyboard()
    )

# ==================== ADMIN COMMANDS ====================

# Admin Panel မီနူး
@app.on_message(filters.command("admin") & filters.user(ADMIN_ID) & filters.private)
async def admin_panel(client, message):
    text = (
        "<b>🛠 ADMIN PANEL</b>\n\n"
        "သီချင်း/Album များ ထည့်သွင်းရန် အောက်ပါ Command များကို သုံးပါ -\n\n"
        "၁။ Album သစ်ထည့်ရန်:\n"
        "<code>/addalbum Albumအမည် | အဆိုတော် | CoverPhoto_URL</code>\n"
        "<i>ဥပမာ: /addalbum ကုသိုလ် | မနော | https://...jpg</i>\n\n"
        "၂။ သီချင်းထည့်ရန် (Audio File အား တွဲ၍ Command စာရိုက်ပါ):\n"
        "<code>/addsong Album_ID | သီချင်းအမည် | အဆိုတော်</code>\n"
        "<i>ဥပမာ: /addsong 1 | ရုက္ခစိုး | မနော</i>"
    )
    await message.reply_text(text)

# Album အသစ်ထည့်ရန် Command
@app.on_message(filters.command("addalbum") & filters.user(ADMIN_ID) & filters.private)
async def add_album(client, message):
    try:
        data = message.text.split(" ", 1)[1].split("|")
        title = data[0].strip()
        artist = data[1].strip()
        cover = data[2].strip() if len(data) > 2 else "https://telegra.ph/file/0b263b6526cbdf61b0c03.jpg"

        album_id = albums_col.count_documents({}) + 1
        albums_col.insert_one({
            "_id": album_id,
            "title": title,
            "artist": artist,
            "cover": cover,
            "songs_count": 0
        })

        await message.reply_text(f"✅ Album အသစ် ထည့်သွင်းအောင်မြင်သည်!\n<b>Album ID:</b> {album_id}\n<b>Title:</b> {title}")
    except Exception as e:
        await message.reply_text("❌ စာရိုက်ပုံစံ မှားယွင်းနေပါသည်။\n<code>/addalbum Albumအမည် | အဆိုတော် | CoverURL</code> ဟု ရိုက်ပါ")

# Audio File ဖြင့် သီချင်းထည့်ရန် Command
@app.on_message(filters.command("addsong") & filters.user(ADMIN_ID) & filters.private & filters.audio)
async def add_song(client, message):
    try:
        data = message.text.split(" ", 1)[1].split("|")
        album_id = int(data[0].strip())
        song_title = data[1].strip()
        artist = data[2].strip() if len(data) > 2 else "Unknown"

        file_id = message.audio.file_id
        duration = message.audio.duration

        # Save Song to Database
        songs_col.insert_one({
            "album_id": album_id,
            "title": song_title,
            "artist": artist,
            "file_id": file_id,
            "duration": duration
        })

        # Update Song Count in Album
        albums_col.update_one({"_id": album_id}, {"$inc": {"songs_count": 1}})

        await message.reply_text(f"✅ <b>{song_title}</b> သီချင်းအား Album ID ({album_id}) ထဲသို့ ထည့်သွင်းပြီးပါပြီ!")
    except Exception as e:
        await message.reply_text("❌ စာရိုက်ပုံစံ မှားယွင်းနေပါသည်။\nAudio File ကို တွဲလျက် <code>/addsong Album_ID | သီချင်းအမည် | အဆိုတော်</code> ဟု ရိုက်ပါ")

# Callback Handlers
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
    print("Bot starting...")
    app.run()
