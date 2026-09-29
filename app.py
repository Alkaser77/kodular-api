import os
import requests
from flask import Flask, jsonify, request, redirect, send_file
try:
    from flask_cors import CORS
except:
    CORS = lambda x: x
from supabase import create_client
from datetime import datetime, timedelta
import io
import threading
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
app = Flask(__name__)
CORS(app)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
DRIVE_NPVT_ID = os.getenv("DRIVE_NPVT_ID")
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_URL = os.getenv("API_URL", "https://file-4-2311.onrender.com")
ADMIN_KEY = "admin123"

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Supabase missing")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

FOLDER = "files"
FILES = ["File.ssc", "File.npvt", "File.nm"]

# --- دوال مساعدة ---
def parse_expire(s):
    if not s:
        return datetime.now()
    try:
        cleaned = s.replace('T', ' ').split('.')[0]
        return datetime.strptime(cleaned, "%Y-%m-%d %H:%M:%S")
    except:
        try:
            return datetime.fromisoformat(s.replace('Z', ''))
        except:
            return datetime.now()

def format_hm(hours_float):
    if hours_float <= 0:
        return "0:00"
    days = int(hours_float // 24)
    h = int(hours_float % 24)
    m = int((hours_float - (days*24 + h)) * 60)
    if days > 0:
        # يطلع هكي: 2 يوم 8:29
        return f"{days} days {h}:{m:02d}"
    else:
        return f"{h}:{m:02d}"
def get_allowed_files(user):
    if not user:
        return FILES
    af = user.get("allowed_files")
    if not af or not isinstance(af, list):
        return FILES
    return [f for f in af if f in FILES]

def get_remaining_hours(user):
    if not user or not user.get("expires_at"):
        return 0
    try:
        expires = parse_expire(user.get("expires_at"))
        diff = (expires - datetime.now()).total_seconds() / 3600
        return max(0, diff)
    except:
        return 0

def save_user(user):
    try:
        supabase.table("users").upsert(user).execute()
    except Exception as e:
        print(f"save error {e}")

def get_user(user_id):
    try:
        res = supabase.table("users").select("*").eq("user_id", user_id).execute()
        if res.data:
            return res.data[0]
        return None
    except:
        return None

# --- الصفحة الرئيسية ---
@app.route('/')
def index():
    return "", 200
# --- فحص كودولار ---
@app.route('/check', methods=['GET'])
def check():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"error": "user_id missing"}), 400
    try:
        now = datetime.now()
        user = get_user(user_id)
        allowed = get_allowed_files(user) if user else FILES
        base_url = request.host_url
        links = [f"{base_url}download/{f}?user_id={user_id}" for f in allowed]

        if not user:
            expires = now + timedelta(hours=2)
            user = {"user_id": user_id, "expires_at": expires.strftime("%Y-%m-%d %H:%M:%S"), "status": "active", "allowed_files": FILES, "page_enabled": True, "can_download": True}
            save_user(user)
            return jsonify({"status": "active", "links": links, "files": allowed, "hours": "2:00", "hours_float": 2.0})

        remaining = get_remaining_hours(user)
        if remaining <= 0:
            last_expire = parse_expire(user.get("expires_at"))
            hours_since_expire = (now - last_expire).total_seconds() / 3600
            if hours_since_expire >= 24:
                new_expire = now + timedelta(hours=2)
                user["expires_at"] = new_expire.strftime("%Y-%m-%d %H:%M:%S")
                user["status"] = "active"
                save_user(user)
                return jsonify({"status": "active", "links": links, "files": allowed, "hours": "2:00", "hours_float": 2.0})
            else:
                remaining_cooldown = max(0, 24 - hours_since_expire)
                save_user(user)
                return jsonify({"status": "cooldown", "message": f"Wait {format_hm(remaining_cooldown)} hours", "hours": format_hm(remaining_cooldown), "hours_float": round(remaining_cooldown, 2), "links": [], "files": []})

        return jsonify({"status": "active", "links": links, "files": allowed, "hours": format_hm(remaining), "hours_float": round(remaining, 2)})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

# --- التحميل ---
@app.route('/download/<filename>', methods=['GET'])
def download(filename):
    if filename not in FILES:
        return "File not allowed", 403
    user_id = request.args.get('user_id')
    user = get_user(user_id)
    if not user:
        return "User not found", 403
    if filename not in get_allowed_files(user):
        return "Not allowed for you", 403
    if not user.get("can_download", True):
        return "Download disabled by admin", 403
    if get_remaining_hours(user) <= 0:
        return "Subscription ended", 403

    try:
        if filename == "File.npvt":
            gdrive_url = f"https://drive.google.com/uc?export=download&id={DRIVE_NPVT_ID}"
            r = requests.get(gdrive_url, stream=True, timeout=60)
            return send_file(io.BytesIO(r.content), as_attachment=True, download_name=filename)
        else:
            path = os.path.join(FOLDER, filename)
            if not os.path.exists(path):
                return f"File {filename} not found on server", 404
            return send_file(path, as_attachment=True)
    except Exception as e:
        return f"Download error: {e}", 500

# --- صفحة المستخدم ---
@app.route('/user/<user_id>')
def user_page(user_id):
    user = get_user(user_id)
    if not user:
        return "<h2 style='text-align:center;margin-top:100px;'>المستخدم غير موجود</h2>", 404
    if not user.get("page_enabled", True):
        return "<h2 style='color:red;text-align:center;margin-top:100px;'>⛔ صفحتك موقوفة من الادمن</h2>", 403

    rem = get_remaining_hours(user)
    is_expired = rem <= 0
    wait_str = ""

    if is_expired:
        try:
            exp_date = parse_expire(user.get("expires_at"))
            hours_since = (datetime.now() - exp_date).total_seconds() / 3600
            wait = max(0, 24 - hours_since)
            wait_str = format_hm(wait)
        except:
            wait_str = "24:00"

    allowed = get_allowed_files(user)
    can_dl = False if is_expired else user.get("can_download", True)

    if is_expired:
        banner = f"""
        <div style='background:#dc3545;color:white;padding:15px;border-radius:10px;margin-bottom:20px;text-align:center;'>
            <h3 style='margin:0;'>⏳ انتهى اشتراكك</h3>
            <p style='margin:5px 0;'>عليك الانتظار: <b style='font-size:22px;'>{wait_str}</b></p>
            <small>ID: {user_id}</small>
        </div>
        """
    else:
        banner = f"""
        <div style='background:linear-gradient(135deg,#007bff,#6610f2);color:white;padding:20px;border-radius:15px;text-align:center;'>
            <h2 style='margin:0;'>صفحتك الخاصة</h2>
            <small><code>{user_id}</code></small>
            <p>متبقي: {format_hm(rem)}</p>
        </div>
        """

    cards = ""
    for f in allowed:
        dl = f"{request.host_url}download/{f}?user_id={user_id}"
        if can_dl:
            btn = f"<a href='{dl}' style='background:#28a745;color:white;padding:12px;border-radius:8px;text-decoration:none;display:block;font-weight:bold;'>⬇️ تحميل</a>"
        else:
            btn = f"<span style='background:#ccc;color:#666;padding:12px;border-radius:8px;display:block;'>🔒 التحميل معطل - انتهى اشتراكك</span>"
        cards += f"<div style='background:white;border:1px solid #eee;border-radius:12px;padding:15px;text-align:center;'><div style='font-size:30px;'>📦</div><h4>{f}</h4>{btn}</div>"

    return f"""<html dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>صفحتي</title></head>
    <body style="font-family:Tahoma;background:#f4f4f4;padding:15px;margin:0;">
    <div style="max-width:800px;margin:auto;">
    {banner}
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:15px;">{cards}</div>
    </div></body></html>"""

# --- الادمن ---
@app.route('/admin', methods=['GET'])
def admin_panel():
    try:
        key = request.args.get('key')
        if key!= ADMIN_KEY:
            return "<h3>key=admin123</h3>", 401
        now = datetime.now()
        msg = "<h3 style='color:green;text-align:center;'>✅ تم</h3>" if request.args.get('msg') == 'done' else ""
        action = request.args.get('action')
        uid = request.args.get('user_id')

        if action == 'set_perm' and uid:
            files = [f for f in request.args.get('files', '').split(',') if f in FILES]
            u = get_user(uid)
            if u:
                u["allowed_files"] = files
                save_user(u)
            return redirect(f"/admin?key={ADMIN_KEY}&msg=done")
        if action == 'toggle_page' and uid:
            u = get_user(uid)
            if u:
                u["page_enabled"] = not u.get("page_enabled", True)
                save_user(u)
            return redirect(f"/admin?key={ADMIN_KEY}&msg=done")
        if action == 'toggle_dl' and uid:
            u = get_user(uid)
            if u:
                u["can_download"] = not u.get("can_download", True)
                save_user(u)
            return redirect(f"/admin?key={ADMIN_KEY}&msg=done")
        if action == 'ban' and uid:
            supabase.table("users").delete().eq("user_id", uid).execute()
            return redirect(f"/admin?key={ADMIN_KEY}&msg=done")
        if action == 'reset' and uid:
            u = get_user(uid)
            if u:
                u["expires_at"] = (now + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
                u["status"] = "active"
                save_user(u)
            return redirect(f"/admin?key={ADMIN_KEY}&msg=done")
        if action in ['add', 'sub', 'add_all', 'sub_all']:
            try:
                days = float(request.args.get('days', 0) or 0)
                hours = float(request.args.get('hours', 0) or 0)
                total = days * 24 + hours
            except:
                total = 0

            if action in ['add', 'sub']:
                users_list = [get_user(uid)] if uid else []
            else:
                users_list = supabase.table("users").select("*").execute().data

            for u in users_list:
                if not u:
                    continue
                cur = parse_expire(u.get("expires_at"))
                if 'add' in action:
                    base = cur if cur > now else now
                    new = base + timedelta(hours=total)
                else:
                    new = cur - timedelta(hours=total)
                    if new < now:
                        new = now - timedelta(minutes=1)
                u["expires_at"] = new.strftime("%Y-%m-%d %H:%M:%S")
                u["status"] = "active" if new > now else "expired"
                save_user(u)
            return redirect(f"/admin?key={ADMIN_KEY}&msg=done")

        query = supabase.table("users").select("*").order("expires_at", desc=True)
        search = request.args.get('search')
        if search:
            query = query.ilike("user_id", f"%{search}%")
        all_users = query.execute().data

        html = f"""<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8"><title>الادمن</title>
        <style>body{{font-family:Tahoma;background:#f4f4f4;padding:10px;font-size:13px}}.c{{max-width:1300px;margin:auto;background:white;padding:15px;border-radius:10px}} table{{width:100%;border-collapse:collapse}} th{{background:#007bff;color:white;padding:8px}} td{{padding:8px;border-bottom:1px solid #ddd;text-align:center}}.b{{padding:5px 9px;border-radius:5px;color:white;text-decoration:none;font-size:11px;display:inline-block;margin:2px}}.on{{background:#28a745}}.off{{background:#dc3545}}.copy{{background:#17a2b8}}.small-inp{{width:55px;padding:4px;text-align:center}}
        </style><script>function copyId(id){{navigator.clipboard.writeText(id);alert('تم نسخ: '+id);}}function savePerm(id){{let c=document.querySelectorAll('.chk_'+id+':checked');let f=Array.from(c).map(x=>x.value).join(',');location.href='/admin?key={ADMIN_KEY}&action=set_perm&user_id='+id+'&files='+f}}</script></head><body><div class="c"><h2 style="text-align:center;">لوحة الادمن</h2>{msg}
        <form method="get" style="background:#f8f9fa;padding:10px;border-radius:8px;margin-bottom:15px;display:flex;gap:5px;flex-wrap:wrap;"><input type="hidden" name="key" value="{ADMIN_KEY}">
        <input type="text" name="search" placeholder="بحث" value="{search if search else ''}"><span>ايام:</span><input class="small-inp" type="number" name="days" value="1"><span>ساعات:</span><input class="small-inp" type="number" name="hours" value="0">
        <button name="action" value="add_all" style="background:#007bff;color:white;border:none;padding:7px 12px;border-radius:5px;">➕ للكل</button><button name="action" value="sub_all" style="background:#dc3545;color:white;border:none;padding:7px 12px;border-radius:5px;">➖ للكل</button><button type="submit">بحث</button></form>
        <table><tr><th>المستخدم</th><th>الوقت</th><th>الملفات</th><th>الصفحة</th><th>التحميل</th><th>تحكم</th></tr>"""
        for u in all_users:
            rem = format_hm(get_remaining_hours(u))
            allowed = get_allowed_files(u)
            perm = "".join([f"<label><input type='checkbox' class='chk_{u['user_id']}' value='{f}' {'checked' if f in allowed else ''}> {f.split('.')[0]}</label><br>" for f in FILES])
            perm += f"<button onclick=\"savePerm('{u['user_id']}')\" style='background:#6610f2;color:white;border:none;padding:4px 8px;border-radius:4px;margin-top:5px;width:100%;'>حفظ</button>"
            page_btn = f"<a class='b {'on' if u.get('page_enabled',True) else 'off'}' href='/admin?key={ADMIN_KEY}&action=toggle_page&user_id={u['user_id']}'>{'مفعلة' if u.get('page_enabled',True) else 'موقوفة'}</a>"
            dl_btn = f"<a class='b {'on' if u.get('can_download',True) else 'off'}' href='/admin?key={ADMIN_KEY}&action=toggle_dl&user_id={u['user_id']}'>{'مسموح' if u.get('can_download',True) else 'ممنوع'}</a>"
            copy_btns = f"<div><code style='font-size:10px;'>{u['user_id']}</code><br><button class='b copy' onclick=\"copyId('{u['user_id']}')\">📋 نسخ</button><br><a href='/user/{u['user_id']}' target='_blank' class='b' style='background:#6f42c1;'>صفحته</a></div>"
            html += f"<tr><td>{copy_btns}</td><td dir='ltr'><b>{rem}</b><br><small>{u.get('expires_at','')}</small></td><td>{perm}</td><td>{page_btn}</td><td>{dl_btn}</td><td><a class='b' style='background:#6c757d' href='/admin?key={ADMIN_KEY}&action=reset&user_id={u['user_id']}'>تصفير</a><br><a class='b off' href='/admin?key={ADMIN_KEY}&action=ban&user_id={u['user_id']}'>حذف</a><hr><form method='get'><input type='hidden' name='key' value='{ADMIN_KEY}'><input type='hidden' name='user_id' value='{u['user_id']}'><input class='small-inp' type='number' name='days' value='0'><input class='small-inp' type='number' name='hours' value='24'><br><button class='b on' name='action' value='add'>+ اضافة</button><button class='b off' name='action' value='sub'>- تنقيص</button></form></td></tr>"
        html += "</table></div></body></html>"
        return html
    except Exception as e:
        return f"<h1>Admin Error</h1><pre>{e}</pre>", 500

# --- بوت تليجرام ---
def run_bot():
    if not BOT_TOKEN:
        print("BOT_TOKEN missing")
        return
    bot = telebot.TeleBot(BOT_TOKEN)
    print("Bot started...")

    @bot.message_handler(commands=['start'])
    def handle_start(message):
        tg_id = str(message.from_user.id)
        user_id = f"TG-{tg_id}"
        try:
            user = get_user(user_id)
            if not user:
                expires = datetime.now() + timedelta(hours=2)
                user = {"user_id": user_id, "expires_at": expires.strftime("%Y-%m-%d %H:%M:%S"), "status": "active", "allowed_files": FILES, "page_enabled": True, "can_download": True}
                save_user(user)
                rem = 2.0
                is_cooldown = False
                wait_str = ""
            else:
                rem = get_remaining_hours(user)
                if rem <= 0:
                    exp_date = parse_expire(user.get("expires_at"))
                    hours_since = (datetime.now() - exp_date).total_seconds() / 3600
                    if hours_since < 24:
                        is_cooldown = True
                        wait_str = format_hm(24 - hours_since)
                    else:
                        new_exp = datetime.now() + timedelta(hours=2)
                        user["expires_at"] = new_exp.strftime("%Y-%m-%d %H:%M:%S")
                        user["status"] = "active"
                        save_user(user)
                        rem = 2.0
                        is_cooldown = False
                        wait_str = ""
                else:
                    is_cooldown = False
                    wait_str = ""

        except Exception as e:
            bot.reply_to(message, f"خطأ: {e}")
            return

        page_link = f"{API_URL}/user/{user_id}"
        if is_cooldown:
            markup = InlineKeyboardMarkup(row_width=1)
            markup.add(InlineKeyboardButton("🌐 فتح صفحتي", url=page_link))
            bot.send_message(message.chat.id, f"⏳ انتهى اشتراكك يا {message.from_user.first_name}\n\nID: <code>{user_id}</code>\nباقي انتظار: <b>{wait_str}</b>", parse_mode='HTML', reply_markup=markup)
        else:
            markup = InlineKeyboardMarkup(row_width=2)
            for f in get_allowed_files(user):
                markup.add(InlineKeyboardButton(f"📦 {f}", callback_data=f"dl|{f}|{user_id}"))
            markup.add(InlineKeyboardButton("🌐 فتح صفحتي", url=page_link))
            bot.send_message(message.chat.id, f"مرحبا {message.from_user.first_name} 👋\n\nID: <code>{user_id}</code>\nمتبقي: <b>{format_hm(rem)}</b>", parse_mode='HTML', reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: True)
    def handle_callback(call):
        try:
            _, filename, user_id = call.data.split("|")
            bot.answer_callback_query(call.id, f"جاري تجهيز {filename}")
            user = get_user(user_id)
            if not user or get_remaining_hours(user) <= 0:
                bot.send_message(call.message.chat.id, "❌ انتهى وقتك")
                return
            bot.send_message(call.message.chat.id, f"⏳ جاري تجهيز {filename}...")
            if filename == "File.npvt":
                gdrive_url = f"https://drive.google.com/uc?export=download&id={DRIVE_NPVT_ID}"
                r = requests.get(gdrive_url, stream=True, timeout=60)
                content = r.content
            else:
                file_path = os.path.join(FOLDER, filename)
                if not os.path.exists(file_path):
                    bot.send_message(call.message.chat.id, f"❌ الملف غير موجود: {filename}")
                    return
                with open(file_path, 'rb') as f:
                    content = f.read()
            tmp_path = f"/tmp/{filename}"
            with open(tmp_path, 'wb') as f:
                f.write(content)
            with open(tmp_path, 'rb') as f:
                bot.send_document(call.message.chat.id, f, caption=f"✅ {filename}")
        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ خطأ: {e}")

    bot.infinity_polling()

if BOT_TOKEN:
    threading.Thread(target=run_bot, daemon=True).start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 10000)))
