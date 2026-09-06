import os
import sys
import logging
import traceback
import asyncio
from aiohttp import web
from pyrogram import Client, filters
from pymongo import MongoClient

# ==================== LOGGING ====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s"
)
logger = logging.getLogger(__name__)

# ==================== ENVIRONMENT VARIABLES ====================
try:
    API_ID = int(os.getenv("API_ID"))
    API_HASH = os.getenv("API_HASH")
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    MONGO_URL = os.getenv("MONGO_URL")
    ADMIN_ID = int(os.getenv("ADMIN_ID"))
    PORT = int(os.getenv("PORT", 8080))

    if not all([API_ID, API_HASH, BOT_TOKEN, MONGO_URL, ADMIN_ID]):
        logger.error("❌ Environment Variables တွေ မပြည့်စုံပါ။")
        sys.exit(1)
    logger.info("✅ Environment Variables အကုန် ဖတ်မိပါပြီ။")
except Exception as e:
    logger.error(f"❌ Config Error: {e}")
    sys.exit(1)

# ==================== DATABASE ====================
try:
    mongo_client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
    mongo_client.admin.command('ping')
    db = mongo_client["music_bot_db"]
    albums_col = db["albums"]
    songs_col = db["songs"]
    logger.info("✅ MongoDB ချိတ်ဆက်မှု အောင်မြင်ပါသည်။")
except Exception as e:
    logger.error(f"❌ MongoDB Error: {e}")
    sys.exit(1)

# ==================== BOT INITIALIZATION ====================
app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ==================== WEB SERVER FOR RENDER ====================
async def web_server():
    web_app = web.Application()
    web_app.router.add_get("/", lambda r: web.Response(text="Bot is running!"))
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"🌐 Web server started on port {PORT}")

# ==================== USER COMMANDS (မြန်မာလို) ====================

@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    try:
        logger.info(f"📩 /start from {message.from_user.id}")
        await message.reply_text(
            "🎵 **မင်္ဂလာပါ! Myanmar Music Library Bot မှ ကြိုဆိုပါတယ်။**\n\n"
            "ကျွန်တော်ဟာ သီချင်းစာကြည့်တိုက် Bot ဖြစ်ပါတယ်။ အောက်ပါ Command များကို အသုံးပြုနိုင်ပါတယ်။\n"
            "/help - အကူအညီ ကြည့်ရန်\n"
            "/admin - အက်ဒမင် Panel ဖွင့်ရန်"
        )
    except Exception as e:
        logger.error(f"❌ Start Error: {e}")

@app.on_message(filters.command("help") & filters.private)
async def help_command(client, message):
    try:
        await message.reply_text(
            "📋 **ရရှိနိုင်သော Command များ:**\n\n"
            "/start - Bot ကို စတင်ရန်\n"
            "/help - ဤအကူအညီ စာသားကို ကြည့်ရန်\n"
            "/test - Bot အလုပ်လုပ်မလား စစ်ရန်\n"
            "/admin - အက်ဒမင် Panel (သီချင်းနှင့် Album ထည့်ရန်)"
        )
    except Exception as e:
        logger.error(f"❌ Help Error: {e}")

@app.on_message(filters.command("test") & filters.private)
async def test_command(client, message):
    try:
        logger.info(f"🧪 /test from {message.from_user.id}")
        await message.reply_text("✅ **Bot အလုပ်လုပ်နေပါပြီ!**")
    except Exception as e:
        logger.error(f"❌ Test Error: {e}")

# ==================== ADMIN COMMANDS (မြန်မာလို) ====================

@app.on_message(filters.command("admin") & filters.user(ADMIN_ID) & filters.private)
async def admin_panel(client, message):
    try:
        await message.reply_text(
            "🛠 **အက်ဒမင် Panel**\n\n"
            "၁။ **Album အသစ်ထည့်ရန်:**\n"
            "ပုံ (Photo) ပို့ပြီး Caption တွင် အောက်ပါအတိုင်း ရိုက်ပါ။\n"
            "<code>/addalbum အယ်လ်ဘမ်အမည် | အဆိုတော်အမည်</code>\n\n"
            "၂။ **သီချင်းအသစ်ထည့်ရန်:**\n"
            "Audio File ပို့ပြီး Caption တွင် အောက်ပါအတိုင်း ရိုက်ပါ။\n"
            "<code>/addsong Album_ID | သီချင်းအမည် | အဆိုတော်အမည်</code>"
        )
    except Exception as e:
        logger.error(f"❌ Admin Panel Error: {e}")

@app.on_message(filters.command("addalbum") & filters.user(ADMIN_ID) & filters.private & filters.photo)
async def add_album(client, message):
    try:
        # /addalbum အယ်လ်ဘမ်အမည် | အဆိုတော်
        parts = message.caption.split(" ", 1)[1].split("|")
        title = parts[0].strip()
        artist = parts[1].strip() if len(parts) > 1 else "Unknown"
        
        album_id = albums_col.count_documents({}) + 1
        albums_col.insert_one({
            "_id": album_id,
            "title": title,
            "artist": artist,
            "cover": message.photo.file_id,
            "songs_count": 0
        })
        
        await message.reply_text(
            f"✅ **Album အသစ် ဖန်တီးပြီးပါပြီ!**\n\n"
            f"🆔 **Album ID:** <code>{album_id}</code>\n"
            f"💿 **အမည်:** {title}\n"
            f"🎤 **အဆိုတော်:** {artist}"
        )
    except Exception as e:
        logger.error(f"❌ Add Album Error: {traceback.format_exc()}")
        await message.reply_text(
            "❌ စာရိုက်ပုံစံ မှားယွင်းနေပါသည်။\n"
            "Photo ပို့ပြီး Caption တွင် <code>/addalbum အယ်လ်ဘမ်အမည် | အဆိုတော်အမည်</code> ဟု ရိုက်ပေးပါ။"
        )

@app.on_message(filters.command("addsong") & filters.user(ADMIN_ID) & filters.private & filters.audio)
async def add_song(client, message):
    try:
        # /addsong Album_ID | သီချင်းအမည် | အဆိုတော်
        parts = message.caption.split(" ", 1)[1].split("|")
        album_id = int(parts[0].strip())
        song_title = parts[1].strip()
        artist = parts[2].strip() if len(parts) > 2 else "Unknown"
        
        songs_col.insert_one({
            "album_id": album_id,
            "title": song_title,
            "artist": artist,
            "file_id": message.audio.file_id,
            "duration": message.audio.duration
        })
        
        albums_col.update_one({"_id": album_id}, {"$inc": {"songs_count": 1}})
        
        await message.reply_text(
            f"✅ **{song_title}** သီချင်းအား Album ID ({album_id}) ထဲသို့ ထည့်သွင်းပြီးပါပြီ!"
        )
    except Exception as e:
        logger.error(f"❌ Add Song Error: {traceback.format_exc()}")
        await message.reply_text(
            "❌ စာရိုက်ပုံစံ မှားယွင်းနေပါသည်။\n"
            "Audio File ပို့ပြီး Caption တွင် <code>/addsong Album_ID | သီချင်းအမည် | အဆိုတော်အမည်</code> ဟု ရိုက်ပေးပါ။"
        )

# ==================== MAIN ====================
async def main():
    await web_server()
    await app.start()
    logger.info("🚀 Bot started successfully!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.critical(f"💥 CRITICAL ERROR: {traceback.format_exc()}")
