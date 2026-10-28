from flask import Flask, request, jsonify, Response, redirect
from datetime import datetime, timedelta
from supabase import create_client, Client
import os, requests, random, string

app = Flask(__name__)
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
ADMIN_KEY = os.environ.get('ADMIN_KEY', "123456")
ALLOWED_KEYS = [ADMIN_KEY, "123456", "admin123"]
ROOT_WALLET = os.getenv("ROOT_WALLET", "0x2d447f9d656594f6c65de039aebe7da32a968400")
USDT = "0x55d398326f99059fF775485246999027B3196775"
RPC = "https://bsc-dataseed.binance.org/"
TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
DRIVE_NPVT_ID = os.environ.get('DRIVE_NPVT_ID', '1T8zHaaiCEf-Zkgxpz-ig5Q8_5hScsq1I')
FOLDER = 'files'
FILES = ["File.npvt", "File.ssc", "File.nm", "File.hc", "File.ehi", "File.npvs", "File.v2box"]

def amount_for(uid):
    h = abs(hash(str(uid))) % 900 + 100
    return round(1 + h/10000, 4)

def check_payment(uid):
    amt = amount_for(uid); target = int(amt * 10**18)
    try:
        latest = int(requests.post(RPC, json={"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}, timeout=10).json()["result"],16)
        padded = "0x000000000000000000000000" + ROOT_WALLET[2:].lower()
        logs = requests.post(RPC, json={"jsonrpc":"2.0","method":"eth_getLogs","params":[{"fromBlock":hex(latest-15000),"toBlock":"latest","address":USDT,"topics":[TOPIC,None,padded]}],"id":1}, timeout=15).json().get("result",[])
        used = set()
        try: used = {x["tx_hash"] for x in supabase.table("subscriptions").select("tx_hash").execute().data if x.get("tx_hash")}
        except: pass
        for log in logs:
            if int(log["data"],16) >= target and log["transactionHash"] not in used:
                return True, log["transactionHash"], amt
        return False, "no", amt
    except Exception as e: return False, str(e), amt

def get_user(user_id):
    try:
        res = supabase.table("users").select("*").eq("user_id", user_id).execute()
        return res.data[0] if res.data else None
    except:
        return None

def save_user(user):
    try:
        supabase.table("users").upsert(user).execute()
    except Exception as e:
        print("save error", e)

def parse_expire(exp_str):
    if not exp_str: return None
    s = exp_str.replace('Z','').split('.')[0].replace('T',' ')
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except:
        try:
            return datetime.fromisoformat(exp_str.replace('Z','').split('.')[0])
        except:
            return None

def get_remaining_hours(user):
    if not user or not user.get("expires_at"): return 0
    if user.get("status")=="inactive": return 0
    exp = parse_expire(user["expires_at"])
    if not exp: return 0
    return max(0, (exp - datetime.now()).total_seconds()/3600)

def get_remaining_seconds(user):
    return int(get_remaining_hours(user)*3600)

def format_hm(hours_float):
    if hours_float <=0: return "0:00:00"
    total_seconds = int(hours_float*3600)
    h = total_seconds//3600
    m = (total_seconds%3600)//60
    s = total_seconds%60
    if h>=24:
        d=h//24; rh=h%24
        return f"{d} يوم {rh}:{m:02d}:{s:02d}"
    return f"{h}:{m:02d}:{s:02d}"

HOME_HTML = """
<!DOCTYPE html><html dir="rtl" lang="ar"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PREMIUM GATE</title><script src="https://cdn.tailwindcss.com"></script>
<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
<style>@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700;900&display=swap');*{font-family:'Tajawal',sans-serif}
.glass{background:rgba(255,255,255,0.05);backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,0.1)}
.glow{box-shadow:0 0 40px rgba(139,92,246,0.3)}
</style></head>
<body class="bg-[#050507] text-white min-h-screen">
<div class="fixed inset-0 -z-10"><div class="absolute top-0 right-0 w-[600px] h-[600px] bg-purple-600/20 rounded-full blur-[120px]"></div><div class="absolute bottom-0 left-0 w-[600px] h-[600px] bg-emerald-500/15 rounded-full blur-[120px]"></div></div>
<div class="max-w-6xl mx-auto p-4 flex justify-between items-center"><div class="flex items-center gap-2"><div class="w-9 h-9 bg-white rounded-xl flex items-center justify-center text-black font-black">P</div><span class="font-black">PREMIUM GATE</span></div><div class="text-xs text-gray-500">0x2d44...8400 • SECURE</div></div>
<div class="max-w-6xl mx-auto px-4 mt-10 grid lg:grid-cols-2 gap-8 items-center">
<div>
<div class="inline-flex items-center gap-2 glass rounded-full px-4 py-1.5 text-xs text-emerald-300 mb-4"><span class="w-2 h-2 bg-emerald-400 rounded-full animate-pulse"></span> النظام شغال - دخول فوري</div>
<h1 class="text-4xl lg:text-5xl font-black leading-[1.2]">دخولك للمحتوى<br><span class="bg-gradient-to-r from-violet-400 to-emerald-400 bg-clip-text text-transparent">في ثانية واحدة</span></h1>
<p class="text-gray-400 mt-4 text-sm">رابط واحد ينشألك حساب، يعطيك ساعتين مجانا، ويفتحلك صفحة العرض الاحترافية.</p>
<div class="mt-8 flex flex-col gap-3">
<button onclick="checkAndGo()" class="w-full bg-white text-black py-4 rounded-2xl font-black text-center text-lg glow hover:scale-[1.02] transition">🚀 إنشاء حساب ودخول فوري</button>
<div id="limitMsg" class="hidden bg-yellow-900/30 border border-yellow-500/30 rounded-xl p-3 text-center text-sm text-yellow-200"></div>
<div class="flex gap-2 mt-2"><input id="uidInput" placeholder="عندك ID ؟ اكتبه هنا" class="flex-1 bg-[#12121f] border border-white/10 rounded-2xl px-4 py-3.5 text-sm outline-none focus:border-violet-500"><button onclick="goUid()" class="bg-[#1e1e35] border border-white/10 px-6 rounded-2xl font-bold">دخول</button></div>
</div>
<div class="grid grid-cols-3 gap-3 mt-8"><div class="glass rounded-2xl p-4 text-center"><p class="text-2xl font-black text-violet-400">2H</p><p class="text-[11px] text-gray-400">مجانا</p></div><div class="glass rounded-2xl p-4 text-center"><p class="text-2xl font-black text-emerald-400">1$</p><p class="text-[11px] text-gray-400">30 يوم</p></div><div class="glass rounded-2xl p-4 text-center"><p class="text-2xl font-black">∞</p><p class="text-[11px] text-gray-400">تحميل</p></div></div>
</div>
<div class="bg-[#12121f] rounded-[32px] p-2 border border-white/10 shadow-2xl"><div class="bg-black rounded-[24px] p-6"><div class="flex justify-between mb-6"><span class="text-xs text-gray-500">معاينة مباشرة</span><span class="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></span></div><div class="bg-[#12121f] rounded-[20px] p-5 border border-white/5"><div class="flex items-center justify-end gap-2 mb-3"><span>👤</span><span class="font-bold">USER_ID</span></div><p class="text-sm text-right">متبقي: <span id="previewTimer" class="font-bold text-emerald-400">2:00:00</span> : متبقي</p><p class="text-sm text-right">حالة: active : حالة</p><div class="grid grid-cols-2 gap-3 mt-6"><div class="bg-[#8b5cf6] py-3 rounded-xl text-center font-bold text-sm">📁 محتوى</div><div class="bg-[#10b981] py-3 rounded-xl text-center font-bold text-sm text-black">💳 دفع</div></div></div></div></div>
</div>
<div class="max-w-6xl mx-auto px-4 mt-12 grid md:grid-cols-3 gap-4">
<button onclick="checkAndGo()" class="glass rounded-[24px] p-6 hover:border-violet-500/50 hover:scale-[1.02] transition text-right w-full"><div class="w-12 h-12 bg-violet-500/20 rounded-xl flex items-center justify-center text-violet-300 mb-4"><i class="fa-solid fa-bolt"></i></div><h3 class="font-bold">وصول فوري</h3><p class="text-sm text-gray-400 mt-2">يضغط ويدخل طول لصفحته</p><span class="text-xs text-violet-400 mt-3 block">دخول الآن →</span></button>
<a href="/view/demo_user" class="glass rounded-[24px] p-6 hover:border-emerald-500/50 hover:scale-[1.02] transition text-right"><div class="w-12 h-12 bg-emerald-500/20 rounded-xl flex items-center justify-center text-emerald-300 mb-4"><i class="fa-solid fa-shield"></i></div><h3 class="font-bold">حماية متقدمة</h3><p class="text-sm text-gray-400 mt-2">شوف صفحة العرض</p><span class="text-xs text-emerald-400 mt-3 block">عرض تجريبي →</span></a>
<div onclick="openChat()" class="glass rounded-[24px] p-6 hover:border-yellow-500/50 hover:scale-[1.02] transition text-right cursor-pointer"><div class="w-12 h-12 bg-yellow-500/20 rounded-xl flex items-center justify-center text-yellow-300 mb-4"><i class="fa-solid fa-headset"></i></div><h3 class="font-bold">دعم 24/7</h3><p class="text-sm text-gray-400 mt-2">دردشة فورية داخل الموقع</p><span class="text-xs text-yellow-400 mt-3 block">افتح الدردشة →</span></div>
</div>
<div id="chatBtn" onclick="openChat()" class="fixed bottom-6 right-6 w-14 h-14 bg-white rounded-full flex items-center justify-center text-black shadow-2xl cursor-pointer z-50 glow"><i class="fa-solid fa-comments text-xl"></i></div>
<div id="chatBox" class="fixed bottom-24 right-4 w-[360px] max-w-[90vw] bg-[#12121f] border border-white/10 rounded-[20px] shadow-2xl z-50 hidden flex-col overflow-hidden"><div class="bg-[#1e1e35] p-4 flex justify-between items-center"><div><p class="font-bold text-sm">💬 الدعم الفوري</p><p class="text-[11px] text-green-400">● متصل الآن</p></div><button onclick="closeChat()" class="text-gray-400">✕</button></div><div id="chatMsgs" class="flex-1 p-4 space-y-3 overflow-y-auto max-h-[320px] text-sm"><div class="bg-white/5 p-3 rounded-xl text-xs text-gray-300">مرحبا! 👋 انا الدعم، كيف نساعدك؟</div></div><div class="p-3 bg-black/30 flex gap-2"><input id="chatInput" placeholder="اكتب رسالتك..." class="flex-1 bg-[#0a0a12] border border-white/10 rounded-xl px-3 py-2.5 text-sm outline-none"><button onclick="sendMsg()" class="bg-white text-black px-4 rounded-xl font-bold text-sm">ارسال</button></div></div>
<script>
let SUPPORT_UID = localStorage.getItem('support_uid') || "guest_"+Math.floor(Math.random()*99999);
localStorage.setItem('support_uid', SUPPORT_UID);
function goUid(){let v=document.getElementById('uidInput').value.trim(); if(!v){document.getElementById('uidInput').focus();return;} location.href='/view/'+v;}
function openChat(){document.getElementById('chatBox').classList.remove('hidden'); document.getElementById('chatBox').classList.add('flex'); loadMsgs();}
function closeChat(){document.getElementById('chatBox').classList.add('hidden'); document.getElementById('chatBox').classList.remove('flex');}
async function loadMsgs(){
 try{let r=await fetch(`/api/support/get?user_id=${SUPPORT_UID}`).then(x=>x.json());
 let box=document.getElementById('chatMsgs'); let h='<div class="bg-white/5 p-3 rounded-xl text-xs text-gray-300">مرحبا! 👋 انا الدعم، كيف نساعدك؟</div>';
 r.forEach(m=>{if(m.sender==='user') h+=`<div class="bg-white text-black p-3 rounded-2xl ml-10 rounded-br-sm">${m.message}</div>`; else h+=`<div class="bg-[#1e1e35] p-3 rounded-2xl mr-10 rounded-bl-sm border border-white/10">${m.message}</div>`;});
 box.innerHTML=h; box.scrollTop=box.scrollHeight;}catch(e){}
}
HOME_HTML = """
<!DOCTYPE html><html dir="rtl" lang="ar"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PREMIUM GATE</title><script src="https://cdn.tailwindcss.com"></script>
<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
<style>@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700;900&display=swap');*{font-family:'Tajawal',sans-serif}
.glass{background:rgba(255,255,255,0.05);backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,0.1)}
.glow{box-shadow:0 0 40px rgba(139,92,246,0.3)}
</style></head>
<body class="bg-[#050507] text-white min-h-screen">
<div class="fixed inset-0 -z-10"><div class="absolute top-0 right-0 w-[600px] h-[600px] bg-purple-600/20 rounded-full blur-[120px]"></div><div class="absolute bottom-0 left-0 w-[600px] h-[600px] bg-emerald-500/15 rounded-full blur-[120px]"></div></div>
<div class="max-w-6xl mx-auto p-4 flex justify-between items-center"><div class="flex items-center gap-2"><div class="w-9 h-9 bg-white rounded-xl flex items-center justify-center text-black font-black">P</div><span class="font-black">PREMIUM GATE</span></div><div class="text-xs text-gray-500">0x2d44...8400 • SECURE</div></div>
<div class="max-w-6xl mx-auto px-4 mt-10 grid lg:grid-cols-2 gap-8 items-center">
<div>
<div class="inline-flex items-center gap-2 glass rounded-full px-4 py-1.5 text-xs text-emerald-300 mb-4"><span class="w-2 h-2 bg-emerald-400 rounded-full animate-pulse"></span> النظام شغال - دخول فوري</div>
<h1 class="text-4xl lg:text-5xl font-black leading-[1.2]">دخولك للمحتوى<br><span class="bg-gradient-to-r from-violet-400 to-emerald-400 bg-clip-text text-transparent">في ثانية واحدة</span></h1>
<p class="text-gray-400 mt-4 text-sm">رابط واحد ينشألك حساب، يعطيك ساعتين مجانا.</p>
<div class="mt-8 flex flex-col gap-3">
<button onclick="checkAndGo()" class="w-full bg-white text-black py-4 rounded-2xl font-black text-center text-lg glow hover:scale-[1.02] transition">🚀 إنشاء حساب ودخول فوري</button>
<div id="limitMsg" class="hidden bg-yellow-900/30 border border-yellow-500/30 rounded-xl p-3 text-center text-sm text-yellow-200"></div>
<div class="flex gap-2 mt-2"><input id="uidInput" placeholder="عندك ID ؟ اكتبه هنا" class="flex-1 bg-[#12121f] border border-white/10 rounded-2xl px-4 py-3.5 text-sm outline-none focus:border-violet-500"><button onclick="goUid()" class="bg-[#1e1e35] border border-white/10 px-6 rounded-2xl font-bold">دخول</button></div>
</div>
<div class="grid grid-cols-3 gap-3 mt-8"><div class="glass rounded-2xl p-4 text-center"><p class="text-2xl font-black text-violet-400">2H</p><p class="text-[11px] text-gray-400">مجانا</p></div><div class="glass rounded-2xl p-4 text-center"><p class="text-2xl font-black text-emerald-400">1$</p><p class="text-[11px] text-gray-400">30 يوم</p></div><div class="glass rounded-2xl p-4 text-center"><p class="text-2xl font-black">∞</p><p class="text-[11px] text-gray-400">تحميل</p></div></div>
</div>
<div class="bg-[#12121f] rounded-[32px] p-2 border border-white/10 shadow-2xl"><div class="bg-black rounded-[24px] p-6"><div class="flex justify-between mb-6"><span class="text-xs text-gray-500">معاينة حسابك الحقيقي</span><span class="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></span></div><div class="bg-[#12121f] rounded-[20px] p-5 border border-white/5"><div class="flex items-center justify-end gap-2 mb-3"><span>👤</span><span id="previewUid" class="font-bold">--</span></div><p class="text-sm text-right">متبقي: <span id="previewTimer" class="font-bold text-emerald-400">--:--:--</span> : متبقي</p><p class="text-sm text-right">حالة: <span id="previewStatus">active</span> : حالة</p><div class="grid grid-cols-2 gap-3 mt-6"><button onclick="openRealContent()" class="bg-[#8b5cf6] py-3 rounded-xl text-center font-bold text-sm">📁 محتوى</button><button onclick="openRealPay()" class="bg-[#10b981] py-3 rounded-xl text-center font-bold text-sm text-black">💳 دفع</button></div></div></div></div>
</div>
<div id="chatBtn" onclick="openChat()" class="fixed bottom-6 right-6 w-14 h-14 bg-white rounded-full flex items-center justify-center text-black shadow-2xl cursor-pointer z-50 glow"><i class="fa-solid fa-comments text-xl"></i></div>
<div id="chatBox" class="fixed bottom-24 right-4 w-[360px] max-w-[90vw] bg-[#12121f] border border-white/10 rounded-[20px] shadow-2xl z-50 hidden flex-col overflow-hidden"><div class="bg-[#1e1e35] p-4 flex justify-between items-center"><div><p class="font-bold text-sm">💬 الدعم الفوري</p><p class="text-[11px] text-green-400">● متصل الآن</p></div><button onclick="closeChat()" class="text-gray-400">✕</button></div><div id="chatMsgs" class="flex-1 p-4 space-y-3 overflow-y-auto max-h-[320px] text-sm"><div class="bg-white/5 p-3 rounded-xl text-xs text-gray-300">مرحبا! 👋</div></div><div class="p-3 bg-black/30 flex gap-2"><input id="chatInput" placeholder="اكتب رسالتك..." class="flex-1 bg-[#0a0a12] border border-white/10 rounded-xl px-3 py-2.5 text-sm outline-none"><button onclick="sendMsg()" class="bg-white text-black px-4 rounded-xl font-bold text-sm">ارسال</button></div></div>
<script>
let SUPPORT_UID = localStorage.getItem('support_uid') || "guest_"+Math.floor(Math.random()*99999);
localStorage.setItem('support_uid', SUPPORT_UID);
function goUid(){let v=document.getElementById('uidInput').value.trim(); if(!v)return; location.href='/view/'+v;}
function openChat(){document.getElementById('chatBox').classList.remove('hidden'); document.getElementById('chatBox').classList.add('flex'); loadMsgs();}
function closeChat(){document.getElementById('chatBox').classList.add('hidden'); document.getElementById('chatBox').classList.remove('flex');}
async function loadMsgs(){ try{let r=await fetch(`/api/support/get?user_id=${SUPPORT_UID}`).then(x=>x.json()); let box=document.getElementById('chatMsgs'); let h='<div class="bg-white/5 p-3 rounded-xl text-xs text-gray-300">مرحبا! 👋</div>'; r.forEach(m=>{if(m.sender==='user') h+=`<div class="bg-white text-black p-3 rounded-2xl ml-10 rounded-br-sm">${m.message}</div>`; else h+=`<div class="bg-[#1e1e35] p-3 rounded-2xl mr-10 rounded-bl-sm border border-white/10">${m.message}</div>`;}); box.innerHTML=h; box.scrollTop=box.scrollHeight;}catch(e){}}
async function sendMsg(){ let inp=document.getElementById('chatInput'); let txt=inp.value.trim(); if(!txt) return; await fetch('/api/support/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:SUPPORT_UID,message:txt,sender:'user'})}); inp.value=''; loadMsgs(); }

function openRealContent(){ let id=localStorage.getItem('my_user_id'); if(id) location.href='/content/'+id; else alert('ما عندكش حساب، دير انشاء اول'); }
function openRealPay(){ let id=localStorage.getItem('my_user_id'); if(id) location.href='/pay/'+id; else alert('ما عندكش حساب، دير انشاء اول'); }

async function loadPreview(){
  let myId = localStorage.getItem('my_user_id');
  let uidEl = document.getElementById('previewUid');
  let timerEl = document.getElementById('previewTimer');
  let statusEl = document.getElementById('previewStatus');
  if(!myId){
    uidEl.innerText = "ما عندكش حساب";
    timerEl.innerText = "0:00:00";
    return;
  }
  uidEl.innerText = myId;
  try{
    let c = await fetch(`/check?user_id=${myId}`).then(r=>r.json());
HOME_HTML = """
<!DOCTYPE html><html dir="rtl" lang="ar"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PREMIUM GATE</title><script src="https://cdn.tailwindcss.com"></script>
<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
<style>@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700;900&display=swap');*{font-family:'Tajawal',sans-serif}
.glass{background:rgba(255,255,255,0.05);backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,0.1)}
.glow{box-shadow:0 0 40px rgba(139,92,246,0.3)}
</style></head>
<body class="bg-[#050507] text-white min-h-screen">
<div class="fixed inset-0 -z-10"><div class="absolute top-0 right-0 w-[600px] h-[600px] bg-purple-600/20 rounded-full blur-[120px]"></div><div class="absolute bottom-0 left-0 w-[600px] h-[600px] bg-emerald-500/15 rounded-full blur-[120px]"></div></div>
<div class="max-w-6xl mx-auto p-4 flex justify-between items-center"><div class="flex items-center gap-2"><div class="w-9 h-9 bg-white rounded-xl flex items-center justify-center text-black font-black">P</div><span class="font-black">PREMIUM GATE</span></div><div class="text-xs text-gray-500">0x2d44...8400 • SECURE</div></div>
<div class="max-w-6xl mx-auto px-4 mt-10 grid lg:grid-cols-2 gap-8 items-center">
<div>
<div class="inline-flex items-center gap-2 glass rounded-full px-4 py-1.5 text-xs text-emerald-300 mb-4"><span class="w-2 h-2 bg-emerald-400 rounded-full animate-pulse"></span> النظام شغال - دخول فوري</div>
<h1 class="text-4xl lg:text-5xl font-black leading-[1.2]">دخولك للمحتوى<br><span class="bg-gradient-to-r from-violet-400 to-emerald-400 bg-clip-text text-transparent">في ثانية واحدة</span></h1>
<p class="text-gray-400 mt-4 text-sm">رابط واحد ينشألك حساب، يعطيك ساعتين مجانا.</p>
<div class="mt-8 flex flex-col gap-3">
<button onclick="checkAndGo()" class="w-full bg-white text-black py-4 rounded-2xl font-black text-center text-lg glow hover:scale-[1.02] transition">🚀 إنشاء حساب ودخول فوري</button>
<div id="limitMsg" class="hidden bg-yellow-900/30 border border-yellow-500/30 rounded-xl p-3 text-center text-sm text-yellow-200"></div>
<div class="flex gap-2 mt-2"><input id="uidInput" placeholder="عندك ID ؟ اكتبه هنا" class="flex-1 bg-[#12121f] border border-white/10 rounded-2xl px-4 py-3.5 text-sm outline-none focus:border-violet-500"><button onclick="goUid()" class="bg-[#1e1e35] border border-white/10 px-6 rounded-2xl font-bold">دخول</button></div>
</div>
<div class="grid grid-cols-3 gap-3 mt-8"><div class="glass rounded-2xl p-4 text-center"><p class="text-2xl font-black text-violet-400">2H</p><p class="text-[11px] text-gray-400">مجانا</p></div><div class="glass rounded-2xl p-4 text-center"><p class="text-2xl font-black text-emerald-400">1$</p><p class="text-[11px] text-gray-400">30 يوم</p></div><div class="glass rounded-2xl p-4 text-center"><p class="text-2xl font-black">∞</p><p class="text-[11px] text-gray-400">تحميل</p></div></div>
</div>
<div class="bg-[#12121f] rounded-[32px] p-2 border border-white/10 shadow-2xl"><div class="bg-black rounded-[24px] p-6"><div class="flex justify-between mb-6"><span class="text-xs text-gray-500">معاينة حسابك الحقيقي</span><span class="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></span></div><div class="bg-[#12121f] rounded-[20px] p-5 border border-white/5"><div class="flex items-center justify-end gap-2 mb-3"><span>👤</span><span id="previewUid" class="font-bold">--</span></div><p class="text-sm text-right">متبقي: <span id="previewTimer" class="font-bold text-emerald-400">--:--:--</span> : متبقي</p><p class="text-sm text-right">حالة: <span id="previewStatus">active</span> : حالة</p><div class="grid grid-cols-2 gap-3 mt-6"><button onclick="openRealContent()" class="bg-[#8b5cf6] py-3 rounded-xl text-center font-bold text-sm">📁 محتوى</button><button onclick="openRealPay()" class="bg-[#10b981] py-3 rounded-xl text-center font-bold text-sm text-black">💳 دفع</button></div></div></div></div>
</div>
<div id="chatBtn" onclick="openChat()" class="fixed bottom-6 right-6 w-14 h-14 bg-white rounded-full flex items-center justify-center text-black shadow-2xl cursor-pointer z-50 glow"><i class="fa-solid fa-comments text-xl"></i></div>
<div id="chatBox" class="fixed bottom-24 right-4 w-[360px] max-w-[90vw] bg-[#12121f] border border-white/10 rounded-[20px] shadow-2xl z-50 hidden flex-col overflow-hidden"><div class="bg-[#1e1e35] p-4 flex justify-between items-center"><div><p class="font-bold text-sm">💬 الدعم الفوري</p><p class="text-[11px] text-green-400">● متصل الآن</p></div><button onclick="closeChat()" class="text-gray-400">✕</button></div><div id="chatMsgs" class="flex-1 p-4 space-y-3 overflow-y-auto max-h-[320px] text-sm"><div class="bg-white/5 p-3 rounded-xl text-xs text-gray-300">مرحبا! 👋</div></div><div class="p-3 bg-black/30 flex gap-2"><input id="chatInput" placeholder="اكتب رسالتك..." class="flex-1 bg-[#0a0a12] border border-white/10 rounded-xl px-3 py-2.5 text-sm outline-none"><button onclick="sendMsg()" class="bg-white text-black px-4 rounded-xl font-bold text-sm">ارسال</button></div></div>
<script>
let SUPPORT_UID = localStorage.getItem('support_uid') || "guest_"+Math.floor(Math.random()*99999);
localStorage.setItem('support_uid', SUPPORT_UID);
function goUid(){let v=document.getElementById('uidInput').value.trim(); if(!v)return; location.href='/view/'+v;}
function openChat(){document.getElementById('chatBox').classList.remove('hidden'); document.getElementById('chatBox').classList.add('flex'); loadMsgs();}
function closeChat(){document.getElementById('chatBox').classList.add('hidden'); document.getElementById('chatBox').classList.remove('flex');}
async function loadMsgs(){ try{let r=await fetch('/api/support/get?user_id='+SUPPORT_UID).then(x=>x.json()); let box=document.getElementById('chatMsgs'); let h='<div class="bg-white/5 p-3 rounded-xl text-xs text-gray-300">مرحبا! 👋</div>'; r.forEach(m=>{if(m.sender==='user') h+='<div class="bg-white text-black p-3 rounded-2xl ml-10 rounded-br-sm">'+m.message+'</div>'; else h+='<div class="bg-[#1e1e35] p-3 rounded-2xl mr-10 rounded-bl-sm border border-white/10">'+m.message+'</div>';}); box.innerHTML=h; box.scrollTop=box.scrollHeight;}catch(e){}}
async function sendMsg(){ let inp=document.getElementById('chatInput'); let txt=inp.value.trim(); if(!txt) return; await fetch('/api/support/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:SUPPORT_UID,message:txt,sender:'user'})}); inp.value=''; loadMsgs(); }
function openRealContent(){ let id=localStorage.getItem('my_user_id'); if(id) location.href='/content/'+id; else alert('ما عندكش حساب'); }
function openRealPay(){ let id=localStorage.getItem('my_user_id'); if(id) location.href='/pay/'+id; else alert('ما عندكش حساب'); }
async function loadPreview(){
  let myId = localStorage.getItem('my_user_id');
  let uidEl = document.getElementById('previewUid');
  let timerEl = document.getElementById('previewTimer');
  let statusEl = document.getElementById('previewStatus');
  if(!myId){ uidEl.innerText = "ما عندكش حساب"; timerEl.innerText = "0:00:00"; return; }
  uidEl.innerText = myId;
  try{
    let c = await fetch('/check?user_id='+myId).then(r=>r.json());
    statusEl.innerText = c.status;
    let rem = c.hours || "0:00:00";
    timerEl.innerText = rem;
    let parts = rem.split(':');
    let sec = 0;
    if(parts.length===3){ sec = parseInt(parts[0])*3600 + parseInt(parts[1])*60 + parseInt(parts[2]); }
    setInterval(function(){
      if(sec<=0) return;
      sec--;
      let h=Math.floor(sec/3600), m=Math.floor((sec%3600)/60), s=sec%60;
      timerEl.innerText = h+":"+String(m).padStart(2,'0')+":"+String(s).padStart(2,'0');
    },1000);
  }catch(e){ timerEl.innerText = "خطأ"; }
}
loadPreview();
async function getFingerprint(){
  let s = navigator.userAgent + '|' + screen.width + 'x' + screen.height + '|' + Intl.DateTimeFormat().resolvedOptions().timeZone + '|' + navigator.language;
  let hash = 0; for(let i=0;i<s.length;i++){ hash = ((hash<<5)-hash)+s.charCodeAt(i); hash|=0; }
  return 'fp_'+Math.abs(hash);
}
async function checkAndGo(){
  let fp = await getFingerprint();
  localStorage.setItem('my_fp', fp);
  let savedId = localStorage.getItem('my_user_id');
  let lastTime = localStorage.getItem('last_go_time');
  if(savedId && lastTime){
    let diff = (Date.now() - parseInt(lastTime)) / (1000*60*60);
    if(diff < 24){ location.href='/view/'+savedId; return; }
  }
  location.href='/go?fp='+fp;
}
</script></body></html>
"""

def render_view(user_id, remaining_sec, rem_initial, status):
    html = """
<!DOCTYPE html><html dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>__USERID__</title><script src="https://cdn.tailwindcss.com"></script></head><body class="bg-black min-h-screen p-4"><div class="max-w-md mx-auto mt-10 bg-[#12121f] rounded-[24px] p-6 border border-white/10"><div class="text-right"><p class="text-white">متبقي: <span id="countdown" class="font-black text-emerald-400 text-lg">__REM__</span> : متبقي</p><p class="text-white mt-1">حالة: __STATUS__</p><p id="expiredMsg" class="hidden mt-3 bg-red-900/30 border border-red-500/30 rounded-xl p-3 text-center text-sm text-red-300">⏰ انتهى وقتك</p></div><div class="grid grid-cols-2 gap-3 mt-8"><a href="/content/__USERID__" class="bg-[#8b5cf6] text-white py-3.5 rounded-xl text-center font-bold">📁 محتوى</a><a href="/pay/__USERID__" class="bg-[#10b981] text-black py-3.5 rounded-xl text-center font-bold">💳 دفع</a></div></div>
<script>
localStorage.setItem('my_user_id', '__USERID__');
localStorage.setItem('last_go_time', Date.now().toString());
let remaining = __SEC__;
let el = document.getElementById('countdown');
let expMsg = document.getElementById('expiredMsg');
function formatHM(sec){
    if(sec<=0) return "0:00:00";
    let h=Math.floor(sec/3600); let m=Math.floor((sec%3600)/60); let s=sec%60;
    return h+":"+String(m).padStart(2,'0')+":"+String(s).padStart(2,'0');
}
function tick(){
    if(remaining<=0){ el.innerText="0:00:00"; el.classList.add('text-red-400'); expMsg.classList.remove('hidden'); return; }
    el.innerText=formatHM(remaining);
    remaining--;
    setTimeout(tick,1000);
}
tick();
</script></body></html>
"""
    return html.replace("__USERID__", user_id).replace("__REM__", rem_initial).replace("__STATUS__", status).replace("__SEC__", str(remaining_sec))

PAY_HTML = """<!DOCTYPE html><html dir="rtl" lang="ar"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>الدفع الآمن</title><script src="https://cdn.tailwindcss.com"></script></head><body class="bg-[#0a0a12] min-h-screen flex items-center justify-center p-4"><div class="w-full max-w-md"><div class="bg-[#1e1e35] rounded-[24px] p-6 border border-white/10"><h1 class="text-xl font-bold text-white text-center">الدفع الآمن - BSC</h1><div class="bg-black/40 rounded-2xl p-4 mt-4"><div id="amt" class="text-3xl font-bold text-emerald-400 text-center">-- USDT</div></div><div class="bg-black/40 rounded-2xl p-4 mt-4"><p class="text-xs text-gray-400">عنوان المحفظة</p><div class="bg-[#0a0a12] p-3 rounded-xl font-mono text-[11px] break-all text-white mt-2">__WALLET__</div></div><button onclick="verify()" id="btn" class="w-full bg-emerald-500 text-black py-4 rounded-xl font-bold mt-4">لقد دفعت، فعل حسابي</button><div id="status" class="mt-4 text-center text-sm text-white"></div><div class="text-center mt-3"><a id="toContent" class="text-xs text-gray-400 underline">عرض المحتوى</a></div></div></div>
<script>
let AMT=0,UID="__UID__";
async function init(){let r=await fetch(`/amount/${UID}`).then(x=>x.json());AMT=r.amount;document.getElementById('amt').innerText=AMT+' USDT';document.getElementById('toContent').href=`/content/${UID}`;}
async function verify(){let b=document.getElementById('btn'),s=document.getElementById('status');b.innerHTML="⏳ جاري التحقق...";b.disabled=true;try{let r=await fetch(`/verify/${UID}`).then(x=>x.json());if(r.paid){s.innerHTML="✅ تم التفعيل";setTimeout(()=>location.href=`/content/${UID}`,1500);}else{s.innerHTML=`❌ لم يتم العثور`;b.disabled=false;b.innerHTML="لقد دفعت، فعل حسابي";}}catch(e){s.innerText="خطأ";b.disabled=false;}}
init();
</script></body></html>"""

CONTENT_HTML = """<!DOCTYPE html><html dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>مكتبتي</title><script src="https://cdn.tailwindcss.com"></script></head><body class="bg-[#080810] min-h-screen p-4"><div class="max-w-3xl mx-auto"><div class="flex justify-between items-center mb-6"><h1 class="text-xl font-bold text-white">📁 مكتبتك - __UID__</h1><span id="time" class="bg-[#1e1e35] px-3 py-1 rounded-full text-xs text-white"></span></div><div id="list" class="space-y-3"></div></div>
<script>
const UID="__UID__";
async function load(){
  let c=await fetch(`/check?user_id=${UID}`).then(r=>r.json());
  document.getElementById('time').innerText=c.hours||'';
  if(c.status!=='active'){
    document.getElementById('list').innerHTML=`<div class='bg-[#1e1e35] p-6 rounded-[24px] text-center'><p class='text-white'>${c.message||'انتهى وقتك'}</p><a href='/pay/${UID}' class='mt-6 inline-block w-full bg-emerald-500 text-black py-3 rounded-xl font-bold'>💳 ادفع للتجديد</a></div>`;
    return;
  }
  let h="";c.files.forEach(f=>{h+=`<div class='bg-[#12121f] border border-white/5 rounded-2xl p-4 flex justify-between items-center'><p class='font-bold text-white'>${f}</p><button onclick="location.href='/download/${f}?user_id=${UID}'" class='bg-white text-black px-4 py-2 rounded-xl text-sm font-bold'>تحميل</button></div>`;});
  document.getElementById('list').innerHTML=h;
}
load();
</script></body></html>"""

ADMIN_HTML = """<!DOCTYPE html><html dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Admin</title><script src="https://cdn.tailwindcss.com"></script></head><body class="bg-[#080810] text-white min-h-screen p-4"><div class="max-w-7xl mx-auto"><h1 class="text-2xl font-bold mb-6">لوحة التحكم</h1><div id="tb"></div></div><script>const KEY=new URLSearchParams(location.search).get("key");async function load(){let u=await fetch(`/admin/users?key=${KEY}`).then(r=>r.json());let h="";u.forEach(x=>{h+=`<div class='p-2 border-b border-white/10 flex justify-between'><span>${x.user_id} - ${x.remaining}</span><span>${x.raw_status}</span></div>`});document.getElementById('tb').innerHTML=h}load();</script></body></html>"""

@app.route('/')
def home(): return Response(HOME_HTML, mimetype='text/html')

@app.route('/go')
def go():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    fp = request.args.get('fp','').strip() or request.cookies.get('device_fp','').strip()
    
    if fp and fp.startswith('fp_'):
        try:
            res = supabase.table("device_limits").select("*").eq("fingerprint", fp).execute()
            if res.data:
                row = res.data[0]
                created = parse_expire(row.get("created_at",""))
                if created and (datetime.now() - created).total_seconds() / 3600 < 24:
                    return redirect(f"/view/{row['user_id']}")
        except: pass

    last_uid = request.cookies.get('last_user_id')
    if last_uid:
        u = get_user(last_uid)
        if u:
            exp = parse_expire(u.get("expires_at",""))
            if exp:
                created = exp - timedelta(hours=2)
                if (datetime.now() - created).total_seconds() / 3600 < 24 and u.get("status")!="inactive":
                    return redirect(f"/view/{last_uid}")

    uid = 'user_' + ''.join(random.choices(string.digits, k=6))
    exp = datetime.now() + timedelta(hours=2)
    user = {"user_id": uid, "expires_at": exp.strftime("%Y-%m-%d %H:%M:%S"), "status": "active", "ip_address": ip}
    save_user(user)

    if fp and fp.startswith('fp_'):
        try:
            supabase.table("device_limits").upsert({"fingerprint": fp, "user_id": uid, "ip_address": ip, "created_at": datetime.now().isoformat()}).execute()
        except: pass

    resp = redirect(f"/view/{uid}")
    if fp:
        resp.set_cookie('device_fp', fp, max_age=86400*30, samesite='Lax')
    resp.set_cookie('last_user_id', uid, max_age=86400, samesite='Lax')
    return resp

@app.route('/view/<user_id>')
def view_user(user_id):
    u = get_user(user_id)
    if not u:
        exp = datetime.now() + timedelta(hours=2)
        u = {"user_id": user_id, "expires_at": exp.strftime("%Y-%m-%d %H:%M:%S"), "status": "active"}
        save_user(u)
    remaining_sec = get_remaining_seconds(u)
    rem_initial = format_hm(get_remaining_hours(u)) if u.get("status")!="inactive" else "معطل"
    status = u.get("status", "active")
    html = f"""<!DOCTYPE html><html dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{user_id}</title><script src="https://cdn.tailwindcss.com"></script></head><body class="bg-black min-h-screen p-4"><div class="max-w-md mx-auto mt-10 bg-[#12121f] rounded-[24px] p-6 border border-white/10"><div class="text-right"><p class="text-white">متبقي: <span id="countdown" class="font-black text-emerald-400 text-lg">{rem_initial}</span> : متبقي</p><p class="text-white mt-1">حالة: {status}</p><p id="expiredMsg" class="hidden mt-3 bg-red-900/30 border border-red-500/30 rounded-xl p-3 text-center text-sm text-red-300">⏰ انتهى وقتك</p></div><div class="grid grid-cols-2 gap-3 mt-8"><a href="/content/{user_id}" class="bg-[#8b5cf6] text-white py-3.5 rounded-xl text-center font-bold">📁 محتوى</a><a href="/pay/{user_id}" class="bg-[#10b981] text-black py-3.5 rounded-xl text-center font-bold">💳 دفع</a></div></div>
    <script>
    localStorage.setItem('my_user_id', '{user_id}');
    localStorage.setItem('last_go_time', Date.now().toString());
    let remaining = {remaining_sec};
    let el = document.getElementById('countdown');
    let expMsg = document.getElementById('expiredMsg');
    function formatHM(sec){{
        if(sec<=0) return "0:00:00";
        let h=Math.floor(sec/3600); let m=Math.floor((sec%3600)/60); let s=sec%60;
        return h+":"+String(m).padStart(2,'0')+":"+String(s).padStart(2,'0');
    }}
    function tick(){{
        if(remaining<=0){{ el.innerText="0:00:00"; el.classList.add('text-red-400'); expMsg.classList.remove('hidden'); return; }}
        el.innerText=formatHM(remaining);
        remaining--;
        setTimeout(tick,1000);
    }}
    tick();
    </script></body></html>"""
    return Response(html, mimetype='text/html')

@app.route('/pay/<user_id>')
def pay_page(user_id): return Response(PAY_HTML.replace("__WALLET__", ROOT_WALLET).replace("__UID__", user_id), mimetype='text/html')
@app.route('/content/<user_id>')
def content_page(user_id): return Response(CONTENT_HTML.replace("__UID__", user_id), mimetype='text/html')
@app.route('/amount/<user_id>')
def amount_api(user_id): return jsonify({"amount": amount_for(user_id), "wallet": ROOT_WALLET})
@app.route('/api/files')
def api_files(): return jsonify([{"id":f,"name":f} for f in FILES])

@app.route('/api/support/send', methods=['POST'])
def support_send():
    data = request.json
    supabase.table("support_messages").insert({"user_id": data.get("user_id","guest"),"message": data.get("message"),"sender": data.get("sender","user")}).execute()
    return jsonify({"ok":True})
@app.route('/api/support/get')
def support_get():
    uid = request.args.get("user_id","guest")
    try:
        res = supabase.table("support_messages").select("*").eq("user_id", uid).order("created_at").limit(50).execute()
        return jsonify(res.data)
    except: return jsonify([])

@app.route('/verify/<user_id>')
def verify_api(user_id):
    ok, tx, amt = check_payment(user_id)
    if ok:
        exp = datetime.now() + timedelta(days=30)
        user=get_user(user_id)
        if not user: user={"user_id":user_id}
        user["expires_at"]=exp.strftime("%Y-%m-%d %H:%M:%S"); user["status"]="active"; save_user(user)
        try: supabase.table("subscriptions").upsert({"user_id":user_id,"expire_at":exp.isoformat(),"is_paid":True,"tx_hash":tx,"amount_paid":amt}).execute()
        except: pass
        return jsonify({"paid":True})
    return jsonify({"paid":False,"amount":amt})

@app.route('/check', methods=['GET'])
def check():
    user_id = request.args.get('user_id')
    if not user_id: return jsonify({"error": "user_id missing"}), 400
    now = datetime.now(); user = get_user(user_id)
    base_url = request.host_url
    links = [f"{base_url}download/{f}?user_id={user_id}" for f in FILES]
    if not user:
        expires = now + timedelta(hours=2)
        user = {"user_id": user_id, "expires_at": expires.strftime("%Y-%m-%d %H:%M:%S"), "status": "active"}
        save_user(user)
        return jsonify({"status": "active", "links": links, "files": FILES, "hours": "2:00:00"})
    if user.get("status")=="inactive":
        return jsonify({"status": "disabled", "message": "تم تعطيل حسابك", "hours": "معطل", "files": FILES})
    remaining = get_remaining_hours(user)
    if remaining <= 0:
        last_expire = parse_expire(user["expires_at"])
        if not last_expire: last_expire = now
        hours_since_expire = (now - last_expire).total_seconds() / 3600
        if hours_since_expire >= 24:
            new_expire = now + timedelta(hours=2)
            user["expires_at"] = new_expire.strftime("%Y-%m-%d %H:%M:%S"); user["status"]="active"; save_user(user)
            return jsonify({"status": "active", "links": links, "files": FILES, "hours": "2:00:00"})
        else:
            remaining_cooldown = 24 - hours_since_expire
            return jsonify({"status": "cooldown", "message": f"انتهى - انتظر {format_hm(remaining_cooldown)} او ادفع", "hours": format_hm(remaining_cooldown), "files": FILES})
    return jsonify({"status": "active", "links": links, "files": FILES, "hours": format_hm(remaining)})

@app.route('/download/<filename>')
def download(filename):
    user_id = request.args.get('user_id')
    if not user_id: return "user_id missing", 400
    user = get_user(user_id)
    if not user: return redirect(f"/pay/{user_id}")
    if user.get("status")=="inactive": return Response("🚫 معطل", 403)
    if get_remaining_hours(user) <= 0: return redirect(f"/pay/{user_id}")
    if filename not in FILES: return "not allowed", 403
    if filename == "File.npvt":
        gdrive_url = f"https://drive.google.com/uc?export=download&id={DRIVE_NPVT_ID}"
        r = requests.get(gdrive_url, stream=True, timeout=30)
        return Response(r.iter_content(chunk_size=8192), mimetype='application/octet-stream', headers={"Content-Disposition": f"attachment;filename={filename}"})
    file_path = os.path.join(FOLDER, filename)
    if not os.path.exists(file_path): return f"File {filename} not found", 404
    with open(file_path, 'rb') as f: data = f.read()
    return Response(data, mimetype='application/octet-stream', headers={"Content-Disposition": f"attachment;filename={filename}"})

@app.route("/admin")
def admin():
    if request.args.get("key") not in ALLOWED_KEYS: return Response("401",401)
    return Response(ADMIN_HTML.replace("__KEY__", request.args.get("key","")), mimetype='text/html')

@app.route("/admin/users")
def a_users():
    if request.args.get("key") not in ALLOWED_KEYS: return jsonify({"error":"no"}),401
    users = supabase.table("users").select("*").order("expires_at",desc=True).limit(200).execute().data
    out=[]
    for u in users:
        raw_status=u.get("status","active")
        is_paid = raw_status!="inactive" and get_remaining_hours(u)>0
        rem = format_hm(get_remaining_hours(u)) if raw_status!="inactive" else "معطل"
        out.append({"user_id":u["user_id"],"expire_at":u["expires_at"],"remaining":rem,"raw_status":raw_status, "is_paid": is_paid})
    return jsonify(out)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
