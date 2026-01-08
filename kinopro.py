import os
import logging
import asyncio
import psycopg2
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from flask import Flask
import threading

# --- ASOSIY SOZLAMALAR ---
TOKEN = "8568367157:AAFbMZLry3Wj1tjBTOqgcUIdaKCpjPrjN_k"
ADMIN_ID = 6377391436  
DB_URI = "postgresql://postgres:kinoprohub2026@db.lkndeumxfdnrtfpbmvxg.supabase.co:5432/postgres"

CHANNELS = {
    "@fiftnsvibe": "https://t.me/fiftnsvibe",
    "@KinoHubPro": "https://t.me/KinoHubPro"
}

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
    cur.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY, 
        username TEXT, 
        balance INTEGER DEFAULT 0, 
        last_bonus TEXT, 
        views INTEGER DEFAULT 0,
        premium_until TIMESTAMP WITH TIME ZONE DEFAULT NULL)''')
    conn.commit()
    cur.close()
    conn.close()

# --- KLAVIATURALAR ---
def main_kb():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🎬 Kino olish"), KeyboardButton("👤 Kabinet")],
        [KeyboardButton("🎁 Bonus"), KeyboardButton("💎 Premium")],
        [KeyboardButton("📊 Statistika"), KeyboardButton("🔗 Referal")],
        [KeyboardButton("📞 Admin")],
    ], resize_keyboard=True)

def admin_kb():
    return ReplyKeyboardMarkup([
        [KeyboardButton("➕ Kino qo'shish"), KeyboardButton("❌ Kino o'chirish")],
        [KeyboardButton("📢 Reklama"), KeyboardButton("🏠 Bosh menyu")]
    ], resize_keyboard=True)

# --- PREMIUM TEKSHIRISH ---
async def check_and_update_premium(user_id, context):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT premium_until FROM users WHERE user_id = %s", (user_id,))
    res = cur.fetchone()
    if res and res[0]:
        if datetime.now(res[0].tzinfo) > res[0]:
            cur.execute("UPDATE users SET premium_until = NULL WHERE user_id = %s", (user_id,))
            conn.commit()
            await context.bot.send_message(user_id, "⚠️ Premium muddatingiz tugadi.")
    cur.close()
    conn.close()

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
    await check_and_update_premium(user.id, context)
    
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE user_id = %s", (user.id,))
    if not cur.fetchone():
        cur.execute("INSERT INTO users (user_id, username) VALUES (%s, %s)", (user.id, user.username))
        if context.args and context.args[0].isdigit():
            ref_id = int(context.args[0])
            if ref_id != user.id:
                cur.execute("UPDATE users SET balance = balance + 3 WHERE user_id = %s", (ref_id,))
                try: await context.bot.send_message(ref_id, "🎉 +3 ball!")
                except: pass
        conn.commit()
    cur.close()
    conn.close()

    if not await is_subscribed(user.id, context.bot):
        btns = [[InlineKeyboardButton(text=name, url=url)] for name, url in CHANNELS.items()]
        btns.append([InlineKeyboardButton(text="Tekshirish ✅", callback_data="check")])
        await update.message.reply_text("👋 Obuna bo'ling:", reply_markup=InlineKeyboardMarkup(btns))
        return
    await update.message.reply_text("🎬 Kino kodini yuboring:", reply_markup=main_kb())

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    conn = get_connection()
    cur = conn.cursor()

    if text == "/admin" and user_id == ADMIN_ID:
        await update.message.reply_text("Admin paneli:", reply_markup=admin_kb())
    
    elif text == "🏠 Bosh menyu":
        await update.message.reply_text("Bosh menyu:", reply_markup=main_kb())

    elif text == "💎 Premium":
        cur.execute("SELECT balance FROM users WHERE user_id = %s", (user_id,))
        balance = cur.fetchone()[0]
        txt = (f"💎 **KINO HUB PRO — Premium**\n\nSizning balansingiz: {balance} ball\n\n"
               "Hozircha botimiz boshlang'ich jarayonda. Premium orqali loyihani qo'llab-quvvatlang!\n\n"
               "🎫 70 ball — 1 hafta\n🎫 140 ball — 1 oy")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("1 hafta (70 ball)", callback_data="buy_7")],
            [InlineKeyboardButton("1 oy (140 ball)", callback_data="buy_30")],
            [InlineKeyboardButton("💳 Sotib olish (Admin)", url="https://t.me/onlyjasur")] # Admin bilan aloqa
        ])
        await update.message.reply_text(txt, reply_markup=kb, parse_mode="Markdown")

    elif text == "➕ Kino qo'shish" and user_id == ADMIN_ID:
        await update.message.reply_text("Kino videosini yuboring va captionga KODNI yozing.")
        context.user_data['step'] = 'add'

    elif text == "👤 Kabinet":
        cur.execute("SELECT balance, views, premium_until FROM users WHERE user_id = %s", (user_id,))
        u = cur.fetchone()
        p = "Aktiv ✅" if u[2] else "Oddiy 👤"
        await update.message.reply_text(f"👤 Kabinet:\n🆔 ID: {user_id}\n💎 Status: {p}\n💰 Balans: {u[0]} ball")

    elif text.isdigit():
        cur.execute("SELECT file_id, caption FROM movies WHERE code = %s", (text,))
        movie = cur.fetchone()
        if movie:
            cur.execute("UPDATE users SET views = views + 1 WHERE user_id = %s", (user_id,))
            conn.commit()
            # Kino o'zining saqlangan captioni bilan yuboriladi
            await update.message.reply_video(video=movie[0], caption=f"{movie[1]}\n\n@KinoHubPro")
        else:
            await update.message.reply_text("😔 Topilmadi.")

    cur.close()
    conn.close()

async def premium_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    if query.data.startswith("buy_"):
        days = int(query.data.split("_")[1])
        cost = 70 if days == 7 else 140
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT balance FROM users WHERE user_id = %s", (user_id,))
        if cur.fetchone()[0] >= cost:
            until = datetime.now() + timedelta(days=days)
            cur.execute("UPDATE users SET balance = balance - %s, premium_until = %s WHERE user_id = %s", (cost, until, user_id))
            conn.commit()
            await query.edit_message_text(f"✅ Premium {days} kunga faollashdi!")
        else:
            await query.answer("❌ Ballar yetarli emas!", show_alert=True)
        cur.close()
        conn.close()

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if context.user_data.get('step') == 'add' and update.message.video:
        code = update.message.caption # Caption kodi sifatida olinadi
        full_caption = update.message.caption # Izoh to'liq saqlanadi
        if code:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("INSERT INTO movies (code, file_id, caption) VALUES (%s, %s, %s) ON CONFLICT (code) DO UPDATE SET file_id=EXCLUDED.file_id, caption=EXCLUDED.caption", 
                        (code, update.message.video.file_id, full_caption))
            conn.commit()
            cur.close()
            conn.close()
            await update.message.reply_text(f"✅ Saqlandi: {code}")
            context.user_data['step'] = None

# --- ADMIN /SEND BUYRUG'I ---
async def admin_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not update.message.reply_to_message:
        await update.message.reply_text("Xabarga reply qilib /send yozing!")
        return
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users")
    for u in cur.fetchall():
        try: await update.message.reply_to_message.copy(chat_id=u[0]); await asyncio.sleep(0.05)
        except: pass
    await update.message.reply_text("✅ Yuborildi.")
    cur.close()
    conn.close()

async def check_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await is_subscribed(query.from_user.id, context.bot):
        await query.message.delete()
        await query.message.reply_text("🎬 Bosh menyu:", reply_markup=main_kb())
    else:
        await query.answer("❌ Obuna bo'ling!", show_alert=True)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("send", admin_send))
    app.add_handler(CallbackQueryHandler(premium_callback, pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(check_callback, pattern="check"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VIDEO, handle_media))
    app.run_polling()
