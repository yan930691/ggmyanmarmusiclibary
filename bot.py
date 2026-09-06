import os
import sys
import logging
import traceback
import asyncio
from aiohttp import web

# ==================== PYTHON 3.12+ ASYNCIO FIX ====================
try:
    asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pymongo import MongoClient

# ==================== DETAILED ERROR LOGGING SYSTEM ====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s"
)
logger = logging.getLogger(__name__)

logger.info("🚀 Bot initialization started...")

# ==================== CONFIGURATION (ENVIRONMENT VARIABLES) ====================
try:
    API_ID_RAW = os.environ.get("API_ID", "").strip()
    API_HASH = os.environ.get("API_HASH", "").strip()
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
    MONGO_URL = os.environ.get("MONGO_URL", "").strip()
    ADMIN_ID_RAW = os.environ.get("ADMIN_ID", "").strip()
    CHANNEL_ID_RAW = os.environ.get("CHANNEL_ID", "").strip()

    missing_vars = []
    if not API_ID_RAW: missing_vars.append("API_ID")
    if not API_HASH: missing_vars.append("API_HASH")
    if not BOT_TOKEN: missing_vars.append("BOT_TOKEN")
    if not MONGO_URL: missing_vars.append("MONGO_URL")
    if not ADMIN_ID_RAW: missing_vars.append("ADMIN_ID")
    if not CHANNEL_ID_RAW: missing_vars.append("CHANNEL_ID")

    if missing_vars:
        logger.error(f"❌ ERROR: Render Environment Variables တွင် မပြည့်စုံသေးပါ -> {', '.join(missing_vars)}")
        sys.exit(1)

    API_ID = int(API_ID_RAW)
    ADMIN_ID = int(ADMIN_ID_RAW)
    CHANNEL_ID = int(CHANNEL_ID_RAW)
    logger.info("✅ Environment Variables များကို အောင်မြင်စွာ ဖတ်ယူပြီးပါပြီ။")

except ValueError as ve:
    logger.error(f"❌ ERROR: API_ID, ADMIN_ID သို့မဟုတ် CHANNEL_ID တွင် စာသားများ ပါနေပါသည်။ ကိန်းဂဏန်း (Integer) သာ ထည့်ပါ: {ve}")
    sys.exit(1)
except Exception as e:
    logger.error(f"❌ CONFIG ERROR: {e}\n{traceback.format_exc()}")
    sys.exit(1)

# ==================== DATABASE CONNECTION ====================
try:
    logger.info("⏳ MongoDB သို့ ချိတ်ဆက်နေပါသည်...")
    mongo_client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
    mongo_client.admin.command('ping')
    logger.info("✅ MongoDB ချိတ်ဆက်မှု အောင်မြင်ပါသည်။")
    
    db = mongo_client["music_bot_db"]
    albums_col = db["albums"]
    songs_col = db["songs"]
except Exception as e:
    logger.error(f"❌ MONGODB ERROR: MongoDB ချိတ်ဆက်၍ မရပါ။ MONGO_URL မှန်မမှန် ပြန်စစ်ပါ:\n{traceback.format_exc()}")
    sys.exit(1)

app = Client("MyanmarMusicBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

PAGE_SIZE = 5

# ==================== RENDER FREE PLAN DUMMY WEB SERVER ====================
async def handle_ping(request):
    return web.Response(text="Bot is Alive & Running!")

async def start_web_server():
    server = web.Application()
    server.router.add_get("/", handle_ping)
    runner = web.AppRunner(server)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"🌐 Dummy Web Server started on port {port} for Render Free Plan")

# ==================== HELPER FUNCTIONS ====================

async def is_subscribed(client, user_id):
    try:
        member = await client.get_chat_member(CHANNEL_ID, user_id)
        if member.status in ["member", "administrator", "creator"]:
            return True
    except Exception as e:
        logger.warning(f"⚠️ User ({user_id}) Channel Join စစ်ဆေးစဉ် Error: {e}")
        return False
    return False

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
    try:
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
    except Exception as e:
        logger.error(f"❌ ALBUM KEYBOARD ERROR:\n{traceback.format_exc()}")
        return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Back to Home", callback_data="menu_home")]])

# ==================== USER HANDLERS ====================

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    try:
        user_id = message.from_user.id
        
        if not await is_subscribed(client, user_id):
            try:
                chat = await client.get_chat(CHANNEL_ID)
                channel_url = chat.invite_link or f"https://t.me/{chat.username}"
            except Exception as e:
                logger.error(f"❌ CHANNEL INFO ERROR: {e}")
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
        
        # ========== FIX: Photo မရရင် Text နဲ့ Fallback ==========
        try:
            await message.reply_photo(
                photo=banner_url, 
                caption=text, 
                reply_markup=get_home_keyboard()
            )
        except Exception as photo_error:
            logger.warning(f"⚠️ Photo ပို့လို့မရဘူး၊ Text နဲ့ အစားထိုးလိုက်တယ်: {photo_error}")
            await message.reply_text(
                text, 
                reply_markup=get_home_keyboard()
            )
        # ======================================================
        
    except Exception as e:
        logger.error(f"❌ START COMMAND ERROR:\n{traceback.format_exc()}")
        # ဘယ်လိုမှ မရရင်တောင် ဒီအောက်က စာတစ်ခုခုတော့ ပြန်ပို့ပေးပါ
        await message.reply_text("❌ နည်းပညာအချို့အရ ဝန်ဆောင်မှု ယာယီရပ်နားထားပါသည်။ နောက်မှ ပြန်ကြိုးစားပါ။")

# ==================== ADMIN COMMANDS ====================

@app.on_message(filters.command("admin") & filters.user(ADMIN_ID) & filters.private)
async def admin_panel(client, message):
    try:
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
    except Exception as e:
        logger.error(f"❌ ADMIN PANEL ERROR:\n{traceback.format_exc()}")

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
    except Exception as e:
        logger.error(f"❌ ADD ALBUM ERROR:\n{traceback.format_exc()}")
        await message.reply_text("❌ စာရိုက်ပုံစံ မှားယွင်းနေပါသည်။\nPhoto ပို့ပြီး Caption တွင် <code>/addalbum Albumအမည် | အဆိုတော်</code> ဟု ရိုက်ပေးပါ။")

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
    except Exception as e:
        logger.error(f"❌ ADD SONG ERROR:\n{traceback.format_exc()}")
        await message.reply_text("❌ စာရိုက်ပုံစံ မှားယွင်းနေပါသည်။\nAudio File ပို့ပြီး Caption တွင် <code>/addsong Album_ID | သီချင်းအမည် | အဆိုတော်</code> ဟု ရိုက်ပေးပါ။")

# ==================== CALLBACK HANDLERS ====================

@app.on_callback_query()
async def callback_handler(client, callback_query: CallbackQuery):
    try:
        data = callback_query.data
        user_id = callback_query.from_user.id

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

    except Exception as e:
        logger.error(f"❌ CALLBACK ERROR:\n{traceback.format_exc()}")
        await callback_query.answer("⚠️ Error တစ်ခု ဖြစ်ပေါ်သွားပါသည်!", show_alert=True)

# ==================== MAIN EXECUTION ====================

async def main():
    await start_web_server()
    await app.start()
    logger.info("🎉 Bot ကို Free Plan ပေါ်တွင် အောင်မြင်စွာ တင်ဆက်လိုက်ပါပြီ (Running...)...")
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.critical(f"💥 CRITICAL BOT RUNTIME ERROR:\n{traceback.format_exc()}")
