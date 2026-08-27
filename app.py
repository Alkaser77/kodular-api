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
        return "<h3 style='color:red; text-align:center;'>كلمة السر غلط</h3>", 401

    msg = ""
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
        msg = f"<h3 style='color:green; text-align:center;'>تم اضافة {hours} ساعات لكل المستخدمين</h3>"

    # 2. تنقيص للكل - مع تأكيد
    if request.args.get('action') == 'sub_all':
        hours = float(request.args.get('hours', 1.0))
        all_users = supabase.table("users").select("*").execute().data
        for u in all_users:
            current = get_remaining_hours(u)
            u["total_hours"] = max(0, current - hours)
            if u["total_hours"] <= 0: u["status"] = "expired"
            save_user(u)
        msg = f"<h3 style='color:orange; text-align:center;'>تم تنقيص {hours} ساعات من الكل</h3>"

    # 3. حذف - مع تأكيد
    if request.args.get('action') == 'ban':
        user_id = request.args.get('user_id')
        supabase.table("users").delete().eq("user_id", user_id).execute()
        msg = f"<h3 style='color:red; text-align:center;'>تم حذف {user_id}</h3>"

    # 4. اضافة/تنقيص لجهاز واحد
    if request.args.get('action') in ['add', 'sub']:
        user_id = request.args.get('user_id')
        hours = float(request.args.get('hours', 2.0))
        now = datetime.now()
        user = get_user(user_id)
        if not user: user = {"user_id": user_id, "total_hours": 0, "session_start": None, "status": "expired"}
        current = get_remaining_hours(user)
        
        if request.args.get('action') == 'add':
            user["total_hours"] = current + hours
            user["status"] = "active"
            if not user.get("session_start") or current <= 0:
                user["session_start"] = now.strftime("%Y-%m-%d %H:%M:%S")
            msg = f"<h3 style='color:green; text-align:center;'>تم اضافة {hours} ساعات</h3>"
        else: # تنقيص
            user["total_hours"] = max(0, current - hours)
            if user["total_hours"] <= 0: user["status"] = "expired"
            msg = f"<h3 style='color:orange; text-align:center;'>تم تنقيص {hours} ساعات</h3>"
        save_user(user)

    # 5. عرض الكل
    query = supabase.table("users").select("*")
    search = request.args.get('search')
    if search:
        query = query.ilike("user_id", f"%{search}%")
    all_users = query.execute

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
