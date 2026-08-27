from flask import Flask, request, jsonify, send_from_directory
from datetime import datetime, timedelta
from supabase import create_client, Client
import os

app = Flask(__name__)

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

FOLDER = 'files' # مجلد الملفات اللي رفعت فيه File.npvt
ADMIN_KEY = "admin123" # غير كلمة السر

def get_user(user_id):
    res = supabase.table("users").select("*").eq("user_id", user_id).execute()
    return res.data[0] if res.data else None

def save_user(user):
    supabase.table("users").upsert(user).execute()

def get_remaining_hours(user):
    # لو مافيش تايمر بادي = 0
    if not user or not user.get("session_start") or user["status"] == "expired":
        return 0

    session_start = datetime.strptime(user["session_start"], "%Y-%m-%d %H:%M:%S")
    total_hours = float(user["total_hours"]) # هذا ثابت ما يتغيرش
    now = datetime.now()

    passed_hours = (now - session_start).total_seconds() / 3600
    remaining = total_hours - passed_hours
    return max(0, remaining)

@app.route('/check', methods=['GET'])
def check():
    user_id = request.args.get('user_id')
    filename = request.args.get('file', 'File.npvt') # يستقبل اسم الملف. الافتراضي File.npvt
    if not user_id: return jsonify({"error": "user_id missing"}), 400

    now = datetime.now()
    user = get_user(user_id)

    # 1. مستخدم جديد
    if not user:
        user = {
            "user_id": user_id,
            "total_hours": 2.0, # الوقت اللي شراه او المجاني
            "session_start": now.strftime("%Y-%m-%d %H:%M:%S"), # وقت بداية العد
            "status": "active"
        }
        save_user(user)
        download_url = f"/download/{filename}?user_id={user_id}"
        return jsonify({"status": "active", "link": download_url, "filename": filename, "hours": 2.0})

    remaining = get_remaining_hours(user)

    # 2. لو الوقت تم
    if remaining <= 0:
        user["status"] = "expired"
        session_start = datetime.strptime(user["session_start"], "%Y-%m-%d %H:%M:%S")
        hours_since_last = (now - session_start).total_seconds() / 3600

        if hours_since_last >= 24:
            # فات 24: نجددو ساعتين
            user["total_hours"] = 2.0
            user["session_start"] = now.strftime("%Y-%m-%d %H:%M:%S")
            user["status"] = "active"
            save_user(user)
            download_url = f"/download/{filename}?user_id={user_id}"
            return jsonify({"status": "active", "link": download_url, "filename": filename, "hours": 2.0})
        else:
            wait = round(24 - hours_since_last, 1)
            save_user(user)
            return jsonify({"status": "cooldown", "message": f"Wait {wait} hours", "hours": 0})

    # 3. لو عنده وقت: ما نحدثوش شي في الداتا. نعرضو بس
    download_url = f"/download/{filename}?user_id={user_id}"
    return jsonify({"status": "active", "link": download_url, "filename": filename, "hours": round(remaining, 2)})

@app.route('/download/<filename>')
def download(filename):
    user_id = request.args.get('user_id')
    user = get_user(user_id)
    remaining = get_remaining_hours(user)

    if remaining <= 0:
        return "Time expired", 403

    file_path = os.path.join(FOLDER, filename)
    if not os.path.exists(file_path):
        return f"File {filename} not found", 404

    # هنا الاسم حينزل صح 100%
    return send_from_directory(FOLDER, filename, as_attachment=True, download_name=filename)

@app.route('/addtime', methods=['GET'])
def add_time():
    key = request.args.get('key')
    if key!= ADMIN_KEY: return jsonify({"error": "Unauthorized"}), 401

    user_id = request.args.get('user_id')
    add_hours = float(request.args.get('hours', 2.0))
    now = datetime.now()

    user = get_user(user_id)
    if not user:
        user = {"user_id": user_id, "total_hours": 0, "session_start": None, "status": "expired"}

    current = get_remaining_hours(user)

    # نزيدو الوقت الجديد
    user["total_hours"] = current + add_hours
    user["status"] = "active"
    # نبدا تايمر جديد لو كان صفر
    if not user.get("session_start") or current <= 0:
        user["session_start"] = now.strftime("%Y-%m-%d %H:%M:%S")
    save_user(user)

    return jsonify({"status": "success", "new_hours": round(user['total_hours'], 2)})

# ================== صفحة الادمن الكاملة ==================
@app.route('/admin', methods=['GET'])
def admin_panel():
    key = request.args.get('key')
    if key!= ADMIN_KEY:
        return "كلمة السر غلط", 401

    action = request.args.get('action')
    user_id = request.args.get('user_id')
    hours = request.args.get('hours', type=float)
    search = request.args.get('search')
    msg = ""

    # تنفيذ الاوامر
    if action and user_id:
        user = get_user(user_id)
        if not user and action!= "add":
            user = {"user_id": user_id, "total_hours": 0, "session_start": None, "status": "expired"}

        if action == "extend": # زيادة
            current = get_remaining_hours(user)
            user["total_hours"] = current + hours
            user["status"] = "active"
            if current <= 0: user["session_start"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_user(user)
            msg = f"✅ تمت زيادة {hours} ساعات. المتبقي: {round(user['total_hours'],2)}"

        elif action == "reduce": # نقص
            current = get_remaining_hours(user)
            user["total_hours"] = max(0, current - hours)
            if user["total_hours"] <= 0: user["status"] = "expired"
            save_user(user)
            msg = f"➖ تم نقص {hours} ساعات. المتبقي: {round(user['total_hours'],2)}"

        elif action == "unlimited": # مفتوح
            user["total_hours"] = 99999.0
            user["session_start"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            user["status"] = "active"
            save_user(user)
            msg = f"♾️ تم فتح الـ ID مفتوح"

        elif action == "ban": # حذف
            supabase.table("users").delete().eq("user_id", user_id).execute()
            msg = f"⛔ تم حذف الـ ID"

    # جلب كل اليوزرات مع البحث
    query = supabase.table("users").select("*")
    if search:
        query = query.ilike("user_id", f"%{search}%")
    all_users = query.execute().data

    rows = ""
    for u in all_users:
        rem = round(get_remaining_hours(u), 2)
        if u["total_hours"] > 9999: status = "♾️ مفتوح"
        elif rem > 0: status = "🟢 شغال"
        else: status = "🔴 منتهي"
        # زر النسخ
        rows += f"""<tr>
            <td style='word-break:break-all'>{u['user_id']}
            <button onclick="copyID('{u['user_id']}')" style="padding:3px 6px;font-size:10px;background:#007bff">نسخ</button>
            </td>
            <td>{status}</td>
            <td>{rem}</td>
        </tr>"""

    html = f"""
    <!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8"><title>لوحة الادمن</title>
    <style>
        body{{background:#111;color:#eee;font-family:tahoma;padding:15px}}
        input,select,button{{padding:8px;margin:4px;border-radius:5px;border:1px solid #444;background:#222;color:#eee}}
        button{{background:#28a745;color:#fff;border:none;cursor:pointer}}
       .search-btn{{background:#007bff}}
        table{{width:100%;border-collapse:collapse;margin-top:15px}}
        td,th{{border:1px solid #444;padding:6px;text-align:center;font-size:12px}}
    </style>
    <script>
        function copyID(id) {{
            navigator.clipboard.writeText(id);
            alert('تم نسخ: ' + id);
        }}
    </script>
    </head><body>
    <h2>لوحة تحكم الادمن</h2>
    <p style="color:lightgreen">{msg}</p>

    <form method="get">
        <input type="hidden" name="key" value="{ADMIN_KEY}">
        <input name="search" placeholder="ابحث عن ID" value="{search or ''}">
        <button class="search-btn" type="submit">بحث</button>
        <a href="/admin?key={ADMIN_KEY}"><button type="button">عرض الكل</button></a>
    </form>
    <hr>
    <form method="get">
        <input type="hidden" name="key" value="{ADMIN_KEY}">
        <input name="user_id" id="user_id_input" placeholder="ID الجهاز" required>
        <select name="action">
            <option value="extend">زيادة ساعات</option>
            <option value="reduce">نقص ساعات</option>
            <option value="unlimited">فتح مفتوح</option>
            <option value="ban">حذف</option>
        </select>
        <input name="hours" type="number" step="0.5" placeholder="عدد الساعات" value="24">
        <button>تنفيذ</button>
    </form>

    <h3>المستخدمين: {len(all_users)}</h3>
    <table><tr><th>ID</th><th>الحالة</th><th>المتبقي بالساعات</th></tr>{rows}</table>
    </body></html>
    """
    return html

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
