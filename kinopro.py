import os
import logging
import asyncio
import psycopg2
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from flask import Flask
import threading

# --- TUGMA NOMLARI (XATO BO'LMASLIGI UCHUN) ---
BTN_KINO = "🎬 Kino olish"
BTN_KABINET = "👤 Kabinet"
BTN_BONUS = "🎁 Bonus"
BTN_PREMIUM = "💎 Premium"
BTN_STATS = "📊 Statistika"
BTN_REF = "🔗 Referal"
BTN_ADMIN_CONTACT = "📞 Admin"
BTN_HOME = "🏠 Bosh menyu"

# --- ASOSIY SOZLAMALAR ---
TOKEN = "8568367157:AAFbMZLry3Wj1tjBTOqgcUIdaKCpjPrjN_k"
ADMIN_ID = 6377391436  
DB_URI = "postgresql://postgres:kinoprohub2026@db.lkndeumxfdnrtfpbmvxg.supabase.co:5432/postgres"

CHANNELS = {"@fiftnsvibe": "https://t.me/fiftnsvibe", "@KinoHubPro": "https://t.me/KinoHubPro"}

app = Flask(__name__)
@app.route("/")
def home(): return "Bot Online 🚀"

def run_flask():
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)

def get_connection():
    return psycopg2.connect(DB_URI)

def init_db():
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute('CREATE TABLE IF NOT EXISTS movies (code TEXT PRIMARY KEY, file_id TEXT, caption TEXT)')
        cur.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY, username TEXT, balance INTEGER DEFAULT 0, 
            last_bonus TEXT, views INTEGER DEFAULT 0, premium_until TIMESTAMP WITH TIME ZONE DEFAULT NULL)''')
        conn.commit(); cur.close(); conn.close()
    except Exception as e: print(f"DB Error: {e}")

# --- KLAVIATURALAR ---
def main_kb():
    return ReplyKeyboardMarkup([
        [KeyboardButton(BTN_KINO), KeyboardButton(BTN_KABINET)],
        [KeyboardButton(BTN_BONUS), KeyboardButton(BTN_PREMIUM)],
        [KeyboardButton(BTN_STATS), KeyboardButton(BTN_REF)],
        [KeyboardButton(BTN_ADMIN_CONTACT)],
    ], resize_keyboard=True)

def admin_kb():
    return ReplyKeyboardMarkup([
        [KeyboardButton("➕ Kino qo'shish"), KeyboardButton("❌ Kino o'chirish")],
        [KeyboardButton("📢 Reklama"), KeyboardButton(BTN_HOME)]
    ], resize_keyboard=True)

# --- FUNKSIYALAR ---
async def is_subscribed(user_id, bot):
    if user_id == ADMIN_ID: return True
    for ch in CHANNELS:
        try:
            m = await bot.get_chat_member(chat_id=ch, user_id=user_id)
            if m.status not in ['member', 'administrator', 'creator']: return False
        except: return False
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE user_id = %s", (user.id,))
    if not cur.fetchone():
        cur.execute("INSERT INTO users (user_id, username) VALUES (%s, %s)", (user.id, user.username))
        if context.args and context.args[0].isdigit():
            ref_id = int(context.args[0])
            if ref_id != user.id:
                cur.execute("UPDATE users SET balance = balance + 3 WHERE user_id = %s", (ref_id,))
        conn.commit()
    cur.close(); conn.close()

    if not await is_subscribed(user.id, context.bot):
        btns = [[InlineKeyboardButton(text=n, url=u)] for n, u in CHANNELS.items()]
        btns.append([InlineKeyboardButton(text="Tekshirish ✅", callback_data="check")])
        await update.message.reply_text("👋 Obuna bo'ling:", reply_markup=InlineKeyboardMarkup(btns))
        return
    await update.message.reply_text("🎬 Kino kodini yuboring:", reply_markup=main_kb())

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if not await is_subscribed(user_id, context.bot):
        return await start(update, context)

    conn = get_connection(); cur = conn.cursor()
    try:
        # 1. KABINET
        if text == BTN_KABINET:
            cur.execute("SELECT balance, views, premium_until FROM users WHERE user_id = %s", (user_id,))
            u = cur.fetchone()
            if u:
                p = "Aktiv ✅" if u[2] and u[2] > datetime.now(timezone.utc) else "Oddiy 👤"
                await update.message.reply_text(f"👤 **Kabinet:**\n\n🆔 ID: `{user_id}`\n💎 Status: {p}\n💰 Balans: {u[0]} ball\n🎬 Ko'rilgan: {u[1]} ta", parse_mode="Markdown")

        # 2. PREMIUM
        elif text == BTN_PREMIUM:
            cur.execute("SELECT balance, premium_until FROM users WHERE user_id = %s", (user_id,))
            u = cur.fetchone()
            p_status = u[1].strftime("%Y-%m-%d") if u[1] and u[1] > datetime.now(timezone.utc) else "Aktiv emas ❌"
            txt = f"💎 **Premium:**\n\nBalansingiz: {u[0]} ball\nMuddat: {p_status}"
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("1 hafta (70 ball)", callback_data="buy_7")],
                [InlineKeyboardButton("1 oy (140 ball)", callback_data="buy_30")],
                [InlineKeyboardButton("💳 Admin", url="https://t.me/onlyjasur")]
            ])
            await update.message.reply_text(txt, reply_markup=kb, parse_mode="Markdown")

        # 3. QOLGAN TUGMALAR
        elif text == BTN_KINO:
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🎬 Kanalimiz", url="https://t.me/KinoHubPro")]])
            await update.message.reply_text("Kodlar kanali 👇", reply_markup=kb)

        elif text == BTN_BONUS:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            cur.execute("SELECT last_bonus FROM users WHERE user_id = %s", (user_id,))
            if cur.fetchone()[0] != today:
                cur.execute("UPDATE users SET balance = balance + 1, last_bonus = %s WHERE user_id = %s", (today, user_id))
                conn.commit(); await update.message.reply_text("🎁 Bonus +1 ball!")
            else: await update.message.reply_text("❌ Ertaga qayting.")

        elif text == BTN_STATS:
            cur.execute("SELECT COUNT(*) FROM users"); u_c = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM movies"); m_c = cur.fetchone()[0]
            await update.message.reply_text(f"📊 Azolar: {u_c}\n🎬 Kinolar: {m_c}")

        elif text == BTN_REF:
            b = await context.bot.get_me()
            await update.message.reply_text(f"🔗 Referal: https://t.me/{b.username}?start={user_id}")

        elif text == BTN_ADMIN_CONTACT: await update.message.reply_text("📞 @onlyjasur")
        elif text == BTN_HOME: await update.message.reply_text("Menyu:", reply_markup=main_kb())

        elif text.isdigit():
            cur.execute("SELECT file_id FROM movies WHERE code = %s", (text,))
            m = cur.fetchone()
            if m:
                cur.execute("UPDATE users SET views = views + 1 WHERE user_id = %s", (user_id,)); conn.commit()
                await update.message.reply_video(video=m[0], caption=f"Kodi: {text}\n\n@KinoHubPro")
            else: await update.message.reply_text("😔 Topilmadi.")
    finally: cur.close(); conn.close()

async def add_movie_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or not update.message.reply_to_message or not context.args: return
    code = context.args[0]
    reply = update.message.reply_to_message
    f_id = reply.video.file_id if reply.video else (reply.document.file_id if reply.document else None)
    if f_id:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("INSERT INTO movies (code, file_id, caption) VALUES (%s, %s, %s) ON CONFLICT (code) DO UPDATE SET file_id=EXCLUDED.file_id", (code, f_id, code))
        conn.commit(); cur.close(); conn.close()
        await update.message.reply_text(f"✅ Saqlandi: {code}")

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        await update.message.reply_text("Panel:", reply_markup=admin_kb())

async def premium_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; user_id = query.from_user.id
    if query.data.startswith("buy_"):
        d = 7 if "7" in query.data else 30
        c = 70 if d == 7 else 140
        conn = get_connection(); cur = conn.cursor()
        cur.execute("SELECT balance FROM users WHERE user_id = %s", (user_id,))
        if cur.fetchone()[0] >= c:
            u = datetime.now(timezone.utc) + timedelta(days=d)
            cur.execute("UPDATE users SET balance = balance - %s, premium_until = %s WHERE user_id = %s", (c, u, user_id))
            conn.commit(); await query.edit_message_text(f"✅ Premium {d} kunga faollashdi!")
        else: await query.answer("❌ Balans yetarli emas!", show_alert=True)
        cur.close(); conn.close()

async def check_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_subscribed(update.callback_query.from_user.id, context.bot):
        await update.callback_query.message.delete()
        await update.callback_query.message.reply_text("✅ Xush kelibsiz!", reply_markup=main_kb())

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    init_db()
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("add_movie", add_movie_reply))
    application.add_handler(CallbackQueryHandler(premium_callback, pattern="^buy_"))
    application.add_handler(CallbackQueryHandler(check_callback, pattern="check"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.run_polling()
