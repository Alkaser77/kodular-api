from flask import Flask, request, jsonify
import json
import os
from datetime import datetime

app = Flask(__name__)
DB_FILE = "users.json"
GOOGLE_DRIVE_LINK = "https://drive.google.com/uc?export=download&id=1bB0Tkx2Oc5Dc8DBCjHBQryvkUGj3GWKT"
ADMIN_KEY = "admin123" # غيرها

def read_db():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r") as f:
        return json.load(f)

def write_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=2)

@app.route('/')
def home():
    return "API is Running"

@app.route('/check', methods=['GET'])
def check():
    user_id = request.args.get('user_id')
    
    if not user_id:
        return jsonify({"error": "user_id missing"}), 400

    db = read_db()
    now = datetime.now()

    # لو مستخدم جديد
    if user_id not in db:
        db[user_id] = {
            "hours_left": 2, # نعطيه 2 ساعات بس
            "last_check": now.strftime("%Y-%m-%d %H:%M:%S"),
            "last_used": None # اخر مرة استخدم فيها
        }

    user = db[user_id]
    last = datetime.strptime(user["last_check"], "%Y-%m-%d %H:%M:%S")
    
    # نحسبو الفرق بالساعات ونقصو من الرصيد
    diff_hours = (now - last).total_seconds() / 3600
    user["hours_left"] = user["hours_left"] - diff_hours
    user["last_check"] = now.strftime("%Y-%m-%d %H:%M:%S")

    # حالة 1: عنده ساعات باقية
    if user["hours_left"] > 0:
        write_db(db)
        return jsonify({
            "status": "active",
            "link": GOOGLE_DRIVE_LINK,
            "hours": round(user["hours_left"], 1) # نقرب لرقم واحد
        })

    # حالة 2: الساعات تمو. نشيكو فات 24 ساعة ولا لا
    user["hours_left"] = 0 # نثبتو انه صفر
    if user["last_used"] is not None:
        last_used_time = datetime.strptime(user["last_used"], "%Y-%m-%d %H:%M:%S")
        cooldown_hours = (now - last_used_time).total_seconds() / 3600
        
        if cooldown_hours < 24: # مازال ما كملش 24
            remaining_cooldown = 24 - cooldown_hours
            write_db(db)
            return jsonify({
                "status": "cooldown",
                "message": f"Wait {round(remaining_cooldown,1)} hours to renew",
                "hours": 0
            })

    # حالة 3: كمل 24 ساعة. نجددوله 2 ساعات
    user["hours_left"] = 2
    user["last_used"] = now.strftime("%Y-%m-%d %H:%M:%S") # نسجلو وقت التجديد
    write_db(db)
    return jsonify({
        "status": "active",
        "link": GOOGLE_DRIVE_LINK,
        "hours": 2
    })

# رابط الادمن باش تزيد ساعات يدوي
@app.route('/admin/add', methods=['GET'])
def add_hours():
    user_id = request.args.get('user_id')
    add_hours = int(request.args.get('hours', 0))
    key = request.args.get('key')

    if key != ADMIN_KEY:
        return "Wrong key", 403

    db = read_db()
    if user_id not in db:
        return "User not found", 404

    db[user_id]["hours_left"] += add_hours
    write_db(db)
    return f"Added {add_hours} hours to {user_id}. Total: {db[user_id]['hours_left']}"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
