import os
import logging
import asyncio
import psycopg2
from datetime import datetime, timedelta, timezone
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
    try:
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
    except Exception as e:
        print(f"Baza xatosi: {e}")

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

# --- OBUNA TEKSHIRISH ---
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
    try:
        cur.execute("SELECT user_id FROM users WHERE user_id = %s", (user.id,))
        if not cur.fetchone():
            cur.execute("INSERT INTO users (user_id, username) VALUES (%s, %s)", (user.id, user.username))
            if context.args and context.args[0].isdigit():
                ref_id = int(context.args[0])
                if ref_id != user.id:
                    cur.execute("UPDATE users SET balance = balance + 3 WHERE user_id = %s", (ref_id,))
                    try: await context.bot.send_message(ref_id, "🎉 Do'stingiz qo'shildi! +3 ball.")
                    except: pass
            conn.commit()
    finally:
        cur.close()
        conn.close()

    if not await is_subscribed(user.id, context.bot):
        btns = [[InlineKeyboardButton(text=name, url=url)] for name, url in CHANNELS.items()]
        btns.append([InlineKeyboardButton(text="Tekshirish ✅", callback_data="check")])
        await update.message.reply_text("👋 Botdan foydalanish uchun kanallarga a'zo bo'ling:", reply_markup=InlineKeyboardMarkup(btns))
        return
    await update.message.reply_text("🎬 Kino kodini yuboring:", reply_markup=main_kb())

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        await update.message.reply_text("👨‍💻 Admin paneli ochildi:", reply_markup=admin_kb())

# --- YANGI KINO QO'SHISH FUNKSIYASI (REPLY ORQALI) ---
async def add_movie_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Xato: Kino fayliga reply qilib `/add_movie kod` deb yozing.")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Xato: Kodni yozmadingiz. Masalan: `/add_movie 123`")
        return

    code = context.args[0]
    reply = update.message.reply_to_message
    file_id = None

    if reply.video: file_id = reply.video.file_id
    elif reply.document: file_id = reply.document.file_id

    if not file_id:
        await update.message.reply_text("❌ Xato: Reply qilingan xabarda video yoki fayl yo'q.")
        return

    conn = get_connection(); cur = conn.cursor()
    try:
        cur.execute("INSERT INTO movies (code, file_id, caption) VALUES (%s, %s, %s) ON CONFLICT (code) DO UPDATE SET file_id=EXCLUDED.file_id", (code, file_id, code))
        conn.commit()
        await update.message.reply_text(f"✅ Saqlandi! Kod: `{code}`", parse_mode="Markdown")
    finally:
        cur.close(); conn.close()

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if not await is_subscribed(user_id, context.bot):
        return await start(update, context)

    conn = get_connection(); cur = conn.cursor()
    try:
        if text == "🎬 Kino olish":
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🎬 Kino kodlari kanali", url="https://t.me/KinoHubPro")]])
            await update.message.reply_text("Kino kodlari shu kanalda 👇", reply_markup=kb)

        elif text == "👤 Kabinet":
            cur.execute("SELECT balance, views, premium_until FROM users WHERE user_id = %s", (user_id,))
            u = cur.fetchone()
            if u:
                p = "Aktiv ✅" if u[2] and u[2] > datetime.now(timezone.utc) else "Oddiy 👤"
                await update.message.reply_text(f"👤 **Sizning ma'lumotlaringiz:**\n\n🆔 ID: `{user_id}`\n💎 Status: {p}\n💰 Balans: {u[0]} ball\n🎬 Ko'rilgan: {u[1]} ta", parse_mode="Markdown")

        elif text == "💎 Premium":
            cur.execute("SELECT balance, premium_until FROM users WHERE user_id = %s", (user_id,))
            u = cur.fetchone()
            p_status = u[1].strftime("%Y-%m-%d") if u[1] and u[1] > datetime.now(timezone.utc) else "Aktiv emas ❌"
            txt = f"💎 **Premium Markazi**\n\nBalansingiz: {u[0]} ball\nMuddat: {p_status}"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("1 hafta (70 ball)", callback_data="buy_7")], [InlineKeyboardButton("1 oy (140 ball)", callback_data="buy_30")], [InlineKeyboardButton("💳 Admin", url="https://t.me/onlyjasur")]])
            await update.message.reply_text(txt, reply_markup=kb, parse_mode="Markdown")

        elif text == "🎁 Bonus":
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            cur.execute("SELECT last_bonus FROM users WHERE user_id = %s", (user_id,))
            if cur.fetchone()[0] != today:
                cur.execute("UPDATE users SET balance = balance + 1, last_bonus = %s WHERE user_id = %s", (today, user_id))
                conn.commit(); await update.message.reply_text("🎁 +1 ball berildi!")
            else: await update.message.reply_text("❌ Bugun olgansiz.")

        elif text == "📊 Statistika":
            cur.execute("SELECT COUNT(*) FROM users"); u_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM movies"); m_count = cur.fetchone()[0]
            await update.message.reply_text(f"📊 Azolar: {u_count}\n🎬 Kinolar: {m_count}")

        elif text == "🔗 Referal":
            bot = await context.bot.get_me()
            await update.message.reply_text(f"🔗 Havolangiz: https://t.me/{bot.username}?start={user_id}")

        elif text == "📞 Admin": await update.message.reply_text("📞 Admin: @onlyjasur")
        elif text == "🏠 Bosh menyu": await update.message.reply_text("Asosiy menyu:", reply_markup=main_kb())

        elif text == "➕ Kino qo'shish" and user_id == ADMIN_ID:
            await update.message.reply_text("Kino fayliga reply qilib `/add_movie kod` deb yozing.")

        elif text == "❌ Kino o'chirish" and user_id == ADMIN_ID:
            await update.message.reply_text("O'chirish uchun kodni yuboring:"); context.user_data['step'] = 'del'

        elif context.user_data.get('step') == 'del' and user_id == ADMIN_ID:
            cur.execute("DELETE FROM movies WHERE code = %s", (text,)); conn.commit()
            await update.message.reply_text(f"✅ {text} o'chirildi."); context.user_data['step'] = None

        elif text.isdigit():
            cur.execute("SELECT file_id, caption FROM movies WHERE code = %s", (text,))
            movie = cur.fetchone()
            if movie:
                cur.execute("UPDATE users SET views = views + 1 WHERE user_id = %s", (user_id,)); conn.commit()
                await update.message.reply_video(video=movie[0], caption=f"{movie[1]}\n\n@KinoHubPro")
            else: await update.message.reply_text("😔 Topilmadi.")
    finally:
        cur.close(); conn.close()

# --- QOLGAN FUNKSIYALAR ---
async def premium_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; user_id = query.from_user.id
    if query.data.startswith("buy_"):
        days = 7 if "7" in query.data else 30
        cost = 70 if days == 7 else 140
        conn = get_connection(); cur = conn.cursor()
        try:
            cur.execute("SELECT balance FROM users WHERE user_id = %s", (user_id,))
            if cur.fetchone()[0] >= cost:
                until = datetime.now(timezone.utc) + timedelta(days=days)
                cur.execute("UPDATE users SET balance = balance - %s, premium_until = %s WHERE user_id = %s", (cost, until, user_id))
                conn.commit(); await query.edit_message_text(f"✅ Premium {days} kunga faollashdi!")
            else: await query.answer("❌ Ballar yetarli emas!", show_alert=True)
        finally: cur.close(); conn.close()

async def check_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_subscribed(update.callback_query.from_user.id, context.bot):
        await update.callback_query.message.delete()
        await update.callback_query.message.reply_text("✅ Marhamat!", reply_markup=main_kb())
    else: await update.callback_query.answer("❌ Obuna bo'ling!", show_alert=True)

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Bu yerda oddiy video yuborganda ham saqlash qolsa bo'ladi yoki add_movie ni ishlatsangiz bo'ladi
    pass

async def admin_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or not update.message.reply_to_message: return
    conn = get_connection(); cur = conn.cursor()
    try:
        cur.execute("SELECT user_id FROM users"); users = cur.fetchall()
        for u in users:
            try: await update.message.reply_to_message.copy(chat_id=u[0]); await asyncio.sleep(0.05)
            except: pass
        await update.message.reply_text("📢 Yuborildi.")
    finally: cur.close(); conn.close()

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    init_db()
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("add_movie", add_movie_reply))
    application.add_handler(CommandHandler("send", admin_send))
    application.add_handler(CallbackQueryHandler(premium_callback, pattern="^buy_"))
    application.add_handler(CallbackQueryHandler(check_callback, pattern="check"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    application.run_polling()
