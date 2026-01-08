import os
import logging
import asyncio
import psycopg2
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from flask import Flask
import threading

# --- ASOSIY SOZLAMALAR ---
TOKEN = "8568367157:AAFbMZLry3Wj1tjBTOqgcUIdaKCpjPrjN_k"
ADMIN_ID = 6377391436  
# Diqqat: Parolingizni va URI manzilini tekshirib kiritdim
DB_URI = "postgresql://postgres:kinoprohub2026@db.lkndeumxfdnrtfpbmvxg.supabase.co:5432/postgres"

CHANNELS = {
    "@fiftnsvibe": "https://t.me/fiftnsvibe",
    "@KinoHubPro": "https://t.me/KinoHubPro"
}

# --- KOYEB PORT UCHUN (HEALTH CHECK) ---
app = Flask(__name__)
@app.route("/")
def home(): return "Bot is Online 🚀"

def run_flask():
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)

# --- BAZA BILAN ISHLASH ---
def get_connection():
    return psycopg2.connect(DB_URI)

def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS movies (code TEXT PRIMARY KEY, file_id TEXT, caption TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS users (user_id BIGINT PRIMARY KEY, username TEXT, balance INTEGER DEFAULT 0, last_bonus TEXT, views INTEGER DEFAULT 0)''')
    conn.commit()
    cur.close()
    conn.close()

# --- KLAVIATURALAR ---
def main_kb():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🎬 Kino olish"), KeyboardButton("👤 Kabinet")],
        [KeyboardButton("🎁 Bonus"), KeyboardButton("🔗 Referal")],
        [KeyboardButton("📊 Statistika"), KeyboardButton("📞 Admin")],
    ], resize_keyboard=True)

def admin_kb():
    return ReplyKeyboardMarkup([
        [KeyboardButton("➕ Kino qo'shish"), KeyboardButton("❌ Kino o'chirish")],
        [KeyboardButton("📢 Reklama"), KeyboardButton("🏠 Bosh menyu")]
    ], resize_keyboard=True)

# --- OBUNANI TEKSHIRISH ---
async def is_subscribed(user_id, bot):
    if user_id == ADMIN_ID: return True
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status not in ['member', 'administrator', 'creator']: return False
        except: return False
    return True

# --- HANDLERLAR ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = get_connection()
    cur = conn.cursor()
    
    # Ro'yxatdan o'tkazish
    cur.execute("SELECT user_id FROM users WHERE user_id = %s", (user.id,))
    if not cur.fetchone():
        cur.execute("INSERT INTO users (user_id, username) VALUES (%s, %s)", (user.id, user.username))
        # Referal tizimi
        if context.args and context.args[0].isdigit():
            ref_id = int(context.args[0])
            if ref_id != user.id:
                cur.execute("UPDATE users SET balance = balance + 3 WHERE user_id = %s", (ref_id,))
                try: await context.bot.send_message(ref_id, "🎉 Referal: Do'stingiz qo'shildi! +3 ball.")
                except: pass
        conn.commit()
    
    cur.close()
    conn.close()

    if not await is_subscribed(user.id, context.bot):
        btns = [[InlineKeyboardButton(text=name, url=url)] for name, url in CHANNELS.items()]
        btns.append([InlineKeyboardButton(text="Tekshirish ✅", callback_data="check")])
        await update.message.reply_text("👋 Botdan foydalanish uchun kanallarga a'zo bo'ling:", reply_markup=InlineKeyboardMarkup(btns))
        return

    await update.message.reply_text("🎬 Kino kodini yuboring yoki menyudan foydalaning:", reply_markup=main_kb())

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    if not await is_subscribed(user_id, context.bot):
        await start(update, context)
        return

    conn = get_connection()
    cur = conn.cursor()

    # ADMIN PANEL
    if text == "/admin" and user_id == ADMIN_ID:
        await update.message.reply_text("Admin paneli:", reply_markup=admin_kb())
    
    elif text == "🏠 Bosh menyu":
        await update.message.reply_text("Bosh menyu:", reply_markup=main_kb())

    # ADMIN FUNKSIYALARI
    elif text == "➕ Kino qo'shish" and user_id == ADMIN_ID:
        await update.message.reply_text("Kino videosini yuboring va izohiga kodini yozing (masalan: 10).")
        context.user_data['step'] = 'add'
    
    elif text == "❌ Kino o'chirish" and user_id == ADMIN_ID:
        await update.message.reply_text("O'chiriladigan kino kodini yozing:")
        context.user_data['step'] = 'del'

    elif text == "📢 Reklama" and user_id == ADMIN_ID:
        await update.message.reply_text("Reklama xabarini yuboring (rasm, video yoki matn).")
        context.user_data['step'] = 'reklama'

    # FOYDALANUVCHI FUNKSIYALARI
    elif text == "👤 Kabinet":
        cur.execute("SELECT balance, views FROM users WHERE user_id = %s", (user_id,))
        u = cur.fetchone()
        await update.message.reply_text(f"👤 Kabinetingiz:\n\n🆔 ID: {user_id}\n💰 Balans: {u[0]} ball\n👁 Ko'rilgan kinolar: {u[1]}")

    elif text == "📊 Statistika":
        cur.execute("SELECT COUNT(*) FROM users")
        total = cur.fetchone()[0]
        await update.message.reply_text(f"📊 Bot foydalanuvchilari: {total} ta")

    elif text == "🎁 Bonus":
        today = datetime.now().strftime("%Y-%m-%d")
        cur.execute("SELECT last_bonus FROM users WHERE user_id = %s", (user_id,))
        last = cur.fetchone()[0]
        if last != today:
            cur.execute("UPDATE users SET balance = balance + 1, last_bonus = %s WHERE user_id = %s", (today, user_id))
            conn.commit()
            await update.message.reply_text("🎁 Tabriklaymiz! +1 ball berildi.")
        else:
            await update.message.reply_text("❌ Bugun bonus olgansiz. Ertaga qaytib keling!")

    elif text == "🔗 Referal":
        bot_name = (await context.bot.get_me()).username
        link = f"https://t.me/{bot_name}?start={user_id}"
        await update.message.reply_text(f"🔗 Referal havolangiz:\n`{link}`\n\nHar bir taklif uchun 3 ball!")

    elif text == "📞 Admin":
        await update.message.reply_text("Adminga murojaat: @onlyjasur")

    elif text.isdigit():
        cur.execute("SELECT file_id, caption FROM movies WHERE code = %s", (text,))
        movie = cur.fetchone()
        if movie:
            cur.execute("UPDATE users SET views = views + 1 WHERE user_id = %s", (user_id,))
            conn.commit()
            await update.message.reply_video(video=movie[0], caption=f"🎬 Kino kodi: {movie[1]}\n\n@KinoHubPro")
        else:
            await update.message.reply_text("😔 Bu kod bilan kino topilmadi.")

    # STEPS (Admin uchun jarayonlar)
    elif context.user_data.get('step') == 'del':
        cur.execute("DELETE FROM movies WHERE code = %s", (text,))
        conn.commit()
        await update.message.reply_text(f"✅ Kino {text} kodi bilan o'chirildi.")
        context.user_data['step'] = None

    elif context.user_data.get('step') == 'reklama':
        cur.execute("SELECT user_id FROM users")
        all_users = cur.fetchall()
        count = 0
        for uid in all_users:
            try:
                await update.message.copy(chat_id=uid[0])
                count += 1
            except: pass
        await update.message.reply_text(f"✅ Reklama {count} kishi yuborildi.")
        context.user_data['step'] = None

    cur.close()
    conn.close()

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if context.user_data.get('step') == 'add' and update.message.video:
        code = update.message.caption
        if code:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("INSERT INTO movies (code, file_id, caption) VALUES (%s, %s, %s) ON CONFLICT (code) DO UPDATE SET file_id=EXCLUDED.file_id", 
                         (code, update.message.video.file_id, code))
            conn.commit()
            cur.close()
            conn.close()
            await update.message.reply_text(f"✅ Kino {code} kodi bilan saqlandi!")
            context.user_data['step'] = None
        else:
            await update.message.reply_text("❌ Iltimos, video caption (izoh) qismiga kodini yozing!")

async def check_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await is_subscribed(query.from_user.id, context.bot):
        await query.answer("Rahmat, obuna bo'lgansiz! ✅")
        await query.message.delete()
        await query.message.reply_text("🎬 Bosh menyu:", reply_markup=main_kb())
    else:
        await query.answer("❌ Hali obuna bo'lmagansiz!", show_alert=True)

# --- ISHGA TUSHIRISH ---
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    try: init_db()
    except: print("⚠️ Baza ulanmadi, lekin bot ishlashga urunmoqda...")
    
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(check_callback, pattern="check"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VIDEO, handle_media))
    
    print("🚀 Bot Polling rejimida...")
    app.run_polling()
