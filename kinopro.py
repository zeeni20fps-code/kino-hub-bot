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
        return await start(update, context)

    conn = get_connection()
    cur = conn.cursor()

    # 1. KINO OLISH
    if text == "🎬 Kino olish":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🎬 Kino kodlari kanali", url="https://t.me/KinoHubPro")]])
        await update.message.reply_text("Kino kodlarini kanalimizdan topishingiz mumkin 👇", reply_markup=kb)

    # 2. KABINET
    elif text == "👤 Kabinet":
        cur.execute("SELECT balance, views, premium_until FROM users WHERE user_id = %s", (user_id,))
        u = cur.fetchone()
        p = "Aktiv ✅" if u[2] and u[2] > datetime.now(timezone.utc) else "Oddiy 👤"
        await update.message.reply_text(f"👤 **Sizning ma'lumotlaringiz:**\n\n🆔 ID: `{user_id}`\n💎 Status: {p}\n💰 Balans: {u[0]} ball\n🎬 Ko'rilgan kinolar: {u[1]} ta", parse_mode="Markdown")

    # 3. PREMIUM
    elif text == "💎 Premium":
        cur.execute("SELECT balance, premium_until FROM users WHERE user_id = %s", (user_id,))
        u = cur.fetchone()
        p_status = u[1].strftime("%Y-%m-%d") if u[1] else "Aktiv emas ❌"
        txt = (f"💎 **Premium Markazi**\n\nBalansingiz: {u[0]} ball\nPremium muddati: {p_status}\n\n"
               "🎫 70 ball — 1 hafta\n🎫 140 ball — 1 oy\n\nPremium foydalanuvchilar kinoni reklamasiz va tezkor olishadi!")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("1 hafta (70 ball)", callback_data="buy_7")],
            [InlineKeyboardButton("1 oy (140 ball)", callback_data="buy_30")],
            [InlineKeyboardButton("💳 Admin (Sotib olish)", url="https://t.me/onlyjasur?text=Salom+Premium+olmoqchi+edim")]
        ])
        await update.message.reply_text(txt, reply_markup=kb, parse_mode="Markdown")

    # 4. BONUS
    elif text == "🎁 Bonus":
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        cur.execute("SELECT last_bonus FROM users WHERE user_id = %s", (user_id,))
        last = cur.fetchone()[0]
        if last != today:
            cur.execute("UPDATE users SET balance = balance + 1, last_bonus = %s WHERE user_id = %s", (today, user_id))
            conn.commit()
            await update.message.reply_text("🎁 Tabriklaymiz! Kunlik bonus +1 ball berildi.")
        else:
            await update.message.reply_text("❌ Siz bugungi bonusni olib bo'lgansiz. Ertaga qaytib keling!")

    # 5. STATISTIKA
    elif text == "📊 Statistika":
        cur.execute("SELECT COUNT(*) FROM users")
        u_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM movies")
        m_count = cur.fetchone()[0]
        await update.message.reply_text(f"📊 **Bot Statistikasi:**\n\n👤 Foydalanuvchilar: {u_count} ta\n🎬 Kinolar bazasi: {m_count} ta", parse_mode="Markdown")

    # 6. REFERAL
    elif text == "🔗 Referal":
        bot_info = await context.bot.get_me()
        link = f"https://t.me/{bot_info.username}?start={user_id}"
        await update.message.reply_text(f"🔗 **Referal tizimi**\n\nQuyidagi havolani do'stlaringizga tarqating. Har bir qo'shilgan faol do'stingiz uchun 3 ballga ega bo'ling!\n\nManzil: {link}", parse_mode="Markdown")

    # 7. ADMIN VA BOSHQA TUGMALAR
    elif text == "📞 Admin":
        await update.message.reply_text("📞 Admin bilan bog'lanish: @onlyjasur")

    elif text == "/admin" and user_id == ADMIN_ID:
        await update.message.reply_text("Admin paneli faollashdi:", reply_markup=admin_kb())
    
    elif text == "🏠 Bosh menyu":
        await update.message.reply_text("Bosh menyuga qaytdingiz:", reply_markup=main_kb())

    # KINO O'CHIRISH (ADMIN)
    elif text == "❌ Kino o'chirish" and user_id == ADMIN_ID:
        await update.message.reply_text("O'chiriladigan kino kodini yozing:")
        context.user_data['step'] = 'del'

    elif context.user_data.get('step') == 'del' and user_id == ADMIN_ID:
        cur.execute("DELETE FROM movies WHERE code = %s", (text,))
        conn.commit()
        await update.message.reply_text(f"✅ Kod {text} bazadan o'chirildi.")
        context.user_data['step'] = None

    # KINO QIDIRISH (RAQAM YUBORILSA)
    elif text.isdigit():
        cur.execute("SELECT file_id, caption FROM movies WHERE code = %s", (text,))
        movie = cur.fetchone()
        if movie:
            cur.execute("UPDATE users SET views = views + 1 WHERE user_id = %s", (user_id,))
            conn.commit()
            await update.message.reply_video(video=movie[0], caption=f"{movie[1]}\n\n@KinoHubPro")
        else:
            await update.message.reply_text("😔 Afsuski, bu kod bo'yicha kino topilmadi.")

    cur.close()
    conn.close()

# --- CALLBACKS ---
async def premium_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    if query.data.startswith("buy_"):
        days = int(query.data.split("_")[1])
        cost = 70 if days == 7 else 140
        conn = get_connection(); cur = conn.cursor()
        cur.execute("SELECT balance FROM users WHERE user_id = %s", (user_id,))
        balance = cur.fetchone()[0]
        if balance >= cost:
            until = datetime.now(timezone.utc) + timedelta(days=days)
            cur.execute("UPDATE users SET balance = balance - %s, premium_until = %s WHERE user_id = %s", (cost, until, user_id))
            conn.commit()
            await query.edit_message_text(f"✅ Premium {days} kunga muvaffaqiyatli faollashdi!")
        else:
            await query.answer("❌ Ballaringiz yetarli emas!", show_alert=True)
        cur.close(); conn.close()

async def check_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await is_subscribed(query.from_user.id, context.bot):
        await query.message.delete()
        await query.message.reply_text("✅ Rahmat! Barcha funksiyalar ochildi.", reply_markup=main_kb())
    else:
        await query.answer("❌ Siz hali barcha kanallarga a'zo emassiz!", show_alert=True)

# --- MEDIA VA REKLAMA ---
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID and context.user_data.get('step') == 'add' and update.message.video:
        code = update.message.caption
        if code:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("INSERT INTO movies (code, file_id, caption) VALUES (%s, %s, %s) ON CONFLICT (code) DO UPDATE SET file_id=EXCLUDED.file_id, caption=EXCLUDED.caption", 
                        (code, update.message.video.file_id, code))
            conn.commit(); cur.close(); conn.close()
            await update.message.reply_text(f"✅ Kino bazaga saqlandi: {code}")
            context.user_data['step'] = None

async def admin_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or not update.message.reply_to_message: return
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT user_id FROM users"); users = cur.fetchall()
    count = 0
    for u in users:
        try: 
            await update.message.reply_to_message.copy(chat_id=u[0])
            count += 1
            await asyncio.sleep(0.05)
        except: pass
    await update.message.reply_text(f"📢 Reklama {count} kishiga yuborildi.")
    cur.close(); conn.close()

# --- ISHGA TUSHIRISH ---
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    init_db()
    
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("send", admin_send))
    application.add_handler(CallbackQueryHandler(premium_callback, pattern="^buy_"))
    application.add_handler(CallbackQueryHandler(check_callback, pattern="check"))
    application.add_handler(MessageHandler(filters.VIDEO, handle_media))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    application.run_polling()
