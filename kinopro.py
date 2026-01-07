import os
import logging
import asyncio
import random
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from flask import Flask
import threading

# --- SOZLAMALAR ---
TOKEN = "8568367157:AAFbMZLry3Wj1tjBTOqgcUIdaKCpjPrjN_k"
ADMIN_ID = 6377391436  
ADMIN_USERNAME = "onlyjasur" # @ belgisiz yozing

# Kanallar lug'ati (Vergul bilan to'g'irlandi)
CHANNELS = {
    "@fiftnsvibe": "https://t.me/fiftnsvibe",
    "@KinoHubPro": "https://t.me/KinoHubPro"
}

# Flask (Koyeb porti uchun)
server = Flask(__name__)
@server.route("/")
def home(): return "Bot is running ✅"

def run_flask():
    port = int(os.environ.get("PORT", 8000))
    server.run(host="0.0.0.0", port=port)

# --- BAZA (DIQQAT: SQLite o'rniga Supabase ulanishi kerak!) ---
import sqlite3
def db_query(query, params=(), commit=False, fetchone=False, fetchall=False):
    conn = sqlite3.connect('kinopro_server.db')
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        res = None
        if fetchone: res = cursor.fetchone()
        if fetchall: res = cursor.fetchall()
        if commit: conn.commit()
        return res
    finally: conn.close()

def init_db():
    db_query('''CREATE TABLE IF NOT EXISTS movies (code TEXT PRIMARY KEY, file_id TEXT, caption TEXT)''', commit=True)
    db_query('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, balance INTEGER DEFAULT 0, last_bonus TEXT, premium_until TEXT, views INTEGER DEFAULT 0)''', commit=True)

# --- ASOSIY LOGIKA ---
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
    
    # Ro'yxatdan o'tkazish
    exists = db_query("SELECT user_id FROM users WHERE user_id = ?", (user.id,), fetchone=True)
    if not exists:
        db_query("INSERT INTO users (user_id, username, balance) VALUES (?, ?, 0)", (user.id, user.username), commit=True)
        if args and args[0].isdigit() and int(args[0]) != user.id:
            db_query("UPDATE users SET balance = balance + 3 WHERE user_id = ?", (args[0],), commit=True)
            try: await context.bot.send_message(chat_id=args[0], text="🎉 Yangi do'st qo'shildi! +3 ball.")
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

    # Admin bilan aloqa (TO'G'IRLANDI)
    if text == "📞 Admin bilan aloqa":
        await update.message.reply_text("📝 Adminga xabar yozing (masalan: Muammo bor...):")
        context.user_data['waiting_admin'] = True
        return

    if context.user_data.get('waiting_admin'):
        # Admin ID siga foydalanuvchi xabarini yuborish
        await context.bot.send_message(
            chat_id=ADMIN_ID, 
            text=f"🆘 #ADAL_ALOQA\n👤 Kimdan: {user_id}\n📝 Xabar: {text}"
        )
        await update.message.reply_text("✅ Xabaringiz adminga yuborildi!")
        context.user_data['waiting_admin'] = False
        return

    # Qolgan funksiyalar (Sizning kodingiz...)
    if text == "🎬 Kino olish":
        await update.message.reply_text("🔢 Kino kodini kiriting:")
    elif text.isdigit():
        movie = db_query("SELECT file_id, caption FROM movies WHERE code = ?", (text,), fetchone=True)
        if movie:
            db_query("UPDATE users SET views = views + 1 WHERE user_id = ?", (user_id,), commit=True)
            await update.message.reply_video(video=movie[0], caption=movie[1], parse_mode='HTML')
        else: await update.message.reply_text("😔 Kino topilmadi.")

# --- ISHGA TUSHIRISH ---
if __name__ == "__main__":
    init_db()
    # Portni band qilish
    threading.Thread(target=run_flask, daemon=True).start()
    
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    app.add_handler(CallbackQueryHandler(start, pattern="check")) # Soddalashtirildi
    
    print("🚀 Bot ishga tushdi!")
    app.run_polling()
