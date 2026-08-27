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
    if key != ADMIN_KEY:
        return "كلمة السر غلط", 401

    # 1. اضافة للكل
    if request.args.get('action') == 'add_all':
        hours = float(request.args.get('hours', 2.0))
        all_users = supabase.table("users").select("*").execute().data
        now = datetime.now()
        for u in all_users:
            current = get_remaining_hours(u)
            u["total_hours"] = current + hours
            u["status"] = "active"
            if not u.get("session_start") or current <= 0:
                u["session_start"] = now.strftime("%Y-%m-%d %H:%M:%S")
            save_user(u)
        return f"تم اضافة {hours} ساعات لكل المستخدمين. <a href='/admin?key={ADMIN_KEY}'>رجوع</a>"

    # 2. حذف
    if request.args.get('action') == 'ban':
        user_id = request.args.get('user_id')
        supabase.table("users").delete().eq("user_id", user_id).execute()

    # 3. اضافة لساعة واحدة
    if request.args.get('action') == 'add':
        user_id = request.args.get('user_id')
        hours = float(request.args.get('hours', 2.0))
        now = datetime.now()
        user = get_user(user_id)
        if not user: user = {"user_id": user_id, "total_hours": 0, "session_start": None, "status": "expired"}
        current = get_remaining_hours(user)
        user["total_hours"] = current + hours
        user["status"] = "active"
        if not user.get("session_start") or current <= 0:
            user["session_start"] = now.strftime("%Y-%m-%d %H:%M:%S")
        save_user(user)

    # 4. عرض الكل
    query = supabase.table("users").select("*")
    search = request.args.get('search')
    if search:
        query = query.ilike("user_id", f"%{search}%")
    all_users = query.execute().data

    html = f"""
    <h2>لوحة تحكم الادمن</h2>
    <form method="get">
        <input type="hidden" name="key" value="{ADMIN_KEY}">
        <input type="text" name="search" placeholder="بحث بالـ ID">
        <button type="submit">بحث</button>
        <a href="/admin?key={ADMIN_KEY}"><button type="button">عرض الكل</button></a>
    </form>
    
    <hr>
    <form method="get" style="background:#ffe; padding:10px; border:1px solid orange;">
        <input type="hidden" name="key" value="{ADMIN_KEY}">
        <input type="hidden" name="action" value="add_all">
        <b>اضافة ساعات للكل:</b>
        <input type="number" name="hours" value="2" step="0.5" style="width:80px;">
        <button type="submit" style="background:orange; color:white;">اضافة للكل</button>
    </form>
    <hr>
    
    <form method="get">
        <input type="hidden" name="key" value="{ADMIN_KEY}">
        <input type="text" name="user_id" placeholder="ID الجهاز">
        <input type="number" name="hours" value="24" step="0.5">
        <button name="action" value="add">زيادة ساعات</button>
    </form>
    <hr>
    <table border="1" cellpadding="5">
        <tr><th>ID</th><th>الساعات</th><th>الحالة</th><th>تحكم</th></tr>
    """
    for u in all_users:
        remaining = get_remaining_hours(u)
        status = "🟢 شغال" if remaining > 0 else "🔴 منتهي"
        html += f"<tr><td>{u['user_id']}</td><td>{round(remaining,2)}</td><td>{status}</td>"
        html += f"<td><a href='/admin?key={ADMIN_KEY}&action=ban&user_id={u['user_id']}'>حذف</a></td></tr>"
    html += "</table>"
    return html

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
