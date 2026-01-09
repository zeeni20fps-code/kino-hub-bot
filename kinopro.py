import os
import logging
import asyncio
import psycopg2
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from flask import Flask
import threading

# --- TUGMA NOMLARI ---
BTN_KINO = "🎬 Kino olish"
BTN_KABINET = "👤 Kabinet"
BTN_BONUS = "🎁 Bonus"
BTN_PREMIUM = "💎 Premium"
BTN_ORDER = "✍️ Kino Buyurtma"
BTN_STATS = "📊 Statistika"
BTN_REF = "🔗 Referal"
BTN_ADMIN_CONTACT = "📞 Admin"
BTN_HOME = "🏠 Bosh menyu"
BTN_ADMIN_PREMIUM = "💎 Premium Berish"

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
        # Kinolar jadvali (Seriallar uchun PRIMARY KEY koddan olib tashlandi)
        cur.execute('CREATE TABLE IF NOT EXISTS movies (code TEXT, file_id TEXT, caption TEXT)')
        # Foydalanuvchilar jadvali
        cur.execute('CREATE TABLE IF NOT EXISTS users (user_id BIGINT PRIMARY KEY, username TEXT)')
        
        columns = [
            ("balance", "INTEGER DEFAULT 0"),
            ("views", "INTEGER DEFAULT 0"),
            ("last_bonus", "TEXT"),
            ("premium_until", "TIMESTAMP WITH TIME ZONE DEFAULT NULL")
        ]
        for col_name, col_type in columns:
            try:
                cur.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
            except:
                conn.rollback() 
        
        conn.commit(); cur.close(); conn.close()
        print("Baza muvaffaqiyatli yangilandi! ✅")
    except Exception as e: print(f"DB Error: {e}")

# --- KLAVIATURALAR ---
def main_kb():
    return ReplyKeyboardMarkup([
        [KeyboardButton(BTN_KINO), KeyboardButton(BTN_KABINET)],
        [KeyboardButton(BTN_BONUS), KeyboardButton(BTN_ORDER)],
        [KeyboardButton(BTN_PREMIUM), KeyboardButton(BTN_STATS)],
        [KeyboardButton(BTN_REF), KeyboardButton(BTN_ADMIN_CONTACT)],
    ], resize_keyboard=True)

def admin_kb():
    return ReplyKeyboardMarkup([
        [KeyboardButton("➕ Kino qo'shish"), KeyboardButton("❌ Kino o'chirish")],
        [KeyboardButton("📢 Reklama"), KeyboardButton(BTN_ADMIN_PREMIUM)],
        [KeyboardButton(BTN_HOME)]
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
        await update.message.reply_text("✨ **Xush kelibsiz!**\n\nBotdan to'liq foydalanish uchun quyidagi kanallarga a'zo bo'ling va 'Tekshirish' tugmasini bosing:", reply_markup=InlineKeyboardMarkup(btns), parse_mode="Markdown")
        return
    
    kb = admin_kb() if user.id == ADMIN_ID else main_kb()
    await update.message.reply_text("🎥 **Kino kodini yuboring yoki menyudan foydalaning:**", reply_markup=kb, parse_mode="Markdown")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if not await is_subscribed(user_id, context.bot):
        return await start(update, context)

    conn = get_connection(); cur = conn.cursor()
    try:
        # 1. KABINET
        if BTN_KABINET in text:
            cur.execute("SELECT balance, views, premium_until FROM users WHERE user_id = %s", (user_id,))
            u = cur.fetchone()
            if u:
                is_premium = u[2] and u[2] > datetime.now(timezone.utc)
                p = "Aktiv ✅" if is_premium else "Oddiy foydalanuvchi 👤"
                name = update.effective_user.first_name
                display_name = f"{name} 👑" if is_premium else name
                
                await update.message.reply_text(
                    f"👤 **{display_name} - Shaxsiy kabinetingiz:**\n\n"
                    f"🆔 **ID:** `{user_id}`\n"
                    f"💎 **Status:** {p}\n"
                    f"💰 **Balans:** {u[0]} ball\n"
                    f"🎬 **Ko'rilgan kinolar:** {u[1]} ta\n\n"
                    f"Referal orqali ballar to'plang va Premiumga ega bo'ling!", 
                    parse_mode="Markdown"
                )

        # 2. BUYURTMA TUGMASI
        elif text == BTN_ORDER:
            cur.execute("SELECT premium_until FROM users WHERE user_id = %s", (user_id,))
            u = cur.fetchone()
            if u[0] and u[0] > datetime.now(timezone.utc):
                await update.message.reply_text("🎬 **Kino buyurtma berish:**\nIltimos, qidirayotgan kino nomini yozib yuboring.")
                context.user_data['step'] = 'waiting_order'
            else:
                await update.message.reply_text("❌ **Kechirasiz!**\nKino buyurtma berish funksiyasi faqat **Premium** foydalanuvchilar uchun amal qiladi.")

        # BUYURTMA QABUL QILISH
        elif context.user_data.get('step') == 'waiting_order':
            order_text = text
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔔 **YANGI BUYURTMA!**\n\n👤 Foydalanuvchi: {update.effective_user.first_name}\n🆔 ID: `{user_id}`\n📝 Kino nomi: {order_text}")
            await update.message.reply_text("✅ **Buyurtmangiz qabul qilindi!**")
            context.user_data['step'] = None
            
        # 3. PREMIUM
        elif BTN_PREMIUM in text:
            cur.execute("SELECT balance, premium_until FROM users WHERE user_id = %s", (user_id,))
            u = cur.fetchone()
            p_status = u[1].strftime("%Y-%m-%d") if u[1] and u[1] > datetime.now(timezone.utc) else "Mavjud emas ❌"
            txt = (f"💎 **Premium Markazi**\n\n"
                   f"Sizning balansingiz: `{u[0]}` ball\n"
                   f"Amal qilish muddati: `{p_status}`\n\n"
                   f"Premium afzalliklari:\n✨ Reklamasiz foydalanish\n✨ Maxfiy kinolarga kirish\n✨ Shaxsiy buyurtma berish")
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 1 hafta (70 ball)", callback_data="buy_7")],
                [InlineKeyboardButton("💳 1 oy (140 ball)", callback_data="buy_30")],
                [InlineKeyboardButton("👨‍💻 Admin orqali sotib olish", url="https://t.me/onlyjasur")]
            ])
            await update.message.reply_text(txt, reply_markup=kb, parse_mode="Markdown")

        # 4. KINO OLISH
        elif BTN_KINO in text:
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🎬 Kino kodlari kanali", url="https://t.me/KinoHubPro")]])
            await update.message.reply_text("👇 **Kino kodlarini bizning rasmiy kanalimizdan topishingiz mumkin:**", reply_markup=kb, parse_mode="Markdown")

        # 5. BONUS
        elif BTN_BONUS in text:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            cur.execute("SELECT last_bonus FROM users WHERE user_id = %s", (user_id,))
            last_bonus_date = cur.fetchone()[0]
            if last_bonus_date != today:
                cur.execute("UPDATE users SET balance = balance + 1, last_bonus = %s WHERE user_id = %s", (today, user_id))
                conn.commit(); await update.message.reply_text("🎁 **Tabriklaymiz!**\nSizga +1 ball taqdim etildi!", parse_mode="Markdown")
            else: await update.message.reply_text("❌ Bugun bonus olib bo'lingan.", parse_mode="Markdown")

        # 6. STATISTIKA
        elif BTN_STATS in text:
            cur.execute("SELECT COUNT(*) FROM users"); u_c = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM movies"); m_c = cur.fetchone()[0]
            await update.message.reply_text(f"📊 **Bot Statistikasi:**\n\n👤 Foydalanuvchilar: {u_c} ta\n🎬 Bazadagi kinolar: {m_c} ta", parse_mode="Markdown")

        # 7. REFERAL
        elif BTN_REF in text:
            b = await context.bot.get_me()
            await update.message.reply_text(f"🔗 **Sizning referal havolangiz:**\n\nhttps://t.me/{b.username}?start={user_id}\n\nHar bir do'stingiz uchun 3 ball olasiz!", parse_mode="Markdown")

        # 8. ADMIN TUGMALARI
        elif BTN_ADMIN_CONTACT in text: await update.message.reply_text("👨‍💻 Savollar uchun: @onlyjasur")
        elif BTN_HOME in text: 
            kb = admin_kb() if user_id == ADMIN_ID else main_kb()
            await update.message.reply_text("🏠 Asosiy menyu.", reply_markup=kb)

        elif text == BTN_ADMIN_PREMIUM and user_id == ADMIN_ID:
            await update.message.reply_text("💎 **Premium Berish:**\n\n`/set_premium ID KUN` \n\nMisol: `/set_premium 1234567 30`", parse_mode="Markdown")

        elif text == "➕ Kino qo'shish" and user_id == ADMIN_ID:
            await update.message.reply_text("🎬 Videoga reply qilib yozing:\n`/add_movie kod Kino nomi`", parse_mode="Markdown")
            
        elif text == "❌ Kino o'chirish" and user_id == ADMIN_ID:
            await update.message.reply_text("🗑 O'chirmoqchi bo'lgan kino kodini yozing:"); context.user_data['step'] = 'del'

        elif text == "📢 Reklama" and user_id == ADMIN_ID:
            await update.message.reply_text("📢 Xabarga reply qilib `/send` deb yozing.", parse_mode="Markdown")

        elif context.user_data.get('step') == 'del' and user_id == ADMIN_ID:
            cur.execute("DELETE FROM movies WHERE code = %s", (text,)); conn.commit()
            await update.message.reply_text(f"✅ Kod `{text}` o'chirildi."); context.user_data['step'] = None

        # 9. KINO QIDIRISH (SERIAL TIZIMI BILAN)
        elif text.isdigit():
            cur.execute("SELECT file_id, caption FROM movies WHERE code = %s", (text,))
            all_parts = cur.fetchall()
            if all_parts:
                cur.execute("UPDATE users SET views = views + 1 WHERE user_id = %s", (user_id,)); conn.commit()
                for movie in all_parts:
                    await update.message.reply_video(video=movie[0], caption=f"🍿 **Kino:** {movie[1]}\n🆔 **Kod:** {text}\n\n@KinoHubPro", parse_mode="Markdown")
            else:
                await update.message.reply_text(f"😔 **{text}** kodli kino topilmadi.", parse_mode="Markdown")
    finally: cur.close(); conn.close()

# --- ADMIN BUYRUQLARI ---
async def add_movie_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not update.message.reply_to_message or len(context.args) < 1:
        await update.message.reply_text("⚠️ Videoga reply qilib `/add_movie kod Nomi` deb yozing.")
        return
    code = context.args[0]
    movie_name = " ".join(context.args[1:]) if len(context.args) > 1 else f"Kino {code}"
    reply = update.message.reply_to_message
    f_id = reply.video.file_id if reply.video else (reply.document.file_id if reply.document else None)
    if f_id:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("INSERT INTO movies (code, file_id, caption) VALUES (%s, %s, %s)", (code, f_id, movie_name))
        conn.commit(); cur.close(); conn.close()
        await update.message.reply_text(f"✅ Saqlandi: `{code}`", parse_mode="Markdown")
    else: await update.message.reply_text("❌ Video topilmadi.")

async def set_premium_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ `/set_premium ID KUN`")
        return
    try:
        u_id = int(context.args[0]); days = int(context.args[1])
        expire = datetime.now(timezone.utc) + timedelta(days=days)
        conn = get_connection(); cur = conn.cursor()
        cur.execute("UPDATE users SET premium_until = %s WHERE user_id = %s", (expire, u_id))
        conn.commit()
        if cur.rowcount > 0:
            await update.message.reply_text(f"💎 ID {u_id} ga {days} kun premium berildi.")
            try: await context.bot.send_message(chat_id=u_id, text="🎉 Sizga Premium berildi!")
            except: pass
        else: await update.message.reply_text("❌ User topilmadi.")
        cur.close(); conn.close()
    except Exception as e: await update.message.reply_text(f"❌ Xato: {e}")

async def admin_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or not update.message.reply_to_message: return
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT user_id FROM users"); users = cur.fetchall()
    count = 0
    msg = await update.message.reply_text("🚀 Yuborilmoqda...")
    for u in users:
        try: await update.message.reply_to_message.copy(chat_id=u[0]); count += 1; await asyncio.sleep(0.05)
        except: pass
    await msg.edit_text(f"📢 Jami: {count} ta foydalanuvchiga yuborildi.")
    cur.close(); conn.close()

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        await update.message.reply_text("👨‍💻 Admin Paneli:", reply_markup=admin_kb(), parse_mode="Markdown")

async def premium_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; user_id = query.from_user.id
    if query.data.startswith("buy_"):
        d = 7 if "7" in query.data else 30
        c = 70 if d == 7 else 140
        conn = get_connection(); cur = conn.cursor()
        cur.execute("SELECT balance FROM users WHERE user_id = %s", (user_id,))
        bal = cur.fetchone()[0]
        if bal >= c:
            u = datetime.now(timezone.utc) + timedelta(days=d)
            cur.execute("UPDATE users SET balance = balance - %s, premium_until = %s WHERE user_id = %s", (c, u, user_id))
            conn.commit(); await query.edit_message_text(f"✅ Premium {d} kunga faollashdi!")
        else: await query.answer("❌ Ballaringiz yetarli emas!", show_alert=True)
        cur.close(); conn.close()

async def check_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_subscribed(update.callback_query.from_user.id, context.bot):
        await update.callback_query.message.delete()
        await update.callback_query.message.reply_text("✅ Marhamat:", reply_markup=main_kb())
    else: await update.callback_query.answer("❌ Obuna bo'ling!", show_alert=True)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    init_db()
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("add_movie", add_movie_reply))
    application.add_handler(CommandHandler("send", admin_send))
    application.add_handler(CommandHandler("set_premium", set_premium_manual))
    application.add_handler(CallbackQueryHandler(premium_callback, pattern="^buy_"))
    application.add_handler(CallbackQueryHandler(check_callback, pattern="check"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.run_polling()
