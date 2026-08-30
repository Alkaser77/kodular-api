from flask import Flask, request, jsonify, send_from_directory, redirect
from datetime import datetime, timedelta
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
    expires = datetime.strptime(user["expires_at"], "%Y-%m-%d %H:%M:%S")
    now = datetime.now()
    remaining = (expires - now).total_seconds() / 3600
    return max(0, remaining)

@app.route('/check', methods=['GET'])
def check():
    user_id = request.args.get('user_id')
    filename = request.args.get('file', 'File.npvt')
    if not user_id: return jsonify({"error": "user_id missing"}), 400

    now = datetime.now()
    user = get_user(user_id)

    # 1. مستخدم جديد
    if not user:
        expires = now + timedelta(hours=2)
        user = {"user_id": user_id, "expires_at": expires.strftime("%Y-%m-%d %H:%M:%S"), "status": "active"}
        save_user(user)
        download_url = f"/download/{filename}?user_id={user_id}"
        return jsonify({"status": "active", "link": download_url, "filename": filename, "hours": 2.0})

    remaining = get_remaining_hours(user)

    # 2. لو الوقت تم
    if remaining <= 0:
        user["status"] = "expired"
        last_expire = datetime.strptime(user["expires_at"], "%Y-%m-%d %H:%M:%S")
        hours_since_expire = (now - last_expire).total_seconds() / 3600

        if hours_since_expire >= 24:
            # فات 24: نجددو ساعتين من توا
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

    # 3. لو عنده وقت
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

@app.route('/admin', methods=['GET'])
def admin_panel():
    key = request.args.get('key')
    if key!= ADMIN_KEY: return "<h3 style='color:red; text-align:center;'>كلمة السر غلط</h3>", 401
    msg = ""
    now = datetime.now()
    if request.args.get('msg') == 'done': msg = "<h3 style='color:blue; text-align:center;'>تمت العملية بنجاح</h3>"

    # 1. اضافة للكل
    if request.args.get('action') == 'add_all':
        hours = float(request.args.get('hours', 2.0))
        all_users = supabase.table("users").select("*").execute().data
        for u in all_users:
            current_expire_str = u.get("expires_at")
            current_expire = datetime.strptime(current_expire_str, "%Y-%m-%d %H:%M:%S") if current_expire_str else now
            base_time = max(now, current_expire) # نزيدو على الاكبر: يا توا يا اخر انتهاء
            new_expire = base_time + timedelta(hours=hours)
            u["expires_at"] = new_expire.strftime("%Y-%m-%d %H:%M:%S")
            u["status"] = "active"
            save_user(u)
        return redirect(f"/admin?key={ADMIN_KEY}&msg=done")

    # 2. تنقيص للكل
    if request.args.get('action') == 'sub_all':
        hours = float(request.args.get('hours', 1.0))
        all_users = supabase.table("users").select("*").execute().data
        for u in all_users:
            current_expire_str = u.get("expires_at")
            if current_expire_str:
                current_expire = datetime.strptime(current_expire_str, "%Y-%m-%d %H:%M:%S")
                new_expire = current_expire - timedelta(hours=hours)
                if new_expire < now: new_expire = now
                u["expires_at"] = new_expire.strftime("%Y-%m-%d %H:%M:%S")
                if new_expire <= now: u["status"] = "expired"
                save_user(u)
        return redirect(f"/admin?key={ADMIN_KEY}&msg=done")

    # 3. حذف
    if request.args.get('action') == 'ban':
        user_id = request.args.get('user_id')
        supabase.table("users").delete().eq("user_id", user_id).execute()
        return redirect(f"/admin?key={ADMIN_KEY}&msg=done")

    # 4. تصفير الجهاز
    if request.args.get('action') == 'reset':
        user_id = request.args.get('user_id')
        new_expire = now + timedelta(hours=2)
        user = get_user(user_id)
        if user:
            user["expires_at"] = new_expire.strftime("%Y-%m-%d %H:%M:%S")
            user["status"] = "active"
            save_user(user)
        return redirect(f"/admin?key={ADMIN_KEY}&msg=done")

    # 5. اضافة/تنقيص لجهاز واحد
    if request.args.get('action') in ['add', 'sub']:
        user_id = request.args.get('user_id')
        hours = float(request.args.get('hours', 2.0))
        user = get_user(user_id)
        if not user:
            new_expire = now + timedelta(hours=hours)
            user = {"user_id": user_id, "expires_at": new_expire.strftime("%Y-%m-%d %H:%M:%S"), "status": "active"}
        else:
            current_expire_str = user.get("expires_at")
            current_expire = datetime.strptime(current_expire_str, "%Y-%m-%d %H:%M:%S") if current_expire_str else now
            base_time = max(now, current_expire)
            if request.args.get('action') == 'add':
                new_expire = base_time + timedelta(hours=hours)
                user["status"] = "active"
            else:
                new_expire = current_expire - timedelta(hours=hours)
                if new_expire < now: new_expire = now
                if new_expire <= now: user["status"] = "expired"
            user["expires_at"] = new_expire.strftime("%Y-%m-%d %H:%M:%S")
        save_user(user)
        return redirect(f"/admin?key={ADMIN_KEY}&msg=done")

    # 6. عرض الكل
    query = supabase.table("users").select("*").order("expires_at", desc=True)
    search = request.args.get('search')
    if search: query = query.ilike("user_id", f"%{search}%")
    all_users = query.execute().data

    html = f"""
    <!DOCTYPE html><html dir="rtl" lang="ar"><head><meta charset="UTF-8"><title>لوحة تحكم الادمن</title>
    <style>
        body {{ font-family: Tahoma; background:#f4f4f4; padding:20px; }}
    .container {{ max-width:1000px; margin:auto; background:white; padding:20px; border-radius:10px; box-shadow:0 0 10px #ccc; }}
        h2 {{ text-align:center; color:#333; }}
        table {{ width:100%; border-collapse: collapse; margin-top:20px; table-layout: fixed; }}
        th {{ background:#007bff; color:white; padding:10px; }}
        td {{ padding:10px; text-align:center; border-bottom:1px solid #ddd; word-break: break-all; }}
        input, button {{ padding:8px; margin:5px; border-radius:5px; border:1px solid #ccc; }}
        button {{ background:#007bff; color:white; cursor:pointer; border:none; }}
        button:hover {{ background:#0056b3; }}
    .addall {{ background:#ffc107; padding:15px; border-radius:8px; margin:20px 0; text-align:center; }}
    .addall button {{ background:#ff8800; }}
    .suball button {{ background:#dc3545; }}
    .del {{ background:red; padding:6px 10px; text-decoration:none; color:white; border-radius:5px; font-size:12px; }}
    .copy {{ background:#28a745; padding:6px 10px; font-size:12px; text-decoration:none; color:white; border-radius:5px; cursor:pointer; }}
    .reset {{ background:#6c757d; padding:6px 10px; font-size:12px; text-decoration:none; color:white; border-radius:5px; }}
    .actions {{ display:flex; justify-content:center; gap:5px; flex-wrap:wrap; }}
    </style>
    <script>
        function copyID(id) {{ navigator.clipboard.writeText(id); alert('تم نسخ: ' + id); }}
        function confirmAction(msg) {{ return confirm(msg); }}
    </script>
    </head><body><div class="container">
    <h2>لوحة تحكم الادمن</h2>
    {msg}
    <form method="get"><input type="hidden" name="key" value="{ADMIN_KEY}"><input type="text" name="search" placeholder="بحث بالـ ID" value="{search if search else ''}"><button type="submit">بحث</button><a href="/admin?key={ADMIN_KEY}"><button type="button">عرض الكل</button></a></form>
    <div class="addall">
        <form method="get" style="display:inline-block;" onsubmit="return confirmAction('متأكد تبي تضيف ساعات لكل المستخدمين؟')"><input type="hidden" name="key" value="{ADMIN_KEY}"><input type="hidden" name="action" value="add_all"><b>للكل:</b><input type="number" name="hours" value="2" step="0.5" style="width:80px;"><button type="submit">+ اضافة</button></form>
        <form method="get" style="display:inline-block;" class="suball" onsubmit="return confirmAction('تحذير: متأكد تبي تنقص ساعات من الكل؟')"><input type="hidden" name="key" value="{ADMIN_KEY}"><input type="hidden" name="action" value="sub_all"><input type="number" name="hours" value="1" step="0.5" style="width:80px;"><button type="submit">- تنقيص</button></form>
    </div>
    <form method="get"><input type="hidden" name="key" value="{ADMIN_KEY}"><input type="text" name="user_id" placeholder="ID الجهاز" required><input type="number" name="hours" value="24" step="0.5"><button name="action" value="add">+ زيادة</button><button name="action" value="sub" class="suball">- تنقيص</button></form><hr>
    <table><tr><th style="width:35%">ID الجهاز</th><th style="width:20%">الساعات المتبقية</th><th style="width:15%">الحالة</th><th style="width:30%">تحكم</th></tr>
    """
    for u in all_users:
        remaining = get_remaining_hours(u)
        status = "🟢 شغال" if remaining > 0 else "🔴 منتهي"
        html += f"<tr>"
        html += f"<td style='font-family: monospace;'>{u['user_id']}</td>"
        html += f"<td>{round(remaining,2)}</td>"
        html += f"<td>{status}</td>"
        html += f"<td><div class='actions'>"
        html += f"<span class='copy' onclick=\"copyID('{u['user_id']}')\">نسخ</span>"
        html += f"<a class='reset' href='/admin?key={ADMIN_KEY}&action=reset&user_id={u['user_id']}' onclick=\"return confirmAction('بترجعه 2 ساعات من جديد؟')\">تصفير</a>"
        html += f"<a class='del' href='/admin?key={ADMIN_KEY}&action=ban&user_id={u['user_id']}' onclick=\"return confirmAction('متأكد تبي تحذف {u['user_id']}؟')\">حذف</a>"
        html += f"</div></td></tr>"
    html += "</table></div></body></html>"
    return html

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
