import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pymongo import MongoClient

# ==================== CONFIGURATION (ENVIRONMENT VARIABLES) ====================
API_ID = int(os.environ.get("API_ID", "1234567"))
API_HASH = os.environ.get("API_HASH", "your_api_hash")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token")
MONGO_URL = os.environ.get("MONGO_URL", "your_mongodb_url")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "123456789"))
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "-1001234567890")) # Thag Channel ID (-100...)

# MongoDB Connection
mongo_client = MongoClient(MONGO_URL)
db = mongo_client["music_bot_db"]
albums_col = db["albums"]
songs_col = db["songs"]

app = Client("MyanmarMusicBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

PAGE_SIZE = 5

# ==================== HELPER FUNCTIONS ====================

# User က Channel ကို Join ထားခြင်း ရှိ/မရှိ စစ်ဆေးခြင်း
async def is_subscribed(client, user_id):
    try:
        member = await client.get_chat_member(CHANNEL_ID, user_id)
        if member.status in ["member", "administrator", "creator"]:
            return True
    except Exception:
        return False
    return False

# 1. HOME KEYBOARD
def get_home_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📚 Albums", callback_data="page_albums_1")],
        [InlineKeyboardButton("🔍 Search Music", callback_data="menu_search")],
        [InlineKeyboardButton("🎤 Artists", callback_data="menu_artists")],
        [InlineKeyboardButton("🆕 New Releases", callback_data="menu_new")],
        [InlineKeyboardButton("❤️ Favorites", callback_data="menu_favs")],
        [InlineKeyboardButton("ℹ️ About / Help", callback_data="menu_help")]
    ])

# 2. ALBUMS KEYBOARD WITH PAGINATION
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
    user_id = message.from_user.id
    
    # Channel Join မထားပါက Force Join Message ပြပါမည်
    if not await is_subscribed(client, user_id):
        try:
            chat = await client.get_chat(CHANNEL_ID)
            channel_url = chat.invite_link or f"https://t.me/{chat.username}"
        except Exception:
            channel_url = "https://t.me/"

        join_buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Channel First", url=channel_url)],
            [InlineKeyboardButton("🔄 Try Again", callback_data="check_join")]
        ])
        return await message.reply_text(
            "⚠️ <b>Bot ကို အသုံးပြုနိုင်ရန် ကျေးဇူးပြု၍ ကျွန်ုပ်တို့၏ Channel ကို မဖြစ်မနေ Join ပေးပါရန်။</b>",
            reply_markup=join_buttons
        )

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
        "၁။ <b>Album သစ်ထည့်ရန်:</b>\n"
        "Album Cover ပုံကို ပို့ပြီး Caption တွင် ရိုက်ပါ -\n"
        "<code>/addalbum Albumအမည် | အဆိုတော်</code>\n\n"
        "၂။ <b>သီချင်းထည့်ရန်:</b>\n"
        "Audio File ကို ပို့ပြီး Caption တွင် ရိုက်ပါ -\n"
        "<code>/addsong Album_ID | သီချင်းအမည် | အဆိုတော်</code>"
    )
    await message.reply_text(text)

# Photo ဖြင့် Album အသစ်ထည့်ခြင်း
@app.on_message(filters.command("addalbum") & filters.user(ADMIN_ID) & filters.private & filters.photo)
async def add_album_by_photo(client, message):
    try:
        data = message.caption.split(" ", 1)[1].split("|")
        title = data[0].strip()
        artist = data[1].strip() if len(data) > 1 else "Unknown"
        cover_file_id = message.photo.file_id

        album_id = albums_col.count_documents({}) + 1
        albums_col.insert_one({
            "_id": album_id,
            "title": title,
            "artist": artist,
            "cover": cover_file_id,
            "songs_count": 0
        })

        await message.reply_text(
            f"✅ <b>Album အသစ် ဖန်တီးပြီးပါပြီ!</b>\n\n"
            f"🆔 <b>Album ID:</b> <code>{album_id}</code>\n"
            f"💿 <b>Title:</b> {title}\n"
            f"🎤 <b>Artist:</b> {artist}"
        )
    except Exception:
        await message.reply_text("❌ စာရိုက်ပုံစံ မှားယွင်းနေပါသည်။\nPhoto ပို့ပြီး Caption တွင် <code>/addalbum Albumအမည် | အဆိုတော်</code> ဟု ရိုက်ပေးပါ။")

# Audio ဖြင့် သီချင်းထည့်ခြင်း
@app.on_message(filters.command("addsong") & filters.user(ADMIN_ID) & filters.private & filters.audio)
async def add_song(client, message):
    try:
        data = message.caption.split(" ", 1)[1].split("|")
        album_id = int(data[0].strip())
        song_title = data[1].strip()
        artist = data[2].strip() if len(data) > 2 else "Unknown"

        file_id = message.audio.file_id
        duration = message.audio.duration

        songs_col.insert_one({
            "album_id": album_id,
            "title": song_title,
            "artist": artist,
            "file_id": file_id,
            "duration": duration
        })

        albums_col.update_one({"_id": album_id}, {"$inc": {"songs_count": 1}})
        await message.reply_text(f"✅ <b>{song_title}</b> သီချင်းအား Album ID ({album_id}) ထဲသို့ ထည့်သွင်းပြီးပါပြီ!")
    except Exception:
        await message.reply_text("❌ စာရိုက်ပုံစံ မှားယွင်းနေပါသည်။\nAudio File ပို့ပြီး Caption တွင် <code>/addsong Album_ID | သီချင်းအမည် | အဆိုတော်</code> ဟု ရိုက်ပေးပါ။")

# ==================== CALLBACK HANDLERS ====================

@app.on_callback_query()
async def callback_handler(client, callback_query: CallbackQuery):
    data = callback_query.data
    user_id = callback_query.from_user.id

    # Check Join Button ပြန်နှိပ်သည့်အခါ
    if data == "check_join":
        if await is_subscribed(client, user_id):
            await callback_query.message.delete()
            text = "<b>မြန်မာသီချင်းများကို အလွယ်တကူ ရှာဖွေ နားဆင်နိုင်ပါသည်။</b> 🎵🎧"
            banner_url = "https://telegra.ph/file/0b263b6526cbdf61b0c03.jpg"
            await client.send_photo(
                chat_id=user_id,
                photo=banner_url,
                caption=text,
                reply_markup=get_home_keyboard()
            )
        else:
            await callback_query.answer("⚠️ Channel ကို Join မထားသေးပါ။ Join ပီးမှ နှိပ်ပါ!", show_alert=True)
        return

    # Home သို့ ပြန်သွားရန်
    if data == "menu_home":
        text = "<b>မြန်မာသီချင်းများကို အလွယ်တကူ ရှာဖွေ နားဆင်နိုင်ပါသည်။</b> 🎵🎧"
        await callback_query.message.edit_caption(
            caption=text,
            reply_markup=get_home_keyboard()
        )
        await callback_query.answer()

    # Album စာရင်းများ ကြည့်ရန်
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
    print("Bot starting successfully...")
    app.run()
