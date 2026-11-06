# app.py - كامل - يقرأ من Render Env
# تشغيل: python3 app.py
from flask import Flask, request, jsonify, Response, redirect, make_response
from datetime import datetime, timedelta
from supabase import create_client, Client
import os, requests, random, string, io, hashlib

app = Flask(__name__)

# ======== Render Env - ما تكتب شي هنا ========
ENCRYPT_KEY = os.environ.get("ENCRYPT_KEY", "").encode()
SECRET = os.environ.get("SECRET", "")
VPS_TOKEN = os.environ.get("VPS_TOKEN", "")
VPS_HOST = os.environ.get("VPS_HOST", "")
AGENT_URL = f"http://{VPS_HOST}:5001/api/agent"
VPS_URL = AGENT_URL

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

ADMIN_KEY = os.environ.get("ADMIN_KEY", "123456")
ALLOWED_KEYS = [ADMIN_KEY]
ROOT_WALLET = os.getenv("ROOT_WALLET", "0x2d447f9d656594f6c65de039aebe7da32a968400")
USDT = "0x55d398326f99059fF775485246999027B3196775"
RPC = "https://bsc-dataseed.binance.org/"
TOPIC = "[STRIPPED 66 bytes]"
FILES = ["File.npvt", "File.ssc", "File.nm", "File.hc", "File.ehi", "File.npvs", "File.v2box"]
MADAR_PRICE = 10
# =============================================

def make_ref(user_id, expire):
    raw = f"{user_id}|{expire}|{SECRET}"
    return hashlib.sha256(raw.encode()).hexdigest()[:20]

def agent_post(endpoint, payload):
    try:
        r = requests.post(f"{AGENT_URL}/{endpoint}", json=payload, headers={"Content-Type": "application/json", "X-Agent-Token": VPS_TOKEN}, timeout=20)
        try: return r.status_code, r.json()
        except: return r.status_code, {"error": "invalid json", "raw": r.text}
    except Exception as e:
        return 500, {"error": "agent unreachable", "detail": str(e)}

def time_left(expire_str):
    try:
        exp = datetime.fromisoformat(expire_str)
        diff = exp - datetime.now()
        if diff.total_seconds() <= 0: return "0:00:00"
        h = int(diff.total_seconds() // 3600)
        m = int((diff.total_seconds() % 3600) // 60)
        s = int(diff.total_seconds() % 60)
        return f"{h}:{m:02d}:{s:02d}"
    except: return "0:00:00"

def random_id(n=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=n))

# ======== دوال VPS Agent ========
def agent_create_bundle(user_id, plan):
    try:
        r = requests.post(f"{VPS_URL}/api/agent/create_bundle", headers={"X-Agent-Token": VPS_TOKEN}, json={"user_id": user_id, "plan": plan}, timeout=20)
        if r.status_code == 200: return True, r.json()
        return False, r.text
    except Exception as e: return False, str(e)

def agent_delete_bundle(user_id):
    try:
        r = requests.post(f"{VPS_URL}/api/agent/delete_bundle", headers={"X-Agent-Token": VPS_TOKEN}, json={"user_id": user_id}, timeout=15)
        return r.status_code == 200
    except: return False

def agent_get_blob(user_id):
    try:
        r = requests.post(f"{VPS_URL}/api/agent/get_blob", headers={"X-Agent-Token": VPS_TOKEN}, json={"user_id": user_id}, timeout=15)
        if r.status_code == 200: return r.json().get('blob')
        return None
    except: return None

def agent_status(user_id):
    try:
        r = requests.post(f"{VPS_URL}/api/agent/status", headers={"X-Agent-Token": VPS_TOKEN}, json={"user_id": user_id}, timeout=10)
        if r.status_code == 200: return r.json()
        return None
    except: return None

def agent_connect(blob, ip):
    try:
        r = requests.post(f"{VPS_URL}/api/agent/connect", headers={"X-Agent-Token": VPS_TOKEN}, json={"blob": blob}, timeout=10)
        return r.json(), r.status_code
    except Exception as e: return {"error": str(e)}, 500

# ======== دوال Supabase ========
def get_user(user_id):
    try:
        res = supabase.table("users").select("*").eq("user_id", user_id).execute()
        if res.data: return res.data[0]
    except Exception as e: print("get_user err", e)
    return None

def save_user(user):
    try: supabase.table("users").upsert(user).execute()
    except Exception as e: print("save_user err", e)

def parse_expire(exp_str):
    if not exp_str: return None
    try:
        if "T" in str(exp_str): return datetime.fromisoformat(str(exp_str).replace("Z",""))
        return datetime.strptime(str(exp_str), "%Y-%m-%d %H:%M:%S")
    except: return None

def get_remaining_hours(user):
    if not user or not user.get("expires_at"): return 0
    exp = parse_expire(user["expires_at"])
    if not exp: return 0
    return max(0, (exp - datetime.now()).total_seconds()/3600)

def get_remaining_seconds(user): return int(get_remaining_hours(user)*3600)

def format_hm(hours_float):
    if hours_float <= 0: return "0:00:00"
    total_s = int(hours_float*3600)
    d = total_s//86400; h = (total_s%86400)//3600; m = (total_s%3600)//60; s = total_s%60
    if d>0: return f"{d} يوم {h}:{m:02d}:{s:02d}"
    return f"{h}:{m:02d}:{s:02d}"

def get_active_subscription(user_id):
    try:
        res = supabase.table("subscriptions").select("*").eq("user_id", user_id).eq("is_paid", True).order("expire_at", desc=True).limit(1).execute()
        if res.data:
            sub = res.data[0]
            exp = parse_expire(sub.get("expire_at"))
            if exp and exp > datetime.now(): return sub
    except Exception as e: print("get_active_sub err", e)
    return None

def restore_paid_user(user_id):
    sub = get_active_subscription(user_id)
    if not sub: return None
    user = get_user(user_id) or {"user_id": user_id}
    user["expires_at"] = sub.get("expire_at")
    user["status"] = "active"
    save_user(user)
    return user

def get_paid_users_list():
    try:
        subs = supabase.table("subscriptions").select("*").eq("is_paid", True).order("expire_at", desc=True).execute().data or []
        return subs
    except: return []

def amount_for(uid):
    h = abs(hash(str(uid))) % 900 + 100
    return round(1 + h / 1000, 3)

def check_payment(uid):
    amt = amount_for(uid); target = int(amt * 10**18)
    try:
        payload = {"jsonrpc":"2.0","id":1,"method":"eth_getLogs","params":[{"fromBlock": hex(0),"toBlock":"latest","address":USDT,"topics":[TOPIC, None, "0x000000000000000000000000"+ROOT_WALLET[2:].lower()]}]}
        r = requests.post(RPC, json=payload, timeout=20).json()
        logs = r.get("result", []) if isinstance(r, dict) else []
        for log in logs[-200:]:
            try:
                val = int(log.get("data","0x0"), 16)
                if val == target:
                    tx = log.get("transactionHash","")
                    used = supabase.table("subscriptions").select("tx_hash").execute().data
                    if any(x.get("tx_hash")==tx for x in used): continue
                    return True, tx, amt
            except: continue
    except Exception as e: print("check_payment err", e)
    return False, None, amt

def madar_activate(user_id):
    exp = datetime.now() + timedelta(days=30)
    user = get_user(user_id) or {"user_id": user_id}
    user["expires_at"] = exp.strftime("%Y-%m-%d %H:%M:%S")
    user["status"] = "active"
    save_user(user)
    try: supabase.table("subscriptions").upsert({"user_id": user_id, "expire_at": exp.isoformat(), "is_paid": True, "tx_hash": f"madar_{user_id}_{int(datetime.now().timestamp())}", "amount": MADAR_PRICE}).execute()
    except Exception as e: print("madar sub err", e)
    agent_create_bundle(user_id, "paid")
    return exp

@app.errorhandler(Exception)
def _handle_all_errors(e):
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        if request.path.startswith('/admin') or request.path.startswith('/api'):
            return jsonify({'error': str(e)}), e.code
        return e
    print('SERVER ERROR:', e)
    if request.path.startswith('/admin') or request.path.startswith('/api') or request.path.startswith('/check'):
        return jsonify({'error': str(e), 'message': 'خطأ في السيرفر: '+str(e)}), 500
    raise e
    # ======== HTML ========
HOME_HTML = """<!DOCTYPE html><html dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>PREMIUM GATE</title><script src="https://cdn.tailwindcss.com"></script></head><body class="bg-[#0a0a14] text-white min-h-screen"><div class="max-w-3xl mx-auto px-4 pt-16 text-center"><h1 class="text-4xl font-black">PREMIUM <span class="text-violet-400">GATE</span></h1><p class="text-gray-400 mt-3">احصل على 2 ساعات مجانية - كل الملفات في مكان واحد</p><a href="/go" class="inline-block mt-8 bg-white text-black px-10 py-4 rounded-2xl font-black">ابدأ الآن - مجانا 2 ساعات</a><p class="text-xs text-gray-500 mt-4">زر واحد - بدون تسجيل</p></div></body></html>"""

PAY_HTML = """<!DOCTYPE html><html dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>الدفع</title><script src="https://cdn.tailwindcss.com"></script></head><body class="bg-[#0a0a14] text-white min-h-screen"><div class="max-w-md mx-auto px-4 pt-10"><h1 class="text-2xl font-black">تجديد 30 يوم</h1><p class="text-gray-400 text-sm mt-2">ارسل المبلغ بالضبط للمحفظة التالية USDT - BSC</p><div class="bg-white/5 border border-white/10 rounded-2xl p-4 mt-4 break-all text-sm" dir="ltr">__WALLET__</div><p class="text-sm mt-3">المبلغ: <span id="amt">...</span> USDT</p><a id="vbtn" href="#" class="block text-center mt-4 bg-emerald-500 text-black py-3 rounded-xl font-black">تحقق من الدفع</a><a href="/pay-madar/__UID__" class="block text-center mt-3 bg-white/10 py-3 rounded-xl font-bold">الدفع عبر مدار 📱</a></div><script>const UID="__UID__";fetch('/amount/'+UID).then(r=>r.json()).then(d=>{document.getElementById('amt').innerText=d.amount});document.getElementById('vbtn').onclick=async(e)=>{e.preventDefault();let r=await fetch('/verify/'+UID).then(r=>r.json());alert(r.message||JSON.stringify(r));if(r.ok) location.href='/view/'+UID;};</script></body></html>"""

MADAR_HTML = """<!DOCTYPE html><html dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>مدار</title><script src="https://cdn.tailwindcss.com"></script></head><body class="bg-[#0a0a14] text-white min-h-screen"><div class="max-w-md mx-auto px-4 pt-10"><h1 class="text-2xl font-black">الدفع عبر مدار</h1><p class="text-gray-400 text-sm mt-2">ادخل كود الكارت - 10 دينار = 30 يوم</p><input id="card" placeholder="كود الكارت" class="w-full mt-4 bg-white/10 border border-white/10 rounded-xl px-4 py-3 text-white"><button onclick="send()" class="w-full mt-3 bg-violet-500 py-3 rounded-xl font-black">ارسال للمراجعة</button><p id="msg" class="text-sm mt-3"></p></div><script>const UID="__UID__";async function send(){let c=document.getElementById('card').value;let r=await fetch('/api/madar/charge-card',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:UID,card_code:c})}).then(r=>r.json());document.getElementById('msg').innerText=r.message||r.error||JSON.stringify(r);}</script></body></html>"""

CONTENT_HTML = """<!DOCTYPE html><html dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>مكتبتك</title><script src="https://cdn.tailwindcss.com"></script></head><body class="bg-[#0a0a14] text-white min-h-screen"><div class="max-w-6xl mx-auto px-4 pt-4"><a href="/" class="font-black">PREMIUM <span class="text-violet-400">GATE</span></a><div class="bg-white/5 border border-white/10 rounded-[28px] p-6 mt-6"><h1 class="text-2xl font-black">مكتبتك الخاصة</h1><div class="flex items-center gap-3 mt-4"><span class="bg-emerald-500/15 text-emerald-300 px-3 py-1 rounded-full text-xs font-bold">● نشط</span><span id="time" class="font-black text-xl">...</span></div><div class="h-2 bg-white/10 rounded-full overflow-hidden mt-3"><div id="timeBar" class="h-full bg-gradient-to-l from-violet-500 to-emerald-500" style="width:0%"></div></div><p id="usedPercent" class="text-xs text-gray-400 mt-2">0%</p><div class="flex gap-2 mt-4"><a href="/pay/__UID__" class="flex-1 bg-emerald-500 text-black text-center py-3 rounded-xl font-black text-sm">💳 تجديد</a><a href="/pay-madar/__UID__" class="flex-1 bg-white/10 text-center py-3 rounded-xl font-bold text-sm">📱 مدار</a></div></div><div id="list" class="grid sm:grid-cols-2 lg:grid-cols-3 gap-4 mt-5"></div><div id="expiredBox" class="hidden text-center mt-5"><p class="font-black">انتهى وقتك</p><a href="/pay/__UID__" class="inline-block mt-3 bg-emerald-500 text-black px-8 py-3 rounded-2xl font-black">ادفع للتجديد</a></div></div><script>const UID="__UID__";let remainingSec=0,totalSecondsAtLoad=0,allFiles=[];function fileMeta(n){let e=n.split('.').pop().toLowerCase();let m={'ehi':{icon:'🚀',app:'HTTP Injector'},'hc':{icon:'HC',app:'HTTP Custom'},'ssc':{icon:'SSC',app:'SSH Custom'},'nm':{icon:'M',app:'NetMod'},'npvt':{icon:'nV',app:'Npv Tunnel'},'npvs':{icon:'nV',app:'Npv Tunnel'},'v2box':{icon:'V2',app:'V2Box'}};return m[e]||{icon:'📄',app:n};}function fmt(s){if(s<=0)return"0:00:00";let d=Math.floor(s/86400),h=Math.floor((s%86400)/3600),m=Math.floor((s%3600)/60),ss=s%60;if(d>0)return d+" يوم "+h+":"+String(m).padStart(2,'0')+":"+String(ss).padStart(2,'0');return h+":"+String(m).padStart(2,'0')+":"+String(ss).padStart(2,'0');}function tick(){let el=document.getElementById('time');if(remainingSec<=0){el.innerText="0:00:00";return;}el.innerText=fmt(remainingSec);let pct=totalSecondsAtLoad>0?Math.min(100,Math.round(((totalSecondsAtLoad-remainingSec)/totalSecondsAtLoad)*100)):0;document.getElementById('usedPercent').innerText=pct+"% مستهلك";document.getElementById('timeBar').style.width=pct+"%";remainingSec--;setTimeout(tick,1000);}function render(){let h="";allFiles.forEach((f)=>{let m=fileMeta(f);h+='<div class="bg-white/5 border border-white/10 rounded-3xl p-5"><div class="w-12 h-12 bg-white/10 rounded-2xl flex items-center justify-center font-black">'+m.icon+'</div><h3 class="font-black mt-3" dir="ltr" style="text-align:left">'+f+'</h3><p class="text-xs text-gray-400">'+m.app+'</p><a href="/download/'+f+'?user_id='+UID+'" class="mt-4 flex justify-center w-full bg-white text-black py-3 rounded-xl font-black text-sm">⬇ تحميل الآن</a></div>';});document.getElementById('list').innerHTML=h;}async function load(){let c=await fetch('/check?user_id='+UID).then(r=>r.json());if(c.status!=='active'){document.getElementById('expiredBox').classList.remove('hidden');document.getElementById('list').innerHTML='';return;}let p=(c.hours||"0:00:00").split(':');if(p.length===3)remainingSec=parseInt(p[0])*3600+parseInt(p[1])*60+parseInt(p[2]);if((c.hours||'').includes('يوم')){let d=parseInt((c.hours||'').split(' يوم')[0])||0;remainingSec=d*86400+remainingSec;}totalSecondsAtLoad=remainingSec;allFiles=c.files||[];render();tick();}load();</script></body></html>"""

ADMIN_HTML = """<!DOCTYPE html><html dir="rtl"><head><meta charset="utf-8"><title>Admin</title><script src="https://cdn.tailwindcss.com"></script></head><body class="bg-black text-white p-6"><h1 class="font-black text-2xl">لوحة الأدمن</h1><div class="flex gap-2 mt-4 flex-wrap"><button onclick="loadUsers()" class="bg-white text-black px-4 py-2 rounded-xl font-bold">المستخدمين</button><button onclick="loadPaid()" class="bg-emerald-500 text-black px-4 py-2 rounded-xl font-bold">المدفوعين</button><button onclick="loadMadar()" class="bg-violet-500 px-4 py-2 rounded-xl font-bold">مدار معلق</button></div><div id="box" class="mt-5"></div><script>async function loadUsers(){let k=new URLSearchParams(location.search).get('key');let r=await fetch('/admin/users?key='+k).then(r=>r.json());document.getElementById('box').innerHTML='<pre class="text-xs overflow-auto">'+JSON.stringify(r,null,2)+'</pre>';}async function loadPaid(){let k=new URLSearchParams(location.search).get('key');let r=await fetch('/admin/paid?key='+k).then(r=>r.json());document.getElementById('box').innerHTML='<pre class="text-xs overflow-auto">'+JSON.stringify(r,null,2)+'</pre>';}async function loadMadar(){let k=new URLSearchParams(location.search).get('key');let r=await fetch('/admin/madar-pending?key='+k).then(r=>r.json());document.getElementById('box').innerHTML='<pre class="text-xs overflow-auto">'+JSON.stringify(r,null,2)+'</pre>';}</script></body></html>"""

def render_view(user_id, remaining_sec, rem_initial, status):
    return CONTENT_HTML.replace("__UID__", user_id)

# ======== ROUTES - الرئيسية ========
@app.route('/')
def home(): return Response(HOME_HTML, mimetype='text/html')

@app.route('/go')
def go():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    fp = request.args.get('fp', '') or request.headers.get('User-Agent','')[:80]
    try:
        res = supabase.table("device_limits").select("*").eq("fingerprint", fp).execute()
        if res.data:
            uid = res.data[0].get("user_id")
            return redirect(f"/view/{uid}")
    except: pass
    uid = f"user_{random.randint(1000,9999)}{random.randint(1000,9999)}"
    exp = datetime.now() + timedelta(hours=2)
    user = {"user_id": uid, "expires_at": exp.strftime("%Y-%m-%d %H:%M:%S"), "status": "active"}
    save_user(user)
    try:
        supabase.table("device_limits").upsert({"fingerprint": fp, "user_id": uid, "ip_address": ip, "created_at": datetime.now().isoformat()}).execute()
    except:
        try: supabase.table("device_limits").insert({"fingerprint": fp, "user_id": uid, "ip_address": ip}).execute()
        except Exception as e: print("device insert err", e)
    ok, res = agent_create_bundle(uid, "free")
    if not ok: print(f"تحذير: VPS ما ردش لـ {uid} - {res}")
    return redirect(f"/view/{uid}")

@app.route('/clear')
def clear():
    return make_response("<script>localStorage.clear(); alert('تم المسح'); location.href='/';</script>")

@app.route('/view/<user_id>')
def view_user(user_id):
    u = get_user(user_id)
    if not u:
        restored = restore_paid_user(user_id)
        if restored: u = restored
        else: return redirect(f"/pay/{user_id}")
    rem = get_remaining_seconds(u)
    return Response(render_view(user_id, rem, rem, u.get("status","active")), mimetype='text/html')

@app.route('/pay/<user_id>')
def pay_page(user_id): return Response(PAY_HTML.replace("__WALLET__", ROOT_WALLET).replace("__UID__", user_id), mimetype='text/html')

@app.route('/content/<user_id>')
def content_page(user_id): return Response(CONTENT_HTML.replace("__UID__", user_id), mimetype='text/html')

@app.route('/pay-madar/<user_id>')
def pay_madar_page(user_id): return Response(MADAR_HTML.replace("__UID__", user_id), mimetype='text/html')

@app.route('/amount/<user_id>')
def amount_api(user_id): return jsonify({"amount": amount_for(user_id), "wallet": ROOT_WALLET})

@app.route('/api/support/send', methods=['POST'])
def support_send():
    data = request.get_json(silent=True) or {}
    try:
        supabase.table("support_messages").insert({"user_id": data.get("user_id","guest"), "message": data.get("message",""), "created_at": datetime.now().isoformat()}).execute()
        return jsonify({"ok": True})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/support/get')
def support_get():
    uid = request.args.get("user_id","guest")
    try:
        res = supabase.table("support_messages").select("*").eq("user_id", uid).order("created_at", desc=False).execute()
        return jsonify(res.data or [])
    except Exception as e: return jsonify({"error": str(e)}), 500
        # ======== ROUTES - الدفع والتحقق ========
@app.route('/verify/<user_id>')
def verify(user_id):
    ok, tx, amt = check_payment(user_id)
    if not ok:
        return jsonify({"ok": False, "message": "لا يوجد دفع مؤكد بعد. تأكد أنك أرسلت المبلغ بالضبط وانتظر دقيقة."})
    exp = datetime.now() + timedelta(days=30)
    user = get_user(user_id) or {"user_id": user_id}
    user["expires_at"] = exp.strftime("%Y-%m-%d %H:%M:%S")
    user["status"] = "active"
    save_user(user)
    try:
        supabase.table("subscriptions").upsert({"user_id": user_id, "expire_at": exp.isoformat(), "is_paid": True, "tx_hash": tx, "amount": amt}).execute()
    except Exception as e: print("sub save err", e)
    agent_create_bundle(user_id, "paid")
    return jsonify({"ok": True, "message": "تم التفعيل! 30 يوم", "tx": tx})

@app.route('/check')
def check():
    user_id = request.args.get("user_id", "").strip()
    if not user_id:
        return jsonify({"status": "expired", "files": [], "hours": "0:00:00"})
    user = get_user(user_id)
    if not user:
        restored = restore_paid_user(user_id)
        if restored: user = restored
        else: return jsonify({"status": "expired", "files": [], "hours": "0:00:00"})
    remaining = get_remaining_seconds(user)
    if remaining <= 0:
        return jsonify({"status": "expired", "files": [], "hours": "0:00:00"})
    exp = parse_expire(user.get("expires_at"))
    ref = make_ref(user_id, exp.isoformat() if exp else "")
    return jsonify({
        "status": "active",
        "files": FILES,
        "hours": format_hm(remaining/3600),
        "remaining_seconds": remaining,
        "ref": ref,
        "expire_at": user.get("expires_at")
    })

@app.route('/download/<fname>')
def download(fname):
    if fname not in FILES:
        return jsonify({"error": "file not found"}), 404
    user_id = request.args.get("user_id", "").strip()
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    user = get_user(user_id)
    if not user:
        restored = restore_paid_user(user_id)
        if restored: user = restored
        else: return jsonify({"error": "not found"}), 404
    if get_remaining_seconds(user) <= 0:
        return jsonify({"error": "expired"}), 403
    blob = agent_get_blob(user_id)
    if not blob:
        ok, res = agent_create_bundle(user_id, "paid" if get_active_subscription(user_id) else "free")
        if ok:
            blob = agent_get_blob(user_id)
    if not blob:
        return jsonify({"error": "blob not found - VPS لم يجهز الملف"}), 500
    base = fname.rsplit(".", 1)[0] if "." in fname else fname
    ext = fname.rsplit(".", 1)[1] if "." in fname else ""
    filename = f"{base}.{user_id[:12]}.{ext}" if ext else f"{base}.{user_id[:12]}"
    try:
        raw = bytes.fromhex(blob) if isinstance(blob, str) else blob
    except:
        raw = blob.encode() if isinstance(blob, str) else blob
    return Response(raw, mimetype="application/octet-stream", headers={"Content-Disposition": f"attachment; filename={filename}"})

# ======== ROUTES - Agent / VPS ========
@app.route('/api/agent/connect', methods=['POST'])
def api_agent_connect():
    data = request.get_json(silent=True) or {}
    blob = data.get("blob")
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if not blob:
        return jsonify({"error": "blob required"}), 400
    resp, code = agent_connect(blob, ip)
    return jsonify(resp), code

@app.route('/api/create_free', methods=['POST'])
def api_create_free():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    if not user_id: return jsonify({"error": "user_id required"}), 400
    ok, res = agent_create_bundle(user_id, "free")
    if ok: return jsonify({"ok": True, "data": res})
    return jsonify({"ok": False, "error": str(res)}), 500

@app.route('/api/create_paid', methods=['POST'])
def api_create_paid():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    if not user_id: return jsonify({"error": "user_id required"}), 400
    ok, res = agent_create_bundle(user_id, "paid")
    if ok: return jsonify({"ok": True, "data": res})
    return jsonify({"ok": False, "error": str(res)}), 500

@app.route('/api/agent/status', methods=['POST'])
def api_agent_status():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    if not user_id: return jsonify({"error": "user_id required"}), 400
    st = agent_status(user_id)
    if st is None: return jsonify({"error": "agent unreachable"}), 502
    return jsonify(st)

# ======== ROUTES - مدار ========
@app.route('/api/madar/charge-card', methods=['POST'])
def madar_charge():
    data = request.get_json(silent=True) or {}
    uid = data.get("user_id")
    card = (data.get("card_code") or "").strip()
    if not uid or not card:
        return jsonify({"error": "user_id و card_code مطلوبين"}), 400
    try:
        supabase.table("madar_pending").insert({"user_id": uid, "card_code": card, "amount": MADAR_PRICE, "status": "pending", "created_at": datetime.now().isoformat()}).execute()
        return jsonify({"ok": True, "message": "تم استلام الكارت، سيتم مراجعته وتفعيل حسابك خلال دقائق."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/madar/verify', methods=['POST'])
def madar_verify():
    data = request.get_json(silent=True) or {}
    uid = data.get("user_id")
    if not uid: return jsonify({"error": "user_id required"}), 400
    try:
        res = supabase.table("madar_pending").select("*").eq("user_id", uid).order("created_at", desc=True).limit(1).execute()
        if not res.data: return jsonify({"ok": False, "message": "لا يوجد طلب مدار"})
        row = res.data[0]
        if row.get("status") == "approved":
            exp = madar_activate(uid)
            return jsonify({"ok": True, "message": "تم التفعيل!", "expire_at": exp.isoformat()})
        if row.get("status") == "rejected":
            return jsonify({"ok": False, "message": "تم رفض الكارت"})
        return jsonify({"ok": False, "message": "قيد المراجعة..."})
    except Exception as e: return jsonify({"error": str(e)}), 500
 # ======== ROUTES - Admin ========
def check_admin():
    k = request.args.get("key") or request.headers.get("X-Admin-Key") or ""
    data = request.get_json(silent=True) or {}
    if not k: k = data.get("key","")
    return k in ALLOWED_KEYS

@app.route('/admin')
def admin_page():
    if not check_admin(): return "Unauthorized", 401
    return Response(ADMIN_HTML, mimetype='text/html')

@app.route('/admin/users')
def admin_users():
    if not check_admin(): return jsonify({"error": "unauthorized"}), 401
    try:
        res = supabase.table("users").select("*").order("expires_at", desc=True).limit(200).execute()
        users = res.data or []
        out = []
        for u in users:
            exp = parse_expire(u.get("expires_at"))
            remaining = get_remaining_seconds(u)
            out.append({"user_id": u.get("user_id"), "status": u.get("status"), "expires_at": u.get("expires_at"), "remaining": format_hm(remaining/3600), "active": remaining > 0})
        return jsonify({"total": len(out), "users": out})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/admin/paid')
def admin_paid():
    if not check_admin(): return jsonify({"error": "unauthorized"}), 401
    try:
        subs = get_paid_users_list()
        out = []
        for s in subs:
            exp = parse_expire(s.get("expire_at"))
            active = exp and exp > datetime.now()
            out.append({"user_id": s.get("user_id"), "expire_at": s.get("expire_at"), "tx_hash": s.get("tx_hash"), "amount": s.get("amount"), "active": bool(active)})
        return jsonify({"total": len(out), "paid": out})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/admin/madar-pending')
def admin_madar_pending():
    if not check_admin(): return jsonify({"error": "unauthorized"}), 401
    try:
        res = supabase.table("madar_pending").select("*").eq("status", "pending").order("created_at", desc=True).execute()
        return jsonify(res.data or [])
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/admin/madar-approve', methods=['POST'])
def admin_madar_approve():
    if not check_admin(): return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    rid = data.get("id")
    uid = data.get("user_id")
    if not rid and not uid: return jsonify({"error": "id أو user_id مطلوب"}), 400
    try:
        q = supabase.table("madar_pending")
        if rid: q = q.update({"status": "approved"}).eq("id", rid)
        else: q = q.update({"status": "approved"}).eq("user_id", uid).eq("status", "pending")
        q.execute()
        if uid:
            exp = madar_activate(uid)
            return jsonify({"ok": True, "expire_at": exp.isoformat()})
        return jsonify({"ok": True})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/admin/madar-reject', methods=['POST'])
def admin_madar_reject():
    if not check_admin(): return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    rid = data.get("id"); uid = data.get("user_id")
    if not rid and not uid: return jsonify({"error": "id أو user_id مطلوب"}), 400
    try:
        q = supabase.table("madar_pending")
        if rid: q = q.update({"status": "rejected"}).eq("id", rid)
        else: q = q.update({"status": "rejected"}).eq("user_id", uid).eq("status", "pending")
        q.execute()
        return jsonify({"ok": True})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/admin/delete-user', methods=['POST'])
def admin_delete_user():
    if not check_admin(): return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    uid = data.get("user_id")
    if not uid: return jsonify({"error": "user_id required"}), 400
    try:
        supabase.table("users").delete().eq("user_id", uid).execute()
        agent_delete_bundle(uid)
        return jsonify({"ok": True})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/admin/extend', methods=['POST'])
def admin_extend():
    if not check_admin(): return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    uid = data.get("user_id"); days = int(data.get("days", 30))
    if not uid: return jsonify({"error": "user_id required"}), 400
    exp = datetime.now() + timedelta(days=days)
    user = get_user(uid) or {"user_id": uid}
    user["expires_at"] = exp.strftime("%Y-%m-%d %H:%M:%S"); user["status"] = "active"
    save_user(user)
    return jsonify({"ok": True, "expire_at": exp.isoformat()})

@app.route('/admin/stats')
def admin_stats():
    if not check_admin(): return jsonify({"error": "unauthorized"}), 401
    try:
        users = supabase.table("users").select("user_id,expires_at").execute().data or []
        active = sum(1 for u in users if get_remaining_seconds(u) > 0)
        paid = supabase.table("subscriptions").select("user_id").eq("is_paid", True).execute().data or []
        return jsonify({"total_users": len(users), "active": active, "paid_total": len(paid)})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/health')
def health():
    return jsonify({"ok": True, "time": datetime.now().isoformat(), "vps_host": VPS_HOST, "supabase": bool(SUPABASE_URL)})

# ======== التشغيل ========
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    print(f"Server on port {port} - VPS: {VPS_HOST}")
    app.run(host='0.0.0.0', port=port, debug=False)       
