import os
import logging
import asyncio
import random
import psycopg2 # Supabase uchun kerak
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from flask import Flask
import threading

# --- SOZLAMALAR ---
TOKEN = "8568367157:AAFbMZLry3Wj1tjBTOqgcUIdaKCpjPrjN_k"
ADMIN_ID = 6377391436  
ADMIN_USERNAME = "onlyjasur" 
# Supabase URI (Parolingizni [YOUR-PASSWORD] o'rniga yozing)
DB_URI = "postgresql://postgres:[sgja31306sgja]@db.lkndeumxfdnrtfpbmvxg.supabase.co:5432/postgres"

CHANNELS = {
    "@fiftnsvibe": "https://t.me/fiftnsvibe",
    "@KinoHubPro": "https://t.me/KinoHubPro"
}

# Koyeb Porti uchun Flask
server = Flask(__name__)
@server.route("/")
def home(): return "Bot is running on Supabase ✅"

def run_flask():
    port = int(os.environ.get("PORT", 8000))
    server.run(host="0.0.0.0", port=port)

# --- SUPABASE (POSTGRESQL) BILAN ISHLASH ---
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
    # PostgreSQL sintaksisiga moslangan jadvallar
    db_query('''CREATE TABLE IF NOT EXISTS movies (
        code TEXT PRIMARY KEY, file_id TEXT, caption TEXT)''', commit=True)
    db_query('''CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY, username TEXT, balance INTEGER DEFAULT 0, 
        last_bonus TEXT, premium_until TEXT, views INTEGER DEFAULT 0)''', commit=True)

# --- ASOSIY FUNKSIYALAR ---
async def check_all_subs(user_id, bot):
    if user_id == ADMIN_ID: return True
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status not in ['member', 'administrator', 'creator']: return False
        except: return False
    return True

def main_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🎬 Kino olish"), KeyboardButton("👤 Kabinet")],
        [KeyboardButton("🎁 Bonus"), KeyboardButton("💎 Premium Do'kon")],
        [KeyboardButton("🔗 Referal"), KeyboardButton("📊 Statistika")],
        [KeyboardButton("📞 Admin bilan aloqa")]
    ], resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    
    exists = db_query("SELECT user_id FROM users WHERE user_id = %s", (user.id,), fetchone=True)
    if not exists:
        db_query("INSERT INTO users (user_id, username, balance) VALUES (%s, %s, 0)", (user.id, user.username), commit=True)
        if args and args[0].isdigit() and int(args[0]) != user.id:
            db_query("UPDATE users SET balance = balance + 3 WHERE user_id = %s", (int(args[0]),), commit=True)
            try: await context.bot.send_message(chat_id=int(args[0]), text="🎉 Yangi do'st qo'shildi! +3 ball.")
            except: pass

    if not await check_all_subs(user.id, context.bot):
        btns = [[InlineKeyboardButton(f"{ch} ✅", url=link)] for ch, link in CHANNELS.items()]
        btns.append([InlineKeyboardButton("Tekshirish 🔄", callback_data="check")])
        await update.message.reply_text("❌ Botdan foydalanish uchun kanallarga a'zo bo'ling!", reply_markup=InlineKeyboardMarkup(btns))
        return

    await update.message.reply_text("🎬 Kino Hub Pro botiga xush kelibsiz!", reply_markup=main_menu())

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    if not text: return

    if text == "👤 Kabinet":
        u = db_query("SELECT balance, views, premium_until FROM users WHERE user_id = %s", (user_id,), fetchone=True)
        prem = u[2] if u[2] else "🚫 Faol emas"
        await update.message.reply_text(f"👤 **Kabinet:**\n\n🆔 ID: `{user_id}`\n💰 Balans: {u[0]}\n💎 Premium: {prem}\n👁 Ko'rilgan: {u[1]}", parse_mode='Markdown')

    elif text == "📞 Admin bilan aloqa":
        await update.message.reply_text("📝 Adminga xabaringizni yozing:")
        context.user_data['waiting_admin'] = True
        return

    elif context.user_data.get('waiting_admin'):
        await context.bot.send_message(ADMIN_ID, f"🆘 #XABAR\n👤 ID: {user_id}\n📝 Matn: {text}")
        await update.message.reply_text("✅ Yuborildi!")
        context.user_data['waiting_admin'] = False
        return

    elif text == "🎬 Kino olish":
        await update.message.reply_text("🔢 Kino kodini kiriting:")
    elif text.isdigit():
        movie = db_query("SELECT file_id, caption FROM movies WHERE code = %s", (text,), fetchone=True)
        if movie:
            db_query("UPDATE users SET views = views + 1 WHERE user_id = %s", (user_id,), commit=True)
            await update.message.reply_video(video=movie[0], caption=movie[1], parse_mode='HTML')
        else: await update.message.reply_text("😔 Kino topilmadi.")

# --- ISHGA TUSHIRISH ---
if __name__ == "__main__":
    init_db()
    threading.Thread(target=run_flask, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    app.add_handler(CallbackQueryHandler(start, pattern="check"))
    print("🚀 Bot Supabase bazasi bilan ishga tushdi!")
    app.run_polling()
