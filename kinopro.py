import logging
import sqlite3
import asyncio
import random
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# --- SOZLAMALAR (Bularni albatta o'zgartiring) ---
TOKEN = "8568367157:AAFbMZLry3Wj1tjBTOqgcUIdaKCpjPrjN_k" 
ADMIN_ID = 6377391436  
ADMIN_USERNAME = "@onlyjasur" # O'zingizni username'ingiz

# Majburiy obuna (Bot admin bo'lishi shart!)
CHANNELS = {
    "@fiftnsvibe": "https://t.me/fiftnsvibe"
    "@KinoHubPro" "https://t.me/KinoHubPro"
}

# Loglarni sozlash
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- BAZA BILAN ISHLASH ---
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
    finally:
        conn.close()

def init_db():
    # Kinolar jadvali
    db_query('''CREATE TABLE IF NOT EXISTS movies (
        code TEXT PRIMARY KEY, file_id TEXT, genre TEXT, caption TEXT)''', commit=True)
    # Foydalanuvchilar jadvali
    db_query('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, balance INTEGER DEFAULT 0, 
        last_bonus TEXT, premium_until TEXT, views INTEGER DEFAULT 0)''', commit=True)
    print("✅ Ma'lumotlar bazasi server uchun tayyor!")

# --- TEKSHIRUV ---
async def check_all_subs(user_id, bot):
    if user_id == ADMIN_ID: return True
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status not in ['member', 'administrator', 'creator']: return False
        except Exception as e:
            logger.error(f"Kanal tekshirishda xato: {e}")
            return False
    return True

# --- MENYULAR ---
def main_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🎬 Kino olish"), KeyboardButton("👤 Kabinet")],
        [KeyboardButton("🎁 Bonus"), KeyboardButton("💎 Premium Do'kon")],
        [KeyboardButton("🔗 Referal"), KeyboardButton("📊 Statistika")],
        [KeyboardButton("📞 Admin bilan aloqa")]
    ], resize_keyboard=True)

# --- START VA REFERAL ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    
    # Foydalanuvchini ro'yxatga olish
    exists = db_query("SELECT user_id FROM users WHERE user_id = ?", (user.id,), fetchone=True)
    if not exists:
        db_query("INSERT INTO users (user_id, username, balance) VALUES (?, ?, 0)", (user.id, user.username), commit=True)
        # Referal tizimi
        if args and args[0].isdigit() and int(args[0]) != user.id:
            db_query("UPDATE users SET balance = balance + 3 WHERE user_id = ?", (args[0],), commit=True)
            try: await context.bot.send_message(chat_id=args[0], text="🎉 Yangi do'st qo'shildi! Sizga 3 ball berildi.")
            except: pass

    if not await check_all_subs(user.id, context.bot):
        btns = [[InlineKeyboardButton("A'zo bo'lish ✅", url=link)] for ch, link in CHANNELS.items()]
        btns.append([InlineKeyboardButton("Tekshirish 🔄", callback_data="check")])
        await update.message.reply_text("❌ Botdan foydalanish uchun kanallarga a'zo bo'ling!", reply_markup=InlineKeyboardMarkup(btns))
        return

    await update.message.reply_text("🎬 Kino Hub Pro botiga xush kelibsiz!", reply_markup=main_menu())

# --- ASOSIY FUNKSIYALAR ---
async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    if not text: return

    if not await check_all_subs(user_id, context.bot):
        await start(update, context); return

    if text == "👤 Kabinet":
        u = db_query("SELECT balance, views, premium_until FROM users WHERE user_id = ?", (user_id,), fetchone=True)
        prem = u[2] if u[2] else "🚫 Faol emas"
        await update.message.reply_text(f"👤 **Kabinet ma'lumotlari:**\n\n🆔 ID: `{user_id}`\n💰 Balans: **{u[0]} ball**\n💎 Premium: **{prem}**\n👁 Ko'rilgan kinolar: **{u[1]} ta**", parse_mode='Markdown')

    elif text == "🎁 Bonus":
        user = db_query("SELECT last_bonus FROM users WHERE user_id = ?", (user_id,), fetchone=True)
        now = datetime.now()
        if user[0] and now < datetime.strptime(user[0], '%Y-%m-%d %H:%M:%S') + timedelta(days=1):
            await update.message.reply_text("⏳ Bonusni har 24 soatda olish mumkin!")
        else:
            prize = random.randint(1, 10)
            db_query("UPDATE users SET balance = balance + ?, last_bonus = ? WHERE user_id = ?", 
                     (prize, now.strftime('%Y-%m-%d %H:%M:%S'), user_id), commit=True)
            await update.message.reply_text(f"🎁 Tabriklaymiz! Sizga **{prize} ball** berildi!", parse_mode='Markdown')

    elif text == "💎 Premium Do'kon":
        msg = ("💎 **Premium Tariflar**\n\n"
               "🎫 **1 hafta** — 70 ball\n"
               "🎫 **1 oy** — 140 ball\n\n"
               "💳 Haqiqiy pulga (Card) sotib olish uchun admin bilan bog'laning.")
        btns = [
            [InlineKeyboardButton("🎫 1 Hafta (70 ball)", callback_data="buy_1w"), InlineKeyboardButton("🎫 1 Oy (140 ball)", callback_data="buy_1m")],
            [InlineKeyboardButton("👨‍💻 Admin (To'lov uchun)", url=f"https://t.me/{ADMIN_USERNAME.replace('@','')}")]
        ]
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(btns), parse_mode='Markdown')

    elif text == "📊 Statistika":
        u_count = db_query("SELECT COUNT(*) FROM users", fetchone=True)[0]
        m_count = db_query("SELECT COUNT(*) FROM movies", fetchone=True)[0]
        await update.message.reply_text(f"📊 **Bot statistikasi:**\n\n👥 Foydalanuvchilar: {u_count} ta\n🎬 Kinolar bazasi: {m_count} ta", parse_mode='Markdown')

    elif text == "🔗 Referal":
        bot_u = (await context.bot.get_me()).username
        link = f"https://t.me/{bot_u}?start={user_id}"
        await update.message.reply_text(f"🔗 **Referal havolangiz:**\n\n`{link}`\n\nHar bir taklif qilingan do'stingiz uchun **3 ball** olasiz!", parse_mode='Markdown')

    elif text == "📞 Admin bilan aloqa":
        await update.message.reply_text("📝 Adminga yubormoqchi bo'lgan xabaringizni (yoki to'lov chekini) yuboring:")
        context.user_data['waiting_admin'] = True

    elif context.user_data.get('waiting_admin'):
        await context.bot.forward_message(ADMIN_ID, user_id, update.message.message_id)
        await update.message.reply_text("✅ Xabaringiz adminga yuborildi. Tez orada javob olasiz!")
        context.user_data['waiting_admin'] = False

    elif text == "🎬 Kino olish":
        await update.message.reply_text("🔢 Kino kodini kiriting:")

    elif text.isdigit():
        movie = db_query("SELECT file_id, caption FROM movies WHERE code = ?", (text,), fetchone=True)
        if movie:
            db_query("UPDATE users SET views = views + 1 WHERE user_id = ?", (user_id,), commit=True)
            await update.message.reply_video(video=movie[0], caption=movie[1], parse_mode='HTML')
        else:
            await update.message.reply_text("😔 Kechirasiz, bu kod bilan kino topilmadi.")

# --- CALLBACKLAR ---
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    if query.data == "check":
        if await check_all_subs(user_id, context.bot):
            await query.message.delete()
            await query.message.reply_text("✅ Rahmat! Barcha funksiyalar ochildi.", reply_markup=main_menu())
        else: await query.answer("❌ Hali a'zo emassiz!", show_alert=True)

    elif query.data.startswith("buy_"):
        cost = 70 if "1w" in query.data else 140
        days = 7 if "1w" in query.data else 30
        
        bal = db_query("SELECT balance FROM users WHERE user_id = ?", (user_id,), fetchone=True)[0]
        if bal >= cost:
            end = (datetime.now() + timedelta(days=days)).strftime('%d.%m.%Y')
            db_query("UPDATE users SET balance = balance - ?, premium_until = ? WHERE user_id = ?", (cost, end, user_id), commit=True)
            await query.message.edit_text(f"💎 Premium faol! Muddat: {end}")
        else: await query.answer("❌ Ballaringiz yetarli emas!", show_alert=True)

# --- ADMIN BUYRUQLARI ---
async def add_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        code = context.args[0]
        video = update.message.reply_to_message.video.file_id
        cap = update.message.reply_to_message.caption or "🎬"
        db_query("INSERT OR REPLACE INTO movies (code, file_id, caption) VALUES (?, ?, ?)", (code, video, cap), commit=True)
        await update.message.reply_text(f"✅ Kino {code} kodi bilan saqlandi!")
    except: await update.message.reply_text("⚠️ Xato! Videoga reply qilib yozing: /add_movie 123")

async def send_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or not update.message.reply_to_message: return
    users = db_query("SELECT user_id FROM users", fetchall=True)
    await update.message.reply_text(f"🚀 {len(users)} kishiga xabar yuborilmoqda...")
    for u in users:
        try:
            await context.bot.copy_message(u[0], update.effective_chat.id, update.message.reply_to_message.message_id)
            await asyncio.sleep(0.05)
        except: continue
    await update.message.reply_text("✅ Reklama tarqatildi.")

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add_movie", add_movie))
    app.add_handler(CommandHandler("send", send_all))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_msg)) # Rasm va videolar uchun
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from flask import Flask
import threading
import os

TOKEN = os.environ.get("8568367157:AAFbMZLry3Wj1tjBTOqgcUIdaKCpjPrjN_k")

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running ✅"

def run_flask():
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Salom! Bot ishlayapti 🚀")

def run_bot():
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.run_polling()

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    run_bot()
