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

@app.route('/check', methods=['GET'])
def check():
    user_id = request.args.get('user_id')
    if not user_id: return jsonify({"error": "user_id missing"}), 400

    now = datetime.now()
    user = get_user(user_id)

    # 1. مستخدم جديد
    if not user:
        user = {
            "user_id": user_id,
            "hours_left": 2.0,
            "last_check": now.strftime("%Y-%m-%d %H:%M:%S"),
            "last_used": None,
            "status": "active"
        }
        save_user(user)
        return jsonify({"status": "active", "link": GOOGLE_DRIVE_LINK, "filename": FILENAME, "hours": 2.0})

    last = datetime.strptime(user["last_check"], "%Y-%m-%d %H:%M:%S")
    diff_hours = (now - last).total_seconds() / 3600

    # 2. نقص الوقت بس لو عنده وقت و active
    if user["status"] == "active" and user["hours_left"] > 0:
        user["hours_left"] = max(0, user["hours_left"] - diff_hours)

        if user["hours_left"] <= 0:
            user["hours_left"] = 0
            user["status"] = "expired"

    user["last_check"] = now.strftime("%Y-%m-%d %H:%M:%S")

    # 3. لو عنده وقت مزال
    if user["hours_left"] > 0:
        save_user(user)
        return jsonify({"status": "active", "link": GOOGLE_DRIVE_LINK, "filename": FILENAME, "hours": round(user["hours_left"], 2)})

    # 4. لو صفر نشوفو الكول داون 24 ساعة
    if user["last_used"]:
        last_used_time = datetime.strptime(user["last_used"], "%Y-%m-%d %H:%M:%S")
        hours_since_last = (now - last_used_time).total_seconds() / 3600
        if hours_since_last < 24:
            save_user(user)
            wait = 24 - hours_since_last
            return jsonify({"status": "cooldown", "message": f"Wait {round(wait,1)} hours", "hours": 0})

    # 5. كمل 24 ساعة نعطوه 2 ساعات جداد
    user["hours_left"] = 2.0
    user["last_used"] = now.strftime("%Y-%m-%d %H:%M:%S")
    user["status"] = "active"
    save_user(user)
    return jsonify({"status": "active", "link": GOOGLE_DRIVE_LINK, "filename": FILENAME, "hours": 2.0})

@app.route('/addtime', methods=['GET']) # متاع الاعلان
def add_time():
    user_id = request.args.get('user_id')
    add_hours = float(request.args.get('hours', 2.0))

    user = get_user(user_id)
    if not user:
        user = {"user_id": user_id, "hours_left": 0, "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "last_used": None, "status": "expired"}

    user["hours_left"] += add_hours
    user["status"] = "active"
    user["last_check"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_user(user)

    return jsonify({"status": "success", "new_hours": round(user['hours_left'], 2)})

@app.route('/admin/add', methods=['GET'])
def add_hours():
    user_id = request.args.get('user_id')
    add_hours = float(request.args.get('hours', 0)) # خليتها float
    key = request.args.get('key')
    if key!= ADMIN_KEY: return "Wrong key", 403

    user = get_user(user_id)
    if not user: return "User not found", 404
    user["hours_left"] += add_hours
    user["status"] = "active"
    save_user(user)
    return f"Added {add_hours} hours. Total: {round(user['hours_left'],2)}"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
