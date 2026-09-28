from flask import Flask, request, jsonify, redirect, Response
from datetime import datetime, timedelta
from supabase import create_client, Client
import os, requests, json

app = Flask(__name__)

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

FOLDER = 'files'
ADMIN_KEY = "admin123"
DRIVE_NPVT_ID = os.environ.get('DRIVE_NPVT_ID', '1T8zHaaiCEf-Zkgxpz-ig5Q8_5hScsq1I')
FILES = ["File.npvt", "File.ssc", "File.nm"]

def get_user(user_id):
    res = supabase.table("users").select("*").eq("user_id", user_id).execute()
    return res.data[0] if res.data else None

def save_user(user):
    supabase.table("users").upsert(user).execute()

def get_remaining_hours(user):
    if not user or not user.get("expires_at"): return 0
    try:
        expires = datetime.strptime(user["expires_at"], "%Y-%m-%d %H:%M:%S")
        return max(0, (expires - datetime.now()).total_seconds() / 3600)
    except: return 0

def format_hm(hours_float):
    total_minutes = int(round(hours_float * 60))
    h = total_minutes // 60; m = total_minutes % 60
    if h >= 24:
        d = h // 24; rh = h % 24
        return f"{d} day{'s' if d>1 else ''} {rh}:{m:02d}"
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
    document.getElementById('uid').innerText=uid;try{let r=await fetch('/check?user_id='+uid);let d=await r.json();if(d.status==='cooldown'){document.getElementById('box').innerHTML='<h2 style=color:#dc3545>⏳ انتهى وقتك</h2><p>ارجع بعد: <b dir=ltr>'+d.hours+'</b></p><p><code>'+uid+'</code></p>';return;}}catch(e){}window.location.href='/user/'+uid;}window.onload=start;</script>
    </head><body><div class="box" id="box"><div class="loader"></div><h3>لحظة جاري تجهيز صفحتك...</h3><p style="color:#999;font-size:11px;"><code id="uid"></code></p></div></body></html>"""

@app.route('/check', methods=['GET'])
def check():
    user_id = request.args.get('user_id')
    if not user_id: return jsonify({"error": "user_id missing"}), 400
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
        user["status"] = "expired"
        last_expire = datetime.strptime(user["expires_at"], "%Y-%m-%d %H:%M:%S")
        hours_since_expire = (now - last_expire).total_seconds() / 3600
        if hours_since_expire >= 24:
            new_expire = now + timedelta(hours=2)
            user["expires_at"] = new_expire.strftime("%Y-%m-%d %H:%M:%S"); user["status"] = "active"; save_user(user)
            return jsonify({"status": "active", "links": links, "files": allowed, "hours": "2:00", "hours_float": 2.0})
        else:
            remaining_cooldown = 24 - hours_since_expire
            save_user(user)
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
    if not user: return "<h2 style='text-align:center;margin-top:100px;'>المستخدم غير موجود</h2>",404
    if not user.get("page_enabled", True): return "<h2 style='color:red;text-align:center;margin-top:100px;'>⛔ صفحتك موقوفة من الادمن</h2>",403
    rem = get_remaining_hours(user)
    if rem <= 0: return f"<html dir='rtl'><head><meta charset='UTF-8'></head><body style='font-family:Tahoma;text-align:center;padding-top:100px;'><h2>⏳ انتهى اشتراكك</h2><p>{user_id}</p><a href='/'>الرئيسية</a></body></html>"
    allowed = get_allowed_files(user); can_dl = user.get("can_download", True)
    cards = ""
    for f in allowed:
        dl = f"{request.host_url}download/{f}?user_id={user_id}"
        btn = f"<a href='{dl}' style='background:#28a745;color:white;padding:12px 20px;border-radius:8px;text-decoration:none;display:block;font-weight:bold;'>⬇️ تحميل</a>" if can_dl else "<span style='background:#ccc;color:#666;padding:12px;border-radius:8px;display:block;'>ممنوع</span>"
        cards += f"<div style='background:white;border:1px solid #eee;border-radius:12px;padding:15px;text-align:center;'><div style='font-size:30px;'>📦</div><h4>{f}</h4>{btn}</div>"
    return f"""<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>صفحتي</title>
    <style>body{{font-family:Tahoma;background:#f4f4f4;padding:15px;margin:0}}.container{{max-width:800px;margin:auto}}.header{{background:linear-gradient(135deg,#007bff,#6610f2);color:white;padding:25px;border-radius:15px;text-align:center}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:15px}}</style>
    </head><body><div class="container"><div class="header"><h2>صفحتك الخاصة</h2><small><code>{user_id}</code></small><p>متبقي: {format_hm(rem)}</p></div><br><div class="grid">{cards}</div></div></body></html>"""

@app.route('/admin', methods=['GET'])
def admin_panel():
    key = request.args.get('key')
    if key!= ADMIN_KEY: return "<h3>key=admin123</h3>", 401
    now = datetime.now()
    msg = "<h3 style='color:green;text-align:center;'>✅ تم</h3>" if request.args.get('msg')=='done' else ""
    action = request.args.get('action'); uid = request.args.get('user_id')

    if action == 'set_perm' and uid:
        files = [f for f in request.args.get('files','').split(',') if f in FILES]
        u = get_user(uid);
        if u: u["allowed_files"]=files; save_user(u)
        return redirect(f"/admin?key={ADMIN_KEY}&msg=done")
    if action == 'toggle_page' and uid:
        u=get_user(uid); u["page_enabled"]= not u.get("page_enabled",True); save_user(u)
        return redirect(f"/admin?key={ADMIN_KEY}&msg=done")
    if action == 'toggle_dl' and uid:
        u=get_user(uid); u["can_download"]= not u.get("can_download",True); save_user(u)
        return redirect(f"/admin?key={ADMIN_KEY}&msg=done")
    if action == 'ban' and uid:
        supabase.table("users").delete().eq("user_id", uid).execute()
        return redirect(f"/admin?key={ADMIN_KEY}&msg=done")
    if action == 'reset' and uid:
        u=get_user(uid); u["expires_at"]=(now+timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S"); u["status"]="active"; save_user(u)
        return redirect(f"/admin?key={ADMIN_KEY}&msg=done")
    if action in ['add','sub','add_all','sub_all']:
        total = get_days_hours_from_args()
        users = [get_user(uid)] if action in ['add','sub'] else supabase.table("users").select("*").execute().data
        for u in users:
            if not u: continue
            cur_str = u.get("expires_at"); cur = datetime.strptime(cur_str, "%Y-%m-%d %H:%M:%S") if cur_str else now
            base = max(now,cur) if 'add' in action else cur
            new = base+timedelta(hours=total) if 'add' in action else cur-timedelta(hours=total)
            if new < now: new = now
            u["expires_at"]=new.strftime("%Y-%m-%d %H:%M:%S"); u["status"]="active" if new>now else "expired"; save_user(u)
        return redirect(f"/admin?key={ADMIN_KEY}&msg=done")

    query = supabase.table("users").select("*").order("expires_at", desc=True)
    search = request.args.get('search')
    if search: query = query.ilike("user_id", f"%{search}%")
    all_users = query.execute().data

    html = f"""<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8"><title>الادمن</title>
    <style>body{{font-family:Tahoma;background:#f4f4f4;padding:10px;font-size:13px}}.c{{max-width:1300px;margin:auto;background:white;padding:15px;border-radius:10px}} table{{width:100%;border-collapse:collapse}} th{{background:#007bff;color:white;padding:8px;font-size:12px}} td{{padding:8px;border-bottom:1px solid #ddd;text-align:center}}.b{{padding:5px 9px;border-radius:5px;color:white;text-decoration:none;font-size:11px;display:inline-block;margin:2px}}.on{{background:#28a745}}.off{{background:#dc3545}}.copy{{background:#17a2b8;cursor:pointer}}.small-inp{{width:55px;padding:4px;text-align:center}}
    </style>
    <script>
    function copyId(id){{navigator.clipboard.writeText(id);alert('تم نسخ: '+id);}}
    function savePerm(id){{let c=document.querySelectorAll('.chk_'+id+':checked');let f=Array.from(c).map(x=>x.value).join(',');location.href='/admin?key={ADMIN_KEY}&action=set_perm&user_id='+id+'&files='+f}}
    </script></head><body><div class="c"><h2 style="text-align:center;">لوحة الادمن - كاملة</h2>{msg}
    <form method="get" style="background:#f8f9fa;padding:10px;border-radius:8px;margin-bottom:15px;display:flex;gap:5px;flex-wrap:wrap;align-items:center;">
    <input type="hidden" name="key" value="{ADMIN_KEY}">
    <input type="text" name="search" placeholder="بحث عن ID" value="{search if search else ''}" style="padding:6px;">
    <span>ايام:</span><input class="small-inp" type="number" name="days" value="1">
    <span>ساعات:</span><input class="small-inp" type="number" name="hours" value="0">
    <button name="action" value="add_all" style="background:#007bff;color:white;border:none;padding:7px 12px;border-radius:5px;">➕ اضافة للكل</button>
    <button name="action" value="sub_all" style="background:#dc3545;color:white;border:none;padding:7px 12px;border-radius:5px;">➖ تنقيص للكل</button>
    <button type="submit">بحث</button>
    </form>
    <p>رابط العام: <code>{request.host_url}</code> | عدد المستخدمين: {len(all_users)}</p>
    <table><tr><th>المستخدم + نسخ</th><th>الوقت</th><th>الملفات المسموحة</th><th>الصفحة</th><th>التحميل</th><th>تحكم (ايام/ساعات)</th></tr>"""

    for u in all_users:
        rem = format_hm(get_remaining_hours(u)); allowed = get_allowed_files(u)
        perm = "".join([f"<label style='margin:2px;'><input type='checkbox' class='chk_{u['user_id']}' value='{f}' {'checked' if f in allowed else ''}> {f.split('.')[0]}</label><br>" for f in FILES])
        perm += f"<button onclick=\"savePerm('{u['user_id']}')\" style='background:#6610f2;color:white;border:none;padding:4px 8px;border-radius:4px;margin-top:5px;width:100%;'>حفظ الصلاحيات</button>"
        page_btn = f"<a class='b {'on' if u.get('page_enabled',True) else 'off'}' href='/admin?key={ADMIN_KEY}&action=toggle_page&user_id={u['user_id']}'>{'مفعلة' if u.get('page_enabled',True) else 'موقوفة'}</a>"
        dl_btn = f"<a class='b {'on' if u.get('can_download',True) else 'off'}' href='/admin?key={ADMIN_KEY}&action=toggle_dl&user_id={u['user_id']}'>{'مسموح' if u.get('can_download',True) else 'ممنوع'}</a>"
        copy_btns = f"<div style='word-break:break-all;'><code style='font-size:10px;'>{u['user_id']}</code><br><button class='b copy' onclick=\"copyId('{u['user_id']}')\">📋 نسخ ID</button><br><a href='/user/{u['user_id']}' target='_blank' class='b' style='background:#6f42c1;'>صفحته ↗</a></div>"
        html += f"<tr><td>{copy_btns}</td><td dir='ltr'><b>{rem}</b><br><small>{u.get('expires_at','')}</small></td><td>{perm}</td><td>{page_btn}</td><td>{dl_btn}</td><td><a class='b' style='background:#6c757d' href='/admin?key={ADMIN_KEY}&action=reset&user_id={u['user_id']}'>تصفير 2س</a><br><a class='b off' href='/admin?key={ADMIN_KEY}&action=ban&user_id={u['user_id']}' onclick=\"return confirm('حذف؟')\">حذف</a><hr><form method='get' style='margin:0;'><input type='hidden' name='key' value='{ADMIN_KEY}'><input type='hidden' name='user_id' value='{u['user_id']}'><input class='small-inp' type='number' name='days' value='0' placeholder='يوم'><input class='small-inp' type='number' name='hours' value='24' placeholder='ساعة'><br><button class='b on' name='action' value='add'>+ اضافة</button><button class='b off' name='action' value='sub'>- تنقيص</button></form></td></tr>"
    html += "</table></div></body></html>"
    return html

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
