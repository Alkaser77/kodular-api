from flask import Flask, request, jsonify, redirect, Response
from datetime import datetime, timedelta
from supabase import create_client, Client
import os, requests, json, threading
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

app = Flask(__name__)

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

FOLDER = 'files'
ADMIN_KEY = "admin123"
DRIVE_NPVT_ID = os.environ.get('DRIVE_NPVT_ID', '1T8zHaaiCEf-Zkgxpz-ig5Q8_5hScsq1I')
FILES = ["File.npvt", "File.ssc", "File.nm"]

BOT_TOKEN = os.environ.get("BOT_TOKEN")
API_URL = os.environ.get("API_URL", "https://kodular-api-1.onrender.com")

def get_user(user_id):
    res = supabase.table("users").select("*").eq("user_id", user_id).execute()
    return res.data[0] if res.data else None
def save_user(user):
    supabase.table("users").upsert(user).execute()
def get_remaining_hours(user):
    if not user or not user.get("expires_at"): return 0
    try:
        expires = parse_expire(user.get("expires_at"))
        return max(0, (expires - datetime.now()).total_seconds() / 3600)
    except:
        return 0
def format_hm(hours_float):
    total_minutes = int(round(hours_float * 60))
    h = total_minutes // 60; m = total_minutes % 60
    if h >= 24:
        d = h // 24; rh = h % 24
        return f"{d} day {rh}:{m:02d}"
    return f"{h}:{m:02d}"
def get_allowed_files(user):
    if not user or not user.get("allowed_files"): return FILES
    allowed = user.get("allowed_files")
    if isinstance(allowed, str):
        try: allowed = json.loads(allowed)
        except: allowed = [x.strip() for x in allowed.split(",") if x.strip()]
    return [f for f in allowed if f in FILES]
def get_days_hours_from_args():
    days = float(request.args.get('days', 0) or 0)
    hours = float(request.args.get('hours', 0) or 0)
    return days * 24 + hours

@app.route('/')
def home():
    return """<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>جاري التحميل...</title>
    <style>body{font-family:Tahoma;background:#f4f4f4;display:flex;justify-content:center;align-items:center;height:100vh;margin:0}
 .box{background:white;padding:30px;border-radius:15px;box-shadow:0 5px 20px #0002;text-align:center;width:90%;max-width:400px}
 .loader{border:4px solid #f3f3f3;border-top:4px solid #007bff;border-radius:50%;width:40px;height:40px;animation:spin 1s linear infinite;margin:15px auto}
    @keyframes spin{0%{transform:rotate(0deg)}100%{transform:rotate(360deg)}}</style>
    <script>async function start(){let uid=localStorage.getItem('my_user_id');if(!uid){uid='WEB-'+Math.random().toString(36).substr(2,9).toUpperCase()+Date.now().toString().slice(-5);localStorage.setItem('my_user_id',uid);}
    document.getElementById('uid').innerText=uid;try{let r=await fetch('/check?user_id='+uid);let d=await r.json();if(d.status==='cooldown'){document.getElementById('box').innerHTML='<h2 style=color:#dc3545>⏳ انتهى وقتك</h2><p>ارجع بعد: <b dir=ltr>'+d.hours+'</b></p>';return;}}catch(e){}window.location.href='/user/'+uid;}window.onload=start;</script>
    </head><body><div class="box" id="box"><div class="loader"></div><h3>لحظة جاري تجهيز صفحتك...</h3><p><code id="uid"></code></p></div></body></html>"""

@app.route('/check', methods=['GET'])
def check():
    user_id = request.args.get('user_id')
    if not user_id: return jsonify({"error": "user_id missing"}), 400
    now = datetime.now(); user = get_user(user_id); allowed = get_allowed_files(user) if user else FILES
    base_url = request.host_url; links = [f"{base_url}download/{f}?user_id={user_id}" for f in allowed]
    if not user:
        expires = now + timedelta(hours=2)
        user = {"user_id": user_id, "expires_at": expires.strftime("%Y-%m-%d %H:%M:%S"), "status": "active", "allowed_files": FILES, "page_enabled": True, "can_download": True}
        save_user(user)
        return jsonify({"status": "active", "links": links, "files": allowed, "hours": "2:00", "hours_float": 2.0})
    remaining = get_remaining_hours(user)
    if remaining <= 0:
        user["status"] = "expired"; last_expire = datetime.strptime(user["expires_at"], "%Y-%m-%d %H:%M:%S")
        hours_since_expire = (now - last_expire).total_seconds() / 3600
        if hours_since_expire >= 24:
            new_expire = now + timedelta(hours=2); user["expires_at"] = new_expire.strftime("%Y-%m-%d %H:%M:%S"); user["status"] = "active"; save_user(user)
            return jsonify({"status": "active", "links": links, "files": allowed, "hours": "2:00", "hours_float": 2.0})
        else:
            remaining_cooldown = 24 - hours_since_expire; save_user(user)
            return jsonify({"status": "cooldown", "message": f"Wait {format_hm(remaining_cooldown)} hours", "hours": format_hm(remaining_cooldown), "hours_float": round(remaining_cooldown, 2)})
    return jsonify({"status": "active", "links": links, "files": allowed, "hours": format_hm(remaining), "hours_float": round(remaining, 2)})

@app.route('/download/<filename>')
def download(filename):
    user_id = request.args.get('user_id')
    if not user_id: return "user_id missing", 400
    user = get_user(user_id)
    if not user: return "user not found", 403
    if not user.get("page_enabled", True): return "صفحتك موقوفة", 403
    if not user.get("can_download", True): return "التحميل موقف", 403
    if get_remaining_hours(user) <= 0: return "Time expired", 403
    if filename not in FILES or filename not in get_allowed_files(user): return "not allowed", 403
    if filename == "File.npvt":
        gdrive_url = f"https://drive.google.com/uc?export=download&id={DRIVE_NPVT_ID}"
        try:
            r = requests.get(gdrive_url, stream=True, timeout=30)
            return Response(r.iter_content(chunk_size=8192), mimetype='application/octet-stream', headers={"Content-Disposition": f"attachment;filename={filename}"})
        except Exception as e: return f"Drive error: {e}", 500
    file_path = os.path.join(FOLDER, filename)
    if not os.path.exists(file_path): return "File not found", 404
    with open(file_path, 'rb') as f: data = f.read()
    return Response(data, mimetype='application/octet-stream', headers={"Content-Disposition": f"attachment;filename={filename}"})

@app.route('/user/<user_id>')
def user_page(user_id):
    user = get_user(user_id)
    if not user: return "<h2>المستخدم غير موجود</h2>",404
    if not user.get("page_enabled", True): return "<h2 style='color:red'>⛔ موقوفة</h2>",403
    rem = get_remaining_hours(user)
    if rem <= 0: return f"<h2>⏳ انتهى اشتراكك</h2><p>{user_id}</p>"
    allowed = get_allowed_files(user); can_dl = user.get("can_download", True); cards = ""
    for f in allowed:
        dl = f"{request.host_url}download/{f}?user_id={user_id}"
        btn = f"<a href='{dl}' style='background:#28a745;color:white;padding:12px;border-radius:8px;text-decoration:none;display:block;'>⬇️ تحميل</a>" if can_dl else "<span>ممنوع</span>"
        cards += f"<div style='background:white;border:1px solid #eee;border-radius:12px;padding:15px;text-align:center;'><h4>{f}</h4>{btn}</div>"
    return f"""<html dir="rtl"><head><meta charset="UTF-8"></head><body style="font-family:Tahoma;background:#f4f4f4;padding:15px;"><div style="max-width:800px;margin:auto;"><div style="background:linear-gradient(135deg,#007bff,#6610f2);color:white;padding:20px;border-radius:15px;text-align:center;"><h2>صفحتك الخاصة</h2><code>{user_id}</code><p>متبقي: {format_hm(rem)}</p></div><br><div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:15px;">{cards}</div></div></body></html>"""

@app.route('/admin', methods=['GET'])
def admin_panel():
    try:
        key = request.args.get('key')
        if key!= ADMIN_KEY: return "<h3>key=admin123</h3>", 401
        now = datetime.now()
        msg = "<h3 style='color:green;text-align:center;'>✅ تم</h3>" if request.args.get('msg')=='done' else ""
        action = request.args.get('action')
        uid = request.args.get('user_id')

        def parse_expire(s):
    if not s: return datetime.now()
    try:
        s = s.replace('T',' ').split('.')[0]
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except:
        try:
            return datetime.fromisoformat(s.replace('Z',''))
        except:
            return datetime.now()

@app.route('/check', methods=['GET'])
def check():
    user_id = request.args.get('user_id')
    if not user_id: return jsonify({"error": "user_id missing"}), 400
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
