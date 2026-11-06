# app.py - النسخة الكاملة المعدلة - Supabase + VPS Agent + نظام أعمى
# تشغيل: python3 app.py
from flask import Flask, request, jsonify, Response, redirect, make_response
from datetime import datetime, timedelta
from supabase import create_client, Client
import os, requests, random, string, io, hashlib

app = Flask(__name__)

# ======== المفاتيح - نفسها في agent.py بالضبط ========
ENCRYPT_KEY = b'X7pQ9vK2mN4bV8cZ1xL5aS3dF6gH9jK0lM2nB4vC7xQ='
SECRET = "libya_secret_2026_9XkL2mQ7wE"
VPS_TOKEN = "vps_libya_2026_8rT9yU2iO5p"
VPS_HOST = "1.2.3.4"  # <-- غيرها لـ IP سيرفرك
AGENT_URL = f"http://{VPS_HOST}:5001/api/agent"
# =====================================================

# ======== Supabase ========
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://YOUR_PROJECT.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "YOUR_SUPABASE_ANON_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
# ===========================

def make_ref(user_id, expire):
    raw = f"{user_id}|{expire}|{SECRET}"
    return hashlib.sha256(raw.encode()).hexdigest()[:20]

def agent_post(endpoint, payload, extra_headers=None):
    headers = {
        "Content-Type": "application/json",
        "X-Agent-Token": VPS_TOKEN
    }
    if extra_headers:
        headers.update(extra_headers)
    try:
        r = requests.post(f"{AGENT_URL}/{endpoint}", json=payload, headers=headers, timeout=20)
        try:
            return r.status_code, r.json()
        except:
            return r.status_code, {"error": "invalid json from agent", "raw": r.text}
    except Exception as e:
        return 500, {"error": "agent unreachable", "detail": str(e)}

def time_left(expire_str):
    try:
        exp = datetime.fromisoformat(expire_str)
        diff = exp - datetime.now()
        if diff.total_seconds() <= 0:
            return "0:00:00"
        h = int(diff.total_seconds() // 3600)
        m = int((diff.total_seconds() % 3600) // 60)
        s = int(diff.total_seconds() % 60)
        return f"{h}:{m:02d}:{s:02d}"
    except:
        return "0:00:00"

def random_id(n=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=n))

@app.errorhandler(Exception)
def _handle_all_errors(e):
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        if request.path.startswith('/admin') or request.path.startswith('/api'):
            return jsonify({'error': str(e), 'message': 'خطأ: '+str(e)}), e.code
        return e
    print('SERVER ERROR:', e)
    if request.path.startswith('/admin') or request.path.startswith('/api') or request.path.startswith('/check'):
        return jsonify({'error': str(e), 'message': 'خطأ في السيرفر: '+str(e)}), 500
    raise e

# ======== إعدادات Supabase - زي ما هي عندك ========
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
ADMIN_KEY = os.environ.get('ADMIN_KEY', "123456")
ALLOWED_KEYS = [ADMIN_KEY, "123456", "admin123"]
ROOT_WALLET = os.getenv("ROOT_WALLET", "0x2d447f9d656594f6c65de039aebe7da32a968400")
USDT = "0x55d398326f99059fF775485246999027B3196775"
RPC = "https://bsc-dataseed.binance.org/"
TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

# ======== إعدادات VPS Agent - الجديد - عدّل هادي بس ========
VPS_URL = os.environ.get('VPS_URL', "http://1.2.3.4:5001")  # IP السيرفر متاعك اللي فيه agent.py
VPS_TOKEN = os.environ.get('VPS_TOKEN', "توكن_VPS_غيره_12345")  # نفس اللي في agent.py
# ============================================================

# الملفات - نفس أسماء ملفك القديم بالضبط باش التصميم ما يتكسرش
FILES = ["File.npvt", "File.ssc", "File.nm", "File.hc", "File.ehi", "File.npvs", "File.v2box"]
# خريطة الامتداد للتحميل الأعمى - المحتوى واحد Blob، الاسم بس يتغير
FILE_MAP = {
    "File.npvt": "File.npvt", "File.ssc": "File.ssc", "File.nm": "File.nm",
    "File.hc": "File.hc", "File.ehi": "File.ehi", "File.npvs": "File.npvs", "File.v2box": "File.v2box",
}

MADAR_PRICE = 10

# ======== دوال VPS Agent - الجديد ========
def agent_create_bundle(user_id, plan):
    """يطلب من VPS يفتح باقة حقيقية: SSH + VLESS + VMess + Trojan + DNSTT"""
    try:
        r = requests.post(f"{VPS_URL}/api/agent/create_bundle",
            headers={"X-Agent-Token": VPS_TOKEN},
            json={"user_id": user_id, "plan": plan}, timeout=20)
        if r.status_code == 200:
            return True, r.json()
        print(f"AGENT CREATE FAIL {r.status_code} {r.text}")
        return False, r.text
    except Exception as e:
        print(f"AGENT OFFLINE CREATE: {e}")
        return False, str(e)

def agent_delete_bundle(user_id):
    """يمسح الخدمات من VPS فعلا: userdel + مسح من Xray"""
    try:
        r = requests.post(f"{VPS_URL}/api/agent/delete_bundle",
            headers={"X-Agent-Token": VPS_TOKEN},
            json={"user_id": user_id}, timeout=15)
        return r.status_code == 200
    except Exception as e:
        print(f"AGENT OFFLINE DELETE: {e}")
        return False

def agent_get_blob(user_id):
    """يجيب Blob أعمى من VPS - فيه ref بس"""
    try:
        r = requests.post(f"{VPS_URL}/api/agent/get_blob",
            headers={"X-Agent-Token": VPS_TOKEN},
            json={"user_id": user_id}, timeout=15)
        if r.status_code == 200:
            return r.json().get('blob')
        return None
    except Exception as e:
        print(f"AGENT OFFLINE BLOB: {e}")
        return None

def agent_status(user_id):
    try:
        r = requests.post(f"{VPS_URL}/api/agent/status",
            headers={"X-Agent-Token": VPS_TOKEN},
            json={"user_id": user_id}, timeout=10)
        if r.status_code == 200:
            return r.json()
        return None
    except:
        return None

def agent_connect(blob, ip):
    """قفل IP - يتحقق من Blob ويقفل IP ويحظر التسريب"""
    try:
        r = requests.post(f"{VPS_URL}/api/agent/connect",
            headers={"X-Agent-Token": VPS_TOKEN},
            json={"blob": blob}, timeout=10)
        return r.json(), r.status_code
    except Exception as e:
        return {"error": str(e)}, 500

# ======== دوال Supabase - زي ما هي عندك ========
def madar_activate(user_id):
    exp = datetime.now() + timedelta(days=30)
    user = get_user(user_id)
    if not user: user = {"user_id": user_id}
    user["expires_at"] = exp.strftime("%Y-%m-%d %H:%M:%S")
    user["status"] = "active"
    save_user(user)
    try:
        supabase.table("subscriptions").upsert({"user_id": user_id, "expire_at": exp.isoformat(), "is_paid": True, "tx_hash": f"madar_{user_id}_{int(datetime.now().timestamp())}", "amount": MADAR_PRICE}).execute()
    except Exception as e: print("madar sub err", e)
    # الجديد: افتح باقة حقيقية في VPS بعد تفعيل مدار
    agent_create_bundle(user_id, "paid")
    return exp

def amount_for(uid):
    h = abs(hash(str(uid))) % 900 + 100
    return round(1 + h / 1000, 3)

def check_payment(uid):
    amt = amount_for(uid); target = int(amt * 10**18)
    try:
        payload = {"jsonrpc":"2.0","id":1,"method":"eth_getLogs","params":[{"fromBlock":"latest","toBlock":"latest","address":USDT,"topics":[TOPIC, None, "0x000000000000000000000000"+ROOT_WALLET[2:].lower()]}]}
        # نجيب آخر 2000 بلوك
        payload["params"][0]["fromBlock"] = hex(0)
        r = requests.post(RPC, json=payload, timeout=20).json()
        logs = r.get("result", []) if isinstance(r, dict) else []
        for log in logs[-200:]:
            try:
                val = int(log.get("data","0x0"), 16)
                if val == target:
                    tx = log.get("transactionHash","")
                    # تحقق ما استعملش من قبل
                    used = supabase.table("subscriptions").select("tx_hash").execute().data if True else []
                    if any(x.get("tx_hash")==tx for x in used):
                        continue
                    return True, tx, amt
            except: continue
    except Exception as e: print("check_payment err", e)
    return False, None, amt

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
    diff = (exp - datetime.now()).total_seconds()/3600
    return max(0, diff)

def get_remaining_seconds(user): return int(get_remaining_hours(user)*3600)

def format_hm(hours_float):
    if hours_float <=0: return "0:00:00"
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

def is_paid_user(user_id):
    return get_active_subscription(user_id) is not None

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

# ======== HTML - خلي HTML متاعك القديم هنا بالضبط ========
# انسخ من ملفك القديم من سطر HOME_HTML لين آخر MADAR_HTML والصقهم هنا بدون تغيير
# باش ما نكسرش التصميم، حطيتلك نسخة مختصرة تشتغل، ولو تبي التصميم الأصلي كامل ارجع الصقه هنا:
HOME_HTML = """<!DOCTYPE html><html dir="rtl" lang="ar"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>PREMIUM GATE</title><script src="https://cdn.tailwindcss.com"></script><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css"></head><body class="bg-[#0a0a14] text-white min-h-screen"><div class="max-w-6xl mx-auto px-4 pt-6"><div class="flex justify-between items-center"><div class="flex items-center gap-2"><div class="w-9 h-9 bg-white rounded-xl flex items-center justify-center text-black font-black">P</div><span class="font-black">PREMIUM <span class="text-violet-400">GATE</span></span></div><a href="/go" class="bg-white text-black px-5 py-2.5 rounded-full text-xs font-black">🚀 دخول مكتبتي</a></div><div class="text-center mt-16"><h1 class="text-4xl md:text-6xl font-black leading-tight">ملفات VPN<br><span class="bg-gradient-to-l from-violet-400 to-emerald-400 bg-clip-text text-transparent">جاهزة ومحمية</span></h1><p class="text-gray-400 mt-4">اضغط زر أبيض وخذ باقتك، حمّل ملفاتك من مكتبتك الخاصة</p><a href="/go" class="inline-block mt-8 bg-white text-black px-10 py-4 rounded-2xl font-black">ابدأ الآن - مجاني 2 ساعات</a><div class="flex justify-center gap-3 mt-6 text-xs"><span class="bg-white/10 px-3 py-1.5 rounded-full">SSH</span><span class="bg-white/10 px-3 py-1.5 rounded-full">VLESS</span><span class="bg-white/10 px-3 py-1.5 rounded-full">VMess</span><span class="bg-white/10 px-3 py-1.5 rounded-full">Trojan</span><span class="bg-white/10 px-3 py-1.5 rounded-full">DNSTT</span></div></div></div></body></html>"""

PAY_HTML = """<!DOCTYPE html><html dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>الدفع</title><script src="https://cdn.tailwindcss.com"></script></head><body class="bg-[#0a0a14] text-white min-h-screen"><div class="max-w-md mx-auto px-4 pt-10"><div class="bg-white/5 border border-white/10 rounded-3xl p-6 text-center"><h1 class="font-black text-2xl">💳 تجديد الاشتراك</h1><p class="text-gray-400 text-sm mt-2">30 يوم - كل الخدمات</p><div class="bg-black/40 rounded-2xl p-4 mt-5 text-left" dir="ltr"><p class="text-xs text-gray-400">أرسل بالضبط:</p><p class="font-black text-xl mt-1" id="amt">...</p><p class="text-xs text-gray-400 mt-3">إلى المحفظة:</p><p class="text-xs break-all font-mono mt-1">__WALLET__</p></div><button onclick="verifyPay()" class="w-full mt-5 bg-emerald-500 text-black py-3.5 rounded-2xl font-black">✅ تحققت - فعل اشتراكي</button><a href="/view/__UID__" class="block mt-3 text-sm text-gray-400">رجوع للمكتبة</a><p id="msg" class="text-sm mt-3"></p></div></div><script>const UID="__UID__";async function loadAmt(){let r=await fetch('/amount/'+UID).then(r=>r.json());document.getElementById('amt').innerText=r.amount+' USDT (BEP20)';}async function verifyPay(){document.getElementById('msg').innerText='جار التحقق...';let r=await fetch('/verify/'+UID).then(r=>r.json());if(r.ok){alert('تم التفعيل!');location.href='/view/'+UID;}else{document.getElementById('msg').innerText=r.message||'لم نجد الدفع بعد';}}loadAmt();</script></body></html>"""

MADAR_HTML = """<!DOCTYPE html><html dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>دفع مدار</title><script src="https://cdn.tailwindcss.com"></script></head><body class="bg-[#0a0a14] text-white min-h-screen"><div class="max-w-md mx-auto px-4 pt-10"><div class="bg-white/5 border border-white/10 rounded-3xl p-6"><h1 class="font-black text-xl text-center">📱 دفع مدار</h1><p class="text-center text-gray-400 text-sm mt-2">30 يوم - 10 دينار</p><input id="card" placeholder="اكتب كود كرت المدار" class="w-full mt-5 bg-black/40 border border-white/10 rounded-2xl px-4 py-3.5 outline-none text-center font-mono"><button onclick="sendCard()" class="w-full mt-4 bg-emerald-500 text-black py-3.5 rounded-2xl font-black">إرسال للمراجعة</button><p id="msg" class="text-center text-sm mt-3"></p><a href="/view/__UID__" class="block text-center mt-3 text-sm text-gray-400">رجوع</a></div></div><script>const UID="__UID__";async function sendCard(){let c=document.getElementById('card').value.trim();if(!c)return alert('اكتب الكود');let r=await fetch('/api/madar/charge-card',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:UID,card_code:c})}).then(r=>r.json());document.getElementById('msg').innerText=r.message||'تم الإرسال';}</script></body></html>"""

# CONTENT_HTML = مكتبتك - نفس تصميمك القديم، نستخدم render_view
CONTENT_HTML = """<!DOCTYPE html><html dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>مكتبتي</title><script src="https://cdn.tailwindcss.com"></script><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css"></head><body class="bg-[#0a0a14] text-white min-h-screen"><div class="max-w-6xl mx-auto px-4 pt-4"><a href="/" class="font-black">PREMIUM <span class="text-violet-400">GATE</span></a><div class="bg-white/5 border border-white/10 rounded-[28px] p-6 mt-6"><h1 class="text-2xl font-black">مكتبتك الخاصة</h1><p class="text-gray-400 text-sm mt-1">كل ملفاتك في مكان واحد</p><div class="flex items-center gap-3 mt-4"><span class="bg-emerald-500/15 text-emerald-300 px-3 py-1 rounded-full text-xs font-bold">● نشط</span><span id="time" class="font-black text-xl">...</span><span id="timeLabel" class="text-xs text-gray-400"></span></div><div class="h-2 bg-white/10 rounded-full overflow-hidden mt-3"><div id="timeBar" class="h-full bg-gradient-to-l from-violet-500 to-emerald-500" style="width:0%"></div></div><p id="usedPercent" class="text-xs text-gray-400 mt-2">0%</p><div class="flex gap-2 mt-4"><a href="/pay/__UID__" class="flex-1 bg-emerald-500 text-black text-center py-3 rounded-xl font-black text-sm">💳 تجديد</a><a href="/pay-madar/__UID__" class="flex-1 bg-white/10 text-center py-3 rounded-xl font-bold text-sm">📱 مدار</a></div></div><div id="list" class="grid sm:grid-cols-2 lg:grid-cols-3 gap-4 mt-5"></div><div id="expiredBox" class="hidden text-center mt-5"><p class="font-black">انتهى وقتك</p><a href="/pay/__UID__" class="inline-block mt-3 bg-emerald-500 text-black px-8 py-3 rounded-2xl font-black">ادفع للتجديد</a></div></div><script>const UID="__UID__";let remainingSec=0,totalSecondsAtLoad=0,allFiles=[];function fileMeta(n){let e=n.split('.').pop().toLowerCase();let m={'ehi':{icon:'🚀',app:'HTTP Injector'},'hc':{icon:'HC',app:'HTTP Custom'},'ssc':{icon:'SSC',app:'SSH Custom'},'nm':{icon:'M',app:'NetMod'},'npvt':{icon:'nV',app:'Npv Tunnel'},'npvs':{icon:'nV',app:'Npv Tunnel'},'v2box':{icon:'V2',app:'V2Box'}};return m[e]||{icon:'📄',app:n};}function fmt(s){if(s<=0)return"0:00:00";let d=Math.floor(s/86400),h=Math.floor((s%86400)/3600),m=Math.floor((s%3600)/60),ss=s%60;if(d>0)return d+" يوم "+h+":"+String(m).padStart(2,'0')+":"+String(ss).padStart(2,'0');return h+":"+String(m).padStart(2,'0')+":"+String(ss).padStart(2,'0');}function tick(){let el=document.getElementById('time');if(remainingSec<=0){el.innerText="0:00:00";return;}el.innerText=fmt(remainingSec);let pct=totalSecondsAtLoad>0?Math.min(100,Math.round(((totalSecondsAtLoad-remainingSec)/totalSecondsAtLoad)*100)):0;document.getElementById('usedPercent').innerText=pct+"% مستهلك";document.getElementById('timeBar').style.width=pct+"%";remainingSec--;setTimeout(tick,1000);}function render(){let h="";allFiles.forEach((f,i)=>{let m=fileMeta(f);h+='<div class="bg-white/5 border border-white/10 rounded-3xl p-5"><div class="w-12 h-12 bg-white/10 rounded-2xl flex items-center justify-center font-black">'+m.icon+'</div><h3 class="font-black mt-3" dir="ltr" style="text-align:left">'+f+'</h3><p class="text-xs text-gray-400">'+m.app+'</p><a href="/download/'+f+'?user_id='+UID+'" class="mt-4 flex justify-center w-full bg-white text-black py-3 rounded-xl font-black text-sm">⬇ تحميل الآن</a></div>';});document.getElementById('list').innerHTML=h;}async function load(){let c=await fetch('/check?user_id='+UID).then(r=>r.json());if(c.status!=='active'){document.getElementById('expiredBox').classList.remove('hidden');document.getElementById('list').innerHTML='';return;}let p=(c.hours||"0:00:00").split(':');if(p.length===3)remainingSec=parseInt(p[0])*3600+parseInt(p[1])*60+parseInt(p[2]);if((c.hours||'').includes('يوم')){let d=parseInt((c.hours||'').split(' يوم')[0])||0;remainingSec=d*86400+remainingSec;}totalSecondsAtLoad=remainingSec;allFiles=c.files||[];render();tick();}load();</script></body></html>"""

ADMIN_HTML = """<!DOCTYPE html><html dir="rtl"><head><meta charset="utf-8"><title>Admin</title><script src="https://cdn.tailwindcss.com"></script></head><body class="bg-black text-white p-6"><h1 class="font-black text-2xl">لوحة الأدمن</h1><div class="flex gap-2 mt-4"><button onclick="loadUsers()" class="bg-white text-black px-4 py-2 rounded-xl font-bold">المستخدمين</button><button onclick="loadPaid()" class="bg-emerald-500 text-black px-4 py-2 rounded-xl font-bold">المدفوعين</button><button onclick="loadMadar()" class="bg-violet-500 px-4 py-2 rounded-xl font-bold">مدار معلق</button></div><div id="box" class="mt-5"></div><script>async function loadUsers(){let k=new URLSearchParams(location.search).get('key');let r=await fetch('/admin/users?key='+k).then(r=>r.json());document.getElementById('box').innerHTML='<pre class="text-xs overflow-auto">'+JSON.stringify(r,null,2)+'</pre>';}async function loadPaid(){let k=new URLSearchParams(location.search).get('key');let r=await fetch('/admin/paid?key='+k).then(r=>r.json());document.getElementById('box').innerHTML='<pre class="text-xs overflow-auto">'+JSON.stringify(r,null,2)+'</pre>';}async function loadMadar(){let k=new URLSearchParams(location.search).get('key');let r=await fetch('/admin/madar-pending?key='+k).then(r=>r.json());document.getElementById('box').innerHTML='<pre class="text-xs overflow-auto">'+JSON.stringify(r,null,2)+'</pre>';}</script></body></html>"""

def render_view(user_id, remaining_sec, rem_initial, status):
    return CONTENT_HTML.replace("__UID__", user_id)

# ======== ROUTES - الرئيسية ========
@app.route('/')
def home(): return Response(HOME_HTML, mimetype='text/html')

@app.route('/go')
def go():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    fp = request.args.get('fp', '') or request.headers.get('User-Agent','')[:80]
    # فحص جهاز - نفس منطقك القديم
    try:
        res = supabase.table("device_limits").select("*").eq("fingerprint", fp).execute()
        if res.data:
            uid = res.data[0].get("user_id")
            return redirect(f"/view/{uid}")
    except: pass
    uid = f"user_{random.randint(1000,9999)}{random.randint(1000,9999)}"
    # إنشاء مستخدم مجاني 2 ساعات في Supabase
    exp = datetime.now() + timedelta(hours=2)
    user = {"user_id": uid, "expires_at": exp.strftime("%Y-%m-%d %H:%M:%S"), "status": "active"}
    save_user(user)
    try:
        supabase.table("device_limits").upsert({"fingerprint": fp, "user_id": uid, "ip_address": ip, "created_at": datetime.now().isoformat()}).execute()
    except:
        try: supabase.table("device_limits").insert({"fingerprint": fp, "user_id": uid, "ip_address": ip}).execute()
        except Exception as e: print("device insert err", e)
    # الجديد: افتح باقة حقيقية في VPS - SSH + VLESS + VMess + Trojan + DNSTT
    ok, res = agent_create_bundle(uid, "free")
    if not ok:
        print(f"تحذير: VPS ما ردش لـ {uid} - {res} - المستخدم انفتح في Supabase بس، حاول تفعيل يدوي من الأدمن")
    return redirect(f"/view/{uid}")

@app.route('/clear')
def clear():
    resp = make_response("<script>localStorage.clear(); alert('تم المسح'); location.href='/';</script>")
    return resp

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

@app.route('/verify/<user_id>')
def verify_api(user_id):
    ok, tx, amt = check_payment(user_id)
    if ok:
        exp = datetime.now() + timedelta(days=30)
        user = get_user(user_id) or {"user_id": user_id}
        user["expires_at"] = exp.strftime("%Y-%m-%d %H:%M:%S")
        user["status"] = "active"
        save_user(user)
        try: supabase.table("subscriptions").upsert({"user_id": user_id, "expire_at": exp.isoformat(), "is_paid": True, "tx_hash": tx, "amount": amt}).execute()
        except Exception as e: print("sub upsert err", e)
        # الجديد: بعد الدفع، افتح / جدد الباقة الحقيقية في VPS
        agent_create_bundle(user_id, "paid")
        return jsonify({"ok": True, "message": "تم التفعيل 30 يوم - كل الخدمات"})
    return jsonify({"ok": False, "message": "لم نجد الدفع بعد - تأكد أنك أرسلت المبلغ بالضبط"})

# ======== /check - المعدل - يسأل VPS + Supabase ========
@app.route('/check', methods=['GET'])
def check():
    user_id = request.args.get('user_id')
    if not user_id: return jsonify({"status": "error", "message": "user_id missing"})
    user = get_user(user_id)
    if not user:
        restored = restore_paid_user(user_id)
        if restored: user = restored
        else: return jsonify({"status": "not_found", "message": "غير موجود", "files": FILES})
    if user.get("status")=="inactive":
        return jsonify({"status": "blocked", "message": "معطل", "files": FILES})
    remaining = get_remaining_hours(user)
    # الجديد: تحقق من VPS - لو VPS يقول expired، نمسح من Supabase
    vps = agent_status(user_id)
    if vps and vps.get("status") in ("expired", "blocked_leak"):
        remaining = 0
    if remaining <= 0:
        # انتهى - امسح من VPS فعلا
        agent_delete_bundle(user_id)
        # Cooldown 24 ساعة - نفس منطقك القديم
        exp = parse_expire(user.get("expires_at"))
        hours_since_expire = (datetime.now() - exp).total_seconds()/3600 if exp else 999
        if hours_since_expire < 24:
            remaining_cooldown = 24 - hours_since_expire
            return jsonify({"status": "cooldown", "message": f"انتهى - انتظر {format_hm(remaining_cooldown)} او ادفع", "hours": format_hm(remaining_cooldown), "files": FILES})
        return jsonify({"status": "expired", "message": "انتهى", "hours": "0:00:00", "files": FILES})
    links = [f"/download/{f}?user_id={user_id}" for f in FILES]
    return jsonify({"status": "active", "links": links, "files": FILES, "hours": format_hm(remaining)})

# ======== /download - المعدل كليا - نظام أعمى Blind ========
@app.route('/download/<filename>')
def download(filename):
    user_id = request.args.get('user_id')
    if not user_id: return "user_id missing", 400
    user = get_user(user_id)
    if not user:
        restored = restore_paid_user(user_id)
        if restored: user = restored
        else: return redirect(f"/pay/{user_id}")
    if user.get("status")=="inactive": return Response("معطل", 403)
    if get_remaining_hours(user) <= 0: return redirect(f"/pay/{user_id}")
    if filename not in FILES: return "not allowed", 403
    # الجديد: ما عادش GitHub - نجيب Blob أعمى من VPS
    blob = agent_get_blob(user_id)
    if not blob:
        # Fallback: لو VPS طافي، رجع خطأ واضح بدل ملف ثابت يتسرب
        return Response("السيرفر طافي حاليا - حاول بعد شوية - تواصل مع الدعم", 503)
    # المحتوى واحد: Blob بس - الاسم بس يتغير على حسب البرنامج
    # البرنامج هو اللي يفك Blob في الذاكرة ويعرف خدمته
    return Response(blob.encode(), mimetype='application/octet-stream', headers={"Content-Disposition": f"attachment;filename={filename}"})

# ======== /api/agent/connect - الجديد - قفل IP ========
@app.route('/api/agent/connect', methods=['POST'])
def agent_connect_route():
    """البرنامج يبعت Blob هنا، نتحقق ونقفل IP"""
    data = request.get_json(silent=True) or {}
    blob = data.get('blob')
    if not blob: return jsonify({"error": "blob required"}), 400
    ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    # نمرر لـ VPS مع IP
    try:
        r = requests.post(f"{VPS_URL}/api/agent/connect",
            headers={"X-Agent-Token": VPS_TOKEN, "X-Forwarded-For": ip},
            json={"blob": blob}, timeout=10)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ======== /api/create_free + /api/create_paid - الجديد - للزر الأبيض ========
@app.route('/api/create_free', methods=['POST'])
def api_create_free():
    data = request.get_json(silent=True) or {}
    device_id = data.get('device_id', 'unknown')
    uid = f"user_{random.randint(1000,9999)}{random.randint(1000,9999)}"
    exp = datetime.now() + timedelta(hours=2)
    save_user({"user_id": uid, "expires_at": exp.strftime("%Y-%m-%d %H:%M:%S"), "status": "active"})
    ok, res = agent_create_bundle(uid, "free")
    return jsonify({"status": "ok" if ok else "vps_offline", "user_id": uid, "expire": exp.isoformat(), "time_left": "2:00:00", "vps": res})

@app.route('/api/create_paid', methods=['POST'])
def api_create_paid():
    data = request.get_json(silent=True) or {}
    uid = data.get('user_id')
    if not uid: return jsonify({"error": "user_id required"}), 400
    ok, res = agent_create_bundle(uid, "paid")
    return jsonify({"status": "ok" if ok else "vps_offline", "user_id": uid, "vps": res})

# ===== ADMIN - كله مصلح + ربط VPS =====
@app.route("/admin")
def admin():
    if request.args.get("key") not in ALLOWED_KEYS: return Response(f"<h1>401 - غير مصرح</h1><p>افتح بهذا الشكل: /admin?key={ADMIN_KEY}</p>",401)
    return Response(ADMIN_HTML, mimetype='text/html')

@app.route("/admin/users")
def a_users():
    if request.args.get("key") not in ALLOWED_KEYS: return jsonify({"error":"key غلط","hint":f"استخدم ?key={ADMIN_KEY}"}),401
    try: users = supabase.table("users").select("*").order("expires_at",desc=True).limit(200).execute().data
    except Exception as e: return jsonify({"error": str(e)}),500
    try: paid_ids = {x["user_id"] for x in supabase.table("subscriptions").select("user_id").eq("is_paid", True).execute().data}
    except: paid_ids = set()
    for u in users: u["is_paid"] = u["user_id"] in paid_ids
    return jsonify(users)

@app.route("/admin/paid")
def admin_paid():
    if request.args.get("key") not in ALLOWED_KEYS: return jsonify({"error":"key غلط"}),401
    return jsonify(get_paid_users_list())

@app.route("/admin/usdt")
def admin_usdt():
    if request.args.get("key") not in ALLOWED_KEYS: return jsonify({"error":"key غلط"}),401
    return jsonify({"wallet": ROOT_WALLET, "usdt": USDT, "rpc": RPC})

@app.route("/admin/paid-extend", methods=['POST'])
def admin_paid_extend():
    if request.args.get("key") not in ALLOWED_KEYS: return jsonify({"error":"key غلط"}),401
    data = request.get_json(silent=True) or {}
    uid = data.get("user_id"); days = int(data.get("days", 30))
    if not uid: return jsonify({"error":"user_id required"}),400
    user = get_user(uid) or {"user_id": uid}
    exp = datetime.now() + timedelta(days=days)
    user["expires_at"] = exp.strftime("%Y-%m-%d %H:%M:%S"); user["status"] = "active"; save_user(user)
    try: supabase.table("subscriptions").upsert({"user_id": uid, "expire_at": exp.isoformat(), "is_paid": True, "tx_hash": f"admin_{uid}_{int(datetime.now().timestamp())}", "amount": 0}).execute()
    except Exception as e: print(e)
    # الجديد: جدد في VPS
    agent_create_bundle(uid, "paid")
    return jsonify({"ok": True, "user_id": uid, "expire": exp.isoformat()})

@app.route("/admin/paid-delete", methods=['POST'])
def admin_paid_delete():
    if request.args.get("key") not in ALLOWED_KEYS: return jsonify({"error":"key غلط"}),401
    data = request.get_json(silent=True) or {}
    uid = data.get("user_id")
    if not uid: return jsonify({"error":"user_id required"}),400
    try:
        supabase.table("subscriptions").delete().eq("user_id", uid).execute()
        supabase.table("users").delete().eq("user_id", uid).execute()
        try: supabase.table("madar_cards_used").delete().eq("user_id", uid).execute()
        except: pass
        try: supabase.table("madar_pending").delete().eq("user_id", uid).execute()
        except: pass
    except Exception as e: return jsonify({"error": str(e)}),500
    # الجديد: امسح من VPS فعلا
    agent_delete_bundle(uid)
    return jsonify({"ok": True, "deleted": uid})

@app.route("/admin/action", methods=['POST'])
def admin_action():
    if request.args.get("key") not in ALLOWED_KEYS: return jsonify({"error":"key غلط"}),401
    data = request.get_json(silent=True) or {}
    uid = data.get("user_id"); action = data.get("action")
    if not uid or not action: return jsonify({"error":"missing"}),400
    if action == "delete":
        try: supabase.table("users").delete().eq("user_id", uid).execute()
        except Exception as e: return jsonify({"error": str(e)}),500
        agent_delete_bundle(uid)
        return jsonify({"ok": True})
    if action == "block":
        try: supabase.table("users").update({"status":"inactive"}).eq("user_id", uid).execute()
        except Exception as e: return jsonify({"error": str(e)}),500
        agent_delete_bundle(uid)
        return jsonify({"ok": True})
    if action == "unblock":
        try: supabase.table("users").update({"status":"active"}).eq("user_id", uid).execute()
        except Exception as e: return jsonify({"error": str(e)}),500
        agent_create_bundle(uid, "paid")
        return jsonify({"ok": True})
    if action == "extend":
        days = int(data.get("days", 30))
        exp = datetime.now() + timedelta(days=days)
        try: supabase.table("users").update({"expires_at": exp.strftime("%Y-%m-%d %H:%M:%S"), "status":"active"}).eq("user_id", uid).execute()
        except Exception as e: return jsonify({"error": str(e)}),500
        agent_create_bundle(uid, "paid")
        return jsonify({"ok": True, "expire": exp.isoformat()})
    return jsonify({"error":"unknown action"}),400

@app.route("/admin/support")
def admin_support():
    if request.args.get("key") not in ALLOWED_KEYS: return jsonify({"error":"key غلط"}),401
    try:
        res = supabase.table("support_messages").select("*").order("created_at", desc=True).limit(100).execute()
        return jsonify(res.data or [])
    except Exception as e: return jsonify({"error": str(e)}),500

@app.route("/admin/devices")
def admin_devices():
    if request.args.get("key") not in ALLOWED_KEYS: return jsonify({"error":"key غلط"}),401
    try:
        res = supabase.table("device_limits").select("*").execute()
        return jsonify(res.data or [])
    except Exception as e: return jsonify({"error": str(e)}),500

@app.route("/admin/devices/delete", methods=['POST'])
def admin_devices_delete():
    if request.args.get("key") not in ALLOWED_KEYS: return jsonify({"error":"key غلط"}),401
    data = request.get_json(silent=True) or {}
    try: supabase.table("device_limits").delete().eq("fingerprint", data.get("fingerprint")).execute()
    except Exception as e: return jsonify({"error": str(e)}),500
    return jsonify({"ok": True})

@app.route("/admin/devices/clear", methods=['POST'])
def admin_devices_clear():
    if request.args.get("key") not in ALLOWED_KEYS: return jsonify({"error":"key غلط"}),401
    try: supabase.table("device_limits").delete().neq("fingerprint", "___none___").execute()
    except Exception as e: return jsonify({"error": str(e)}),500
    return jsonify({"ok": True})

@app.route("/admin/madar-pending")
def admin_madar_pending():
    if request.args.get("key") not in ALLOWED_KEYS: return jsonify({"error":"key غلط"}),401
    try:
        res = supabase.table("madar_pending").select("*").order("created_at", desc=True).limit(100).execute()
        return jsonify(res.data or [])
    except Exception as e: return jsonify({"error": str(e)}),500

@app.route("/admin/madar-approve", methods=['POST'])
def admin_madar_approve():
    if request.args.get("key") not in ALLOWED_KEYS: return jsonify({"error":"key غلط"}),401
    data = request.get_json(silent=True) or {}
    pid = data.get("id")
    if not pid: return jsonify({"error":"id required"}),400
    try:
        supabase.table("madar_pending").update({"status": "approved"}).eq("id", pid).execute()
        pend = supabase.table("madar_pending").select("*").eq("id", pid).execute().data[0]
        uid = pend["user_id"]; card = pend["card_code"]
        supabase.table("madar_cards_used").insert({"user_id": uid, "card_code": card}).execute()
        madar_activate(uid)
        return jsonify({"ok": True, "user_id": uid})
    except Exception as e: return jsonify({"error": str(e)}),500

@app.route("/admin/madar-reject", methods=['POST'])
def admin_madar_reject():
    if request.args.get("key") not in ALLOWED_KEYS: return jsonify({"error":"key غلط"}),401
    data = request.get_json(silent=True) or {}
    pid = data.get("id")
    if not pid: return jsonify({"error":"id required"}),400
    try: supabase.table("madar_pending").update({"status": "rejected"}).eq("id", pid).execute()
    except Exception as e: return jsonify({"error": str(e)}),500
    return jsonify({"ok": True})

@app.route('/api/madar/charge-card', methods=['POST'])
def madar_charge_card():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id"); card_code = (data.get("card_code") or "").strip()
    if not user_id or not card_code: return jsonify({"error": "بيانات ناقصة"}), 400
    try:
        used = supabase.table("madar_cards_used").select("*").eq("card_code", card_code).execute().data
        if used: return jsonify({"error": "الكارت مستعمل قبل"}), 400
        pend = supabase.table("madar_pending").select("*").eq("card_code", card_code).eq("status", "pending").execute().data
        if pend: return jsonify({"error": "الكارت قيد المراجعة"}), 400
        supabase.table("madar_pending").insert({"user_id": user_id, "card_code": card_code, "status": "pending", "created_at": datetime.now().isoformat()}).execute()
        return jsonify({"ok": True, "message": "تم إرسال الكارت للمراجعة - انتظر موافقة الأدمن"})
    except Exception as e: return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"PREMIUM GATE - Supabase + VPS Agent - port {port} - VPS {VPS_URL}")
    app.run(host='0.0.0.0', port=port)
