import os, requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN") # حط توكن بوتك في Render Env
API_URL = os.environ.get("API_URL") # مثال: https://موقعك.onrender.com

FILES = ["File.npvt", "File.ssc", "File.nm"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = str(update.effective_user.id)
    user_id = f"TG-{tg_id}" # نستخدم ID التليجرام كنفس ID الموقع

    # 1- نكلم سيرفرك باش ينشئ المستخدم (نفس تشيك كودولار)
    try:
        r = requests.get(f"{API_URL}/check?user_id={user_id}", timeout=10)
        data = r.json()
        hours = data.get('hours', '2:00')
        status = data.get('status')
    except Exception as e:
        await update.message.reply_text(f"خطأ في السيرفر: {e}")
        return

    if status == 'cooldown':
        await update.message.reply_text(f"⏳ انتهى وقتك يا {update.effective_user.first_name}\nارجع بعد: {hours}")
        return

    # 2- نبعتله رابط صفحته HTML
    page_link = f"{API_URL}/user/{user_id}"

    keyboard = [
        [InlineKeyboardButton(f"📦 {f}", callback_data=f"dl|{f}|{user_id}") for f in FILES[:2]],
        [InlineKeyboardButton(f"📦 {FILES[2]}", callback_data=f"dl|{FILES[2]}|{user_id}")],
        [InlineKeyboardButton("🌐 فتح صفحتي في المتصفح", url=page_link)]
    ]

    await update.message.reply_text(
        f"مرحبا {update.effective_user.first_name} 👋\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"⏰ المتبقي: <b>{hours}</b>\n\n"
        f"اختار ملف للتحميل مباشرة او افتح صفحتك:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, filename, user_id = query.data.split("|")

    await query.message.reply_text(f"⏳ جاري تجهيز {filename}...")

    # 3- التحميل المباشر عبر البوت
    dl_url = f"{API_URL}/download/{filename}?user_id={user_id}"
    try:
        r = requests.get(dl_url, timeout=60)
        if r.status_code!= 200:
            await query.message.reply_text(f"❌ فشل: {r.text[:200]}")
            return

        # نبعت الملف للمستخدم في التليجرام
        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=r.content,
            filename=filename,
            caption=f"✅ {filename}\nID: {user_id}"
        )
    except Exception as e:
        await query.message.reply_text(f"❌ خطأ: {e}")

app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_click))

print("Bot running...")
app.run_polling()
