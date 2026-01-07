import os
import logging
import asyncio
import random
import psycopg2
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from flask import Flask
import threading

# --- SOZLAMALAR ---
TOKEN = "8568367157:AAFbMZLry3Wj1tjBTOqgcUIdaKCpjPrjN_k"
ADMIN_ID = 6377391436  
DB_URI = "postgresql://postgres:[sgja31306sgja]@db.lkndeumxfdnrtfpbmvxg.supabase.co:5432/postgres"

CHANNELS = {
    "@fiftnsvibe": "https://t.me/fiftnsvibe",
    "@KinoHubPro": "https://t.me/KinoHubPro"
}

# --- SERVER (Koyeb uchun) ---
app = Flask(__name__)
@app.route("/")
def home(): return "Bot is Active! ✅"

def run_flask():
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)

# --- BAZA (PostgreSQL) ---
def get_db_connection():
    return psycopg2.connect(DB_URI)

def db_query(query, params=(), commit=False, fetchone=False, fetchall=False):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(query, params)
        res = None
        if fetchone: res = cur.fetchone()
        if fetchall: res = cur.fetchall()
        if commit: conn.commit()
        return res
    finally:
        cur.close()
        conn.close()

def init_db():
    db_query('''CREATE TABLE IF NOT EXISTS movies (code TEXT PRIMARY KEY, file_id TEXT, caption TEXT)''', commit=True)
    db_query('''CREATE TABLE IF NOT EXISTS users (user_id BIGINT PRIMARY KEY, username TEXT, balance INTEGER DEFAULT 0, last_bonus TEXT, views INTEGER DEFAULT 0)''', commit=True)

# --- MENYULAR ---
def main_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🎬 Kino olish"), KeyboardButton("👤 Kabinet")],
        [KeyboardButton("🎁 Bonus"), KeyboardButton("🔗 Referal")],
        [KeyboardButton("📊 Statistika"), KeyboardButton("📞 Admin bilan aloqa")]
    ], resize_keyboard=True)

def admin_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("➕ Kino qo'shish"), KeyboardButton("❌ Kino o'chirish")],
        [KeyboardButton("📢 Reklama yuborish"), KeyboardButton("🏠 Bosh menyu")]
    ], resize_keyboard=True)

# --- FUNKSIYALAR ---
async def check_subs(user_id, bot):
    if user_id == ADMIN_ID: return True
    for ch in CHANNELS:
        try:
            m = await bot.get_chat_member(chat_id=ch, user_id=user_id)
            if m.status not in ['member', 'administrator', 'creator']: return False
        except: return False
    return True

# --- HANDLERLAR ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    
    exists = db_query("SELECT user_id FROM users WHERE user_id = %s", (user.id,), fetchone=True)
    if not exists:
        db_query("INSERT INTO users (user_id, username) VALUES (%s, %s)", (user.id, user.username), commit=True)
        if args and args[0].isdigit() and int(args[0]) != user.id:
            db_query("UPDATE users SET balance = balance + 3 WHERE user_id = %s", (int(args[0]),), commit=True)
            try: await context.bot.send_message(int(args[0]), "🎉 Referal orqali do'st qo'shildi! +3 ball.")
            except: pass

    if not await check_subs(user.id, context.bot):
        btns = [[InlineKeyboardButton(f"{ch} ✅", url=l)] for ch, l in CHANNELS.items()]
        btns.append([InlineKeyboardButton("Tekshirish 🔄", callback_data="check")])
        await update.message.reply_text("❌ Kanallarga a'zo bo'ling!", reply_markup=InlineKeyboardMarkup(btns))
        return
    await update.message.reply_text("🎬 Kino Hub Pro botiga xush kelibsiz!", reply_markup=main_menu())

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    if not text: return

    # ADMIN PANELGA KIRISH
    if text == "/admin" and user_id == ADMIN_ID:
        await update.message.reply_text("Xush kelibsiz, Admin!", reply_markup=admin_menu())
        return

    # ADMIN FUNKSIYALARI
    if user_id == ADMIN_ID:
        if text == "➕ Kino qo'shish":
            await update.message.reply_text("Kino videosini yuboring va captionga kodini yozing (Masalan: 100)")
            context.user_data['step'] = 'add_movie'
            return
        elif text == "❌ Kino o'chirish":
            await update.message.reply_text("O'chiriladigan kino kodini yozing:")
            context.user_data['step'] = 'del_movie'
            return
        elif text == "📢 Reklama yuborish":
            await update.message.reply_text("Reklama xabarini yuboring (rasm, video yoki matn):")
            context.user_data['step'] = 'broadcast'
            return

    # KINO QO'SHISH JARAYONI
    if context.user_data.get('step') == 'add_movie' and update.message.video:
        code = update.message.caption
        if code:
            db_query("INSERT INTO movies (code, file_id, caption) VALUES (%s, %s, %s) ON CONFLICT (code) DO UPDATE SET file_id=EXCLUDED.file_id", 
                     (code, update.message.video.file_id, code), commit=True)
            await update.message.reply_text(f"✅ Kino {code} kodi bilan saqlandi!")
            context.user_data['step'] = None
            return

    # ODDY FOYDALANUVCHI FUNKSIYALARI
    if text == "🎬 Kino olish":
        await update.message.reply_text("🔢 Kino kodini yozing:")
    elif text == "👤 Kabinet":
        u = db_query("SELECT balance, views FROM users WHERE user_id = %s", (user_id,), fetchone=True)
        await update.message.reply_text(f"👤 ID: {user_id}\n💰 Balans: {u[0]} ball\n👁 Ko'rildi: {u[1]}")
    elif text == "🎁 Bonus":
        u = db_query("SELECT last_bonus FROM users WHERE user_id = %s", (user_id,), fetchone=True)
        today = datetime.now().strftime("%Y-%m-%d")
        if u[0] != today:
            db_query("UPDATE users SET balance = balance + 1, last_bonus = %s WHERE user_id = %s", (today, user_id), commit=True)
            await update.message.reply_text("🎁 Kunlik bonus: +1 ball!")
        else: await update.message.reply_text("❌ Bugun bonus olgansiz.")
    elif text == "🔗 Referal":
        link = f"https://t.me/{(await context.bot.get_me()).username}?start={user_id}"
        await update.message.reply_text(f"🔗 Referal havolangiz:\n{link}\n\nHar bir do'stingiz uchun 3 ball!")
    elif text == "📊 Statistika":
        count = db_query("SELECT COUNT(*) FROM users", fetchone=True)[0]
        await update.message.reply_text(f"📊 Bot a'zolari: {count} ta")
    elif text.isdigit():
        m = db_query("SELECT file_id, caption FROM movies WHERE code = %s", (text,), fetchone=True)
        if m:
            db_query("UPDATE users SET views = views + 1 WHERE user_id = %s", (user_id,), commit=True)
            await update.message.reply_video(video=m[0], caption=f"🎬 Kod: {m[1]}")
        else: await update.message.reply_text("😔 Kino topilmadi.")

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(start, pattern="check"))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_msg))
    app.run_polling()
