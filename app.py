from flask import Flask, request, jsonify, send_from_directory
from datetime import datetime, timedelta, timezone # 1. زيد timezone
from supabase import create_client, Client
import os

app = Flask(__name__)

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

FOLDER = 'files'
ADMIN_KEY = "admin123"

def get_user(user_id):
    res = supabase.table("users").select("*").eq("user_id", user_id).execute()
    return res.data[0] if res.data else None

def save_user(user):
    supabase.table("users").upsert(user).execute()

def get_remaining_hours(user):
    if not user or not user.get("expires_at"):
        return 0
    # 2. صلح المقارنة
    expires = datetime.strptime(user["expires_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    remaining = (expires - now).total_seconds() / 3600
    return max(0, remaining)

@app.route('/check', methods=['GET'])
def check():
    user_id = request.args.get('user_id')
    filename = request.args.get('file', 'File.npvt')
    if not user_id: return jsonify({"error": "user_id missing"}), 400

    now = datetime.now(timezone.utc) # 3. غيرها
    user = get_user(user_id)

    if not user: # مستخدم جديد
        expires = now + timedelta(hours=2)
        user = {"user_id": user_id, "expires_at": expires.strftime("%Y-%m-%d %H:%M:%S"), "status": "active"}
        save_user(user)
        download_url = f"/download/{filename}?user_id={user_id}"
        return jsonify({"status": "active", "link": download_url, "filename": filename, "hours": 2.0})

    remaining = get_remaining_hours(user)

    if remaining <= 0: # الوقت تم
        user["status"] = "expired"
        last_expire = datetime.strptime(user["expires_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc) # صلحها
        hours_since_expire = (now - last_expire).total_seconds() / 3600

        if hours_since_expire >= 24: # فات 24 نجددو
            new_expire = now + timedelta(hours=2)
            user["expires_at"] = new_expire.strftime("%Y-%m-%d %H:%M:%S")
            user["status"] = "active"
            save_user(user)
            download_url = f"/download/{filename}?user_id={user_id}"
            return jsonify({"status": "active", "link": download_url, "filename": filename, "hours": 2.0})
        else:
            wait = round(24 - hours_since_expire, 1)
            save_user(user)
            return jsonify({"status": "cooldown", "message": f"Wait {wait} hours", "hours": 0})

    # عنده وقت
    download_url = f"/download/{filename}?user_id={user_id}"
    return jsonify({"status": "active", "link": download_url, "filename": filename, "hours": round(remaining, 2)})

@app.route('/download/<filename>')
def download(filename):
    user_id = request.args.get('user_id')
    user = get_user(user_id)
    remaining = get_remaining_hours(user)
    if remaining <= 0: return "Time expired", 403
    file_path = os.path.join(FOLDER, filename)
    if not os.path.exists(file_path): return f"File {filename} not found", 404
    return send_from_directory(FOLDER, filename, as_attachment=True, download_name=filename)

# باقي الكود متاع الادمن زي ما هو... بس غير datetime.now() ل datetime.now(timezone.utc)
