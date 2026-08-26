from flask import Flask, request, jsonify
from datetime import datetime
from supabase import create_client, Client
import os

app = Flask(__name__)

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

GOOGLE_DRIVE_LINK = "https://drive.google.com/uc?export=download&id=1bB0Tkx2Oc5Dc8DBCjHBQryvkUGj3GWKT"
FILENAME = "server1.npvt"
ADMIN_KEY = "admin123"

def get_user(user_id):
    res = supabase.table("users").select("*").eq("user_id", user_id).execute()
    return res.data[0] if res.data else None

def save_user(user):
    supabase.table("users").upsert(user).execute()

def get_remaining_hours(user):
    # لو مافيش تايمر بادي معناها ماعنداش وقت
    if not user.get("last_used"):
        return user["hours_left"]

    last_used = datetime.strptime(user["last_used"], "%Y-%m-%d %H:%M:%S")
    now = datetime.now()
    passed_hours = (now - last_used).total_seconds() / 3600

    # الوقت المتبقي = الوقت الاصلي - الوقت اللي فات
    remaining = user["hours_left"] - passed_hours
    return max(0, remaining)

@app.route('/check', methods=['GET'])
def check():
    user_id = request.args.get('user_id')
    if not user_id: return jsonify({"error": "user_id missing"}), 400

    now = datetime.now()
    user = get_user(user_id)

    # 1. مستخدم جديد: نعطيه ساعتين ونبدا التايمر
    if not user:
        user = {
            "user_id": user_id,
            "hours_left": 2.0, # هذا ثابت. وقت التفعيل
            "last_used": now.strftime("%Y-%m-%d %H:%M:%S"), # بداية العد
            "status": "active"
        }
        save_user(user)
        return jsonify({"status": "active", "link": GOOGLE_DRIVE_LINK, "filename": FILENAME, "hours": 2.0})

    # 2. نحسب الوقت المتبقي توا
    remaining = get_remaining_hours(user)

    # 3. لو الوقت تم
    if remaining <= 0:
        user["hours_left"] = 0
        user["status"] = "expired"

        # نشوفو فات 24 ساعة ولا لا
        last_used_time = datetime.strptime(user["last_used"], "%Y-%m-%d %H:%M:%S")
        hours_since_last = (now - last_used_time).total_seconds() / 3600

        if hours_since_last >= 24:
            # فات 24: نجدد ساعتين جداد ونبدا عد جديد
            user["hours_left"] = 2.0
            user["last_used"] = now.strftime("%Y-%m-%d %H:%M:%S")
            user["status"] = "active"
            save_user(user)
            return jsonify({"status": "active", "link": GOOGLE_DRIVE_LINK, "filename": FILENAME, "hours": 2.0})
        else:
            # مزال في الكول داون
            wait = round(24 - hours_since_last, 1)
            save_user(user)
            return jsonify({"status": "cooldown", "message": f"Wait {wait} hours", "hours": 0})

    # 4. لو عنده وقت: نحدث hours_left باش ما يقعدش يجمع
    # بس last_used يقعد ثابت. هكي كل تشيك يعطي رقم اقل
    user["hours_left"] = remaining
    save_user(user)

    return jsonify({"status": "active", "link": GOOGLE_DRIVE_LINK, "filename": FILENAME, "hours": round(remaining, 2)})

@app.route('/addtime', methods=['GET'])
def add_time():
    user_id = request.args.get('user_id')
    add_hours = float(request.args.get('hours', 2.0))
    now = datetime.now()

    user = get_user(user_id)
    if not user:
        user = {"user_id": user_id, "hours_left": 0, "last_used": None, "status": "expired"}

    current = get_remaining_hours(user)
    user["hours_left"] = current + add_hours
    user["status"] = "active"
    # نبدا تايمر جديد لو كان صفر
    if not user.get("last_used") or current <= 0:
        user["last_used"] = now.strftime("%Y-%m-%d %H:%M:%S")
    save_user(user)

    return jsonify({"status": "success", "new_hours": round(user['hours_left'], 2)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
