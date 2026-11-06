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
HOME_HTML = """<!DOCTYPE html><html dir="rtl" lang="ar"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>PREMIUM GATE</title><script src="https://cdn.tailwindcss.com"></script><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet"><style>@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700;900&display=swap');*{font-family:'Tajawal',sans-serif}.glass{background:rgba(255,255,255,0.05);backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,0.1)}.glow{box-shadow:0 0 40px rgba(139,92,246,0.3)}</style></head><body class="bg-[#050507] text-white min-h-screen"><div class="fixed inset-0 -z-10"><div class="absolute top-0 right-0 w-[600px] h-[600px] bg-purple-600/20 rounded-full blur-[120px]"></div><div class="absolute bottom-0 left-0 w-[600px] h-[600px] bg-emerald-500/15 rounded-full blur-[120px]"></div></div><div class="max-w-6xl mx-auto p-4 flex justify-between items-center"><div class="flex items-center gap-2"><div class="w-9 h-9 bg-white rounded-xl flex items-center justify-center text-black font-black">P</div><span class="font-black">PREMIUM GATE</span></div><div class="text-xs text-gray-500">0x2d44...8400 • SECURE</div></div><div class="max-w-6xl mx-auto px-4 mt-10 grid lg:grid-cols-2 gap-8 items-center"><div><div class="inline-flex items-center gap-2 glass rounded-full px-4 py-1.5 text-xs text-emerald-300 mb-4"><span class="w-2 h-2 bg-emerald-400 rounded-full animate-pulse"></span> النظام شغال - دخول فوري</div><h1 class="text-4xl lg:text-5xl font-black leading-[1.2]">دخولك للمحتوى<br><span class="bg-gradient-to-r from-violet-400 to-emerald-400 bg-clip-text text-transparent">في ثانية واحدة</span></h1><p class="text-gray-400 mt-4 text-sm">رابط واحد ينشألك حساب، يعطيك ساعتين مجانا، ويفتحلك صفحة العرض الاحترافية.</p><div class="mt-8 flex flex-col gap-3"><button onclick="checkAndGo()" class="w-full bg-white text-black py-4 rounded-2xl font-black text-center text-lg glow hover:scale-[1.02] transition">🚀 إنشاء حساب ودخول فوري</button></div><div class="grid grid-cols-3 gap-3 mt-8"><div class="glass rounded-2xl p-4 text-center"><p class="text-2xl font-black text-violet-400">2H</p><p class="text-[11px] text-gray-400">مجانا</p></div><div class="glass rounded-2xl p-4 text-center"><p class="text-2xl font-black text-emerald-400">1$</p><p class="text-[11px] text-gray-400">30 يوم</p></div><div class="glass rounded-2xl p-4 text-center"><p class="text-2xl font-black">∞</p><p class="text-[11px] text-gray-400">تحميل</p></div></div></div><div class="bg-[#12121f] rounded-[32px] p-2 border border-white/10 shadow-2xl"><div class="bg-black rounded-[24px] p-6"><div class="flex justify-between mb-6"><span class="text-xs text-gray-500">معاينة حسابك الحقيقي</span><span class="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></span></div><div class="bg-[#12121f] rounded-[20px] p-5 border border-white/5"><div class="flex items-center justify-end gap-2 mb-3"><span>👤</span><span id="previewUid" class="font-bold">--</span></div><p class="text-sm text-right">متبقي: <span id="previewTimer" class="font-bold text-emerald-400">--:--:--</span> : متبقي</p><p class="text-sm text-right">حالة: <span id="previewStatus">active</span> : حالة</p><div class="grid grid-cols-2 gap-3 mt-6"><button onclick="openRealContent()" class="bg-[#8b5cf6] py-3 rounded-xl text-center font-bold text-sm">📁 محتوى</button><button onclick="openRealPay()" class="bg-[#10b981] py-3 rounded-xl text-center font-bold text-sm text-black">💳 دفع</button></div></div></div></div></div><div class="max-w-6xl mx-auto px-4 mt-12 grid md:grid-cols-3 gap-4"><button onclick="checkAndGo()" class="glass rounded-[24px] p-6 hover:border-violet-500/50 hover:scale-[1.02] transition text-right w-full"><div class="w-12 h-12 bg-violet-500/20 rounded-xl flex items-center justify-center text-violet-300 mb-4"><i class="fa-solid fa-bolt"></i></div><h3 class="font-bold">وصول فوري</h3><p class="text-sm text-gray-400 mt-2">يضغط ويدخل طول لصفحته</p><span class="text-xs text-violet-400 mt-3 block">دخول الآن →</span></button><a href="/view/demo_user" class="glass rounded-[24px] p-6 hover:border-emerald-500/50 hover:scale-[1.02] transition text-right"><div class="w-12 h-12 bg-emerald-500/20 rounded-xl flex items-center justify-center text-emerald-300 mb-4"><i class="fa-solid fa-shield"></i></div><h3 class="font-bold">حماية متقدمة</h3><p class="text-sm text-gray-400 mt-2">شوف صفحة العرض</p><span class="text-xs text-emerald-400 mt-3 block">عرض تجريبي →</span></a><div onclick="openChat()" class="glass rounded-[24px] p-6 hover:border-yellow-500/50 hover:scale-[1.02] transition text-right cursor-pointer"><div class="w-12 h-12 bg-yellow-500/20 rounded-xl flex items-center justify-center text-yellow-300 mb-4"><i class="fa-solid fa-headset"></i></div><h3 class="font-bold">دعم 24/7</h3><p class="text-sm text-gray-400 mt-2">دردشة فورية داخل الموقع</p><span class="text-xs text-yellow-400 mt-3 block">افتح الدردشة →</span></div></div><div id="chatBtn" onclick="openChat()" class="fixed bottom-6 right-6 w-14 h-14 bg-white rounded-full flex items-center justify-center text-black shadow-2xl cursor-pointer z-50 glow"><i class="fa-solid fa-comments text-xl"></i></div><div id="chatBox" class="fixed bottom-24 right-4 w-[360px] max-w-[90vw] bg-[#12121f] border border-white/10 rounded-[20px] shadow-2xl z-50 hidden flex-col overflow-hidden"><div class="bg-[#1e1e35] p-4 flex justify-between items-center"><div><p class="font-bold text-sm">💬 الدعم الفوري</p><p class="text-[11px] text-green-400">● متصل الآن</p></div><button onclick="closeChat()" class="text-gray-400">✕</button></div><div id="chatMsgs" class="flex-1 p-4 space-y-3 overflow-y-auto max-h-[320px] text-sm"><div class="bg-white/5 p-3 rounded-xl text-xs text-gray-300">مرحبا! 👋 انا الدعم، كيف نساعدك؟</div></div><div class="p-3 bg-black/30 flex gap-2"><input id="chatInput" placeholder="اكتب رسالتك..." class="flex-1 bg-[#0a0a12] border border-white/10 rounded-xl px-3 py-2.5 text-sm outline-none"><button onclick="sendMsg()" class="bg-white text-black px-4 rounded-xl font-bold text-sm">ارسال</button></div></div><script>
let SUPPORT_UID = localStorage.getItem('support_uid') || "guest_"+Math.floor(Math.random()*99999);localStorage.setItem('support_uid', SUPPORT_UID);let chatInterval = null;function goUid(){let v=document.getElementById('uidInput').value.trim(); if(!v){document.getElementById('uidInput').focus();return;} location.href='/view/'+v;}function openChat(){ document.getElementById('chatBox').classList.remove('hidden'); document.getElementById('chatBox').classList.add('flex'); loadMsgs(); if(chatInterval) clearInterval(chatInterval); chatInterval = setInterval(loadMsgs, 2000); }function closeChat(){ document.getElementById('chatBox').classList.add('hidden'); document.getElementById('chatBox').classList.remove('flex'); if(chatInterval) clearInterval(chatInterval); }async function loadMsgs(){ try{let r=await fetch('/api/support/get?user_id='+SUPPORT_UID).then(x=>x.json()); let box=document.getElementById('chatMsgs'); let h='<div class="bg-white/5 p-3 rounded-xl text-xs text-gray-300">مرحبا! 👋 انا الدعم، كيف نساعدك؟</div>'; r.forEach(m=>{if(m.sender==='user') h+='<div class="bg-white text-black p-3 rounded-2xl ml-10 rounded-br-sm">'+m.message+'</div>'; else h+='<div class="bg-[#1e1e35] p-3 rounded-2xl mr-10 rounded-bl-sm border border-white/10">'+m.message+'</div>';}); box.innerHTML=h; box.scrollTop=box.scrollHeight;}catch(e){}}async function sendMsg(){ let inp=document.getElementById('chatInput'); let txt=inp.value.trim(); if(!txt) return; await fetch('/api/support/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:SUPPORT_UID,message:txt,sender:'user'})}); inp.value=''; loadMsgs(); }function openRealContent(){ let id=localStorage.getItem('my_user_id'); if(id) location.href='/content/'+id; else alert('ما عندكش حساب، دير انشاء اول'); }function openRealPay(){ let id=localStorage.getItem('my_user_id'); if(id) location.href='/pay/'+id; else alert('ما عندكش حساب، دير انشاء اول'); }async function loadPreview(){let myId=localStorage.getItem('my_user_id');let uidEl=document.getElementById('previewUid');let timerEl=document.getElementById('previewTimer');let statusEl=document.getElementById('previewStatus');if(!myId){uidEl.innerText="ما عندكش حساب";timerEl.innerText="0:00:00";return;}uidEl.innerText=myId;try{let c=await fetch('/check?user_id='+myId).then(r=>r.json());statusEl.innerText=c.status;let rem=c.hours||"0:00:00";timerEl.innerText=rem;let parts=rem.split(':');let sec=0;if(parts.length>=2){if(parts.length===3) sec=parseInt(parts[0])*3600+parseInt(parts[1])*60+parseInt(parts[2]); else sec=parseInt(parts[0])*60+parseInt(parts[1]);}setInterval(function(){if(sec<=0) return; sec--; let h=Math.floor(sec/3600), m=Math.floor((sec%3600)/60), s=sec%60; timerEl.innerText=h+":"+String(m).padStart(2,'0')+":"+String(s).padStart(2,'0');},1000);}catch(e){timerEl.innerText="خطأ";}}loadPreview();async function getFingerprint(){let s=navigator.userAgent+'|'+screen.width+'x'+screen.height+'|'+Intl.DateTimeFormat().resolvedOptions().timeZone+'|'+navigator.language;let hash=0; for(let i=0;i<s.length;i++){hash=((hash<<5)-hash)+s.charCodeAt(i); hash|=0;}return 'fp_'+Math.abs(hash);}async function checkAndGo(){let fp=await getFingerprint();localStorage.setItem('my_fp',fp);localStorage.removeItem('my_user_id');localStorage.removeItem('last_go_time');document.cookie="last_user_id=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";document.cookie="device_fp=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";location.href='/go?fp='+encodeURIComponent(fp);}</script></body></html>"""
PAY_HTML = """<!DOCTYPE html><html dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>دفع</title><script src="https://cdn.tailwindcss.com"></script></head><body class="bg-[#0a0a12] min-h-screen flex items-center justify-center p-4"><div class="w-full max-w-md"><div class="bg-[#1e1e35] rounded-[24px] p-6 border border-white/10"><h1 class="text-xl font-bold text-white text-center">الدفع الآمن - USDT (BEP20)</h1><div class="bg-black/40 rounded-2xl p-4 mt-4"><div class="flex justify-between items-center gap-2"><div id="amt" class="text-2xl font-bold text-emerald-400">-- USDT</div><button onclick="copyAmt()" class="bg-white/10 hover:bg-white/20 text-white text-xs px-3 py-2 rounded-lg whitespace-nowrap">📋 نسخ المبلغ</button></div></div><div class="bg-black/40 rounded-2xl p-4 mt-4"><p class="text-xs text-gray-400">عنوان المحفظة</p><div class="flex gap-2 items-center mt-2"><div class="bg-[#0a0a12] p-3 rounded-xl font-mono text-[11px] break-all text-white flex-1">__WALLET__</div><button onclick="copyWallet()" class="bg-white/10 hover:bg-white/20 text-white text-xs px-3 py-2 rounded-lg whitespace-nowrap">📋 نسخ المحفظة</button></div></div><button onclick="verify()" id="btn" class="w-full bg-emerald-500 text-black py-4 rounded-xl font-bold mt-4">لقد دفعت، فعل حسابي</button><a href="/pay-madar/__UID__" class="block w-full bg-yellow-400 text-black py-4 rounded-xl font-bold mt-3 text-center">💳 دفع بالمدار - 10 دينار</a><div id="status" class="mt-4 text-center text-sm text-white"></div><div class="text-center mt-3"><a id="toContent" class="text-xs text-gray-400 underline">عرض المحتوى</a></div></div></div><script>let UID="__UID__"; let currentAmount=""; let currentWallet="__WALLET__";async function init(){ let r=await fetch('/amount/'+UID).then(x=>x.json()); currentAmount=r.amount; document.getElementById('amt').innerText=r.amount+' USDT'; document.getElementById('toContent').href='/content/'+UID; }function copyAmt(){ navigator.clipboard.writeText(currentAmount); }function copyWallet(){ navigator.clipboard.writeText(currentWallet); }async function verify(){let b=document.getElementById('btn'),s=document.getElementById('status');b.innerHTML="جاري التحقق...";b.disabled=true;try{let r=await fetch('/verify/'+UID).then(x=>x.json());if(r.paid){s.innerHTML="تم التفعيل";setTimeout(()=>location.href='/content/'+UID,1500);}else{s.innerHTML='لم يتم العثور';b.disabled=false;b.innerHTML="لقد دفعت، فعل حسابي";}}catch(e){s.innerText="خطأ";b.disabled=false;}}init();</script></body></html>"""
MADAR_HTML = """<!DOCTYPE html><html dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>دفع بالمدار</title><script src="https://cdn.tailwindcss.com"></script></head><body class="bg-[#0a0a12] min-h-screen flex items-center justify-center p-4"><div class="w-full max-w-md"><div class="bg-[#1e1e35] rounded-[24px] p-6 border border-white/10 text-center"><h1 class="text-xl font-bold text-white">دفع بالمدار - 10 دينار</h1><p class="text-yellow-400 text-[11px] mt-4">سيتم مراجعته يدويا وتفعيل حسابك</p><input id="cardCode" type="text" inputmode="numeric" placeholder="رقم الكرت السري" class="w-full bg-black border border-white/20 rounded-xl px-4 py-4 text-center text-lg font-bold mt-4 outline-none text-white tracking-widest" maxlength="20"><button onclick="chargeCard()" id="btnPaid" class="w-full bg-yellow-400 text-black py-4 rounded-xl font-black mt-3">ارسال الكرت للمراجعة</button><p id="msg1" class="mt-3 text-sm"></p><div id="done" class="hidden mt-4 bg-emerald-500/20 border border-emerald-500/30 rounded-xl p-4"><p class="text-emerald-300 font-bold">تم ارسال الكرت ✅</p><p class="text-gray-400 text-xs mt-1">انتظر تفعيل حسابك من الادمن</p><a href="/view/__UID__" class="block mt-3 bg-white text-black py-2 rounded-xl font-bold text-sm">الرجوع لحسابي</a></div></div></div><script>
let UID="__UID__";async function chargeCard(){let card=document.getElementById('cardCode').value.trim();if(card.length<10){document.getElementById('msg1').innerHTML='<span class="text-red-400">اكتب الرقم كامل</span>';return;}document.getElementById('msg1').innerHTML='جاري الارسال...';document.getElementById('btnPaid').disabled=true;let r=await fetch('/api/madar/charge-card',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:UID,card_code:card})}).then(x=>x.json());document.getElementById('btnPaid').disabled=false;if(r.status=='used'){document.getElementById('msg1').innerHTML='<span class="text-red-400">الكرت مستعمل قبل</span>';}else if(r.status=='pending'){document.getElementById('cardCode').classList.add('hidden');document.getElementById('btnPaid').classList.add('hidden');document.getElementById('msg1').classList.add('hidden');document.getElementById('done').classList.remove('hidden');}else{document.getElementById('msg1').innerHTML='<span class="text-red-400">خطأ، حاول مرة اخرى</span>';}}</script></body></html>"""
CONTENT_HTML = """<!DOCTYPE html><html dir="rtl" lang="ar"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>مكتبتي | __UID__</title><script src="https://cdn.tailwindcss.com"></script><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet"><style>@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800;900&display=swap');*{font-family:'Tajawal',sans-serif}body{background:#06060b}.glass{background:rgba(255,255,255,.04);backdrop-filter:blur(18px);border:1px solid rgba(255,255,255,.08)}.card{transition:.25s}.card:hover{transform:translateY(-4px);border-color:rgba(139,92,246,.5);box-shadow:0 20px 40px rgba(0,0,0,.5)}@keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-8px)}}.float{animation:float 4s ease-in-out infinite}.ring{stroke-dasharray:283;stroke-dashoffset:0;transition:stroke-dashoffset 1s linear;transform:rotate(-90deg);transform-origin:center}</style></head>
<body class="text-white min-h-screen">
<div class="fixed inset-0 -z-10 pointer-events-none"><div class="absolute top-[-100px] right-[-100px] w-[500px] h-[500px] bg-violet-600/20 rounded-full blur-[120px]"></div><div class="absolute bottom-[-100px] left-[-100px] w-[500px] h-[500px] bg-emerald-500/15 rounded-full blur-[120px]"></div><div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-blue-600/10 rounded-full blur-[140px]"></div></div>
<div class="max-w-6xl mx-auto px-4 pt-4 flex items-center justify-between">
<a href="/" class="flex items-center gap-2"><div class="w-9 h-9 bg-white rounded-xl flex items-center justify-center text-black font-black text-lg">P</div><span class="font-black tracking-wide">PREMIUM <span class="text-violet-400">GATE</span></span></a>
<div class="flex items-center gap-2">
<a href="/view/__UID__" class="bg-white/10 border border-white/10 px-4 py-2 rounded-full text-xs font-bold hover:bg-white/20">👤 حسابي</a>
<a href="/" class="bg-white text-black px-4 py-2 rounded-full text-xs font-black">🏠 الرئيسية</a>
</div>
</div>
<div class="max-w-6xl mx-auto px-4 mt-6">
<div class="glass rounded-[28px] p-5 md:p-7 relative overflow-hidden">
<div class="absolute top-0 left-0 w-full h-[1px] bg-gradient-to-l from-transparent via-violet-400/60 to-transparent"></div>
<div class="flex flex-col md:flex-row md:items-center gap-6 justify-between">
<div class="flex-1">
<div class="flex items-center gap-2 mb-3"><span class="bg-emerald-500/15 text-emerald-300 text-[11px] px-3 py-1 rounded-full font-bold">● مكتبتك مفتوحة</span><span id="planBadge" class="bg-violet-500/15 text-violet-300 text-[11px] px-3 py-1 rounded-full font-bold">⭐ PRO</span></div>
<h1 class="text-[28px] md:text-[36px] font-black leading-[1.15]">مكتبتك الخاصة<br><span class="bg-gradient-to-l from-violet-400 via-fuchsia-400 to-emerald-400 bg-clip-text text-transparent">كل ملفاتك في مكان واحد</span></h1>
<p class="text-gray-400 text-sm mt-3 leading-6">حمّل أي ملف بضغطة واحدة. ملفاتك محمية بحسابك ومربوطة بوقتك المتبقي.</p>
<div class="flex flex-wrap gap-2 mt-5">
<div class="bg-black/40 border border-white/10 rounded-2xl px-4 py-2.5 flex items-center gap-2"><i class="fa-solid fa-folder-open text-violet-400"></i><span class="text-xs text-gray-400">الملفات:</span><b id="totalFiles" class="text-sm">--</b></div>
<div class="bg-black/40 border border-white/10 rounded-2xl px-4 py-2.5 flex items-center gap-2"><i class="fa-solid fa-user text-emerald-400"></i><span class="text-xs text-gray-400">ID:</span><b class="text-sm font-mono">__UID__</b></div>
<div class="bg-black/40 border border-white/10 rounded-2xl px-4 py-2.5 flex items-center gap-2"><i class="fa-solid fa-shield-halved text-yellow-400"></i><span class="text-xs text-gray-400">حماية:</span><b class="text-sm text-emerald-300">نشطة</b></div>
</div>
</div>
<div class="shrink-0 mx-auto md:mx-0">
<div class="relative w-[140px] h-[140px]">
<svg class="w-full h-full" viewBox="0 0 100 100"><circle cx="50" cy="50" r="45" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="7"/><circle id="ringCircle" class="ring" cx="50" cy="50" r="45" fill="none" stroke="url(#grad)" stroke-width="7" stroke-linecap="round"/><defs><linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="#8b5cf6"/><stop offset="100%" stop-color="#10b981"/></linearGradient></defs></svg>
<div class="absolute inset-0 flex flex-col items-center justify-center"><span class="text-[10px] text-gray-400">متبقي</span><span id="time" class="text-[18px] font-black leading-none mt-1">--:--:--</span><span id="timeLabel" class="text-[10px] text-emerald-300 mt-1 font-bold">نشط</span></div>
</div>
<div class="flex gap-2 mt-3"><a href="/pay/__UID__" class="flex-1 bg-emerald-500 text-black text-center py-2.5 rounded-xl font-black text-xs">💳 تجديد</a><a href="/view/__UID__" class="flex-1 bg-white/10 border border-white/10 text-center py-2.5 rounded-xl font-bold text-xs">حسابي</a></div>
</div>
</div>
<div class="mt-5"><div class="flex justify-between text-[11px] text-gray-400 mb-2"><span>نسبة الوقت المستهلك</span><span id="usedPercent">0%</span></div><div class="h-2 bg-white/10 rounded-full overflow-hidden"><div id="timeBar" class="h-full bg-gradient-to-l from-violet-500 to-emerald-500 rounded-full transition-all duration-700" style="width:0%"></div></div></div>
</div>
<div class="flex flex-col md:flex-row gap-3 mt-5">
<div class="flex-1 relative"><i class="fa-solid fa-magnifying-glass absolute right-4 top-1/2 -translate-y-1/2 text-gray-500 text-sm"></i><input id="searchInput" oninput="filterFiles()" placeholder="دوّر على ملف... مثلا File.ehi" class="w-full bg-[#12121f] border border-white/10 rounded-2xl pr-11 pl-4 py-3.5 text-sm outline-none focus:border-violet-500 placeholder:text-gray-500"></div>
<div class="flex gap-2 overflow-x-auto pb-1">
<button onclick="setFilter('all',this)" data-filter="all" class="filterBtn shrink-0 bg-white text-black px-4 py-3 rounded-2xl text-xs font-black">الكل</button>
<button onclick="setFilter('vpn',this)" data-filter="vpn" class="filterBtn shrink-0 bg-white/10 border border-white/10 px-4 py-3 rounded-2xl text-xs font-bold">VPN</button>
<button onclick="setFilter('config',this)" data-filter="config" class="filterBtn shrink-0 bg-white/10 border border-white/10 px-4 py-3 rounded-2xl text-xs font-bold">Configs</button>
<button onclick="setFilter('other',this)" data-filter="other" class="filterBtn shrink-0 bg-white/10 border border-white/10 px-4 py-3 rounded-2xl text-xs font-bold">أخرى</button>
<button onclick="downloadAll()" class="shrink-0 bg-violet-600 px-4 py-3 rounded-2xl text-xs font-black">⬇ تحميل الكل</button>
</div>
</div>
<div id="list" class="grid sm:grid-cols-2 lg:grid-cols-3 gap-4 mt-5 pb-6"></div>
<div id="expiredBox" class="hidden glass rounded-[28px] p-8 text-center mt-5">
<div class="w-16 h-16 mx-auto bg-red-500/15 rounded-2xl flex items-center justify-center text-2xl float">⏰</div>
<h3 class="font-black text-lg mt-4">انتهى وقتك</h3>
<p class="text-gray-400 text-sm mt-2">جدد اشتراكك باش ترجع تحمل ملفاتك من جديد.</p>
<a href="/pay/__UID__" class="inline-block mt-5 bg-emerald-500 text-black px-8 py-3.5 rounded-2xl font-black">ادفع للتجديد - 30 يوم</a>
</div>
<div class="flex items-center justify-center gap-2 text-[11px] text-gray-500 pb-8"><span class="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></span> جميع الملفات محمية • التحميل مباشر وآمن • PREMIUM GATE</div>
</div>
<script>
const UID="__UID__";
let remainingSec=0; let allFiles=[]; let currentFilter='all'; let totalSecondsAtLoad=0;
function fileMeta(name){
  let ext=(name.split('.').pop()||'').toLowerCase();
  let map={
    'ehi':{icon:'🚀', bg:'bg-[#2f3f3f]', text:'text-white', label:'EHI', cat:'config', app:'HTTP Injector', border:'border-white/20', desc:''},
    'hc':{icon:'HC', bg:'bg-orange-500', text:'text-white', label:'HC', cat:'vpn', app:'HTTP Custom', border:'border-orange-300', big:true, desc:''},
    'ssc':{icon:'SSC', bg:'bg-[#6b21a8]', text:'text-yellow-300', label:'ssc', cat:'vpn', app:'SSH Custom', border:'border-purple-400', big:true, desc:''},
    'nm':{icon:'M', bg:'bg-white', text:'text-red-500', label:'NM', cat:'config', app:'NetMod', border:'border-red-200', big:true, desc:''},
    'npvt':{icon:'nV', bg:'bg-[#1d4ed8]', text:'text-white', label:'NPVT', cat:'vpn', app:'Npv Tunnel', border:'border-blue-400', big:true, desc:''},
    'npvs':{icon:'nV', bg:'bg-[#1d4ed8]', text:'text-white', label:'NPVS', cat:'vpn', app:'Npv Tunnel', border:'border-blue-400', big:true, desc:''},
    'v2box':{icon:'V2', bg:'bg-black', text:'text-white', label:'V2BOX', cat:'other', app:'V2Box', border:'border-white/30', big:true, desc:''}
  };
  return map[ext]||{icon:'📄', bg:'bg-white/10', text:'text-white', label:ext.toUpperCase(), cat:'other', app:name, desc:'ملف جاهز', border:'border-white/10'};
}
function formatHM(sec){ if(sec<=0) return "0:00:00"; let d=Math.floor(sec/86400); let h=Math.floor((sec%86400)/3600); let m=Math.floor((sec%3600)/60); let s=sec%60; if(d>0) return d+" يوم "+h+":"+String(m).padStart(2,'0')+":"+String(s).padStart(2,'0'); return h+":"+String(m).padStart(2,'0')+":"+String(s).padStart(2,'0'); }
function tick(){ let el=document.getElementById('time'); if(remainingSec<=0){ el.innerText="0:00:00"; document.getElementById('timeLabel').innerText="منتهي"; return; } el.innerText=formatHM(remainingSec); let pct=0; if(totalSecondsAtLoad>0) pct=Math.min(100, Math.round(((totalSecondsAtLoad-remainingSec)/totalSecondsAtLoad)*100)); document.getElementById('usedPercent').innerText=pct+"% مستهلك"; document.getElementById('timeBar').style.width=pct+"%"; let ring=document.getElementById('ringCircle'); if(ring) ring.style.strokeDashoffset = 283 * (pct/100); remainingSec--; setTimeout(tick,1000); }
function setFilter(f,btn){ currentFilter=f; document.querySelectorAll('.filterBtn').forEach(b=>{ b.className='filterBtn shrink-0 bg-white/10 border border-white/10 px-4 py-3 rounded-2xl text-xs font-bold'; }); if(btn) btn.className='filterBtn shrink-0 bg-white text-black px-4 py-3 rounded-2xl text-xs font-black'; renderFiles(); }
function filterFiles(){ renderFiles(); }
function renderFiles(){
  let q=(document.getElementById('searchInput').value||'').toLowerCase().trim();
  let filtered=allFiles.filter(f=>{ let m=fileMeta(f); if(currentFilter!='all' && m.cat!=currentFilter) return false; if(q && !f.toLowerCase().includes(q)) return false; return true; });
  let list=document.getElementById('list');
  if(filtered.length==0){ list.innerHTML='<div class="col-span-full glass rounded-[24px] p-10 text-center"><div class="text-3xl mb-3">🔍</div><p class="font-bold">مافيش ملف مطابق</p><p class="text-gray-400 text-sm mt-1">جرب كلمة تانية او غير الفلتر</p></div>'; return; }
  let h=""; filtered.forEach(function(f,i){
    let m=fileMeta(f); let num=String(i+1).padStart(2,'0');
    h+='<div class="card glass rounded-[24px] p-5 relative overflow-hidden">'
    +'<div class="absolute top-0 left-0 w-full h-[1px] bg-gradient-to-l from-transparent via-white/20 to-transparent"></div>'
    +'<div class="flex justify-between items-start"><div class="w-14 h-14 '+m.bg+' '+(m.border||'border-white/10')+' border-2 rounded-2xl flex items-center justify-center text-[22px] font-black '+m.text+'">'+m.icon+'</div><span class="text-[10px] bg-white/10 px-2.5 py-1 rounded-full font-mono text-gray-300">#'+num+'</span></div>'
    +'<h3 class="font-black text-[17px] mt-4 truncate" dir="ltr" style="text-align:left">'+f+'</h3>'
    +'<p class="text-xs font-bold '+m.text+' mt-1">'+m.app+'</p>'
    +'<p class="text-xs text-gray-400 mt-1">'+m.desc+'</p>'
    +'<div class="flex items-center gap-2 mt-3"><span class="text-[10px] '+m.bg+' '+m.text+' px-2.5 py-1 rounded-full font-bold">'+m.label+'</span><span class="text-[10px] bg-emerald-500/15 text-emerald-300 px-2.5 py-1 rounded-full font-bold">● جاهز</span><span class="text-[10px] text-gray-500">• تحميل مباشر</span></div>'
    +'<a href="/download/'+f+'?user_id='+UID+'" class="mt-4 flex items-center justify-center gap-2 w-full bg-white text-black py-3 rounded-xl font-black text-sm hover:bg-violet-100 transition"><i class="fa-solid fa-download"></i> تحميل الآن</a>'
    +'<button onclick="copyLink(\\''+f+'\\')" class="mt-2 w-full bg-white/5 border border-white/10 py-2.5 rounded-xl text-xs font-bold text-gray-300 hover:bg-white/10">📋 نسخ رابط التحميل</button>'
    +'</div>';
  });
  list.innerHTML=h;
}
function copyLink(f){ let link=location.origin+'/download/'+f+'?user_id='+UID; navigator.clipboard.writeText(link); alert('تم نسخ رابط '+f); }
function downloadAll(){ if(!allFiles.length) return; if(!confirm('تحميل كل الملفات ('+allFiles.length+') واحد ورا واحد؟')) return; allFiles.forEach(function(f,i){ setTimeout(()=>{ window.open('/download/'+f+'?user_id='+UID,'_blank'); }, i*600); }); }
async function load(){
  try{
    let c=await fetch('/check?user_id='+UID).then(r=>r.json());
    let parts=(c.hours||"0:00:00").split(':');
    if(parts.length===3) remainingSec=parseInt(parts[0])*3600+parseInt(parts[1])*60+parseInt(parts[2]);
    else if(parts.length===2) remainingSec=parseInt(parts[0])*60+parseInt(parts[1]);
    else remainingSec=0;
    if((c.hours||'').includes('يوم')){ let d=parseInt((c.hours||'').split(' يوم')[0])||0; remainingSec = d*86400 + remainingSec; }
    totalSecondsAtLoad=remainingSec; tick();
    let list=document.getElementById('list');
    if(c.status!=='active'){ list.innerHTML=''; document.getElementById('expiredBox').classList.remove('hidden'); document.getElementById('time').innerText="0:00:00"; return; }
    allFiles=c.files||[];
    document.getElementById('totalFiles').innerText=allFiles.length+" ملف";
    if(c.status==='active' && remainingSec>24*3600) document.getElementById('planBadge').innerText='⭐ PRO • مدفوع';
    renderFiles();
  }catch(e){ document.getElementById('list').innerHTML='<div class="col-span-full glass p-6 rounded-2xl text-center text-red-300">خطأ في التحميل، حدث الصفحة</div>'; }
}
load();
</script></body></html>"""
ADMIN_HTML = '''<!DOCTYPE html><html dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Admin - يدوي</title><script src="https://cdn.tailwindcss.com"></script><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet"></head><body class="bg-[#050507] text-white min-h-screen p-3"><div class="max-w-7xl mx-auto">
<div class="flex justify-between items-center mb-4"><h1 class="text-xl font-black">PROMAX V2 - يدوي</h1><div class="flex gap-2 items-center"><input id="search" placeholder="بحث user_id" class="bg-[#12121f] border border-white/10 rounded-xl px-3 py-1.5 text-xs w-32"><span id="keyStatus" class="text-[10px] px-3 py-1.5 rounded-full"></span></div></div>
<div id="errorBox" class="hidden bg-red-900/30 border border-red-500/50 rounded-xl p-4 mb-4 text-sm"></div>
<div class="grid grid-cols-5 gap-2 mb-4">
<div class="bg-[#12121f] p-3 rounded-xl border border-white/5"><p class="text-[11px] text-gray-400">مجاني</p><p id="totalUsers" class="text-xl font-black">--</p></div>
<div class="bg-[#12121f] p-3 rounded-xl border border-white/5"><p class="text-[11px] text-gray-400">نشط مجاني</p><p id="activeUsers" class="text-xl font-black text-emerald-400">--</p></div>
<div class="bg-[#12121f] p-3 rounded-xl border border-white/5"><p class="text-[11px] text-gray-400">منتهي</p><p id="expiredUsers" class="text-xl font-black text-red-400">--</p></div>
<div class="bg-[#12121f] p-3 rounded-xl border border-white/5"><p class="text-[11px] text-gray-400">مدفوع</p><p id="paidCount" class="text-xl font-black text-violet-400">--</p></div>
<div class="bg-[#12121f] p-3 rounded-xl border border-white/5"><p class="text-[11px] text-gray-400">أجهزة</p><p id="deviceCount" class="text-xl font-black text-yellow-400">--</p></div>
</div>
<div class="flex gap-2 mb-4 text-xs overflow-x-auto">
<button onclick="showTab('madar')" id="tab-madar" class="bg-yellow-400 text-black px-4 py-2 rounded-xl font-bold whitespace-nowrap">💳 كروت المدار <span id="madarBadge" class="hidden bg-red-500 text-white text-[10px] px-2 py-0.5 rounded-full"></span></button>
<button onclick="showTab('usdt')" id="tab-usdt" class="bg-[#12121f] border border-white/10 px-4 py-2 rounded-xl whitespace-nowrap">💵 USDT <span id="usdtBadge" class="hidden bg-emerald-500 text-white text-[10px] px-2 py-0.5 rounded-full"></span></button>
<button onclick="showTab('paid')" id="tab-paid" class="bg-[#12121f] border border-white/10 px-4 py-2 rounded-xl whitespace-nowrap">⭐ المشتركين</button>
<button onclick="showTab('users')" id="tab-users" class="bg-[#12121f] border border-white/10 px-4 py-2 rounded-xl whitespace-nowrap">المستخدمين (مجاني)</button>
<button onclick="showTab('support')" id="tab-support" class="bg-[#12121f] border border-white/10 px-4 py-2 rounded-xl whitespace-nowrap">الدعم <span id="supportBadge" class="hidden bg-red-500 text-white text-[10px] px-2 py-0.5 rounded-full"></span></button>
<button onclick="showTab('devices')" id="tab-devices" class="bg-[#12121f] border border-white/10 px-4 py-2 rounded-xl whitespace-nowrap">الأجهزة</button>
</div>
<div id="view-madar" class="bg-[#12121f] rounded-2xl border border-white/5 p-3"><div class="flex justify-between items-center mb-3"><h2 class="font-bold text-sm">كروت المدار - يدوي - اشحن في تليفونك وبعدها فعل</h2><button onclick="loadMadar()" class="text-[11px] bg-white text-black px-3 py-1 rounded-lg font-bold">تحديث</button></div><div id="madarList" class="space-y-2 max-h-[75vh] overflow-y-auto"></div></div>
<div id="view-usdt" class="hidden bg-[#12121f] rounded-2xl border border-white/5 p-3"><div class="flex justify-between items-center mb-3"><h2 class="font-bold text-sm">💵 مدفوعات USDT - تلقائي</h2><button onclick="loadUsdt()" class="text-[11px] bg-white text-black px-3 py-1 rounded-lg font-bold">تحديث</button></div><div class="flex gap-2 mb-3 text-[11px]"><button onclick="usdtFilter='all';loadUsdt()" class="bg-white text-black px-3 py-1 rounded-lg font-bold">الكل</button><button onclick="usdtFilter='active';loadUsdt()" class="bg-white/10 px-3 py-1 rounded-lg">نشط فقط</button></div><div id="usdtList" class="space-y-2 max-h-[75vh] overflow-y-auto"></div></div>
<div id="view-paid" class="hidden bg-[#12121f] rounded-2xl border border-white/5 p-3"><div class="flex justify-between items-center mb-3"><h2 class="font-bold text-sm">⭐ المشتركين المدفوعين - مدار + USDT</h2><button onclick="loadPaid()" class="text-[11px] bg-white text-black px-3 py-1 rounded-lg font-bold">تحديث</button></div><div class="flex gap-2 mb-3 text-[11px]"><button onclick="paidFilter='all';loadPaid()" class="bg-white text-black px-3 py-1 rounded-lg font-bold">الكل</button><button onclick="paidFilter='مدار';loadPaid()" class="bg-yellow-400 text-black px-3 py-1 rounded-lg font-bold">مدار فقط</button><button onclick="paidFilter='USDT';loadPaid()" class="bg-emerald-400 text-black px-3 py-1 rounded-lg font-bold">USDT فقط</button></div><div id="paidList" class="space-y-2 max-h-[75vh] overflow-y-auto"></div></div>
<div id="view-users" class="hidden bg-[#12121f] rounded-2xl border border-white/5 overflow-hidden"><div class="p-3 border-b border-white/5 flex justify-between items-center gap-2"><h2 class="font-bold text-sm">المستخدمين المجانيين فقط</h2><div class="flex gap-2"><input id="customDays" type="number" placeholder="أيام" class="w-16 bg-black border border-white/10 rounded-lg px-2 py-1 text-xs"><input id="customHours" type="number" placeholder="ساعات" class="w-16 bg-black border border-white/10 rounded-lg px-2 py-1 text-xs"></div><button onclick="loadUsers()" class="text-[11px] bg-white text-black px-3 py-1 rounded-lg font-bold">تحديث</button></div><div id="tb" class="divide-y divide-white/5 max-h-[75vh] overflow-y-auto text-sm"></div></div>
<div id="view-support" class="hidden bg-[#12121f] rounded-2xl border border-white/5 p-3"><div id="convList" class="flex gap-2 overflow-x-auto mb-3"></div><div id="supportList" class="space-y-2 max-h-[70vh] overflow-y-auto"></div></div>
<div id="view-devices" class="hidden bg-[#12121f] rounded-2xl border border-white/5 p-3"><div id="deviceList" class="space-y-2 max-h-[70vh] overflow-y-auto"></div><button onclick="clearDevices()" class="mt-3 w-full bg-red-500/20 text-red-300 py-2 rounded-xl text-xs">مسح كل الأجهزة</button></div>
</div>
<script>
const KEY=new URLSearchParams(location.search).get("key");
let allUsers=[]; let allSupport=[]; let currentFilter='all';
let madarInterval=null; let usdtFilter='all'; let paidFilter='all';
function showKeyStatus(){ let el=document.getElementById('keyStatus'); let err=document.getElementById('errorBox'); if(!KEY){ el.innerText='مافيش key'; el.className='text-[10px] bg-red-500/20 text-red-300 px-3 py-1.5 rounded-full'; err.classList.remove('hidden'); err.innerHTML='⚠️ لازم تفتح الرابط هكي:<br><b>/admin?key=123456</b>'; return false; } else { el.innerText='key: '+KEY; el.className='text-[10px] bg-emerald-500/20 text-emerald-300 px-3 py-1.5 rounded-full'; return true; }}
function showTab(t){ ['madar','usdt','paid','users','support','devices'].forEach(x=>document.getElementById('view-'+x).classList.add('hidden')); ['madar','usdt','paid','users','support','devices'].forEach(x=>{ let b=document.getElementById('tab-'+x); if(b) b.className='bg-[#12121f] border border-white/10 px-4 py-2 rounded-xl whitespace-nowrap'; }); document.getElementById('view-'+t).classList.remove('hidden'); let active=document.getElementById('tab-'+t); if(t=='madar') active.className='bg-yellow-400 text-black px-4 py-2 rounded-xl font-bold whitespace-nowrap'; else if(t=='usdt') active.className='bg-emerald-400 text-black px-4 py-2 rounded-xl font-bold whitespace-nowrap'; else if(t=='paid') active.className='bg-violet-500 text-white px-4 py-2 rounded-xl font-bold whitespace-nowrap'; else active.className='bg-white text-black px-4 py-2 rounded-xl font-bold whitespace-nowrap'; if(madarInterval) clearInterval(madarInterval); if(t==='madar'){ loadMadar(); madarInterval=setInterval(loadMadar, 3000); } if(t==='usdt') loadUsdt(); if(t==='paid') loadPaid(); if(t==='support') loadSupport(); if(t==='devices') loadDevices(); if(t==='users') loadUsers(); }
async function loadUsers(){ if(!showKeyStatus()) return; let tb=document.getElementById('tb'); tb.innerHTML='<div class="p-6 text-center text-gray-400">جاري التحميل...</div>'; try{ let res = await fetch('/admin/users?key='+KEY); let data = await res.json(); if(data.error){ tb.innerHTML='<div class="p-6 text-center text-red-400">❌ '+data.error+'</div>'; return; } allUsers=data; renderUsers(data); document.getElementById('totalUsers').innerText=data.length; document.getElementById('activeUsers').innerText=data.filter(x=>x.is_active).length; document.getElementById('expiredUsers').innerText=data.filter(x=>!x.is_active).length; }catch(e){ tb.innerHTML='<div class="p-4 text-red-300">فشل: '+e.message+'</div>'; }}
function renderUsers(list){ let s=document.getElementById('search').value.trim(); if(s) list=list.filter(x=>x.user_id.includes(s)); let h=""; list.forEach(function(x){ let statusBadge = x.is_active ? '<span class="bg-emerald-500/20 text-emerald-300 px-2 py-0.5 rounded-full text-[10px]">مجاني فعال</span>' : '<span class="bg-red-500/20 text-red-300 px-2 py-0.5 rounded-full text-[10px]">منتهي/معطل</span>'; let timeColor = x.is_active ? 'text-emerald-400' : 'text-red-400'; h+='<div class="p-3 hover:bg-white/5 border-b border-white/5 last:border-0"><div class="flex justify-between items-start gap-2"><div class="flex-1"><div class="flex items-center gap-2"><p class="font-bold text-[13px]">'+x.user_id+'</p>'+statusBadge+'</div><p class="text-[11px] text-gray-500 mt-1">'+(x.ip_address||'')+'</p><p class="text-[12px] mt-1">متبقي مجاني: <span class="font-black '+timeColor+'">'+x.remaining_formatted+'</span></p><p class="text-[10px] text-gray-600 mt-1">ينتهي: '+x.expire_at+'</p></div><div class="flex flex-col gap-1 text-[11px] min-w-[140px]"><div class="flex gap-1"><button onclick="actionUser(\\''+x.user_id+'\\',\\'extend_custom\\')" class="flex-1 bg-violet-500 text-white px-2 py-1.5 rounded-lg font-bold">+ مخصص</button><button onclick="actionUser(\\''+x.user_id+'\\',\\'add_days\\',30)" class="bg-emerald-500 text-black px-2 py-1.5 rounded-lg font-bold">+30 يوم</button></div><div class="flex gap-1"><button onclick="actionUser(\\''+x.user_id+'\\',\\'enable\\')" class="flex-1 bg-white/10 px-2 py-1.5 rounded-lg">تفعيل</button><button onclick="actionUser(\\''+x.user_id+'\\',\\'disable\\')" class="flex-1 bg-yellow-500/10 text-yellow-300 px-2 py-1.5 rounded-lg">تعطيل</button><button onclick="actionUser(\\''+x.user_id+'\\',\\'delete\\')" class="bg-red-500/20 text-red-300 px-2 py-1.5 rounded-lg">حذف</button></div><a href="/view/'+x.user_id+'" target="_blank" class="text-center bg-white text-black py-1 rounded-lg font-bold text-[10px] mt-1">فتح صفحته</a></div></div></div>'; }); document.getElementById('tb').innerHTML=h||'<div class="p-6 text-center text-gray-500">لا يوجد مجانيين</div>'; }
document.getElementById('search').addEventListener('input', function(){ renderUsers(allUsers); });
async function actionUser(uid, act, val){ let days=0, hours=0; if(act==='extend_custom'){ days=parseInt(document.getElementById('customDays').value)||0; hours=parseInt(document.getElementById('customHours').value)||0; if(days===0 && hours===0){ alert('اكتب عدد الأيام او الساعات فوق'); return; }} if(act==='add_days'){ days=val; } if(!confirm(act+' ل '+uid+' ؟')) return; let r=await fetch('/admin/action?key='+KEY, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({user_id:uid, action:act, days:days, hours:hours})}).then(x=>x.json()); alert(r.message||'تم'); loadUsers(); }
async function loadMadar(){ let list=document.getElementById('madarList'); list.innerHTML='<div class="p-6 text-center text-gray-400">جاري التحميل...</div>'; try{ let data=await fetch('/admin/madar-pending?key='+KEY).then(r=>r.json()); let badge=document.getElementById('madarBadge'); let pending=data.filter(x=>x.status=='pending'); if(pending.length>0){ badge.innerText=pending.length; badge.classList.remove('hidden'); } else { badge.classList.add('hidden'); } let h=""; data.forEach(function(x){ let color = x.status=='pending' ? 'border-yellow-500/30 bg-yellow-500/10' : x.status=='approved' ? 'border-emerald-500/30 bg-emerald-500/10' : 'border-red-500/30 bg-red-500/10'; h+='<div class="p-3 rounded-xl border '+color+'"><div class="flex justify-between"><div><p class="font-bold text-sm">'+(x.user_id||'')+'</p><p class="font-mono text-[13px] mt-1 tracking-widest">'+(x.card_code||'')+'</p><p class="text-[11px] text-gray-500 mt-1">'+(x.created_at||'')+' - '+(x.status||'')+'</p></div><div class="flex flex-col gap-1">'; if(x.status=='pending'){ h+='<button onclick="approveMadar('+x.id+',\\''+(x.user_id||'')+'\\',\\''+(x.card_code||'')+'\\')" class="bg-emerald-500 text-black px-3 py-1.5 rounded-lg font-bold text-xs">✅ تفعيل بعد الشحن</button>'; h+='<button onclick="rejectMadar('+x.id+')" class="bg-red-500/20 text-red-300 px-3 py-1.5 rounded-lg text-xs">❌ رفض</button>'; } h+='<a href="/view/'+(x.user_id||'')+'" target="_blank" class="text-center bg-white/10 px-3 py-1 rounded-lg text-[11px]">فتح حسابه</a></div></div></div>'; }); list.innerHTML=h||'<div class="p-6 text-center text-gray-400">لا يوجد كروت</div>'; }catch(e){ list.innerHTML='خطأ: '+e.message; } }
async function approveMadar(id, uid, card){ if(!confirm('هل شحنت الكرت '+card+' ؟')) return; let r=await fetch('/admin/madar-approve?key='+KEY,{method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({id:id, user_id:uid, card_code:card})}).then(x=>x.json()); alert(r.message||'تم'); loadMadar(); loadPaid(); loadUsers(); }
async function rejectMadar(id){ if(!confirm('رفض الكرت؟')) return; await fetch('/admin/madar-reject?key='+KEY,{method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({id:id})}); loadMadar(); }
async function loadUsdt(){ let list=document.getElementById('usdtList'); list.innerHTML='<div class="p-6 text-center text-gray-400">جاري التحميل...</div>'; try{ let data=await fetch('/admin/usdt?key='+KEY).then(r=>r.json()); let badge=document.getElementById('usdtBadge'); if(data.length>0){ badge.innerText=data.length; badge.classList.remove('hidden'); } else { badge.classList.add('hidden'); } if(usdtFilter=='active') data=data.filter(x=>x.is_active); let h=""; data.forEach(function(x){ let tx=(x.tx_hash||''); h+='<div class="p-3 rounded-xl border border-emerald-500/30 bg-emerald-500/10"><div class="flex justify-between"><div><p class="font-bold text-sm">'+(x.user_id||'')+' <span class="text-[10px] bg-emerald-500 text-black px-2 py-0.5 rounded-full">USDT</span></p><p class="font-mono text-[11px] mt-1 break-all">'+tx+'</p><p class="text-[11px] text-gray-400 mt-1">المبلغ: '+(x.amount_paid||'')+' USDT</p><p class="text-[11px] text-gray-500">متبقي: '+(x.remaining_formatted||'')+'</p></div><div class="flex flex-col gap-1"><a href="/view/'+(x.user_id||'')+'" target="_blank" class="text-center bg-white text-black px-3 py-1.5 rounded-lg text-[11px] font-bold">فتح حسابه</a><button onclick="deletePaid(\\''+(x.user_id||'')+'\\')" class="bg-red-500/20 text-red-300 px-3 py-1.5 rounded-lg text-[11px]">حذف</button></div></div></div>'; }); list.innerHTML=h||'<div class="p-6 text-center text-gray-400">لا يوجد دفعات USDT</div>'; }catch(e){ list.innerHTML='خطأ: '+e.message; } }
async function loadPaid(){ let list=document.getElementById('paidList'); list.innerHTML='<div class="p-6 text-center text-gray-400">جاري التحميل...</div>'; try{ let _resp=await fetch('/admin/paid?key='+KEY); let _txt=await _resp.text(); let data; try{ data=JSON.parse(_txt); }catch{ list.innerHTML='خطأ من السيرفر: '+_txt.slice(0,200); return; } if(!Array.isArray(data)){ list.innerHTML='خطأ: '+(data.error||data.message||_txt.slice(0,200)); return; } document.getElementById('paidCount').innerText=data.length; if(paidFilter!='all') data=data.filter(x=>x.method==paidFilter); let h=""; data.forEach(function(x){ let isMadar=x.method=='مدار'; let color=isMadar?'border-yellow-500/30 bg-yellow-500/10':'border-emerald-500/30 bg-emerald-500/10'; let badge=isMadar?'<span class="text-[10px] bg-yellow-400 text-black px-2 py-0.5 rounded-full font-bold">مدار</span>':'<span class="text-[10px] bg-emerald-400 text-black px-2 py-0.5 rounded-full font-bold">USDT</span>'; let tx=(x.tx_hash||''); let card=(x.card_code||''); let extra=isMadar?'كرت: '+card:'Tx: '+(tx?tx.slice(0,20)+'...':'بدون Tx'); h+='<div class="p-3 rounded-xl border '+color+'"><div class="flex justify-between"><div><p class="font-bold text-sm">'+(x.user_id||'')+' '+badge+'</p><p class="font-mono text-[11px] mt-1 break-all">'+extra+'</p><p class="text-[11px] text-gray-400 mt-1">متبقي: '+(x.remaining_formatted||'')+' - ينتهي: '+(x.expire_at||'')+'</p></div><div class="flex flex-col gap-1"><a href="/view/'+(x.user_id||'')+'" target="_blank" class="text-center bg-white text-black px-3 py-1.5 rounded-lg text-[11px] font-bold">فتح حسابه</a><button onclick="extendPaid(\\''+(x.user_id||'')+'\\')" class="bg-violet-500 text-white px-3 py-1.5 rounded-lg text-[11px] font-bold">+30 يوم</button><button onclick="deletePaid(\\''+(x.user_id||'')+'\\')" class="bg-red-500/20 text-red-300 px-3 py-1.5 rounded-lg text-[11px]">حذف نهائي</button></div></div></div>'; }); list.innerHTML=h||'<div class="p-6 text-center text-gray-400">لا يوجد مشتركين</div>'; }catch(e){ list.innerHTML='خطأ: '+e.message; } }
async function extendPaid(uid){ if(!confirm('تمديد 30 يوم ل '+uid+' ؟')) return; try{ let res=await fetch('/admin/paid-extend?key='+KEY,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:uid})}); let text=await res.text(); let r; try{ r=JSON.parse(text); }catch{ alert('السيرفر رد: '+text.slice(0,200)); return; } alert(r.message||'تم'); loadPaid(); }catch(e){ alert('خطأ: '+e.message); } }
async function deletePaid(uid){ if(!confirm('حذف اشتراك '+uid+' نهائيا؟')) return; let r=await fetch('/admin/paid-delete?key='+KEY,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:uid})}).then(x=>x.json()); alert(r.message||'تم'); loadPaid(); loadUsdt(); loadUsers(); }
function filterChat(uid){ currentFilter=uid; renderSupportList(); }
function renderSupportList(){ let filtered=currentFilter==='all'?allSupport:allSupport.filter(m=>m.user_id===currentFilter); let h=""; filtered.forEach(function(m){ h+='<div class="bg-black/30 p-3 rounded-xl"><p class="text-[11px] text-gray-500">'+m.user_id+' - '+(m.created_at||'')+'</p><p class="text-sm mt-1">'+(m.message||'')+'</p><div class="flex gap-2 mt-2"><input id="reply-'+m.id+'" placeholder="رد..." class="flex-1 bg-[#0a0a12] border border-white/10 rounded-lg px-2 py-1 text-xs"><button onclick="replySupport(\\''+m.user_id+'\\','+m.id+')" class="bg-white text-black px-3 py-1 rounded-lg text-xs font-bold">رد</button></div></div>'; }); document.getElementById('supportList').innerHTML=h||'لا رسائل'; let groups={}; allSupport.forEach(m=>{ if(!groups[m.user_id]) groups[m.user_id]=[]; groups[m.user_id].push(m); }); let convHtml='<button onclick="filterChat(\\'all\\')" class="'+(currentFilter==='all'?'bg-white text-black':'bg-white/10')+' px-3 py-2 rounded-xl text-xs">الكل</button>'; Object.keys(groups).forEach(function(uid){ convHtml+='<button onclick="filterChat(\\''+uid+'\\')" class="'+(currentFilter===uid?'bg-white text-black':'bg-white/10')+' px-3 py-2 rounded-xl text-xs">'+uid+'</button>'; }); document.getElementById('convList').innerHTML=convHtml;}
async function loadSupport(){ let data=await fetch('/admin/support?key='+KEY).then(r=>r.json()); allSupport=data; renderSupportList(); }
async function replySupport(uid, id){ let txt=document.getElementById('reply-'+id).value.trim(); if(!txt) return; await fetch('/api/support/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:uid, message:txt, sender:'admin'})}); alert('تم الرد'); loadSupport(); }
async function loadDevices(){ let d=await fetch('/admin/devices?key='+KEY).then(r=>r.json()); document.getElementById('deviceCount').innerText=Array.isArray(d)?d.length:0; let h=""; if(Array.isArray(d)) d.forEach(function(x){ h+='<div class="flex justify-between items-center bg-black/20 p-2 rounded-xl"><div><p class="text-xs font-bold">'+x.fingerprint+'</p><p class="text-[11px] text-gray-500">'+x.user_id+' - '+(x.ip_address||'')+'</p></div><button onclick="delDevice(\\''+x.fingerprint+'\\')" class="bg-red-500/20 text-red-300 px-2 py-1 rounded-lg text-[11px]">حذف</button></div>'; }); document.getElementById('deviceList').innerHTML=h||'فارغ'; }
async function delDevice(fp){ await fetch('/admin/devices/delete?key='+KEY, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({fingerprint:fp})}); loadDevices(); }
async function clearDevices(){ if(!confirm('مسح كل الأجهزة؟')) return; await fetch('/admin/devices/clear?key='+KEY, {method:'POST'}); loadDevices(); }
let supportInterval=null; let lastSupportCount=0;
function startLiveChat(){ if(supportInterval) clearInterval(supportInterval); supportInterval=setInterval(async ()=>{ try{ let data=await fetch('/admin/support?key='+KEY).then(r=>r.json()); if(Array.isArray(data) && data.length!==lastSupportCount){ allSupport=data; lastSupportCount=data.length; if(!document.getElementById('view-support').classList.contains('hidden')){ renderSupportList(); } let groups={}; data.forEach(function(m){ if(!groups[m.user_id]) groups[m.user_id]=[]; groups[m.user_id].push(m); }); let totalUnread=0; Object.keys(groups).forEach(function(uid){ let msgs=groups[uid].sort(function(a,b){ return new Date(a.created_at)-new Date(b.created_at); }); let last=msgs[msgs.length-1]; if(last && last.sender==='user'){ totalUnread++; }}); let badge=document.getElementById('supportBadge'); if(totalUnread>0){ badge.innerText=totalUnread; badge.classList.remove('hidden'); } else { badge.classList.add('hidden'); }}}catch(e){}}, 2000);}
showKeyStatus(); loadMadar(); loadUsers(); loadPaid(); startLiveChat(); madarInterval=setInterval(loadMadar, 3000);
</script></body></html>'''
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
