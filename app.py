from flask import Flask, request, jsonify, Response, redirect
from datetime import datetime, timedelta
from supabase import create_client, Client
import os, requests, random, string

app = Flask(__name__)
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
ADMIN_KEY = os.environ.get('ADMIN_KEY', "123456")
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
    res = supabase.table("users").select("*").eq("user_id", user_id).execute()
    return res.data[0] if res.data else None
def save_user(user): supabase.table("users").upsert(user).execute()
def get_remaining_hours(user):
    if not user or not user.get("expires_at"): return 0
    if user.get("status")=="inactive": return 0
    try:
        expires = datetime.strptime(user["expires_at"], "%Y-%m-%d %H:%M:%S")
        return max(0, (expires - datetime.now()).total_seconds()/3600)
    except: return 0
def get_remaining_seconds(user):
    return int(get_remaining_hours(user)*3600)
def format_hm(hours_float):
    total_minutes=int(round(hours_float*60)); h=total_minutes//60; m=total_minutes%60
    if h>=24: d=h//24; rh=h%24; return f"{d} day {rh}:{m:02d}" if d==1 else f"{d} days {rh}:{m:02d}"
    return f"{h}:{m:02d}"

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
<a href="/go" class="w-full bg-white text-black py-4 rounded-2xl font-black text-center text-lg glow hover:scale-[1.02] transition">🚀 إنشاء حساب ودخول فوري</a>
<div class="flex gap-2"><input id="uidInput" placeholder="عندك ID ؟ اكتبه هنا" class="flex-1 bg-[#12121f] border border-white/10 rounded-2xl px-4 py-3.5 text-sm outline-none focus:border-violet-500"><button onclick="goUid()" class="bg-[#1e1e35] border border-white/10 px-6 rounded-2xl font-bold">دخول</button></div>
</div>
<div class="grid grid-cols-3 gap-3 mt-8"><div class="glass rounded-2xl p-4 text-center"><p class="text-2xl font-black text-violet-400">2H</p><p class="text-[11px] text-gray-400">مجانا</p></div><div class="glass rounded-2xl p-4 text-center"><p class="text-2xl font-black text-emerald-400">1$</p><p class="text-[11px] text-gray-400">30 يوم</p></div><div class="glass rounded-2xl p-4 text-center"><p class="text-2xl font-black">∞</p><p class="text-[11px] text-gray-400">تحميل</p></div></div>
</div>
<div class="bg-[#12121f] rounded-[32px] p-2 border border-white/10 shadow-2xl"><div class="bg-black rounded-[24px] p-6"><div class="flex justify-between mb-6"><span class="text-xs text-gray-500">معاينة مباشرة</span><span class="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></span></div><div class="bg-[#12121f] rounded-[20px] p-5 border border-white/5"><div class="flex items-center justify-end gap-2 mb-3"><span>👤</span><span class="font-bold">USER_ID</span></div><p class="text-sm text-right">متبقي: <span id="previewTimer" class="font-bold text-emerald-400">2:00:00</span> : متبقي</p><p class="text-sm text-right">حالة: active : حالة</p><div class="grid grid-cols-2 gap-3 mt-6"><div class="bg-[#8b5cf6] py-3 rounded-xl text-center font-bold text-sm">📁 محتوى</div><div class="bg-[#10b981] py-3 rounded-xl text-center font-bold text-sm text-black">💳 دفع</div></div></div></div></div>
</div>
<div class="max-w-6xl mx-auto px-4 mt-12 grid md:grid-cols-3 gap-4">
<a href="/go" class="glass rounded-[24px] p-6 hover:border-violet-500/50 hover:scale-[1.02] transition text-right"><div class="w-12 h-12 bg-violet-500/20 rounded-xl flex items-center justify-center text-violet-300 mb-4"><i class="fa-solid fa-bolt"></i></div><h3 class="font-bold">وصول فوري</h3><p class="text-sm text-gray-400 mt-2">يضغط ويدخل طول لصفحته</p><span class="text-xs text-violet-400 mt-3 block">دخول الآن →</span></a>
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
async function sendMsg(){
 let inp=document.getElementById('chatInput'); let txt=inp.value.trim(); if(!txt) return;
 await fetch('/api/support/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:SUPPORT_UID,message:txt,sender:'user'})});
 inp.value=''; loadMsgs();
}
document.getElementById('chatInput')?.addEventListener('keydown',e=>{if(e.key==='Enter') sendMsg();});
let pt=7200;
setInterval(()=>{
  if(pt<=0) return;
  pt--;
  let h=Math.floor(pt/3600), m=Math.floor((pt%3600)/60), s=pt%60;
  let el=document.getElementById('previewTimer');
  if(el) el.innerText=h+":"+String(m).padStart(2,'0')+":"+String(s).padStart(2,'0');
},1000);
</script></body></html>
"""

ADMIN_SUPPORT_HTML = """
<!DOCTYPE html><html dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>دعم فوري</title><script src="https://cdn.tailwindcss.com"></script><style>@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');*{font-family:'Tajawal',sans-serif}</style></head><body class="bg-[#050507] text-white min-h-screen flex flex-col">
<div class="bg-[#12121f] p-4 border-b border-white/10 flex justify-between items-center"><h1 class="font-bold">💬 مركز الدعم - 0x2d44...8400 - التفعيل تلقائي بالدفع</h1><a id="backLink" class="text-xs text-gray-400 underline">رجوع للادمن</a></div>
<div class="flex flex-1 overflow-hidden"><div class="w-[300px] bg-[#0a0a12] border-l border-white/10 flex flex-col"><div class="p-3 border-b border-white/5"><input id="searchUser" placeholder="بحث user..." class="w-full bg-black border border-white/10 rounded-xl px-3 py-2 text-xs"></div><div id="userList" class="flex-1 overflow-y-auto"></div></div>
<div class="flex-1 flex flex-col bg-[#080810]"><div class="p-4 bg-[#12121f] border-b border-white/10 flex justify-between items-center"><div><p id="currentUser" class="font-bold">اختر محادثة</p><p class="text-xs text-gray-400">التفعيل تلقائي عند الدفع - بدون زر تفعيل يدوي</p></div><button onclick="viewUserPage()" class="bg-[#1e1e35] px-3 py-1.5 rounded-lg text-xs">👁️ عرض صفحته</button></div><div id="messages" class="flex-1 p-4 space-y-3 overflow-y-auto"></div><div class="p-3 bg-[#12121f] border-t border-white/10 flex gap-2"><input id="replyInput" placeholder="اكتب ردك..." class="flex-1 bg-black border border-white/10 rounded-xl px-4 py-3 text-sm outline-none"><button onclick="sendReply()" class="bg-white text-black px-6 rounded-xl font-bold">ارسال</button></div></div></div>
<script>
const KEY=new URLSearchParams(location.search).get("key");document.getElementById('backLink').href=`/admin?key=${KEY}`;
let CURRENT=null;async function loadUsers(){let r=await fetch(`/admin/support/users?key=${KEY}`).then(x=>x.json());let q=document.getElementById('searchUser').value.toLowerCase();let f=r.filter(u=>u.user_id.toLowerCase().includes(q));let h="";f.forEach(u=>{let a=CURRENT===u.user_id?"bg-[#1e1e35]":"";h+=`<div onclick="selectUser('${u.user_id}')" class="p-3 border-b border-white/5 cursor-pointer hover:bg-white/5 ${a}"><div class="flex justify-between"><span class="font-mono text-sm text-cyan-400">${u.user_id}</span><span class="text-[10px] text-gray-500">${u.count} رسائل</span></div><p class="text-xs text-gray-400 truncate mt-1">${u.last||''}</p></div>`;});document.getElementById('userList').innerHTML=h;}
function selectUser(uid){CURRENT=uid;document.getElementById('currentUser').innerText=uid;loadMessages();loadUsers();}
async function loadMessages(){if(!CURRENT)return;let r=await fetch(`/admin/support/messages?user_id=${CURRENT}&key=${KEY}`).then(x=>x.json());let box=document.getElementById('messages');let h="";r.forEach(m=>{if(m.sender==='user')h+=`<div class="flex justify-start"><div class="bg-white text-black p-3 rounded-2xl max-w-[70%] rounded-br-sm text-sm">${m.message}</div></div>`;else h+=`<div class="flex justify-end"><div class="bg-[#1e1e35] border p-3 rounded-2xl max-w-[70%] rounded-bl-sm text-sm">${m.message}</div></div>`;});box.innerHTML=h;box.scrollTop=box.scrollHeight;}
async function sendReply(){let inp=document.getElementById('replyInput');let txt=inp.value.trim();if(!txt||!CURRENT)return;await fetch(`/admin/support/reply?key=${KEY}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:CURRENT,message:txt})});inp.value='';loadMessages();loadUsers();}
function viewUserPage(){if(CURRENT)window.open(`/view/${CURRENT}`,'_blank');}
document.getElementById('searchUser').addEventListener('input',loadUsers);document.getElementById('replyInput').addEventListener('keydown',e=>{if(e.key==='Enter')sendReply();});
loadUsers();setInterval(()=>{loadUsers();if(CURRENT)loadMessages();},3000);
</script></body></html>
"""

PAY_HTML = """<!DOCTYPE html><html dir="rtl" lang="ar"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>الدفع الآمن</title><script src="https://cdn.tailwindcss.com"></script><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet"><style>@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');*{font-family:'Tajawal',sans-serif}#toast-copy{position:fixed;top:20px;left:50%;transform:translateX(-50%);z-index:9999;transition:all 0.3s}</style></head><body class="bg-[#0a0a12] min-h-screen flex items-center justify-center p-4">
<div id="toast-copy" class="hidden"><div id="toastCopyBox" class="bg-white text-black px-6 py-3 rounded-full font-bold shadow-2xl text-sm">✅ تم النسخ</div></div>
<div class="w-full max-w-md"><div class="bg-gradient-to-b from-[#1e1e35] to-[#151528] rounded-[24px] p-6 border border-white/10 shadow-2xl"><div class="text-center mb-6"><div class="w-16 h-16 bg-gradient-to-br from-green-400 to-emerald-600 rounded-2xl flex items-center justify-center mx-auto mb-3"><i class="fa-solid fa-shield-halved text-2xl text-white"></i></div><h1 class="text-xl font-bold text-white">الدفع الآمن</h1><p class="text-gray-400 text-sm mt-1">BSC BEP20 • تأكيد تلقائي</p><p class="text-[10px] text-gray-500 mt-1">0x2d447f9d656594f6c65de039aebe7da32a968400</p></div><div class="bg-black/40 rounded-2xl p-4 border border-white/5 mb-4"><div class="flex justify-between text-sm text-gray-400 mb-2"><span>المبلغ المطلوب</span><span class="text-yellow-400">مميز لك</span></div><div id="amt" class="text-3xl font-bold text-emerald-400 text-center">-- USDT</div></div><div class="bg-black/40 rounded-2xl p-4 border border-white/5 mb-4"><p class="text-xs text-gray-400 mb-2">عنوان المحفظة</p><div class="bg-[#0a0a12] p-3 rounded-xl font-mono text-[11px] break-all border border-white/10 text-left text-white">__WALLET__</div><div class="grid grid-cols-2 gap-2 mt-3"><button onclick="copyText('__WALLET__','العنوان')" class="bg-white text-black py-3 rounded-xl font-bold text-sm">نسخ العنوان</button><button onclick="copyText(AMT+'','المبلغ')" class="bg-white/10 text-white border border-white/10 py-3 rounded-xl font-bold text-sm">نسخ المبلغ</button></div></div><button onclick="verify()" id="btn" class="w-full bg-gradient-to-r from-emerald-500 to-green-500 text-black py-4 rounded-xl font-bold">لقد دفعت، فعل حسابي</button><div id="status" class="mt-4 text-center text-sm min-h-[24px] text-white"></div><div class="text-center mt-3"><a id="toContent" class="text-xs text-gray-400 underline">عرض المحتوى</a></div></div></div>
<script>
let AMT=0,UID="__UID__";
function showCopyToast(msg){let t=document.getElementById('toast-copy'),b=document.getElementById('toastCopyBox');b.innerText=msg;t.classList.remove('hidden');setTimeout(()=>t.classList.add('hidden'),2000);}
function copyText(text,label){if(navigator.clipboard && window.isSecureContext){navigator.clipboard.writeText(text).then(()=>{showCopyToast('✅ تم نسخ '+label);}).catch(()=>{fallbackCopy(text,label);});}else{fallbackCopy(text,label);}}
function fallbackCopy(text,label){let ta=document.createElement('textarea');ta.value=text;ta.style.position='fixed';ta.style.top='-1000px';document.body.appendChild(ta);ta.focus();ta.select();try{document.execCommand('copy');showCopyToast('✅ تم نسخ '+label);}catch(e){showCopyToast('❌ فشل النسخ');}document.body.removeChild(ta);}
async function init(){let r=await fetch(`/amount/${UID}`).then(x=>x.json());AMT=r.amount;document.getElementById('amt').innerText=AMT+' USDT';document.getElementById('toContent').href=`/content/${UID}`;}
async function verify(){let b=document.getElementById('btn'),s=document.getElementById('status');b.innerHTML="⏳ جاري التحقق...";b.disabled=true;try{let r=await fetch(`/verify/${UID}`).then(x=>x.json());if(r.paid){s.innerHTML="<span class='text-emerald-400 font-bold'>✅ تم التفعيل - 30 يوم</span>";setTimeout(()=>location.href=`/content/${UID}`,1500);}else{s.innerHTML=`<span class='text-red-400'>❌ لم يتم العثور على الدفع</span>`;b.disabled=false;b.innerHTML="لقد دفعت، فعل حسابي";}}catch(e){s.innerText="خطأ";b.disabled=false;}}
init();
</script></body></html>"""

CONTENT_HTML = """<!DOCTYPE html><html dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>مكتبتي</title><script src="https://cdn.tailwindcss.com"></script></head><body class="bg-[#080810] min-h-screen p-4"><div class="max-w-3xl mx-auto"><div class="flex justify-between items-center mb-6"><h1 class="text-xl font-bold text-white">📁 مكتبتك - __UID__</h1><span id="time" class="bg-[#1e1e35] px-3 py-1 rounded-full text-xs text-white"></span></div><div id="list" class="space-y-3"></div></div>
<script>
const UID="__UID__";
async function load(){
  let c=await fetch(`/check?user_id=${UID}`).then(r=>r.json());
  document.getElementById('time').innerText=c.hours||'';
  if(c.status==='disabled'){
    document.getElementById('list').innerHTML=`<div class='bg-gradient-to-b from-[#1e1e35] to-[#151528] p-6 rounded-[24px] text-center border border-red-500/20'><p class='text-red-400 font-bold text-lg'>🚫 ${c.message||'تم تعطيل حسابك'}</p></div>`;
    return;
  }
  if(c.status!=='active'){
    let filesHtml="";(c.files||[]).forEach(f=>{filesHtml+=`<div class='bg-[#12121f] border border-white/5 rounded-2xl p-4 flex justify-between items-center opacity-30 pointer-events-none'><div><p class='font-bold text-white'>${f}</p><p class='text-xs text-gray-500'>مقفل</p></div><button disabled class='bg-gray-700 text-gray-400 px-4 py-2 rounded-xl text-sm'>مقفل 🔒</button></div>`;});
    document.getElementById('list').innerHTML=`<div class='bg-gradient-to-b from-[#1e1e35] to-[#151528] p-6 rounded-[24px] text-center border border-white/10 mb-4'><p class='text-white'>${c.message||'انتهى وقتك'}</p><a href='/pay/${UID}' class='mt-6 inline-block w-full bg-emerald-500 text-black py-3 rounded-xl font-bold'>💳 ادفع للتجديد 30 يوم</a></div>`+filesHtml;
    return;
  }
  let h="";c.files.forEach(f=>{h+=`<div class='bg-[#12121f] border border-white/5 rounded-2xl p-4 flex justify-between items-center'><div><p class='font-bold text-white'>${f}</p></div><button onclick="location.href='/download/${f}?user_id=${UID}'" class='bg-white text-black px-4 py-2 rounded-xl text-sm font-bold'>تحميل</button></div>`;});
  document.getElementById('list').innerHTML=h;
}
load();
</script></body></html>"""

ADMIN_HTML = """<!DOCTYPE html><html dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Admin Pro MAX</title><script src="https://cdn.tailwindcss.com"></script></head><body class="bg-[#080810] text-white min-h-screen p-4">
<div id="toast" class="fixed top-4 right-4 z-50 hidden"><div id="toastBox" class="bg-emerald-500 text-black px-6 py-3 rounded-xl font-bold shadow-2xl flex items-center gap-2 text-sm"><span id="toastText"></span></div></div>
<div class="max-w-7xl mx-auto"><div class="flex justify-between items-center mb-6"><h1 class="text-2xl font-bold">لوحة التحكم <span class="text-emerald-400">Pro MAX - 0x2d44</span> <a href="/admin/support?key=__KEY__" class="text-sm bg-yellow-500 text-black px-3 py-1 rounded-lg ml-3">💬 الدعم الفوري</a></h1><button onclick="load()" class="bg-emerald-500 text-black px-4 py-2 rounded-xl text-sm font-bold">تحديث</button></div>
<div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6"><div class="bg-emerald-900/40 p-5 rounded-2xl"><p class="text-gray-400 text-xs">النشطين</p><p id="active" class="text-3xl font-bold">--</p></div><div class="bg-[#1a1a2e] p-5 rounded-2xl"><p class="text-gray-400 text-xs">الكل</p><p id="total" class="text-3xl font-bold">--</p></div><div class="bg-[#1a1a2e] p-5 rounded-2xl"><p class="text-gray-400 text-xs">منتهي</p><p id="exp" class="text-3xl font-bold text-red-400">--</p></div><div class="bg-yellow-900/30 p-5 rounded-2xl"><p class="text-gray-400 text-xs">الارباح</p><p id="rev" class="text-xl font-bold text-yellow-400">--</p></div></div>
<div class="bg-[#12121f] rounded-2xl border border-white/5 overflow-hidden">
<div class="p-4 bg-black/30 border-b border-white/5 flex flex-wrap gap-3 items-end">
<div><label class="text-[11px] text-gray-400">اضافة يوزر جديد</label><div class="flex gap-2 mt-1"><input id="newUid" placeholder="USER_ID" class="bg-black border border-white/20 rounded-lg px-3 py-2 text-xs w-36 text-white"><input id="newDays" type="number" value="30" class="bg-black border border-white/20 rounded-lg px-2 py-2 text-xs w-20 text-center text-white"><button onclick="addUser()" class="bg-emerald-500 text-black px-4 py-2 rounded-lg text-xs font-bold">+ اضافة يوزر</button></div></div>
<div class="mr-auto"><input id="search" oninput="filter()" placeholder="بحث..." class="bg-black/50 border border-white/10 rounded-lg px-3 py-2 text-xs w-48"></div>
</div>
<div class="overflow-x-auto"><table class="w-full text-sm"><thead class="text-gray-500 bg-black/30"><tr><th class="p-3 text-right">User</th><th class="p-3">متبقي</th><th class="p-3">المبلغ</th><th class="p-3">الحالة</th><th class="p-3 min-w-[650px]">تحكم</th></tr></thead><tbody id="tb"></tbody></table></div></div></div>
<script>
const KEY=new URLSearchParams(location.search).get("key");let ALL=[];
function showToast(msg,color="emerald"){let t=document.getElementById('toast'),box=document.getElementById('toastBox'),txt=document.getElementById('toastText');txt.innerText=msg;box.className=`px-6 py-3 rounded-xl font-bold shadow-2xl flex items-center gap-2 text-sm ${color==='red'?'bg-red-500 text-white':color==='blue'?'bg-blue-500 text-white':'bg-emerald-500 text-black'}`;t.classList.remove('hidden');setTimeout(()=>{t.classList.add('hidden')},3000);}
async function load(){let s=await fetch(`/admin/stats?key=${KEY}`).then(r=>r.json());document.getElementById('active').innerText=s.active_users;document.getElementById('total').innerText=s.total_users;document.getElementById('exp').innerText=s.expired;document.getElementById('rev').innerText=s.total_revenue+" USDT";let u=await fetch(`/admin/users?key=${KEY}`).then(r=>r.json());ALL=u;render(u);}
function render(list){let h="";list.forEach(x=>{let isActive = x.is_paid;let status = x.raw_status==='inactive' ? '<span class="bg-orange-900/50 text-orange-300 px-2 py-1 rounded-full text-xs">⏸️ معطل</span>' : isActive ? '<span class="bg-emerald-900/50 text-emerald-300 px-2 py-1 rounded-full text-xs">✅ نشط</span>' : '<span class="bg-red-900/50 text-red-300 px-2 py-1 rounded-full text-xs">❌ منتهي</span>';let toggleBtn = x.raw_status==='inactive' ? `<button onclick="toggleUser('${x.user_id}')" class='bg-emerald-900/50 text-emerald-300 px-2 py-1.5 rounded-lg text-xs'>🟢 تنشيط</button>` : `<button onclick="toggleUser('${x.user_id}')" class='bg-orange-900/50 text-orange-300 px-2 py-1.5 rounded-lg text-xs'>🔴 تعطيل</button>`;h+=`<tr class='border-b border-white/5'><td class='p-3 font-mono text-xs'><a href='/admin/view/${x.user_id}?key=${KEY}' target='_blank' class='text-cyan-400 underline'>${x.user_id} ↗</a></td><td class='p-3 text-xs'>${x.remaining||''}</td><td class='p-3 text-emerald-400'>${x.amount_paid||0}</td><td class='p-3'>${status}</td><td class='p-2 flex gap-1 flex-wrap'>${toggleBtn}<input id='d_${x.user_id}' type='number' value='30' class='bg-black border border-white/20 rounded-lg w-14 px-2 py-1.5 text-xs text-center text-white'><button onclick="extCustom('${x.user_id}')" class='bg-white text-black px-2 py-1.5 rounded-lg text-xs font-bold'>+ اضافة</button><a href='/admin/view/${x.user_id}?key=${KEY}' target='_blank' class='bg-blue-900/40 text-blue-300 px-2 py-1.5 rounded-lg text-xs'>👁️ فتح</a><a href='/content/${x.user_id}' target='_blank' class='bg-purple-900/40 text-purple-300 px-2 py-1.5 rounded-lg text-xs'>📁 محتوى</a><a href='/pay/${x.user_id}' target='_blank' class='bg-emerald-900/40 text-emerald-300 px-2 py-1.5 rounded-lg text-xs'>💳 دفع</a><button onclick="resetU('${x.user_id}')" class='bg-gray-700 px-2 py-1.5 rounded-lg text-xs'>تصفير 0</button><button onclick="del('${x.user_id}')" class='bg-red-900/50 text-red-300 px-2 py-1.5 rounded-lg text-xs'>حذف</button></td></tr>`});document.getElementById('tb').innerHTML=h}
function filter(){let q=document.getElementById('search').value;render(ALL.filter(x=>x.user_id.toLowerCase().includes(q.toLowerCase())))}
async function addUser(){let uid=document.getElementById('newUid').value.trim();let days=parseInt(document.getElementById('newDays').value)||0;if(!uid){showToast('اكتب الـ ID','red');return;}let r=await fetch(`/admin/add_user?key=${KEY}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({user_id:uid,days:days})});let j=await r.json();if(j.ok){showToast('✅ تم اضافة '+uid,'emerald');document.getElementById('newUid').value='';load();}else{showToast(j.error||'موجود','red');}}
async function del(uid){if(!confirm('حذف '+uid+' ?'))return;await fetch(`/admin/delete?key=${KEY}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({user_id:uid})});showToast('🗑️ تم حذف '+uid,'red');load();}
async function resetU(uid){await fetch(`/admin/reset?key=${KEY}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({user_id:uid})});showToast('🔄 تم تصفير '+uid,'blue');load();}
async function extCustom(uid){let days=parseInt(document.getElementById('d_'+uid).value)||0;if(days<=0){showToast('اكتب عدد الايام','red');return;}await fetch(`/admin/extend?key=${KEY}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({user_id:uid,days:days})});showToast('✅ تم اضافة '+days+' يوم','emerald');load();}
async function toggleUser(uid){let r=await fetch(`/admin/toggle?key=${KEY}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({user_id:uid})});let j=await r.json();if(j.action==='enabled') showToast('✅ تم تنشيط '+uid,'emerald'); else showToast('⏸️ تم تعطيل '+uid,'red');load();}
load();
</script></body></html>"""

@app.route('/')
def home(): return Response(HOME_HTML, mimetype='text/html')

@app.route('/go')
def go():
    uid = 'user_' + ''.join(random.choices(string.digits, k=6))
    exp = datetime.now() + timedelta(hours=2)
    user = {"user_id": uid, "expires_at": exp.strftime("%Y-%m-%d %H:%M:%S"), "status": "active"}
    save_user(user)
    return redirect(f"/view/{uid}")

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
    html = f"""<!DOCTYPE html><html dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{user_id}</title><script src="https://cdn.tailwindcss.com"></script><style>@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@700&display=swap');*{{font-family:'Tajawal',sans-serif}}</style></head><body class="bg-black min-h-screen p-4"><div class="max-w-md mx-auto mt-10 bg-[#12121f] rounded-[24px] p-6 border border-white/10 shadow-2xl"><div class="text-right"><div class="flex items-center justify-end gap-2 mb-4"><span class="text-2xl">👤</span><h1 class="text-white font-bold text-xl">{user_id}</h1></div><p class="text-white">متبقي: <span id="countdown" class="font-black text-emerald-400 text-lg">{rem_initial}</span> : متبقي</p><p class="text-white mt-1">حالة: {status} : حالة</p><p id="expiredMsg" class="hidden mt-3 bg-red-900/30 border border-red-500/30 rounded-xl p-3 text-center text-sm text-red-300">⏰ انتهى وقتك - ادفع للتجديد</p></div><div class="grid grid-cols-2 gap-3 mt-8"><a href="/content/{user_id}" class="bg-[#8b5cf6] text-white py-3.5 rounded-xl text-center font-bold">📁 محتوى</a><a href="/pay/{user_id}" class="bg-[#10b981] text-black py-3.5 rounded-xl text-center font-bold">💳 دفع</a></div><a href="/" class="block text-center text-xs text-gray-500 mt-6 underline">الرئيسية</a></div>
    <script>
    let remaining = {remaining_sec};
    let el = document.getElementById('countdown');
    let expMsg = document.getElementById('expiredMsg');
    function formatHM(sec){{
        if(sec<=0) return "0:00";
        let h=Math.floor(sec/3600); let m=Math.floor((sec%3600)/60); let s=sec%60;
        if(h>=24){{ let d=Math.floor(h/24); let rh=h%24; return d+" يوم "+rh+":"+String(m).padStart(2,'0'); }}
        return h+":"+String(m).padStart(2,'0')+":"+String(s).padStart(2,'0');
    }}
    function tick(){{
        if(remaining<=0){{ el.innerText="0:00"; el.classList.add('text-red-400'); expMsg.classList.remove('hidden'); return; }}
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
@app.route('/admin/support')
def admin_support_page():
    if request.args.get("key")!=ADMIN_KEY: return Response("401",401)
    return Response(ADMIN_SUPPORT_HTML, mimetype='text/html')
@app.route('/admin/support/users')
def admin_support_users():
    if request.args.get("key")!=ADMIN_KEY: return jsonify({"error":"no"}),401
    try:
        msgs = supabase.table("support_messages").select("*").order("created_at", desc=True).limit(500).execute().data
        users = {}
        for m in msgs:
            uid = m['user_id']
            if uid not in users:
                users[uid] = {"user_id":uid, "last":m['message'], "time":m['created_at'], "count":0}
            users[uid]['count']+=1
        return jsonify(list(users.values()))
    except: return jsonify([])
@app.route('/admin/support/messages')
def admin_support_msgs():
    if request.args.get("key")!=ADMIN_KEY: return jsonify({"error":"no"}),401
    uid = request.args.get("user_id")
    try:
        res = supabase.table("support_messages").select("*").eq("user_id", uid).order("created_at").limit(100).execute()
        return jsonify(res.data)
    except: return jsonify([])
@app.route('/admin/support/reply', methods=['POST'])
def admin_support_reply():
    if request.args.get("key")!=ADMIN_KEY: return jsonify({"error":"no"}),401
    data=request.json
    supabase.table("support_messages").insert({"user_id": data['user_id'], "message": data['message'], "sender":"support"}).execute()
    return jsonify({"ok":True})

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
        return jsonify({"status": "active", "links": links, "files": FILES, "hours": "2:00", "content_url": f"/content/{user_id}", "pay_url": f"/pay/{user_id}"})
    if user.get("status")=="inactive":
        return jsonify({"status": "disabled", "message": "تم تعطيل حسابك من الادارة", "hours": "معطل", "files": FILES, "pay_url": f"/pay/{user_id}", "content_url": f"/content/{user_id}"})
    remaining = get_remaining_hours(user)
    if remaining <= 0:
        last_expire = datetime.strptime(user["expires_at"], "%Y-%m-%d %H:%M:%S")
        hours_since_expire = (now - last_expire).total_seconds() / 3600
        if hours_since_expire >= 24:
            new_expire = now + timedelta(hours=2)
            user["expires_at"] = new_expire.strftime("%Y-%m-%d %H:%M:%S"); user["status"]="active"; save_user(user)
            return jsonify({"status": "active", "links": links, "files": FILES, "hours": "2:00", "content_url": f"/content/{user_id}"})
        else:
            remaining_cooldown = 24 - hours_since_expire
            save_user(user)
            return jsonify({"status": "cooldown", "message": f"انتهى - انتظر {format_hm(remaining_cooldown)} او ادفع", "hours": format_hm(remaining_cooldown), "files": FILES, "pay_url": f"/pay/{user_id}", "content_url": f"/content/{user_id}"})
    return jsonify({"status": "active", "links": links, "files": FILES, "hours": format_hm(remaining), "content_url": f"/content/{user_id}", "pay_url": f"/pay/{user_id}"})

@app.route('/download/<filename>')
def download(filename):
    user_id = request.args.get('user_id')
    if not user_id: return "user_id missing", 400
    user = get_user(user_id)
    if not user: return redirect(f"/pay/{user_id}")
    if user.get("status")=="inactive": return Response("🚫 تم تعطيل حسابك من الادارة", 403)
    if get_remaining_hours(user) <= 0: return redirect(f"/pay/{user_id}")
    if filename not in FILES: return f"File {filename} not allowed", 403
    if filename == "File.npvt":
        gdrive_url = f"https://drive.google.com/uc?export=download&id={DRIVE_NPVT_ID}"
        r = requests.get(gdrive_url, stream=True, timeout=30)
        return Response(r.iter_content(chunk_size=8192), mimetype='application/octet-stream', headers={"Content-Disposition": f"attachment;filename={filename}"})
    file_path = os.path.join(FOLDER, filename)
    if not os.path.exists(file_path): return f"File {filename} not found in repo/files", 404
    with open(file_path, 'rb') as f: data = f.read()
    return Response(data, mimetype='application/octet-stream', headers={"Content-Disposition": f"attachment;filename={filename}"})

@app.route("/admin")
def admin():
    if request.args.get("key")!=ADMIN_KEY: return Response("401 ?key=",401)
    return Response(ADMIN_HTML.replace("__KEY__", request.args.get("key","")), mimetype='text/html')

@app.route("/admin/stats")
def a_stats():
    if request.args.get("key")!=ADMIN_KEY: return jsonify({"error":"no"}),401
    users = supabase.table("users").select("*").execute().data
    active = sum(1 for u in users if u.get("status")!="inactive" and get_remaining_hours(u)>0)
    try: subs = supabase.table("subscriptions").select("*").execute().data; rev = sum(float(s.get("amount_paid",0) or 0) for s in subs)
    except: rev=0
    return jsonify({"total_users":len(users),"active_users":active,"expired":len(users)-active,"total_revenue":round(rev,4)})

@app.route("/admin/users")
def a_users():
    if request.args.get("key")!=ADMIN_KEY: return jsonify({"error":"no"}),401
    users = supabase.table("users").select("*").order("expires_at",desc=True).limit(200).execute().data
    out=[]
    for u in users:
        raw_status=u.get("status","active")
        is_paid = raw_status!="inactive" and get_remaining_hours(u)>0
        rem = format_hm(get_remaining_hours(u)) if raw_status!="inactive" else "معطل"
        amt=0
        try:
            r=supabase.table("subscriptions").select("*").eq("user_id",u["user_id"]).execute()
            if r.data: amt=r.data[0].get("amount_paid",0)
        except: pass
        out.append({"user_id":u["user_id"],"expire_at":u["expires_at"],"remaining":rem,"amount_paid":amt,"is_paid":is_paid,"raw_status":raw_status})
    return jsonify(out)

@app.route("/admin/add_user", methods=["POST"])
def a_add_user():
    if request.args.get("key")!=ADMIN_KEY: return jsonify({"error":"no"}),401
    uid=request.json.get("user_id","").strip()
    days=int(request.json.get("days",0))
    if not uid: return jsonify({"error":"اكتب ID"}),400
    if get_user(uid): return jsonify({"error":"موجود مسبقا"}),400
    if days>0: exp=datetime.now()+timedelta(days=days)
    else: exp=datetime.now()
    user={"user_id":uid,"expires_at":exp.strftime("%Y-%m-%d %H:%M:%S"),"status":"active"}
    save_user(user)
    return jsonify({"ok":True})

@app.route("/admin/delete", methods=["POST"])
def a_del():
    if request.args.get("key")!=ADMIN_KEY: return jsonify({"error":"no"}),401
    uid=request.json.get("user_id")
    supabase.table("users").delete().eq("user_id", uid).execute()
    try: supabase.table("subscriptions").delete().eq("user_id", uid).execute()
    except: pass
    return jsonify({"ok":True})

@app.route("/admin/reset", methods=["POST"])
def a_reset():
    if request.args.get("key")!=ADMIN_KEY: return jsonify({"error":"no"}),401
    uid=request.json.get("user_id")
    user=get_user(uid)
    if user:
        user["expires_at"]=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user["status"]="active"
        save_user(user)
    return jsonify({"ok":True})

@app.route("/admin/extend", methods=["POST"])
def a_ext():
    if request.args.get("key")!=ADMIN_KEY: return jsonify({"error":"no"}),401
    uid=request.json.get("user_id"); days=int(request.json.get("days",30))
    user=get_user(uid)
    if not user: return jsonify({"error":"not found"}),404
    try: old=datetime.strptime(user["expires_at"], "%Y-%m-%d %H:%M:%S")
    except: old=datetime.now()
    if old<datetime.now(): old=datetime.now()
    new_exp=old+timedelta(days=days)
    user["expires_at"]=new_exp.strftime("%Y-%m-%d %H:%M:%S"); user["status"]="active"; save_user(user)
    return jsonify({"ok":True})

@app.route("/admin/toggle", methods=["POST"])
def a_toggle():
    if request.args.get("key")!=ADMIN_KEY: return jsonify({"error":"no"}),401
    uid=request.json.get("user_id")
    user=get_user(uid)
    if not user: return jsonify({"error":"not found"}),404
    if user.get("status")=="inactive":
        user["expires_at"]=(datetime.now()+timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        user["status"]="active"
        save_user(user)
        return jsonify({"ok":True,"action":"enabled"})
    else:
        user["status"]="inactive"
        save_user(user)
        return jsonify({"ok":True,"action":"disabled"})

@app.route("/admin/view/<user_id>")
def a_view(user_id):
    if request.args.get("key")!=ADMIN_KEY: return Response("401",401)
    u=get_user(user_id)
    if not u: return Response(f"<body style='background:#080810;color:white;padding:20px'><h1>{user_id} مش موجود</h1></body>",404)
    rem="معطل" if u.get("status")=="inactive" else format_hm(get_remaining_hours(u))
    html=f"""<html dir='rtl'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><script src='https://cdn.tailwindcss.com'></script></head><body class='bg-[#080810] text-white p-6'><div class='max-w-lg mx-auto bg-[#12121f] rounded-2xl p-6 border border-white/10'><h1 class='text-xl font-bold mb-4'>👤 {user_id}</h1><p>متبقي: {rem}</p><p>حالة: {u.get("status")}</p><div class='mt-6 grid grid-cols-2 gap-2'><a href='/pay/{user_id}' target='_blank' class='bg-emerald-500 text-black py-3 rounded-xl text-center font-bold'>💳 دفع</a><a href='/content/{user_id}' target='_blank' class='bg-purple-600 text-white py-3 rounded-xl text-center font-bold'>📁 محتوى</a></div></div></body></html>"""
    return Response(html,mimetype='text/html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
