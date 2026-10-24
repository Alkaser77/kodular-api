import os, requests, hashlib, hmac, base58
from flask import Flask, jsonify, request, redirect, send_file
try:
    from flask_cors import CORS
except:
    CORS = lambda x: x
from supabase import create_client
from datetime import datetime, timedelta
import io
import threading
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from Crypto.Hash import keccak
from ecdsa import VerifyingKey, SECP256k1

app = Flask(__name__)
CORS(app)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
DRIVE_NPVT_ID = os.getenv("DRIVE_NPVT_ID")
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_URL = os.getenv("API_URL", "https://kodular-api-1.onrender.com")
ADMIN_KEY = "admin123"
XPUB_BNB = os.getenv("XPUB_BNB")
BSC_API_KEY = os.getenv("BSC_API_KEY")

USDT_BEP20_CONTRACT = "0x55d398326f99059fF775485246999027B3197955"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
FOLDER = "files"
FILES = ["File.npvt", "File.ssc", "File.nm", "File1.ssc"]

# --- نظام BNB ---
def ckd_pub(chain, pub, index):
    data = pub + index.to_bytes(4, 'big')
    I = hmac.new(chain, data, hashlib.sha512).digest()
    il_int = int.from_bytes(I[:32], 'big')
    vk = VerifyingKey.from_string(pub[1:], curve=SECP256k1)
    point = vk.pubkey.point + il_int * SECP256k1.generator
    x, y = point.x(), point.y()
    new_pub = (b'\x02' if y % 2 == 0 else b'\x03') + x.to_bytes(32, 'big')
    return I[32:], new_pub, point

def get_bnb_address(user_index):
    raw = base58.b58decode_check(XPUB_BNB)
    chain, pub = raw[13:45], raw[45:78]
    c0, p0, _ = ckd_pub(chain, pub, 0)
    _, _, pt = ckd_pub(c0, p0, user_index)
    k = keccak.new(digest_bits=256)
    k.update(b'\x04' + pt.x().to_bytes(32,'big') + pt.y().to_bytes(32,'big'))
    addr = k.digest()[-20:].hex()
    k2 = keccak.new(digest_bits=256); k2.update(addr.encode()); h = k2.hexdigest()
    return "0x" + "".join(c.upper() if int(h[i],16)>=8 else c for i,c in enumerate(addr))

def user_index_from_id(user_id):
    return int(hashlib.sha256(user_id.encode()).hexdigest()[:8], 16) % 1000000

def parse_expire(s):
    if not s: return datetime.now()
    try:
        cleaned = s.replace('T', ' ').split('.')[0]
        return datetime.strptime(cleaned, "%Y-%m-%d %H:%M:%S")
    except:
        try: return datetime.fromisoformat(s.replace('Z', ''))
        except: return datetime.now()

def format_hm(hours_float):
    if hours_float <= 0: return "0:00"
    days = int(hours_float // 24)
    h = int(hours_float % 24)
    m = int((hours_float - (days*24 + h)) * 60)
    if days > 0: return f"{days} days {h}:{m:02d}"
    else: return f"{h}:{m:02d}"

def get_allowed_files(user):
    if not user: return FILES
    af = user.get("allowed_files")
    if not af or not isinstance(af, list): return FILES
    return [f for f in FILES if f in af]

def get_remaining_hours(user):
    if not user or not user.get("expires_at"): return 0
    try:
        expires = parse_expire(user.get("expires_at"))
        diff = (expires - datetime.now()).total_seconds() / 3600
        return max(0, diff)
    except: return 0

def save_user(user):
    try: supabase.table("users").upsert(user).execute()
    except: pass

def get_user(user_id):
    try:
        res = supabase.table("users").select("*").eq("user_id", user_id).execute()
        if res.data: return res.data[0]
        return None
    except: return None

@app.route('/')
def index():
    return f"""<html><head><meta charset="UTF-8"><title>OK</title></head>
    <body style="font-family:Tahoma;text-align:center;padding:50px;">OK - NO ADS - BNB System Working V2</body></html>""", 200

@app.route('/pay/<user_id>')
def pay_page(user_id):
    idx=user_index_from_id(user_id)
    bnb_addr=get_bnb_address(idx)
    return f"""
    <html dir="rtl"><head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>دفع 1$ - {user_id}</title>
    <style>body{{font-family:Tahoma;background:#0f172a;color:#fff;padding:20px}}
    .card{{background:#1e293b;padding:25px;border-radius:15px;max-width:500px;margin:auto;text-align:center}}
    .addr{{background:#0f172a;padding:15px;border-radius:10px;word-break:break-all;border:2px solid #f0b90b;color:#f0b90b;font-weight:bold;margin:15px 0}}
    .btn{{background:#f0b90b;color:#000;padding:16px;border-radius:12px;width:100%;border:none;font-size:18px;font-weight:bold;cursor:pointer;margin-top:10px}}
    </style></head><body>
    <div class="card">
      <h1>💰 اشتراك مميز - 1$ فقط</h1>
      <p>30 يوم بدون قيود + كل الملفات</p>
      <p style="color:#94a3b8">شبكة: <b>BNB Smart Chain (BEP20)</b></p>
      <div class="addr">{bnb_addr}</div>
      <button class="btn" onclick="navigator.clipboard.writeText('{bnb_addr}');alert('تم نسخ العنوان')">📋 نسخ العنوان</button>
      <p style="margin:15px 0">المبلغ: <b style="font-size:26px;color:#f0b90b">1 USDT (BEP20)</b></p>
      <button class="btn" style="background:#22c55e;color:white" onclick="checkPay()">🔍 تحقق من الدفع</button>
      <p id="st"></p>
    </div>
    <script>
    function checkPay(){{
      document.getElementById('st').innerHTML='⏳ نتحقق...';
      fetch('/verify/{user_id}').then(r=>r.json()).then(d=>{{
        if(d.paid){{ document.getElementById('st').innerHTML='✅ تم! 30 يوم تفعلو'; }}
        else{{ document.getElementById('st').innerHTML='❌ لم يصل بعد - حول 1 USDT BEP20'; }}
      }});
    }}
    </script></body></html>
    """

@app.route('/verify/<user_id>')
def verify(user_id):
    idx=user_index_from_id(user_id)
    bnb_addr=get_bnb_address(idx)
    try:
        url=f"https://api.etherscan.io/v2/api?chainid=56&module=account&action=tokentx&contractaddress={USDT_BEP20_CONTRACT}&address={bnb_addr}&page=1&offset=5&sort=desc&apikey={BSC_API_KEY}"
        r=requests.get(url,timeout=15).json()
        for tx in r.get('result',[]):
            try:
                if isinstance(tx,str): continue
                val=int(tx.get('value',0))/10**18
                if val>=0.9:
                    u=get_user(user_id) or {{"user_id":user_id}}
                    u["expires_at"]=(datetime.now()+timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
                    u["status"]="active"; u["plan"]="paid"
                    u["allowed_files"]=FILES
                    u["page_enabled"]=True; u["can_download"]=True
                    save_user(u)
                    return jsonify({{"paid":True,"tx":tx.get('hash'),"amount":val}})
            except: continue
    except Exception as e:
        return jsonify({{"paid":False,"error":str(e)}})
    return jsonify({{"paid":False,"bnb_addr":bnb_addr}})

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
            return jsonify({"status": "cooldown", "hours": format_hm(remaining_cooldown), "hours_float": round(remaining_cooldown, 2), "links": [], "files": []})
    return jsonify({"status": "active", "links": links, "files": allowed, "hours": format_hm(remaining), "hours_float": round(remaining, 2)})

@app.route('/user/<user_id>')
def user_page(user_id):
    user = get_user(user_id)
    if not user:
        return f"<html><head><meta charset='UTF-8'></head><body><h2>المستخدم غير موجود</h2></body></html>", 404
    if not user.get("page_enabled", True):
        return f"<html><head><meta charset='UTF-8'></head><body><h2 style='color:red;text-align:center;margin-top:100px;'>⛔ صفحتك موقوفة</h2></body></html>", 403
    rem = get_remaining_hours(user)
    is_expired = rem <= 0
    wait_str = ""
    if is_expired:
        try:
            exp_date = parse_expire(user.get("expires_at"))
            hours_since = (datetime.now() - exp_date).total_seconds() / 3600
            wait = max(0, 24 - hours_since)
            wait_str = format_hm(wait)
        except: wait_str = "24:00"
    allowed = get_allowed_files(user)
    can_dl = False if is_expired else user.get("can_download", True)
    if is_expired:
        banner = f"<div style='background:#dc3545;color:white;padding:15px;border-radius:10px;margin-bottom:20px;text-align:center;'><h3>⏳ انتهى اشتراكك</h3><p>عليك الانتظار: <b>{wait_str}</b></p><a href='/pay/{user_id}' style='background:#f0b90b;color:#000;padding:10px 20px;border-radius:8px;text-decoration:none;display:inline-block;margin-top:10px;'>💰 تجديد 1$ - 30 يوم</a></div>"
    else:
        banner = f"<div style='background:linear-gradient(135deg,#007bff,#6610f2);color:white;padding:20px;border-radius:15px;text-align:center;margin-bottom:20px;'><h2>صفحتك الخاصة</h2><small><code>{user_id}</code></small><p>متبقي: {format_hm(rem)}</p><a href='/pay/{user_id}' style='background:#f0b90b;color:#000;padding:8px 15px;border-radius:8px;text-decoration:none;display:inline-block;margin-top:10px;'>💰 ترقية 30 يوم</a></div>"
    cards = ""
    for f in allowed:
        go_link = f"{request.host_url}go/{f}?user_id={user_id}"
        if can_dl:
            btn = f"<a href='{go_link}' style='background:#28a745;color:white;padding:12px;border-radius:8px;text-decoration:none;display:block;font-weight:bold;'>⬇️ تحميل {f}</a>"
        else:
            btn = f"<span style='background:#ccc;color:#666;padding:12px;border-radius:8px;display:block;'>🔒 معطل</span>"
        cards += f"<div style='background:white;border:1px solid #eee;border-radius:12px;padding:15px;text-align:center;'><div style='font-size:30px;'>📦</div><h4>{f}</h4>{btn}</div>"
    return f"""<html dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>صفحتي</title></head>
    <body style="font-family:Tahoma;background:#f4f4f4;padding:15px;margin:0;"><div style="max-width:800px;margin:auto;">{banner}<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:15px;">{cards}</div></div></body></html>"""

@app.route('/go/<filename>')
def go_file(filename):
    user_id = request.args.get('user_id')
    if filename not in FILES: return "File not allowed", 403
    user = get_user(user_id)
    if not user or get_remaining_hours(user) <= 0: return "Subscription ended", 403
    direct = f"{request.host_url}download/{filename}?user_id={user_id}"
    return f"""
    <html dir="rtl"><head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>تحميل {filename}</title>
    <style>body{{font-family:Tahoma;background:#f4f4f4;color:#333;text-align:center;padding:20px}} .box{{background:white;padding:30px;border-radius:15px;max-width:500px;margin:20px auto}} .timer{{font-size:60px;color:#007bff;margin:15px}} .btn{{background:#28a745;color:white;padding:15px 30px;border-radius:10px;display:none;font-size:20px;text-decoration:none}}</style>
    </head><body><div class="box"><h2>📦 {filename}</h2><p>جاري تجهيز الرابط</p><div class="timer" id="tm">3</div><a id="dl" class="btn" href="{direct}">⬇️ تحميل الآن</a></div>
    <script>let c=3;function t(){{document.getElementById('tm').innerHTML=c;if(c<=0){{document.getElementById('dl').style.display='inline-block';document.getElementById('tm').style.display='none';}} else{{c--; setTimeout(t,1000);}}}}window.onload=t;</script></body></html>
    """

@app.route('/download/<filename>', methods=['GET'])
def download(filename):
    if filename not in FILES: return "File not allowed", 403
    user_id = request.args.get('user_id')
    user = get_user(user_id)
    if not user: return "User not found", 403
    if filename not in get_allowed_files(user): return "Not allowed for you", 403
    if not user.get("can_download", True): return "Download disabled by admin", 403
    if get_remaining_hours(user) <= 0: return "Subscription ended", 403
    try:
        if filename == "File.npvt":
            gdrive_url = f"https://drive.google.com/uc?export=download&id={DRIVE_NPVT_ID}"
            r = requests.get(gdrive_url, stream=True, timeout=60)
            return send_file(io.BytesIO(r.content), as_attachment=True, download_name=filename)
        else:
            path = os.path.join(FOLDER, filename)
            if not os.path.exists(path): return f"File {filename} not found", 404
            return send_file(path, as_attachment=True)
    except Exception as e:
        return f"Download error: {e}", 500

@app.route('/admin', methods=['GET'])
def admin_panel():
    key = request.args.get('key')
    if key!= ADMIN_KEY: return "<h3>key=admin123</h3>", 401
    now = datetime.now()
    msg = "<h3 style='color:green;text-align:center;'>✅ تم</h3>" if request.args.get('msg') == 'done' else ""
    action = request.args.get('action')
    uid = request.args.get('user_id')
    if action == 'set_perm' and uid:
        files = [f for f in request.args.get('files', '').split(',') if f in FILES]
        u = get_user(uid)
        if u: u["allowed_files"] = files; save_user(u)
        return redirect(f"/admin?key={ADMIN_KEY}&msg=done")
    if action == 'toggle_page' and uid:
        u = get_user(uid)
        if u: u["page_enabled"] = not u.get("page_enabled", True); save_user(u)
        return redirect(f"/admin?key={ADMIN_KEY}&msg=done")
    if action == 'toggle_dl' and uid:
        u = get_user(uid)
        if u: u["can_download"] = not u.get("can_download", True); save_user(u)
        return redirect(f"/admin?key={ADMIN_KEY}&msg=done")
    if action == 'ban' and uid:
        supabase.table("users").delete().eq("user_id", uid).execute()
        return redirect(f"/admin?key={ADMIN_KEY}&msg=done")
    if action == 'reset' and uid:
        u = get_user(uid)
        if u: u["expires_at"] = (now + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S"); u["status"] = "active"; save_user(u)
        return redirect(f"/admin?key={ADMIN_KEY}&msg=done")
    if action in ['add', 'sub', 'add_all', 'sub_all']:
        try:
            days = float(request.args.get('days', 0) or 0)
            hours = float(request.args.get('hours', 0) or 0)
            total = days * 24 + hours
        except: total = 0
        if action in ['add', 'sub']: users_list = [get_user(uid)] if uid else []
        else: users_list = supabase.table("users").select("*").execute().data
        for u in users_list:
            if not u: continue
            cur = parse_expire(u.get("expires_at"))
            if 'add' in action:
                base = cur if cur > now else now
                new = base + timedelta(hours=total)
            else:
                new = cur - timedelta(hours=total)
                if new < now: new = now - timedelta(minutes=1)
            u["expires_at"] = new.strftime("%Y-%m-%d %H:%M:%S")
            u["status"] = "active" if new > now else "expired"
            save_user(u)
        return redirect(f"/admin?key={ADMIN_KEY}&msg=done")
    query = supabase.table("users").select("*").order("expires_at", desc=True)
    search = request.args.get('search')
    if search: query = query.ilike("user_id", f"%{search}%")
    all_users = query.execute().data
    html = f"""<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8"><title>الادمن</title>
    <style>body{{font-family:Tahoma;background:#f4f4f4;padding:10px;font-size:13px}}.c{{max-width:1300px;margin:auto;background:white;padding:15px;border-radius:10px}} table{{width:100%;border-collapse:collapse}} th{{background:#007bff;color:white;padding:8px}} td{{padding:8px;border-bottom:1px solid #ddd;text-align:center}}.b{{padding:5px 9px;border-radius:5px;color:white;text-decoration:none;font-size:11px;display:inline-block;margin:2px}}.on{{background:#28a745}}.off{{background:#dc3545}}.copy{{background:#17a2b8}}.small-inp{{width:55px;padding:4px;text-align:center}}</style>
    <script>function copyId(id){{navigator.clipboard.writeText(id);alert('تم نسخ: '+id);}}function savePerm(id){{let c=document.querySelectorAll('.chk_'+id+':checked');let f=Array.from(c).map(x=>x.value).join(',');location.href='/admin?key={ADMIN_KEY}&action=set_perm&user_id='+id+'&files='+f}}</script></head><body><div class="c"><h2 style="text-align:center;">لوحة الادمن - بدون اعلانات ✅ BNB V2</h2>{msg}
    <form method="get" style="background:#f8f9fa;padding:10px;border-radius:8px;margin-bottom:15px;display:flex;gap:5px;flex-wrap:wrap;"><input type="hidden" name="key" value="{ADMIN_KEY}">
    <input type="text" name="search" placeholder="بحث" value="{search if search else ''}"><span>ايام:</span><input class="small-inp" type="number" name="days" value="1"><span>ساعات:</span><input class="small-inp" type="number" name="hours" value="0">
    <button name="action" value="add_all" style="background:#007bff;color:white;border:none;padding:7px 12px;border-radius:5px;">➕ للكل</button><button name="action" value="sub_all" style="background:#dc3545;color:white;border:none;padding:7px 12px;border-radius:5px;">➖ للكل</button><button type="submit">بحث</button></form>
    <table><tr><th>المستخدم</th><th>الوقت</th><th>الملفات</th><th>الصفحة</th><th>التحميل</th><th>تحكم</th></tr>"""
    for u in all_users:
        rem = format_hm(get_remaining_hours(u))
        allowed = get_allowed_files(u)
        perm = "".join([f"<label><input type='checkbox' class='chk_{u['user_id']}' value='{f}' {'checked' if f in allowed else ''}> {f.split('.')[0]}</label><br>" for f in FILES])
        perm += f"<button onclick=\"savePerm('{u['user_id']}')\" style='background:#6610f2;color:white;border:none;padding:4px 8px;border-radius:4px;margin-top:5px;width:100%;'>حفظ</button>"
        page_btn = f"<a class='b {'on' if u.get('page_enabled',True) else 'off'}' href='/admin?key={ADMIN_KEY}&action=toggle_page&user_id={u['user_id']}'>{'مفعلة' if u.get('page_enabled',True) else 'موقوفة'}</a>"
        dl_btn = f"<a class='b {'on' if u.get('can_download',True) else 'off'}' href='/admin?key={ADMIN_KEY}&action=toggle_dl&user_id={u['user_id']}'>{'مسموح' if u.get('can_download',True) else 'ممنوع'}</a>"
        copy_btns = f"<div><code style='font-size:10px;'>{u['user_id']}</code><br><button class='b copy' onclick=\"copyId('{u['user_id']}')\">📋 نسخ</button><br><a href='/user/{u['user_id']}' target='_blank' class='b' style='background:#6f42c1;'>صفحته</a></div>"
        html += f"<tr><td>{copy_btns}</td><td dir='ltr'><b>{rem}</b><br><small>{u.get('expires_at','')}</small></td><td>{perm}</td><td>{page_btn}</td><td>{dl_btn}</td><td><a class='b' style='background:#6c757d' href='/admin?key={ADMIN_KEY}&action=reset&user_id={u['user_id']}'>تصفير</a><br><a class='b off' href='/admin?key={ADMIN_KEY}&action=ban&user_id={u['user_id']}'>حذف</a><hr><form method='get'><input type='hidden' name='key' value='{ADMIN_KEY}'><input type='hidden' name='user_id' value='{u['user_id']}'><input class='small-inp' type='number' name='days' value='0'><input class='small-inp' type='number' name='hours' value='24'><br><button class='b on' name='action' value='add'>+ اضافة</button><button class='b off' name='action' value='sub'>- تنقيص</button></form></td></tr>"
    html += "</table></div></body></html>"
    return html

def run_bot():
    while True:
        try:
            if not BOT_TOKEN: return
            bot = telebot.TeleBot(BOT_TOKEN)
            bot.delete_webhook(drop_pending_updates=True)
            @bot.message_handler(commands=['start'])
            def handle_start(message):
                tg_id = str(message.from_user.id)
                user_id = f"TG-{tg_id}"
                user = get_user(user_id)
                if not user:
                    expires = datetime.now() + timedelta(hours=2)
                    user = {"user_id": user_id, "expires_at": expires.strftime("%Y-%m-%d %H:%M:%S"), "status": "active", "allowed_files": FILES, "page_enabled": True, "can_download": True}
                    save_user(user)
                    rem = 2.0
                else:
                    rem = get_remaining_hours(user)
                    if rem <= 0:
                        exp_date = parse_expire(user.get("expires_at"))
                        hours_since = (datetime.now() - exp_date).total_seconds() / 3600
                        if hours_since >= 24:
                            new_exp = datetime.now() + timedelta(hours=2)
                            user["expires_at"] = new_exp.strftime("%Y-%m-%d %H:%M:%S")
                            user["status"] = "active"
                            save_user(user)
                            rem = 2.0
                page_link = f"{API_URL}/user/{user_id}"
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("🌐 فتح صفحتي الخاصة", url=page_link))
                bot.send_message(message.chat.id, f"مرحبا {message.from_user.first_name} 👋\nID: <code>{user_id}</code>\nمتبقي: <b>{format_hm(rem)}</b>", parse_mode='HTML', reply_markup=markup)
            bot.infinity_polling(skip_pending=True, timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"Bot crashed: {e}")
            threading.Event().wait(10)

if BOT_TOKEN:
    threading.Thread(target=run_bot, daemon=True).start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 10000)))
